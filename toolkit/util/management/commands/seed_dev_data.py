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
import urllib.request

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone
from PIL import Image, ImageDraw

from toolkit.diary.models import Event, EventTag, EventTemplate, MediaItem, Role, RotaEntry, Room, Showing
from toolkit.members.models import Member, Volunteer

try:
    from wagtail.models import Page, Site
    from toolkit.content.models import BasicArticlePage, SectionRootWithLinks
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
        "image_url": "https://images.pexels.com/photos/1267320/pexels-photo-1267320.jpeg?auto=compress&cs=tinysrgb&w=800",
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
        "image_url": "https://images.pexels.com/photos/3171837/pexels-photo-3171837.jpeg?auto=compress&cs=tinysrgb&w=800",
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
        "image_url": "https://images.pexels.com/photos/3184418/pexels-photo-3184418.jpeg?auto=compress&cs=tinysrgb&w=800",
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
        "image_url": "https://images.pexels.com/photos/279810/pexels-photo-279810.jpeg?auto=compress&cs=tinysrgb&w=800",
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
        "image_url": "https://images.pexels.com/photos/7991579/pexels-photo-7991579.jpeg?auto=compress&cs=tinysrgb&w=800",
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
        "image_url": "https://images.pexels.com/photos/4239091/pexels-photo-4239091.jpeg?auto=compress&cs=tinysrgb&w=800",
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
        "image_url": "https://images.pexels.com/photos/102127/pexels-photo-102127.jpeg?auto=compress&cs=tinysrgb&w=800",
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
        "image_url": "https://images.pexels.com/photos/33129/popcorn-movie-party-entertainment.jpg?auto=compress&cs=tinysrgb&w=800",
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
        "image_url": "https://images.pexels.com/photos/1763075/pexels-photo-1763075.jpeg?auto=compress&cs=tinysrgb&w=800",
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
        "image_url": "https://images.pexels.com/photos/733856/pexels-photo-733856.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Programme Development Meeting",
        "copy_summary": "Meeting to discuss upcoming programme proposals. Open to all.",
        "copy": "Monthly meeting open to all volunteers and members of the public interested in programming. "
        "Bring proposals, costings, and ideas.",
        "tags": ["meeting"],
        "private": False,
        "rota_notes": "Agenda to be circulated by Friday. Please review proposals in advance.",
        "roles": ["Facilitator", "Minute taker"],
        "day_offset": 25,
        "hour": 18,
        "image_url": "https://images.pexels.com/photos/3183150/pexels-photo-3183150.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Cafe Induction",
        "copy_summary": "Training on how to use the coffee machine and run the cafe.",
        "copy": "Essential training for anyone wanting to volunteer in the cafe. Covers "
        "food hygiene, coffee machine operation, and till use.",
        "tags": ["induction", "cafe", "training-for-volunteers"],
        "private": True,
        "hide_in_programme": True,
        "rota_notes": "Please read the cafe handbook before attending.",
        "roles": ["Inductor - 1 (trained)", "Trainee (inducted)"],
        "day_offset": 26,
        "hour": 11,
        "image_url": "https://images.pexels.com/photos/1307698/pexels-photo-1307698.jpeg?auto=compress&cs=tinysrgb&w=800",
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
        "image_url": "https://images.pexels.com/photos/269140/pexels-photo-269140.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
]

