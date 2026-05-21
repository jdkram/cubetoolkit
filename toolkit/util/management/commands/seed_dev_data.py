"""
seed_dev_data - populate database with anonymised sample data.

Data is now loaded from TOML files in toolkit/util/management/commands/seed_data/ package.
This makes the data more maintainable and allows non-coders to add sample events.
"""

import datetime
import hashlib
import io
import os
import random
import re
import tempfile
import urllib.request
from collections import defaultdict

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.utils import timezone

from PIL import Image, ImageDraw, ImageFont

from toolkit.diary.models import (
    Event,
    EventLink,
    EventTag,
    EventTemplate,
    EventTemplateRole,
    MediaItem,
    Role,
    RoomBooking,
    RotaEntry,
    Room,
    Showing,
)
from toolkit.index.models import IndexCategory, IndexLink
from toolkit.members.models import Member, Volunteer

from toolkit.util.management.commands.seed_data import (
    ROLES,
    ROOMS,
    TAGS,
    TAG_COLOURS,
    VOLUNTEERS,
    EVENT_TEMPLATES,
    EVENTS,
    WEEKLY_SUNDAY_EVENTS,
    BIWEEKLY_SUNDAY_EVENTS,
    MONTHLY_EVENTS,
    SUNDAY_FILMS,
    THURSDAY_FILMS,
)

try:
    from wagtail.models import Page, Site

    from toolkit.content.models import BasicArticlePage, SectionRootWithLinks

    WAGTAIL_AVAILABLE = True
except ImportError:
    WAGTAIL_AVAILABLE = False

SAFER_SPACES_BODY = (
    "<p>Star and Shadow Cinema is committed to creating a safer space for everyone. "
    "We want our cinema to be welcoming, inclusive, and free from harassment, "
    "discrimination, and harm.</p>"
    "<p>We ask everyone who enters our building to respect these principles:</p>"
    "<ul>"
    "<li>Respect each other's boundaries and identities</li>"
    "<li>Listen to and believe people's experiences</li>"
    "<li>Challenge oppressive behaviour when you see it</li>"
    "<li>Take responsibility for your actions and their impact</li>"
    "</ul>"
    "<p>If you experience or witness anything that makes you feel unsafe, please "
    "speak to a volunteer or contact us.</p>"
)

WHO_ARE_WE_BODY = (
    "<p>Star and Shadow Cinema is a volunteer-run cinema in Newcastle upon Tyne. "
    "We are a registered charity and community benefit society, operated entirely by "
    "volunteers.</p>"
    "<p>We programme a diverse range of films, events, workshops, and performances. "
    "Everything we do is made possible by the people who give their time to keep the "
    "building open and the projectors running.</p>"
    "<p>We believe in collective ownership, consensus decision-making, and the power "
    "of shared cultural experience.</p>"
)

HOW_TO_VOLUNTEER_BODY = (
    "<p>Anyone can volunteer at Star and Shadow. You don't need any experience, just "
    "enthusiasm and a willingness to learn.</p>"
    "<h3>Getting started</h3>"
    "<ol>"
    "<li>Attend a volunteer induction (monthly, first Sunday)</li>"
    "<li>Choose roles that interest you</li>"
    "<li>Sign up for showings on the rota</li>"
    "<li>Learn on the job from experienced volunteers</li>"
    "</ol>"
    "<h3>What you can do</h3>"
    "<p>Projection, bar work, box office, café, cleaning, maintenance, event "
    "programming, marketing, IT, fundraising, and much more.</p>"
)

SAFEGUARDING_BODY = (
    "<p>Star and Shadow Cinema is committed to safeguarding the welfare of all "
    "people who use our building, including children, young people, and adults at risk.</p>"
    "<p>We have a designated safeguarding lead and clear procedures for reporting "
    "concerns. All volunteers who work with vulnerable groups undergo appropriate checks.</p>"
    "<p>If you have a safeguarding concern, please contact our safeguarding lead "
    "immediately.</p>"
)

FURTHER_RESOURCES_BODY = (
    "<h3>Useful contacts</h3>"
    "<ul>"
    "<li><strong>Samaritans:</strong> 116 123 (free, 24/7)</li>"
    "<li><strong>Newcastle Citizens Advice:</strong> 0808 278 7920</li>"
    "<li><strong>Northumberland, Tyne and Wear NHS:</strong> 0191 246 6800</li>"
    "</ul>"
    "<h3>Our policies</h3>"
    "<p>Our full policy documents are available on request, including our Safer Spaces "
    "policy, safeguarding policy, privacy policy, and health and safety policy.</p>"
)

PRIVACY_POLICY_BODY = (
    "<p>Star and Shadow Cinema respects your privacy and is committed to protecting "
    "your personal data.</p>"
    "<p>We only collect the information we need to run the cinema and keep in touch "
    "with our volunteers and audiences. We never sell or share your data with third "
    "parties for marketing purposes.</p>"
    "<p>For full details of what data we collect, why, and how to request deletion, "
    "please contact us.</p>"
)

_SEED_CACHE_DIR = "/site/.seed_cache/images"


