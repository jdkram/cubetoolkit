"""
seed_dev_data — populate the database with realistic anonymised sample data.

Data is drawn from live S&S site HTML captured 18 Feb 2026.
Real volunteer names have been replaced with fictional ones.

Usage:
    manage.py seed_dev_data              # idempotent, safe to run repeatedly
    manage.py seed_dev_data --wipe       # clear diary/member data first
"""

import datetime
import io
import os
import random

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone
from PIL import Image, ImageDraw

from toolkit.diary.models import Event, EventTag, MediaItem, Role, RotaEntry, Room, Showing
from toolkit.members.models import Member, Volunteer

try:
    from wagtail.models import Site
    from toolkit.content.models import BasicArticlePage
    WAGTAIL_AVAILABLE = True
except ImportError:
    WAGTAIL_AVAILABLE = False


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

ROLES = [
    {"name": "Keyholder", "standard": True},
    {"name": "Programmer", "standard": True},
    {"name": "Projectionist - DCP", "standard": True},
    {"name": "Projectionist - MP4", "standard": False},
    {"name": "Projectionist - Video/DVD", "standard": False},
    {"name": "Projectionist (trained shadowing)", "standard": False},
    {"name": "Bar Staff - Shift 1", "standard": True},
    {"name": "Bar Staff - Shift 2", "standard": False},
    {"name": "Bar Shadow", "standard": False},
    {"name": "Box Office - Admission Tickets", "standard": True},
    {"name": "Box Office - Greeter", "standard": False},
    {"name": "Box Office - Memberships and Merch", "standard": False},
    {"name": "Usher - Fire Trained", "standard": True},
    {"name": "Facilitator", "standard": True},
    {"name": "Facilitator Shadow", "standard": False},
    {"name": "Minute taker", "standard": False},
    {"name": "Inductor - 1 (trained)", "standard": False},
    {"name": "Inductor - 2 (shadowing)", "standard": False},
    {"name": "Trainee (inducted)", "standard": False},
    {"name": "Audio Visual Technician", "standard": False},
    {"name": "Sound Technician level 1", "standard": False},
    {"name": "Sound Technician level 2", "standard": False},
    {"name": "Cafe (Level 1)", "standard": False},
    {"name": "Cafe (Level 2)", "standard": False},
    {"name": "Cafe Shadowing", "standard": False},
    {"name": "Cleaner", "standard": False},
    {"name": "Extra Hands (no training needed)", "standard": False},
    {"name": "Line Cleaner", "standard": False},
    {"name": "Tech (Shadowing)", "standard": False},
]

TAGS = [
    "film",
    "music",
    "workshop",
    "exhibition",
    "performance",
    "meeting",
    "induction",
    "volunteer",
    "party",
    "training-for-volunteers",
    "cafe",
    "online",
    "subtitles",
    "closed-captions",
    "free",
    "outside-hire",
]

# Fictional volunteer names — not real people.
# Inspired by characters/performers from arthouse & world cinema.
VOLUNTEERS = [
    {"name": "Cleo Marchetti", "email": "cleo.marchetti@example.com"},
    {"name": "Elia Silveira", "email": "elia.silveira@example.com"},
    {"name": "Marta Voss", "email": "marta.voss@example.com"},
    {"name": "Rex Hollis", "email": "rex.hollis@example.com"},
    {"name": "Phoebe Lund", "email": "phoebe.lund@example.com"},
    {"name": "Kalani Horita", "email": "kalani.horita@example.com"},
    {"name": "Vera Deschamps", "email": "vera.deschamps@example.com"},
    {"name": "Remy Okafor", "email": "remy.okafor@example.com"},
    {"name": "Jules Travers", "email": "jules.travers@example.com"},
    {"name": "Lena Barrow", "email": "lena.barrow@example.com"},
    {"name": "Sasha Pryce", "email": "sasha.pryce@example.com"},
    {"name": "Tomás Ferreira", "email": "tomas.ferreira@example.com"},
    {"name": "Nell Arundel", "email": "nell.arundel@example.com"},
    {"name": "Ivan Solis", "email": "ivan.solis@example.com"},
    {"name": "Ana Fonseca", "email": "ana.fonseca@example.com"},
]