# Event templates — pre-defined event types selectable when creating a new event.
# (The "add event" UI form requires an EventTemplate to be chosen.)
# Roles and tags reference names defined in ROLES and TAGS above.
EVENT_TEMPLATES = [
    {
        "name": "Film (DCP)",
        "pricing": "£7/£5",
        "roles": [
            "Keyholder",
            "Programmer",
            "Projectionist - DCP",
            "Box Office - Admission Tickets",
            "Bar Staff - Shift 1",
            "Usher - Fire Trained",
        ],
        "tags": ["film"],
    },
    {
        "name": "Film (MP4/DVD)",
        "pricing": "£7/£5",
        "roles": [
            "Keyholder",
            "Programmer",
            "Projectionist - MP4",
            "Box Office - Admission Tickets",
            "Bar Staff - Shift 1",
            "Usher - Fire Trained",
        ],
        "tags": ["film"],
    },
    {
        "name": "Family Film Club",
        "pricing": "Free",
        "roles": [
            "Keyholder",
            "Projectionist - MP4",
            "Box Office - Admission Tickets",
            "Bar Staff - Shift 1",
        ],
        "tags": ["film", "free"],
    },
    {
        "name": "Gig",
        "pricing": "",
        "roles": [
            "Keyholder",
            "Sound Technician level 1",
            "Sound Technician level 2",
            "Bar Staff - Shift 1",
            "Bar Staff - Shift 2",
            "Box Office - Admission Tickets",
            "Usher - Fire Trained",
        ],
        "tags": ["music", "performance"],
    },
    {
        "name": "Volunteer Induction",
        "pricing": "Free",
        "roles": [
            "Inductor - 1 (trained)",
            "Inductor - 2 (shadowing)",
            "Trainee (inducted)",
        ],
        "tags": ["induction", "volunteer"],
    },
    {
        "name": "Meeting",
        "pricing": "Free",
        "roles": ["Facilitator", "Minute taker"],
        "tags": ["meeting"],
    },
    {
        "name": "Workshop",
        "pricing": "",
        "roles": ["Keyholder", "Facilitator", "Facilitator Shadow"],
        "tags": ["workshop"],
    },
    {
        "name": "Cleaning Session",
        "pricing": "Free",
        "roles": ["Keyholder", "Cleaner", "Extra Hands (no training needed)"],
        "tags": ["volunteer"],
    },
    {
        "name": "Keyholder Training",
        "pricing": "Free",
        "roles": ["Keyholder", "Extra Hands (no training needed)"],
        "tags": ["training-for-volunteers"],
    },
    {
        "name": "Community Kitchen",
        "pricing": "Free",
        "roles": ["Keyholder", "Cafe (Level 1)", "Extra Hands (no training needed)"],
        "tags": ["cafe", "workshop"],
    },
    {
        "name": "Party",
        "pricing": "",
        "roles": ["Keyholder", "Bar Staff - Shift 1", "Bar Shadow"],
        "tags": ["volunteer", "party"],
    },
    {
        "name": "Exhibition",
        "pricing": "",
        "roles": ["Keyholder", "Extra Hands (no training needed)"],
        "tags": ["exhibition"],
    },
    {
        "name": "Outside Hire",
        "pricing": "",
        "roles": ["Keyholder"],
        "tags": ["outside-hire"],
    },
    {
        "name": "Training",
        "pricing": "Free",
        "roles": ["Keyholder", "Trainee (inducted)"],
        "tags": ["training-for-volunteers"],
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

WHO_ARE_WE_BODY = """
<h2>About the Star and Shadow</h2>
<p>The Star and Shadow Cinema is a volunteer-run community cinema based in
Newcastle upon Tyne. We're not just a cinema — we're a workspace, a meeting
space, an arts space, and a community hub.</p>
<p>Everything we do is run by volunteers. There are no permanent paid staff.
The building is collectively managed, programmed, and cared for by a community
of around 200 active volunteers.</p>
<p>We show independent and world cinema, host live music and performance, run
workshops, and welcome groups who want to use the space. If you've never been,
come along — the bar's open, the welcome's warm, and the programming is always
interesting.</p>
<h2>How We Work</h2>
<p>Decisions are made collectively. There's no boss. The cinema is governed by
a combination of regular volunteer meetings, working groups, and a co-operative
structure that gives every active volunteer a say in how the place is run.</p>
<p>We believe that cinema — and culture more broadly — should be accessible to
everyone, regardless of income, background, or how much they already know about
film. Our pricing reflects that: we keep tickets cheap and our bar is not a
markup machine.</p>
"""

HOW_TO_VOLUNTEER_BODY = """
<h2>How to Get Involved</h2>
<p>The Star and Shadow is run entirely by volunteers. Whether you want to work
behind the bar, operate the projector, help with events, or get involved in
programming — there's a role for you.</p>
<h2>First Steps</h2>
<p>Attend a <strong>Volunteer Induction</strong> — these run regularly and are
the starting point for all new volunteers. You'll meet people, learn how the
building works, and find out what opportunities are available.</p>
<p>Induction dates are listed on the <a href="/">programme page</a>.</p>
<h2>What Happens Next</h2>
<p>After induction you'll be added to the volunteer mailing list and can start
signing up for roles on the rota. Training for most roles (bar, box office,
projection) is hands-on and arranged through the rota.</p>
<h2>Roles Available</h2>
<ul>
<li><strong>Keyholder</strong> — opens and closes the venue</li>
<li><strong>Bar</strong> — bar staff, shadowing, and bar management</li>
<li><strong>Box Office</strong> — tickets, memberships, and greeting</li>
<li><strong>Projectionist</strong> — DCP, MP4/DVD, and shadowing</li>
<li><strong>Facilitator</strong> — facilitating meetings and events</li>
<li><strong>Programmer</strong> — proposing and booking events</li>
<li><strong>Cleaner</strong> — keeping the building clean and welcoming</li>
</ul>
"""

PRIVACY_POLICY_BODY = """
<h2>Privacy Policy</h2>
<p>The Star and Shadow Cinema takes your privacy seriously. We collect only the
data we need to run the cinema and keep our volunteer community informed.</p>
<h2>What We Collect</h2>
<ul>
<li>Your name and email address if you join our mailing list or volunteer</li>
<li>Booking information if you purchase tickets through our box office</li>
</ul>
<h2>How We Use It</h2>
<p>We use your data to send programme information (with your consent), manage
volunteering, and administer the cinema. We never sell your data or share it
with third parties for marketing purposes.</p>
<h2>Your Rights</h2>
<p>You have the right to access, correct, or request deletion of your personal
data at any time. To unsubscribe from our mailing list, follow the link at the
bottom of any email we send you.</p>
<h2>Contact</h2>
<p>If you have any questions about how we handle your data, contact us at
<a href="mailto:info@starandshadow.org.uk">info@starandshadow.org.uk</a>.</p>
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
        parser.add_argument(
            "--bulk-volunteers",
            type=int,
            default=0,
            metavar="N",
            help="Also create N numbered test volunteers (voltest_NNNN) for performance testing.",
        )

    def handle(self, *args, **options):
        if options["wipe"]:
            self.stdout.write("Wiping existing data...")
            RotaEntry.objects.all().delete()
            Showing.objects.all().delete()
            Event.objects.all().delete()
            EventTemplate.objects.all().delete()
            EventTag.objects.filter(read_only=False).delete()
            # Delete seed-generated media items (and their files)
            for mi in MediaItem.objects.filter(credit="seed_dev_data"):
                if mi.media_file:
                    mi.media_file.delete(save=False)
                mi.delete()
            Volunteer.objects.all().delete()
            Member.objects.all().delete()
            User.objects.filter(username__contains=".").delete()
            User.objects.filter(username__startswith="voltest_").delete()
            if WAGTAIL_AVAILABLE:
                # Delete seeded section roots and their children.
                # Use page.delete() (not queryset delete) so treebeard
                # properly repairs numchild counts on ancestor pages.
                for slug in ("about", "get-involved", "important-info"):
                    for page in Page.objects.filter(slug=slug):
                        page.delete()
                # Also remove any old-style standalone article pages that
                # might have been seeded before the section structure existed.
                for page in Page.objects.filter(slug="safer-spaces"):
                    page.delete()
            self.stdout.write("  Done.")

        counts = {
            "roles": 0,
            "tags": 0,
            "event_templates": 0,
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

        # Event templates
        for tmpl_data in EVENT_TEMPLATES:
            tmpl, created = EventTemplate.objects.get_or_create(
                name=tmpl_data["name"],
                defaults={"pricing": tmpl_data.get("pricing", "")},
            )
            if created:
                counts["event_templates"] += 1
                for role_name in tmpl_data.get("roles", []):
                    try:
                        tmpl.roles.add(Role.objects.get(name=role_name))
                    except Role.DoesNotExist:
                        pass
                for tag_name in tmpl_data.get("tags", []):
                    try:
                        tmpl.tags.add(EventTag.objects.get(name=tag_name))
                    except EventTag.DoesNotExist:
                        pass

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
                if self._make_event_image(event, colour, event_data.get("image_url")):
                    counts["images"] += 1

        # CMS pages
        if WAGTAIL_AVAILABLE:
            counts["cms_pages"] += self._seed_cms_pages()

        # Bulk test volunteers (performance testing only)
        if options["bulk_volunteers"]:
            counts["volunteers"] += self._seed_bulk_volunteers(options["bulk_volunteers"])

        self.stdout.write(
            self.style.SUCCESS(
                f"\nSeed data created:\n"
                f"  Roles:           {counts['roles']} new\n"
                f"  Tags:            {counts['tags']} new\n"
                f"  Event templates: {counts['event_templates']} new\n"
                f"  Volunteers:      {counts['volunteers']} new\n"
                f"  Events:          {counts['events']} new\n"
                f"  Showings:        {counts['showings']} new\n"
                f"  Rota entries:    {counts['rota_entries']} new\n"
                f"  Images:          {counts['images']} new\n"
                f"  CMS pages:       {counts['cms_pages']} new"
            )
        )

    def _seed_bulk_volunteers(self, count):
        """Bulk-create N numbered test volunteers for performance testing.

        Uses username pattern voltest_NNNN to avoid clashing with real seed
        volunteers. Idempotent: skips indices that already exist.
        Returns count of volunteers created.
        """
        existing = set(
            int(u[8:])
            for u in User.objects.filter(username__startswith="voltest_")
            .values_list("username", flat=True)
            if u[8:].isdigit()
        )
        to_create = [i for i in range(1, count + 1) if i not in existing]
        if not to_create:
            return 0

        self.stdout.write(f"  Creating {len(to_create)} bulk test volunteers...")

        # Members
        Member.objects.bulk_create(
            [
                Member(
                    name=f"Volunteer {i:04d}",
                    email=f"voltest_{i:04d}@example.test",
                )
                for i in to_create
            ]
        )
        members_by_email = {
            m.email: m
            for m in Member.objects.filter(
                email__in=[f"voltest_{i:04d}@example.test" for i in to_create]
            )
        }

        # Users (no password needed — these accounts are never logged into)
        new_users = []
        for i in to_create:
            u = User(
                username=f"voltest_{i:04d}",
                email=f"voltest_{i:04d}@example.test",
            )
            u.set_unusable_password()
            new_users.append(u)
        User.objects.bulk_create(new_users)
        users_by_username = {
            u.username: u
            for u in User.objects.filter(
                username__in=[f"voltest_{i:04d}" for i in to_create]
            )
        }

        # Volunteers
        Volunteer.objects.bulk_create(
            [
                Volunteer(
                    member=members_by_email[f"voltest_{i:04d}@example.test"],
                    user=users_by_username[f"voltest_{i:04d}"],
                )
                for i in to_create
                if f"voltest_{i:04d}@example.test" in members_by_email
                and f"voltest_{i:04d}" in users_by_username
            ]
        )

        return len(to_create)

    def _make_event_image(self, event, bg_colour, image_url=None):
        """Generate or download an 800×450 JPEG test image and attach it to the event."""
        try:
            img = None
            if image_url:
                try:
                    # Download image
                    req = urllib.request.Request(
                        image_url, headers={"User-Agent": "Mozilla/5.0"}
                    )
                    with urllib.request.urlopen(req, timeout=10) as response:
                        img_data = response.read()

                    img = Image.open(io.BytesIO(img_data))
                    if img.mode != "RGB":
                        img = img.convert("RGB")

                    # Resize and center-crop to 800x450
                    target_w, target_h = 800, 450
                    img_ratio = img.width / img.height
                    target_ratio = target_w / target_h

                    if img_ratio > target_ratio:
                        # Image is wider than target
                        new_h = target_h
                        new_w = int(new_h * img_ratio)
                    else:
                        # Image is taller than target
                        new_w = target_w
                        new_h = int(new_w / img_ratio)

                    # Use LANCZOS if available (Pillow 9+), else fallback to default
                    resample = getattr(Image.Resampling, "LANCZOS", Image.BICUBIC)
                    img = img.resize((new_w, new_h), resample=resample)

                    left = (new_w - target_w) / 2
                    top = (new_h - target_h) / 2
                    right = (new_w + target_w) / 2
                    bottom = (new_h + target_h) / 2
                    img = img.crop((left, top, right, bottom))

                except Exception as exc:
                    self.stdout.write(
                        f"  Warning: could not download image for '{event.name}': {exc}"
                    )
                    img = None

            if img is None:
                # Fallback to generated placeholder
                img = Image.new("RGB", (800, 450), color=bg_colour)
                draw = ImageDraw.Draw(img)

                # Draw a subtle lighter panel in the lower third
                panel_y = 300
                draw.rectangle(
                    [0, panel_y, 800, 450],
                    fill=tuple(max(0, c + 20) for c in bg_colour),
                )

                # Title text — wrap at ~40 chars
                title = event.name
                if len(title) > 40:
                    # Simple word-wrap
                    words = title.split()
                    lines, current = [], []
                    for word in words:
                        if (
                            sum(len(w) for w in current) + len(current) + len(word)
                            > 38
                        ):
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
        """Create sample Wagtail CMS pages matching the live S&S nav structure.

        Creates three section roots (About, Get Involved, Important Info) with
        article pages underneath, so the nav menu has the same shape as the
        live starandshadow.org.uk site.  Returns count of pages created.
        """
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

        def get_or_create_section(slug, title):
            nonlocal created
            existing = root_page.get_descendants().filter(slug=slug).first()
            if existing:
                return existing.specific
            try:
                section = SectionRootWithLinks(
                    title=title,
                    slug=slug,
                    show_in_menus=True,
                    live=True,
                )
                root_page.add_child(instance=section)
                created += 1
                return section
            except Exception as exc:
                self.stdout.write(f"  Warning: could not create section '{title}': {exc}")
                return None

        def get_or_create_article(parent, slug, title, body, show_on_programme_page=False):
            nonlocal created
            if parent is None:
                return
            existing = parent.get_descendants().filter(slug=slug).first()
            if existing:
                return existing.specific
            try:
                page = BasicArticlePage(
                    title=title,
                    slug=slug,
                    body=body,
                    show_on_programme_page=show_on_programme_page,
                    live=True,
                    show_in_menus=True,
                )
                parent.add_child(instance=page)
                created += 1
            except Exception as exc:
                self.stdout.write(f"  Warning: could not create page '{title}': {exc}")

        # --- About ---
        about = get_or_create_section("about", "About")
        get_or_create_article(about, "who-are-we", "Who Are We", WHO_ARE_WE_BODY.strip())

        # --- Get Involved ---
        get_involved = get_or_create_section("get-involved", "Get Involved")
        get_or_create_article(
            get_involved, "how-to-volunteer", "How to Volunteer", HOW_TO_VOLUNTEER_BODY.strip()
        )

        # --- Important Info ---
        important_info = get_or_create_section("important-info", "Important Info")
        get_or_create_article(
            important_info,
            "safer-spaces",
            "Safer Spaces",
            SAFER_SPACES_BODY.strip(),
            show_on_programme_page=True,
        )
        get_or_create_article(
            important_info, "privacy-policy", "Privacy Policy", PRIVACY_POLICY_BODY.strip()
        )

        return created