def _nth_weekday_of_month(year, month, weekday, n):
    """Return the date of the nth occurrence of weekday in the given month.

    Args:
        year: e.g. 2026
        month: 1-12
        weekday: 0=Monday ... 6=Sunday
        n: 1=first, 2=second, 3=third, 4=fourth, -1=last

    Returns a datetime.date or None if it doesn't exist.
    """
    import calendar

    if n == -1:
        last_day = calendar.monthrange(year, month)[1]
        d = datetime.date(year, month, last_day)
        while d.weekday() != weekday:
            d -= datetime.timedelta(days=1)
        return d
    else:
        first_of_month = datetime.date(year, month, 1)
        offset = (weekday - first_of_month.weekday()) % 7
        first_occurrence = first_of_month + datetime.timedelta(days=offset)
        target = first_occurrence + datetime.timedelta(weeks=n - 1)
        if target.month != month:
            return None
        return target


class Command(BaseCommand):
    help = "Populate the database with anonymised sample data."

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
            help="Create N numbered test volunteers (voltest_NNNN) for performance testing. Default: 0 (off).",
        )

    def handle(self, *args, **options):
        if options["wipe"]:
            self.stdout.write("Wiping existing data...")
            RotaEntry.objects.all().delete()
            Showing.objects.all().delete()
            Event.objects.all().delete()
            EventTemplate.objects.all().delete()
            Room.objects.all().delete()
            Role.objects.all().delete()
            EventTag.objects.filter(read_only=False).delete()
            for mi in MediaItem.objects.filter(credit="seed_dev_data"):
                if mi.media_file:
                    mi.media_file.delete(save=False)
                mi.delete()
            EventLink.objects.all().delete()
            Volunteer.objects.all().delete()
            Member.objects.all().delete()
            User.objects.filter(username__contains=".").delete()
            User.objects.filter(username__startswith="voltest_").delete()
            IndexLink.objects.all().delete()
            IndexCategory.objects.all().delete()
            if WAGTAIL_AVAILABLE:
                for slug in ("about", "get-involved", "important-info"):
                    for page in Page.objects.filter(slug=slug):
                        page.delete()
                for page in Page.objects.filter(slug="safer-spaces"):
                    page.delete()
            self.stdout.write("Done.")

        counts = {
            "roles": 0,
            "tags": 0,
            "event_templates": 0,
            "volunteers": 0,
            "events": 0,
            "showings": 0,
            "rota_entries": 0,
            "images": 0,
            "event_links": 0,
            "cms_pages": 0,
            "index_links": 0,
        }

        # Roles
        for role_data in ROLES:
            role, created = Role.objects.get_or_create(
                name=role_data["name"],
                defaults={"standard": role_data["standard"]},
            )
            if created:
                counts["roles"] += 1
            role.beginner_friendly = role_data.get("beginner_friendly", False)
            role.wheelchair_accessible = role_data.get("wheelchair_accessible", False)
            role.keyholder_only = role_data.get("keyholder_only", False)
            role.programmer_contact = role_data.get("programmer_contact", False)
            role.description = role_data.get("description", "")
            role.save(
                update_fields=[
                    "beginner_friendly",
                    "wheelchair_accessible",
                    "keyholder_only",
                    "programmer_contact",
                    "description",
                ]
            )

        # Tags
        for tag_data in TAGS:
            tag_name = tag_data["name"]
            tag, created = EventTag.objects.get_or_create(name=tag_name)
            if created:
                tag.clean()
                tag.save()
                counts["tags"] += 1

        # Event templates
        for tmpl_data in EVENT_TEMPLATES:
            tmpl, created = EventTemplate.objects.get_or_create(
                name=tmpl_data["name"],
                defaults={
                    "pricing": tmpl_data.get("pricing", ""),
                    "film_information": tmpl_data.get("film_information", ""),
                    "copy": tmpl_data.get("copy", ""),
                    "copy_summary": tmpl_data.get("copy_summary", ""),
                    "terms": tmpl_data.get("terms", ""),
                    "rota_notes": tmpl_data.get("rota_notes", ""),
                    "private": tmpl_data.get("private", False),
                    "outside_hire": tmpl_data.get("outside_hire", False),
                },
            )
            if created:
                counts["event_templates"] += 1
                for role_name in tmpl_data.get("roles", []):
                    try:
                        EventTemplateRole.objects.create(
                            template=tmpl,
                            role=Role.objects.get(name=role_name),
                            count=1,
                        )
                    except Role.DoesNotExist:
                        pass
                for tag_name in tmpl_data.get("tags", []):
                    try:
                        tmpl.tags.add(EventTag.objects.get(name=tag_name))
                    except EventTag.DoesNotExist:
                        pass

        # Members and Volunteers
        volunteer_objects = {}
        for idx, vol_data in enumerate(VOLUNTEERS):
            member, created = Member.objects.get_or_create(
                email=vol_data["email"],
                defaults={"name": vol_data["name"]},
            )
            if created:
                counts["volunteers"] += 1
            # Pronouns may be added/changed in the toml without re-seeding from
            # scratch; sync them on every run for existing members too.
            pronouns = vol_data.get("pronouns", "")
            if pronouns and member.personal_pronouns != pronouns:
                member.personal_pronouns = pronouns
                member.save(update_fields=["personal_pronouns"])

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

            # Sync directory / access rider / emergency contact fields on every run.
            _bool_fields = {"dir_share_pronouns", "dir_share_email", "dir_share_phone", "dir_share_access_rider", "dir_share_collectives"}
            _str_defaults = {"dir_share_name": Volunteer.DIR_SHARE_NONE}
            vol_dirty = False
            for field in (
                "access_intro", "access_needs", "access_links",
                "emergency_contact_name", "emergency_contact_relationship",
                "emergency_contact_phone",
                "dir_share_name", "dir_share_pronouns", "dir_share_email",
                "dir_share_phone", "dir_share_access_rider", "dir_share_collectives",
            ):
                default = False if field in _bool_fields else _str_defaults.get(field, "")
                val = vol_data.get(field, default)
                if getattr(volunteer, field) != val:
                    setattr(volunteer, field, val)
                    vol_dirty = True
            if vol_dirty:
                volunteer.save()

            # Sync collective memberships.
            from toolkit.labs.models import Collective as CollectiveModel
            wanted_slugs = vol_data.get("collectives", [])
            wanted_collectives = list(CollectiveModel.objects.filter(slug__in=wanted_slugs))
            if set(volunteer.collectives.values_list("slug", flat=True)) != set(wanted_slugs):
                volunteer.collectives.set(wanted_collectives)

            volunteer_objects[vol_data["name"]] = volunteer

        programmers_group, _ = Group.objects.get_or_create(name="Programmers")
        seed_users = [v.user for v in volunteer_objects.values() if v.user]
        if seed_users:
            u = seed_users[0]
            u.is_superuser = True
            u.is_staff = True
            u.save(update_fields=["is_superuser", "is_staff"])
        for u in seed_users[1:]:
            programmers_group.user_set.add(u)

        _DEMO_ACCOUNTS = [
            ("admin", "Admin"),
            ("programmer", "Demo Programmer"),
            ("programmer2", "Demo Programmer 2"),
            ("volunteer", "Demo Volunteer"),
            ("volunteer2", "Demo Volunteer 2"),
            ("volunteer3", "Demo Volunteer 3"),
            ("volunteer4", "Demo Volunteer 4"),
            ("volunteer5", "Demo Volunteer 5"),
        ]
        for _username, _display_name in _DEMO_ACCOUNTS:
            try:
                _demo_user = User.objects.get(username=_username)
            except User.DoesNotExist:
                continue
            if Volunteer.objects.filter(user=_demo_user).exists():
                continue
            _demo_member, _ = Member.objects.get_or_create(
                email=f"{_username}@localhost",
                defaults={"name": _display_name},
            )
            if not Volunteer.objects.filter(member=_demo_member).exists():
                Volunteer.objects.create(user=_demo_user, member=_demo_member)
                counts["volunteers"] += 1

        # Rooms
        rooms_dict = {}
        for room_data in ROOMS:
            room_obj, _ = Room.objects.update_or_create(
                name=room_data["name"],
                defaults={
                    "colour": room_data["colour"],
                    "is_primary": room_data.get("is_primary", False),
                    "map_slug": room_data.get("map_slug", ""),
                    "show_column": room_data.get("show_column", True),
                },
            )
            rooms_dict[room_data["name"]] = room_obj
        default_room = rooms_dict["Venue Space"]

        # Initialise in-memory room schedule for clash detection
        self._init_room_schedule()

        # Events and Showings
        now = timezone.now()
        # localise before replacing hours so that hour=18 means 18:00 local time,
        # not 18:00 UTC (which would be 19:00 BST in summer).
        anchor = timezone.localtime(now + datetime.timedelta(days=14))

        for ev_idx, event_data in enumerate(EVENTS):
            if "duration" in event_data:
                dur_minutes = event_data["duration"]
            else:
                fi = event_data.get("film_information", "")
                fi_match = re.search(r"(\d+)\s*min", fi) if fi else None
                if fi_match:
                    dur_minutes = int(fi_match.group(1))
                else:
                    dur_minutes = int(max(30, min(240, round(random.gauss(90, 20)))))
            dur_time = datetime.time(dur_minutes // 60, dur_minutes % 60)

            terms_text = event_data.get("terms") or event_data.get("copy", "")

            event_room = rooms_dict.get(event_data.get("room"), default_room)

            event, created = Event.objects.get_or_create(
                name=event_data["name"],
                defaults={
                    "copy_summary": event_data.get("copy_summary", ""),
                    "copy": event_data.get("copy", ""),
                    "film_information": event_data.get("film_information", ""),
                    "pricing": event_data.get("pricing", ""),
                    "private": event_data.get("private", False),
                    "outside_hire": event_data.get("outside_hire", False),
                    "terms": terms_text,
                    "duration": dur_time,
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

            showing_start = (
                anchor.replace(
                    hour=event_data["hour"],
                    minute=0,
                    second=0,
                    microsecond=0,
                )
                + datetime.timedelta(days=event_data["day_offset"])
                - datetime.timedelta(days=14)
            )
            showing_start = self._find_free_slot(event_room, showing_start, dur_minutes)

            showing, s_created = Showing.objects.get_or_create(
                event=event,
                start=showing_start,
                defaults={
                    "booked_by": event_data.get("booked_by", "seed_dev_data"),
                    "confirmed": event_data.get("confirmed", True),
                    "cancelled": event_data.get("cancelled", False),
                    "discounted": event_data.get("discounted", False),
                    "hide_in_programme": event_data.get("hide_in_programme", False),
                    "rota_notes": event_data.get("rota_notes", ""),
                },
            )
            if s_created:
                counts["showings"] += 1
                if event_room:
                    RoomBooking.objects.get_or_create(
                        showing=showing,
                        room=event_room,
                        defaults={"start": showing_start},
                    )
                self._book_slot(event_room, showing_start, dur_minutes)

            # Rota entries
            available_vols = list(volunteer_objects.values())
            random.shuffle(available_vols)
            vol_iter = iter(available_vols)

            roles_list = event_data.get("roles", [])
            num_roles = len(roles_list)

            day_offset = event_data.get("day_offset", 14)
            normalized_distance = min(day_offset / 28.0, 1.0)
            fill_rate = 0.8 - (normalized_distance * 0.45)

            expanded_roles = []
            for role_name in roles_list:
                expanded_roles.append(role_name)
                if random.random() < 0.7:
                    expanded_roles.append(role_name)

            num_expanded = len(expanded_roles)
            num_to_fill = max(1, int(num_expanded * fill_rate))
            num_unfilled = max(0, num_expanded - num_to_fill)
            unfilled_indices = set()
            if num_expanded > 0 and num_unfilled > 0:
                unfilled_indices = set(random.sample(range(num_expanded), num_unfilled))

            for i, role_name in enumerate(expanded_roles):
                try:
                    role = Role.objects.get(name=role_name)
                except Role.DoesNotExist:
                    continue
                if i in unfilled_indices:
                    vol_name = ""
                else:
                    try:
                        vol_name = next(vol_iter).member.name
                    except StopIteration:
                        vol_name = ""

                _, re_created = RotaEntry.objects.get_or_create(
                    showing=showing,
                    role=role,
                    rank=1 if i < num_roles else 2,
                    defaults={
                        "required": (i < num_roles),
                        "name": vol_name,
                    },
                )
                if re_created:
                    counts["rota_entries"] += 1

            # Generate a placeholder image for this event
            if not event.media.exists():
                primary_tag = (event_data.get("tags") or ["default"])[0]
                colour = TAG_COLOURS.get(primary_tag, TAG_COLOURS["default"])
                if self._make_event_image(event, colour, event_data["name"], image_url=event_data.get("image_url"), image_path=event_data.get("image_path")):
                    counts["images"] += 1

            # Event resource links — deterministic distribution
            if not event.links.exists():
                slot = ev_idx % 20
                ev_links = []
                if slot >= 10:
                    ev_links.append(
                        (
                            "Event notes",
                            f"https://pad.riseup.net/p/sns-ev-{ev_idx:03d}",
                        )
                    )
                if slot >= 16:
                    ev_links.append(
                        (
                            "Event folder",
                            f"https://starandshadow.nextcloud.com/sns{ev_idx:05d}",
                        )
                    )
                if slot == 19:
                    ev_links.append(
                        (
                            "WhatsApp Group",
                            f"https://chat.whatsapp.com/SNS{ev_idx:010d}LinkSeed",
                        )
                    )
                for _order, (_label, _url) in enumerate(ev_links):
                    EventLink.objects.create(
                        event=event, label=_label, url=_url, order=_order
                    )
                counts["event_links"] += len(ev_links)

        # Recurring Sunday and Thursday events
        self._seed_recurring_events(
            rooms_dict, list(volunteer_objects.values()), counts, anchor
        )

        # CMS pages
        if WAGTAIL_AVAILABLE:
            counts["cms_pages"] += self._seed_cms_pages()

        # Toolkit index links
        counts["index_links"] = self._seed_index_links()

        # Bulk test volunteers (performance testing only)
        if options["bulk_volunteers"] > 0:
            counts["volunteers"] += self._seed_bulk_volunteers(
                options["bulk_volunteers"]
            )

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
                f"  Event links:     {counts['event_links']} new\n"
                f"  CMS pages:       {counts['cms_pages']} new\n"
                f"  Index links:     {counts['index_links']} new\n"
            )
        )

    def _seed_recurring_events(self, rooms_dict, vol_list, counts, anchor):
        today = timezone.now().date()
        window_start = today - datetime.timedelta(weeks=8)
        window_end = today + datetime.timedelta(weeks=16)

        # Collect Sundays in window
        d = window_start
        sundays = []
        while d.weekday() != 6:
            d += datetime.timedelta(days=1)
        while d <= window_end:
            if d >= today:
                sundays.append(d)
            d += datetime.timedelta(days=7)

        # Collect Thursdays in window
        d = window_start
        thursdays = []
        while d.weekday() != 3:
            d += datetime.timedelta(days=1)
        while d <= window_end:
            if d >= today:
                thursdays.append(d)
            d += datetime.timedelta(days=7)

        # Seed weekly Sunday events
        for evt_data in WEEKLY_SUNDAY_EVENTS:
            for d in sundays:
                _dur_mins = evt_data["duration"]
                _dur_time = datetime.time(_dur_mins // 60, _dur_mins % 60)
                self._seed_one_recurring_showing(
                    evt_data["name"],
                    d,
                    evt_data["hour"],
                    _dur_time,
                    rooms_dict.get(evt_data["room"]),
                    vol_list,
                    counts,
                    tags=evt_data.get("tags", []),
                    pricing=evt_data.get("pricing", ""),
                    roles=evt_data.get("roles", []),
                    image_url=evt_data.get("image_url"),
                )

        # Seed biweekly Sunday events
        for evt_data in BIWEEKLY_SUNDAY_EVENTS:
            for d in sundays[::2]:
                _dur_mins = evt_data["duration"]
                _dur_time = datetime.time(_dur_mins // 60, _dur_mins % 60)
                self._seed_one_recurring_showing(
                    evt_data["name"],
                    d,
                    evt_data["hour"],
                    _dur_time,
                    rooms_dict.get(evt_data["room"]),
                    vol_list,
                    counts,
                    tags=evt_data.get("tags", []),
                    pricing=evt_data.get("pricing", ""),
                    roles=evt_data.get("roles", []),
                    image_url=evt_data.get("image_url"),
                )

        # Varied start times for Sunday films — a realistic spread across evening
        # slots. No two consecutive Sundays share a time. Cycling rather than
        # random keeps the sequence stable across idempotent reseeds.
        sunday_film_times = [
            (19, 0), (17, 30), (20, 0), (18, 30),
            (19, 0), (20, 30), (17, 0), (19, 30),
        ]

        # Seed Sunday evening films
        for i, d in enumerate(sundays):
            film_idx = i % len(SUNDAY_FILMS)
            film = SUNDAY_FILMS[film_idx]
            hour, minute = sunday_film_times[i % len(sunday_film_times)]
            self._seed_film_showing(
                film["name"],
                film["film_information"],
                d,
                hour,
                rooms_dict["Cinema"],
                film["tags"],
                vol_list,
                counts,
                copy_summary=film.get("copy_summary", ""),
                copy=film.get("copy", ""),
                pricing=film.get("pricing", "£7/£5/£3/£0"),
                image_url=film.get("image_url"),
                minute=minute,
            )

        # Varied start times for Thursday films — slightly earlier/later
        # than a standard 19:00 to suggest a realistic programme.
        thursday_film_times = [
            (19, 0), (18, 30), (20, 0), (19, 30), (18, 0), (20, 30),
        ]

        # Seed Thursday evening films
        for i, d in enumerate(thursdays):
            film_idx = i % len(THURSDAY_FILMS)
            film = THURSDAY_FILMS[film_idx]
            hour, minute = thursday_film_times[i % len(thursday_film_times)]
            self._seed_film_showing(
                film["name"],
                film["film_information"],
                d,
                hour,
                rooms_dict["Cinema"],
                film["tags"],
                vol_list,
                counts,
                copy_summary=film.get("copy_summary", ""),
                copy=film.get("copy", ""),
                pricing=film.get("pricing", "£7/£5/£3/£0"),
                image_url=film.get("image_url"),
                minute=minute,
            )

        # Seed monthly events
        for evt_data in MONTHLY_EVENTS:
            weekday = evt_data["weekday"]
            occurrence = evt_data["occurrence"]
            n_map = {
                "first": 1,
                "second": 2,
                "third": 3,
                "fourth": 4,
                "last": -1,
            }
            n = n_map[occurrence]

            duration_mins = evt_data["duration"]
            duration_time = datetime.time(duration_mins // 60, duration_mins % 60)

            # Iterate over months in the window
            current = today.replace(day=1)
            while current <= window_end:
                target_date = _nth_weekday_of_month(
                    current.year, current.month, weekday, n
                )
                if target_date and target_date >= today and target_date <= window_end:
                    self._seed_one_recurring_showing(
                        evt_data["name"],
                        target_date,
                        evt_data["hour"],
                        duration_time,
                        rooms_dict.get(evt_data["room"]),
                        vol_list,
                        counts,
                        tags=evt_data.get("tags", []),
                        pricing=evt_data.get("pricing", ""),
                        roles=evt_data.get("roles", []),
                        image_url=evt_data.get("image_url"),
                    )
                # Advance to next month
                if current.month == 12:
                    current = current.replace(year=current.year + 1, month=1)
                else:
                    current = current.replace(month=current.month + 1)

    def _seed_one_recurring_showing(
        self,
        name,
        date,
        hour,
        duration,
        room,
        vol_list,
        counts,
        tags=None,
        pricing="",
        roles=None,
        image_url=None,
    ):
        event, created = Event.objects.get_or_create(
            name=name,
            defaults={
                "copy_summary": "",
                "copy": "",
                "film_information": "",
                "pricing": pricing,
                "private": False,
                "outside_hire": False,
                "terms": "",
                "duration": duration,
            },
        )
        if created:
            counts["events"] += 1
        for tag_name in tags or []:
            try:
                tag = EventTag.objects.get(name=tag_name)
                event.tags.add(tag)
            except EventTag.DoesNotExist:
                pass

        # Generate image on first creation only
        if created and not event.media.exists():
            primary_tag = (tags or ["default"])[0]
            colour = TAG_COLOURS.get(primary_tag, TAG_COLOURS["default"])
            if self._make_event_image(event, colour, name, image_url=image_url):
                counts["images"] += 1

        showing_start = timezone.make_aware(
            datetime.datetime.combine(date, datetime.time(hour, 0, 0))
        )

        if showing_start < timezone.now():
            return

        _dur_mins = duration.hour * 60 + duration.minute or 60
        showing_start = self._find_free_slot(room, showing_start, _dur_mins)

        showing, s_created = Showing.objects.get_or_create(
            event=event,
            start=showing_start,
            defaults={
                "booked_by": "seed_dev_data",
                "confirmed": True,
                "cancelled": False,
                "discounted": False,
                "hide_in_programme": False,
                "rota_notes": "",
            },
        )
        if s_created:
            counts["showings"] += 1
            if room:
                RoomBooking.objects.get_or_create(
                    showing=showing,
                    room=room,
                    defaults={"start": showing_start},
                )
            self._book_slot(room, showing_start, _dur_mins)

        # Rota entries
        if not roles:
            return

        available_vols = list(vol_list)
        random.shuffle(available_vols)
        vol_iter = iter(available_vols)

        num_roles = len(roles)

        expanded_roles = []
        for rn in roles:
            expanded_roles.append(rn)
            if random.random() < 0.7:
                expanded_roles.append(rn)

        num_expanded = len(expanded_roles)
        fill_rate = random.uniform(0.4, 0.8)
        num_to_fill = max(1, int(num_expanded * fill_rate))
        num_unfilled = max(0, num_expanded - num_to_fill)
        unfilled_indices = set()
        if num_expanded > 0 and num_unfilled > 0:
            unfilled_indices = set(random.sample(range(num_expanded), num_unfilled))

        for i, role_name in enumerate(expanded_roles):
            try:
                role = Role.objects.get(name=role_name)
            except Role.DoesNotExist:
                continue
            if i in unfilled_indices:
                vol_name = ""
            else:
                try:
                    vol_name = next(vol_iter).member.name
                except StopIteration:
                    vol_name = ""

            _, re_created = RotaEntry.objects.get_or_create(
                showing=showing,
                role=role,
                rank=1 if i < num_roles else 2,
                defaults={
                    "required": (i < num_roles),
                    "name": vol_name,
                },
            )
            if re_created:
                counts["rota_entries"] += 1

    def _seed_film_showing(
        self,
        title,
        info,
        date,
        hour,
        room,
        tags,
        vol_list,
        counts,
        copy_summary="",
        copy="",
        pricing="£7/£5/£3/£0",
        image_url=None,
        minute=0,
    ):
        event, created = Event.objects.get_or_create(
            name=title,
            defaults={
                "copy_summary": copy_summary,
                "copy": copy,
                "film_information": info,
                "pricing": pricing,
                "private": False,
                "outside_hire": False,
                "terms": "",
                "duration": datetime.time(2, 0),
            },
        )
        if created:
            counts["events"] += 1
        for tag_name in tags or ["film"]:
            try:
                tag = EventTag.objects.get(name=tag_name)
                event.tags.add(tag)
            except EventTag.DoesNotExist:
                pass

        # Generate image on first creation only
        if created and not event.media.exists():
            primary_tag = (tags or ["film"])[0]
            colour = TAG_COLOURS.get(primary_tag, TAG_COLOURS["default"])
            if self._make_event_image(event, colour, title, image_url=image_url):
                counts["images"] += 1

        showing_start = timezone.make_aware(
            datetime.datetime.combine(date, datetime.time(hour, minute, 0))
        )

        if showing_start < timezone.now():
            return

        showing_start = self._find_free_slot(room, showing_start, 120)

        showing, s_created = Showing.objects.get_or_create(
            event=event,
            start=showing_start,
            defaults={
                "booked_by": "seed_dev_data",
                "confirmed": True,
                "cancelled": False,
                "discounted": False,
                "hide_in_programme": False,
                "rota_notes": "",
            },
        )
        if s_created:
            counts["showings"] += 1
            if room:
                RoomBooking.objects.get_or_create(
                    showing=showing,
                    room=room,
                    defaults={"start": showing_start},
                )
            self._book_slot(room, showing_start, 120)

        # Rota entries for a film screening
        available_vols = list(vol_list)
        random.shuffle(available_vols)
        vol_iter = iter(available_vols)

        film_roles = [
            ("Keyholder", True, "Keyholder"),
            ("Projectionist - DCP", True, None),
            ("Box Office - Admission Tickets", True, None),
            ("Bar Staff - Shift 1", True, None),
            ("Usher - Fire Trained", True, None),
        ]

        for role_name, required, default_name in film_roles:
            try:
                role = Role.objects.get(name=role_name)
            except Role.DoesNotExist:
                continue

            if default_name:
                vol_name = default_name
            else:
                try:
                    vol_name = next(vol_iter).member.name
                except StopIteration:
                    vol_name = ""

            _, re_created = RotaEntry.objects.get_or_create(
                showing=showing,
                role=role,
                defaults={"required": required, "name": vol_name},
            )
            if re_created:
                counts["rota_entries"] += 1

    def _init_room_schedule(self):
        """Pre-load existing future showings into an in-memory schedule.

        Called once before any showings are created so that _find_free_slot
        and _book_slot can detect clashes without hitting the DB on every check.
        """
        self._room_bookings = defaultdict(list)  # room_pk → [(start, end), ...]
        # Exclude seed showings: they will register themselves via _book_slot as
        # they're created, so existing seed data doesn't cause time-shifting on
        # idempotent re-runs (which would create duplicate showings).
        for rb in RoomBooking.objects.filter(
            showing__start__gte=timezone.now()
        ).exclude(
            showing__booked_by="seed_dev_data"
        ).select_related("showing__event", "room"):
            duration = rb.showing.event.duration
            if duration is None:
                dur_mins = 120
            else:
                dur_mins = duration.hour * 60 + duration.minute or 120
            end = rb.start + datetime.timedelta(minutes=dur_mins)
            self._room_bookings[rb.room.pk].append((rb.start, end))

    def _find_free_slot(self, room, preferred_start, duration_minutes):
        """Return the first start time >= preferred_start where room is free.

        Shifts in 30-minute steps; gives up after 3 hours and returns the
        preferred_start unchanged (to avoid infinite deferral).
        """
        if room is None:
            return preferred_start
        duration = datetime.timedelta(minutes=duration_minutes)
        step = datetime.timedelta(minutes=30)
        attempt = preferred_start
        limit = preferred_start + datetime.timedelta(hours=3)
        while attempt <= limit:
            end = attempt + duration
            booked = self._room_bookings.get(room.pk, [])
            if not any(attempt < b_end and end > b_start for b_start, b_end in booked):
                return attempt
            attempt += step
        return preferred_start

    def _book_slot(self, room, start, duration_minutes):
        """Register a newly created showing in the in-memory schedule."""
        if room is None:
            return
        end = start + datetime.timedelta(minutes=duration_minutes)
        self._room_bookings[room.pk].append((start, end))

    def _seed_cms_pages(self):
        """Seed CMS content pages under the site root."""
        try:
            home_page = Page.objects.get(slug="home")
        except Page.DoesNotExist:
            return 0

        pages_data = [
            ("Safer Spaces Statement", "safer-spaces", SAFER_SPACES_BODY),
            ("About Star and Shadow", "about", WHO_ARE_WE_BODY),
            ("How to Volunteer", "get-involved", HOW_TO_VOLUNTEER_BODY),
            ("Safeguarding", "safeguarding", SAFEGUARDING_BODY),
            ("Further Resources", "important-info", FURTHER_RESOURCES_BODY),
            ("Privacy Policy", "privacy", PRIVACY_POLICY_BODY),
        ]

        created_count = 0
        for title, slug, body_text in pages_data:
            if Page.objects.filter(slug=slug).exists():
                continue
            page = BasicArticlePage(
                title=title,
                slug=slug,
                live=True,
                show_in_menus=True,
                body=body_text,
            )
            home_page.add_child(instance=page)
            created_count += 1

        return created_count

    def _seed_index_links(self):
        """Seed index links for the toolkit homepage."""
        cat_names = ["Programme", "Get Involved", "Important Info"]

        categories = {}
        for cat_name in cat_names:
            cat, _ = IndexCategory.objects.get_or_create(name=cat_name)
            categories[cat_name] = cat

        links_data = [
            (
                "Programme",
                "View Programme",
                "http://localhost:8000/diary/",
                "What's on at Star and Shadow",
            ),
            (
                "Get Involved",
                "Volunteer Rota",
                "http://localhost:8000/diary/edit/rota/",
                "Sign up for showings",
            ),
            (
                "Important Info",
                "Safer Spaces",
                "http://localhost:8000/safer-spaces/",
                "Our safer spaces policy",
            ),
            (
                "Important Info",
                "Privacy Policy",
                "http://localhost:8000/privacy/",
                "How we handle your data",
            ),
        ]

        created_count = 0
        for cat_name, text, url, desc in links_data:
            cat = categories.get(cat_name)
            if not cat:
                continue
            _, created = IndexLink.objects.get_or_create(
                category=cat,
                link=url,
                defaults={
                    "text": text,
                    "description": desc,
                },
            )
            if created:
                created_count += 1

        return created_count

    def _seed_bulk_volunteers(self, n):
        """Create N numbered test volunteers for performance testing."""
        programmers_group, _ = Group.objects.get_or_create(name="Programmers")
        created_count = 0

        for i in range(n):
            email = f"voltest_{i:04d}@localhost"
            name = f"Volunteer Test {i}"
            member, _ = Member.objects.get_or_create(
                email=email, defaults={"name": name}
            )
            user, _ = User.objects.get_or_create(
                username=email.split("@")[0],
                defaults={
                    "email": email,
                    "first_name": name.split()[0],
                    "last_name": name.split()[1],
                },
            )
            Volunteer.objects.get_or_create(member=member, defaults={"user": user})
            created_count += 1

            if i < 5:
                programmers_group.user_set.add(user)

        return created_count

    _BOLD_FONT_CANDIDATES = [
        # Bundled font — always available regardless of host/container setup
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "seed_data", "fonts", "DejaVuSans-Bold.ttf"),
        # System fallbacks (host machines)
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/opentype/urw-base35/NimbusSans-Bold.otf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]

    def _find_bold_font(self):
        for path in self._BOLD_FONT_CANDIDATES:
            if os.path.exists(path):
                return path
        return None

    def _make_poster_image(self, event_name, bg_colour, width=800, height=450):
        """Generate a bold typographic poster: gradient background, text stretched to fill."""
        from PIL import ImageFont

        r0, g0, b0 = bg_colour
        top_c = (min(255, r0 + 40), min(255, g0 + 40), min(255, b0 + 50))
        bot_c = (max(0, r0 - 15), max(0, g0 - 15), max(0, b0 - 10))
        pixels = []
        for y in range(height):
            t = y / max(height - 1, 1)
            pixels.extend([(
                int(top_c[0] + (bot_c[0] - top_c[0]) * t),
                int(top_c[1] + (bot_c[1] - top_c[1]) * t),
                int(top_c[2] + (bot_c[2] - top_c[2]) * t),
            )] * width)
        img = Image.new("RGB", (width, height))
        img.putdata(pixels)

        lum = 0.299 * r0 + 0.587 * g0 + 0.114 * b0
        text_colour = (255, 255, 255) if lum < 128 else (0, 0, 0)

        font_path = self._find_bold_font()
        pad = 24

        # Wrap words into lines of roughly equal character length.
        words = event_name.upper().split()
        total_chars = sum(len(w) for w in words)
        if total_chars <= 10:
            n_lines = 1
        elif total_chars <= 22:
            n_lines = 2
        elif total_chars <= 40:
            n_lines = 3
        else:
            n_lines = 4

        target_per_line = total_chars / n_lines
        raw_lines = []
        current = []
        current_len = 0
        for word in words:
            if current and current_len + len(word) > target_per_line and len(raw_lines) < n_lines - 1:
                raw_lines.append(" ".join(current))
                current = [word]
                current_len = len(word)
            else:
                current.append(word)
                current_len += len(word)
        if current:
            raw_lines.append(" ".join(current))

        # Each line is rendered at high resolution then scaled to fill its slot exactly —
        # both full width and equal share of the height. This gives the blocky, full-bleed
        # typographic poster effect.
        usable_w = width - pad * 2
        usable_h = height - pad * 2
        gap = max(4, height // 80)
        slot_h = (usable_h - gap * (len(raw_lines) - 1)) // len(raw_lines)

        def font_at(size):
            if font_path:
                try:
                    return ImageFont.truetype(font_path, size)
                except Exception:
                    pass
            return ImageFont.load_default()

        resample = getattr(Image.Resampling, "LANCZOS", Image.BICUBIC)
        render_size = 300
        y = pad
        for line in raw_lines:
            f = font_at(render_size)
            probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
            bb = probe.textbbox((0, 0), line, font=f)
            tw, th = bb[2] - bb[0], bb[3] - bb[1]
            if tw <= 0 or th <= 0:
                y += slot_h + gap
                continue

            text_img = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
            ImageDraw.Draw(text_img).text(
                (-bb[0], -bb[1]), line, fill=(*text_colour, 255), font=f
            )
            stretched = text_img.resize((usable_w, slot_h), resample=resample)
            img.paste(stretched, (pad, y), stretched)
            y += slot_h + gap

        return img

    def _make_event_image(self, event, colour, event_name="Event", image_url=None, image_path=None):
        """Download (with cache) or generate a placeholder image and attach it to the event."""
        try:
            img = None
            if image_path:
                _seed_data_dir = os.path.dirname(os.path.abspath(__file__)) + "/seed_data"
                full_path = os.path.join(_seed_data_dir, image_path)
                try:
                    img = Image.open(full_path)
                    if img.mode != "RGB":
                        img = img.convert("RGB")
                except Exception as exc:
                    self.stdout.write(f"  Warning: could not load local image '{full_path}': {exc}")
                    img = None
            elif image_url:
                # Check cache first
                os.makedirs(_SEED_CACHE_DIR, exist_ok=True)
                url_hash = hashlib.md5(image_url.encode()).hexdigest()
                cache_path = os.path.join(_SEED_CACHE_DIR, f"{url_hash}.jpg")
                if os.path.exists(cache_path):
                    with open(cache_path, "rb") as f:
                        img_data = f.read()
                else:
                    try:
                        req = urllib.request.Request(
                            image_url, headers={"User-Agent": "Mozilla/5.0"}
                        )
                        with urllib.request.urlopen(req, timeout=10) as response:
                            img_data = response.read()
                        with open(cache_path, "wb") as f:
                            f.write(img_data)
                    except Exception as exc:
                        self.stdout.write(
                            f"  Warning: could not download image for '{event_name}': {exc}"
                        )
                        img_data = None

                if img_data:
                    img = Image.open(io.BytesIO(img_data))
                    if img.mode != "RGB":
                        img = img.convert("RGB")
                    # Scale down if very large, preserving aspect ratio.
                    # Do NOT crop -- store the full image so real-world aspect
                    # ratios (portrait posters, landscape banners, square social
                    # cards) are preserved and the index/detail templates can be
                    # tested with authentic variety.
                    max_dim = 1200
                    if img.width > max_dim or img.height > max_dim:
                        resample = getattr(Image.Resampling, "LANCZOS", Image.BICUBIC)
                        img.thumbnail((max_dim, max_dim), resample=resample)

            if img is None:
                img = self._make_poster_image(event_name, colour)

            buf = io.BytesIO()
            use_jpeg = bool(image_url or image_path)
            img.save(buf, format="JPEG" if use_jpeg else "PNG")
            buf.seek(0)

            safe_name = re.sub(r"[^\w]", "_", event_name)[:40]
            ext = "jpg" if use_jpeg else "png"
            media_item = MediaItem.objects.create(
                credit="seed_dev_data",
                media_file=ContentFile(buf.read(), name=f"{safe_name}.{ext}"),
                alt_text=f"Placeholder image for {event_name}",
            )
            event.media.add(media_item)
            return media_item
        except Exception as e:
            self.stderr.write(f"Warning: could not create image for {event_name}: {e}")
            return None