# Background colours for generated test images, keyed by primary tag.
# Chosen to be visually distinct and cinema-appropriate.
TAG_COLOURS = {
    "film":        (20, 20, 60),    # dark navy
    "music":       (60, 10, 60),    # deep purple
    "performance": (60, 10, 40),    # dark crimson
    "workshop":    (10, 50, 30),    # dark forest green
    "exhibition":  (40, 30, 10),    # dark ochre
    "cafe":        (60, 30, 10),    # dark burnt orange
    "volunteer":   (20, 40, 50),    # dark teal
    "meeting":     (30, 30, 30),    # charcoal
    "induction":   (20, 40, 50),    # dark teal
    "party":       (50, 20, 50),    # dark magenta
    "default":     (25, 25, 40),    # neutral dark blue
}

EVENTS = [
    {
        "name": "Community Kitchen Special: Shared Recipes",
        "copy_summary": "Opening the venue for all volunteers to use as they will. "
        "Workshop, print room, cinema — come along and have a go at whatever takes your fancy.",
        "copy": "An open afternoon for S&S volunteers. The kitchen is yours, the print "
        "room is yours, the cinema is yours. Bring something to share, bring your ideas, "
        "bring yourself. No agenda, no structure — just the building and us.",
        "tags": ["cafe", "workshop"],
        "private": False,
        "rota_notes": "Opening the venue for all volunteers to use as they will. "
        "Workshop, print room, cinema. Come along and have a go at whatever takes your fancy.",
        "roles": ["Keyholder", "Cafe (Level 1)", "Extra Hands (no training needed)"],
        "day_offset": 3,
        "hour": 14,
    },
    {
        "name": "Volunteer Hangout",
        "copy_summary": "A chill get together for all volunteers, perfect if you are new or experienced.",
        "copy": "No agenda, no tasks, just volunteers getting to know each other over "
        "a drink. New volunteers especially welcome — this is a great way to meet people "
        "and find out what's going on.",
        "tags": ["volunteer", "party"],
        "private": False,
        "rota_notes": "A chill get together for all volunteers, perfect if you are new or experienced.",
        "roles": ["Keyholder", "Bar Staff - Shift 1"],
        "day_offset": 5,
        "hour": 19,
    },
    {
        "name": "Volunteer Induction",
        "copy_summary": "New to S&S? Come along to our volunteer induction.",
        "copy": "Our regular volunteer induction — a friendly introduction to the Star "
        "and Shadow, how we run things, what roles are available, and how to get started. "
        "Everyone who wants to volunteer should come to one of these first.",
        "tags": ["induction", "volunteer"],
        "private": False,
        "rota_notes": "Please feel free to join us all and share your experiences of "
        "volunteering at the Star and Shadow.",
        "roles": [
            "Inductor - 1 (trained)",
            "Inductor - 2 (shadowing)",
            "Trainee (inducted)",
        ],
        "day_offset": 7,
        "hour": 18,
    },
    {
        "name": "Keyholder Training",
        "copy_summary": "Training for proposed and agreed keyholders.",
        "copy": "Keyholder training for those who have been proposed and agreed as "
        "keyholders but have not yet had training. Existing keyholders welcome if you "
        "want a refresh.",
        "tags": ["training-for-volunteers"],
        "private": True,
        "hide_in_programme": True,
        "rota_notes": "Keyholder Training for those who have been proposed and agreed "
        "as Keyholders but have not yet had training. (Or if any existing keyholder "
        "wants a refresh then that is good too!)",
        "roles": ["Keyholder", "Extra Hands (no training needed)"],
        "day_offset": 10,
        "hour": 11,
    },
    {
        "name": "Seeking a Friend for the End of the World",
        "copy_summary": "2012 comedy-drama. Dodge embarks on a road trip as an asteroid "
        "threatens Earth. Dir. Lorene Scafaria. 101 min.",
        "copy": "As a massive asteroid nears Earth, a man finds himself alone after his "
        "wife leaves him. He and his neighbour take a road trip across America to find "
        "his high school sweetheart. Funny, sweet, and oddly comforting.",
        "film_information": "Dir. Lorene Scafaria, USA 2012, 101 min, 15",
        "tags": ["film"],
        "private": False,
        "rota_notes": "Doors 6:30pm. Film 7pm. Projectionist please set up by 6pm.",
        "roles": [
            "Keyholder",
            "Projectionist - DCP",
            "Box Office - Admission Tickets",
            "Bar Staff - Shift 1",
            "Usher - Fire Trained",
        ],
        "day_offset": 12,
        "hour": 19,
    },
    {
        "name": "Friday Cleaning Club and Brunch Social",
        "copy_summary": "Monthly cleaning morning followed by brunch for all volunteers.",
        "copy": "The building doesn't clean itself. Join us from 10am for a cleaning "
        "session, then stay for brunch from noon. A great way to give back and meet "
        "people at the same time.",
        "tags": ["volunteer", "cafe"],
        "private": False,
        "rota_notes": "Cleaning from 10am, brunch from noon. Cafe open to public: 10:00–1:30pm",
        "roles": ["Keyholder", "Cleaner", "Cafe (Level 1)", "Cafe Shadowing"],
        "day_offset": 14,
        "hour": 10,
    },
    {
        "name": "Art Club",
        "copy_summary": "Open workshop in the art room. All welcome, no experience needed.",
        "copy": "Drop in, pick up some materials, make something. Art Club meets weekly "
        "and is open to everyone — members, volunteers, and the curious.",
        "tags": ["workshop", "exhibition"],
        "private": False,
        "rota_notes": "",
        "roles": ["Keyholder", "Extra Hands (no training needed)"],
        "day_offset": 16,
        "hour": 15,
    },
    {
        "name": "Family Film Club",
        "copy_summary": "A free film screening suitable for families and children.",
        "copy": "Our monthly family film club — free, child-friendly, and always "
        "something worth watching. Popcorn available.",
        "pricing": "Free",
        "tags": ["film", "free"],
        "private": False,
        "rota_notes": "Doors 5:30pm. Bar shift 1: 5:30pm–8pm. Bar shift 2: 8pm–10pm. Bar closes at 10pm.",
        "roles": [
            "Keyholder",
            "Projectionist - MP4",
            "Box Office - Admission Tickets",
            "Bar Staff - Shift 1",
        ],
        "day_offset": 19,
        "hour": 13,
    },
    {
        "name": "Starcade",
        "copy_summary": "An evening of live music and performance.",
        "copy": "Three acts, two bars, one night. Starcade is S&S's irregular gig night "
        "— always something different, always worth coming to.",
        "tags": ["music", "performance"],
        "private": False,
        "rota_notes": "Doors 7pm. First act 8pm. Sound check from 5pm — sound techs please arrive by 4:30pm.",
        "roles": [
            "Keyholder",
            "Sound Technician level 1",
            "Sound Technician level 2",
            "Bar Staff - Shift 1",
            "Bar Staff - Shift 2",
            "Box Office - Admission Tickets",
            "Usher - Fire Trained",
        ],
        "day_offset": 21,
        "hour": 19,
    },
    {
        "name": "Creative Writing",
        "copy_summary": "A small group workshop for writers at all levels.",
        "copy": "Weekly creative writing workshop. Exercises, sharing, feedback. "
        "All welcome — from first-timers to experienced writers.",
        "tags": ["workshop", "meeting"],
        "private": False,
        "rota_notes": "",
        "roles": ["Facilitator", "Facilitator Shadow"],
        "day_offset": 23,
        "hour": 18,
    },
    {
        "name": "Programme Development Meeting",
        "copy_summary": "Internal meeting to discuss upcoming programme proposals.",
        "copy": "Monthly meeting open to all volunteers interested in programming. "
        "Bring proposals, costings, and ideas.",
        "tags": ["meeting"],
        "private": True,
        "hide_in_programme": True,
        "rota_notes": "Agenda to be circulated by Friday. Please review proposals in advance.",
        "roles": ["Facilitator", "Minute taker"],
        "day_offset": 25,
        "hour": 18,
    },
    {
        "name": "It's Such a Beautiful Day + ME",
        "copy_summary": "Don Hertzfeldt double bill. Strange, beautiful, and genuinely moving.",
        "copy": "A rare chance to see Don Hertzfeldt's animated features on the big screen. "
        "It's Such a Beautiful Day (2012) and ME (2022). Warning: may cause existential "
        "feelings in a good way.",
        "film_information": "Dir. Don Hertzfeldt, USA 2012/2022",
        "tags": ["film"],
        "private": False,
        "rota_notes": "Two films, short break between. Projectionist: check format carefully — "
        "the ME print is DCP, Beautiful Day is MP4.",
        "roles": [
            "Keyholder",
            "Projectionist - DCP",
            "Projectionist - MP4",
            "Box Office - Admission Tickets",
            "Bar Staff - Shift 1",
            "Usher - Fire Trained",
        ],
        "day_offset": 28,
        "hour": 19,
    },
]

# Safer Spaces page content (based on the live S&S website).
# Used for CMS seed data.
SAFER_SPACES_BODY = """
<h2>Safer Spaces Statement</h2>
<p>The Star and Shadow is committed to being a welcoming space for everyone.
We take all concerns around safety, abuse, and wellbeing seriously — whether
they affect our volunteers, audience members, or anyone in our community.
All volunteers read our Safer Spaces Statement at induction.</p>
<p>If you experience or witness something that concerns you, please come forward.
We have procedures in place to support confidential communication and to take
action where needed.</p>

<h2>Conflict and Breaches of Safer Spaces</h2>
<p>We acknowledge that conflict is inevitable in collective spaces, and that
most issues are resolved through direct conversation. When additional support
is needed, our Mediation Collective is available to help.</p>
<p>Current Mediation Collective members: Dawn Felicia Knox, Amanda McBride, and
Steve Watson. You can reach the team at
<a href="mailto:mediation@starandshadow.org.uk">mediation@starandshadow.org.uk</a>.</p>

<h2>Safeguarding</h2>
<p>Safeguarding is a legal responsibility we take seriously. Our current
Safeguarding Officer is Josephine Walker.</p>
<p>You can submit safeguarding concerns (in confidence) to
<a href="mailto:safeguarding@starandshadow.org.uk">safeguarding@starandshadow.org.uk</a>.</p>
<p>All disclosures to the safeguarding team are treated as confidential.</p>

<h2>Further Resources</h2>
<ul>
<li>Rape Crisis Newcastle upon Tyne — 0800 035 2794</li>
<li>National Male Survivors Helpline — 0808 800 5005</li>
<li>Childline — 0800 1111</li>
<li>LGBT+ Switchboard</li>
<li>GALOP (LGBTQ+ domestic violence support)</li>
</ul>
"""


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------


class Command(BaseCommand):
    help = "Populate the database with anonymised sample data for development."

    def add_arguments(self, parser):
        parser.add_argument(
            "--wipe",
            action="store_true",
            help="Delete all existing diary/member data before seeding.",
        )

    def handle(self, *args, **options):
        if options["wipe"]:
            self.stdout.write("Wiping existing data...")
            RotaEntry.objects.all().delete()
            Showing.objects.all().delete()
            Event.objects.all().delete()
            EventTag.objects.filter(read_only=False).delete()
            # Delete seed-generated media items (and their files)
            for mi in MediaItem.objects.filter(credit="seed_dev_data"):
                if mi.media_file:
                    mi.media_file.delete(save=False)
                mi.delete()
            Volunteer.objects.all().delete()
            Member.objects.all().delete()
            User.objects.filter(username__contains=".").delete()
            if WAGTAIL_AVAILABLE:
                BasicArticlePage.objects.filter(slug="safer-spaces").delete()
            self.stdout.write("  Done.")

        counts = {
            "roles": 0,
            "tags": 0,
            "volunteers": 0,
            "events": 0,
            "showings": 0,
            "rota_entries": 0,
            "images": 0,
            "cms_pages": 0,
        }

        # Roles
        for role_data in ROLES:
            _, created = Role.objects.get_or_create(
                name=role_data["name"],
                defaults={"standard": role_data["standard"]},
            )
            if created:
                counts["roles"] += 1

        # Tags
        for tag_name in TAGS:
            tag, created = EventTag.objects.get_or_create(name=tag_name)
            if created:
                tag.clean()  # generates slug
                tag.save()
                counts["tags"] += 1

        # Members and Volunteers
        volunteer_objects = {}
        for vol_data in VOLUNTEERS:
            member, created = Member.objects.get_or_create(
                email=vol_data["email"],
                defaults={"name": vol_data["name"]},
            )
            if created:
                counts["volunteers"] += 1

            # Create or get Django user
            username = vol_data["email"].split("@")[0]
            user, _ = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": vol_data["email"],
                    "first_name": vol_data["name"].split()[0],
                    "last_name": " ".join(vol_data["name"].split()[1:]),
                },
            )

            volunteer, _ = Volunteer.objects.get_or_create(
                member=member, defaults={"user": user}
            )
            volunteer_objects[vol_data["name"]] = volunteer

        vol_list = list(volunteer_objects.values())

        # Default room
        room, _ = Room.objects.get_or_create(
            name="Main Room",
            defaults={"colour": "#cc3399"},
        )

        # Events and Showings
        now = timezone.now()
        anchor = now + datetime.timedelta(days=14)  # centre window 2 weeks out

        for event_data in EVENTS:
            event, created = Event.objects.get_or_create(
                name=event_data["name"],
                defaults={
                    "copy_summary": event_data.get("copy_summary", ""),
                    "copy": event_data.get("copy", ""),
                    "film_information": event_data.get("film_information", ""),
                    "pricing": event_data.get("pricing", ""),
                    "private": event_data.get("private", False),
                },
            )

            if created:
                counts["events"] += 1
                for tag_name in event_data.get("tags", []):
                    try:
                        tag = EventTag.objects.get(name=tag_name)
                        event.tags.add(tag)
                    except EventTag.DoesNotExist:
                        pass

            # Showing
            showing_start = anchor.replace(
                hour=event_data["hour"],
                minute=0,
                second=0,
                microsecond=0,
            ) + datetime.timedelta(days=event_data["day_offset"] - 14)

            showing, s_created = Showing.objects.get_or_create(
                event=event,
                start=showing_start,
                defaults={
                    "room": room,
                    "booked_by": "seed_dev_data",
                    "confirmed": True,
                    "hide_in_programme": event_data.get("hide_in_programme", False),
                    "rota_notes": event_data.get("rota_notes", ""),
                },
            )
            if s_created:
                counts["showings"] += 1

            # Rota entries
            available_vols = vol_list[:]
            random.shuffle(available_vols)
            vol_iter = iter(available_vols)

            roles_list = event_data.get("roles", [])
            num_roles = len(roles_list)
            unfilled_indices = set()
            if num_roles > 1 and random.random() < 0.3:
                num_unfilled = random.randint(1, min(2, num_roles - 1))
                unfilled_indices = set(random.sample(range(num_roles), num_unfilled))

            for i, role_name in enumerate(roles_list):
                try:
                    role = Role.objects.get(name=role_name)
                except Role.DoesNotExist:
                    continue

                if i in unfilled_indices:
                    name = ""
                else:
                    try:
                        name = next(vol_iter).member.name
                    except StopIteration:
                        name = ""

                _, re_created = RotaEntry.objects.get_or_create(
                    showing=showing,
                    role=role,
                    rank=1,
                    defaults={
                        "required": True,
                        "name": name,
                    },
                )
                if re_created:
                    counts["rota_entries"] += 1

            # Generate a test image for this event (for layout testing)
            if not event.media.exists():
                primary_tag = (event_data.get("tags") or ["default"])[0]
                colour = TAG_COLOURS.get(primary_tag, TAG_COLOURS["default"])
                if self._make_event_image(event, colour):
                    counts["images"] += 1

        # CMS pages
        if WAGTAIL_AVAILABLE:
            counts["cms_pages"] += self._seed_cms_pages()

        self.stdout.write(
            self.style.SUCCESS(
                f"\nSeed data created:\n"
                f"  Roles:        {counts['roles']} new\n"
                f"  Tags:         {counts['tags']} new\n"
                f"  Volunteers:   {counts['volunteers']} new\n"
                f"  Events:       {counts['events']} new\n"
                f"  Showings:     {counts['showings']} new\n"
                f"  Rota entries: {counts['rota_entries']} new\n"
                f"  Images:       {counts['images']} new\n"
                f"  CMS pages:    {counts['cms_pages']} new"
            )
        )

    def _make_event_image(self, event, bg_colour):
        """Generate an 800×450 JPEG test image and attach it to the event."""
        try:
            # Create image
            img = Image.new("RGB", (800, 450), color=bg_colour)
            draw = ImageDraw.Draw(img)

            # Draw a subtle lighter panel in the lower third
            panel_y = 300
            draw.rectangle([0, panel_y, 800, 450], fill=tuple(max(0, c + 20) for c in bg_colour))

            # Title text — wrap at ~40 chars
            title = event.name
            if len(title) > 40:
                # Simple word-wrap
                words = title.split()
                lines, current = [], []
                for word in words:
                    if sum(len(w) for w in current) + len(current) + len(word) > 38:
                        lines.append(" ".join(current))
                        current = [word]
                    else:
                        current.append(word)
                if current:
                    lines.append(" ".join(current))
            else:
                lines = [title]

            y = panel_y + 20
            for line in lines:
                draw.text((30, y), line, fill=(240, 240, 240))
                y += 28

            # "SEED IMAGE" watermark in top-right corner
            draw.text((670, 12), "SEED IMAGE", fill=(180, 180, 180))

            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=80)
            jpeg_bytes = buf.getvalue()

            # Write to MEDIA_ROOT
            safe_name = "".join(c if c.isalnum() else "_" for c in event.name[:30])
            filename = f"seed_{event.pk}_{safe_name}.jpg"
            media_dir = os.path.join(settings.MEDIA_ROOT, "diary")
            os.makedirs(media_dir, exist_ok=True)
            file_path = os.path.join(media_dir, filename)
            with open(file_path, "wb") as f:
                f.write(jpeg_bytes)

            # Create MediaItem record pointing to the file
            media_item = MediaItem(
                media_file=f"diary/{filename}",
                credit="seed_dev_data",
                caption=event.name,
            )
            media_item.save()
            event.media.add(media_item)
            return True

        except Exception as exc:
            self.stdout.write(f"  Warning: image generation failed for '{event.name}': {exc}")
            return False

    def _seed_cms_pages(self):
        """Create sample Wagtail CMS pages. Returns count of pages created."""
        try:
            site = Site.objects.filter(is_default_site=True).first()
            if not site:
                self.stdout.write("  No Wagtail site configured — skipping CMS pages.")
                return 0
            root_page = site.root_page
        except Exception as exc:
            self.stdout.write(f"  Warning: could not get Wagtail site: {exc}")
            return 0

        created = 0

        # Safer Spaces page
        if not root_page.get_descendants().filter(slug="safer-spaces").exists():
            try:
                page = BasicArticlePage(
                    title="Safer Spaces / Safety / Safeguarding",
                    slug="safer-spaces",
                    body=SAFER_SPACES_BODY.strip(),
                    show_on_programme_page=True,
                    live=True,
                    show_in_menus=False,
                )
                root_page.add_child(instance=page)
                created += 1
            except Exception as exc:
                self.stdout.write(f"  Warning: could not create Safer Spaces page: {exc}")

        return created
