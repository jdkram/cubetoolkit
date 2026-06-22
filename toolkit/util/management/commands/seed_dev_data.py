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
    EventTemplateRoom,
    MediaItem,
    Role,
    RoomBooking,
    RotaEntry,
    Room,
    Showing,
)
from toolkit.index.models import IndexCategory, IndexLink
from toolkit.members.models import Member, Volunteer, Qualification, VolunteerQualification

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
    COLLECTIVES,
    DONATION_ITEMS,
    JOBS,
    SHOPPING_FLAGS,
    BUILDING_MAP_NOTES,
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
            from toolkit.inductions.models import InductionSession, InductionSignup, InductionRequest
            InductionSignup.objects.all().delete()
            InductionRequest.objects.all().delete()
            InductionSession.objects.all().delete()
            from toolkit.diary.models import Film
            Film.objects.all().delete()
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
            "qualifications": 0,
            "volunteers": 0,
            "events": 0,
            "proposed_events": 0,
            "showings": 0,
            "rota_entries": 0,
            "images": 0,
            "event_links": 0,
            "cms_pages": 0,
            "index_links": 0,
            "collectives": 0,
            "donation_items": 0,
            "shopping_items": 0,
            "shopping_flags": 0,
            "jobs": 0,
            "map_notes": 0,
            "exchange_items": 0,
            "film_records": 0,
            "induction_sessions": 0,
            "induction_signups": 0,
            "induction_requests": 0,
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
            role.stats_label = role_data.get("stats_label", "")
            role.save(
                update_fields=[
                    "beginner_friendly",
                    "wheelchair_accessible",
                    "keyholder_only",
                    "programmer_contact",
                    "description",
                    "stats_label",
                ]
            )

        # Tags
        for tag_data in TAGS:
            tag_name = tag_data["name"]
            filter_group = tag_data.get("filter_group") or None
            description = tag_data.get("description") or None
            tag, created = EventTag.objects.get_or_create(name=tag_name)
            if created:
                tag.filter_group = filter_group
                tag.description = description
                tag.clean()
                tag.save()
                counts["tags"] += 1
            else:
                update_fields = []
                if tag.filter_group != filter_group:
                    tag.filter_group = filter_group
                    update_fields.append("filter_group")
                if tag.description != description:
                    tag.description = description
                    update_fields.append("description")
                if update_fields:
                    tag.save(update_fields=update_fields)

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
                role_slots = tmpl_data.get("role_slots") or [
                    {"role": name, "count": 1} for name in tmpl_data.get("roles", [])
                ]
                for slot in role_slots:
                    try:
                        EventTemplateRole.objects.create(
                            template=tmpl,
                            role=Role.objects.get(name=slot["role"]),
                            count=slot.get("count", 1),
                        )
                    except Role.DoesNotExist:
                        pass
                for tag_name in tmpl_data.get("tags", []):
                    try:
                        tmpl.tags.add(EventTag.objects.get(name=tag_name))
                    except EventTag.DoesNotExist:
                        pass
                for room_data in tmpl_data.get("default_rooms", []):
                    try:
                        EventTemplateRoom.objects.get_or_create(
                            template=tmpl,
                            room=Room.objects.get(name=room_data["room"]),
                            date_offset=0,
                            defaults={
                                "start_delta_minutes": room_data.get("start_delta_minutes", 0),
                                "end_delta_minutes": room_data.get("end_delta_minutes"),
                            },
                        )
                    except Room.DoesNotExist:
                        pass

        # Collectives must be seeded before volunteers so that collective
        # membership can be wired up in the volunteer loop below.
        from toolkit.labs.models import Collective

        for c in COLLECTIVES:
            collective, created = Collective.objects.get_or_create(
                slug=c["slug"],
                defaults={
                    "name": c["name"],
                    "colour": c.get("colour", "#343a40"),
                    "display_order": c.get("display_order", 0),
                    "volunteer_count": c.get("volunteer_count", ""),
                    "about": c.get("about", ""),
                    "roles": c.get("roles", ""),
                    "organising": c.get("organising", ""),
                    "proud_of": c.get("proud_of", ""),
                    "get_involved": c.get("get_involved", ""),
                    "contact": c.get("contact", ""),
                    "invite_only": c.get("invite_only", False),
                    "listed_publicly": c.get("listed_publicly", False),
                    "public_copy": c.get("public_copy", ""),
                },
            )
            if created:
                counts["collectives"] += 1

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
            # Translate the legacy "dir_share_name" enum (full/initial/none) from
            # TOML data into the new dir_share_listed + dir_share_name_style pair.
            legacy_name = vol_data.get("dir_share_name")
            if legacy_name is not None:
                vol_data = dict(vol_data)
                vol_data["dir_share_listed"] = legacy_name != "none"
                vol_data["dir_share_name_style"] = (
                    Volunteer.NAME_STYLE_INITIAL if legacy_name == "initial"
                    else Volunteer.NAME_STYLE_FULL
                )

            _bool_fields = {"dir_share_listed", "dir_share_pronouns", "dir_share_email", "dir_share_phone", "dir_share_access_rider", "dir_share_collectives"}
            _str_defaults = {"dir_share_name_style": Volunteer.NAME_STYLE_FULL}
            vol_dirty = False
            for field in (
                "access_intro", "access_needs", "access_links",
                "emergency_contact_name", "emergency_contact_relationship",
                "emergency_contact_phone",
                "dir_share_listed", "dir_share_name_style",
                "dir_share_pronouns", "dir_share_email",
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
            wanted_slugs = vol_data.get("collectives", [])
            wanted_collectives = list(Collective.objects.filter(slug__in=wanted_slugs))
            if set(volunteer.collectives.values_list("slug", flat=True)) != set(wanted_slugs):
                volunteer.collectives.set(wanted_collectives)

            # Pool-health test fields — only applied when explicitly present in TOML.
            # These create volunteers in specific lifecycle states so the pool-health
            # dashboard (/volunteers/view/pool-health/) has meaningful data to display.
            _ph_now = timezone.now()

            status = vol_data.get("status")
            if status and volunteer.status != status:
                volunteer.status = status
                volunteer.save(update_fields=["status"])

            # User.objects.update() bypasses auto_now fields and model .save() hooks,
            # which is what we want: we're backdating dates for test realism, not
            # triggering the suspension logic that Volunteer.save() applies.
            if "last_login_days_ago" in vol_data:
                User.objects.filter(pk=user.pk).update(
                    last_login=_ph_now - datetime.timedelta(days=vol_data["last_login_days_ago"])
                )
            if "date_joined_days_ago" in vol_data:
                User.objects.filter(pk=user.pk).update(
                    date_joined=_ph_now - datetime.timedelta(days=vol_data["date_joined_days_ago"])
                )
            # Backdate Volunteer.created_at to match the earliest of the two user
            # dates, so that purge_candidates() (which uses Greatest(created_at, ...))
            # correctly classifies these as old accounts.
            _backdate_days = max(
                vol_data.get("last_login_days_ago", 0),
                vol_data.get("date_joined_days_ago", 0),
            )
            if _backdate_days:
                Volunteer.objects.filter(pk=volunteer.pk).update(
                    created_at=_ph_now - datetime.timedelta(days=_backdate_days)
                )

            if "membership_expires_days_from_now" in vol_data:
                expires = (_ph_now + datetime.timedelta(days=vol_data["membership_expires_days_from_now"])).date()
                if member.membership_expires != expires:
                    member.membership_expires = expires
                    member.save(update_fields=["membership_expires"])

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

        # Qualifications — seed named credentials and award them to relevant volunteers
        _QUALIFICATIONS = [
            ("Bar", [
                "Rex Hollis", "Nell Arundel", "Beef", "Nadia Kurosawa", "Zara Moon",
                # many volunteers get bar trained over time; a realistic spread:
                "Sasha Pryce", "Jules Travers", "Remy Okafor", "Cleo Marchetti",
                "Lena Barrow", "Ivan Solis", "Cheddar",
            ]),
            ("Projectionist level 1", [
                "Elia Silveira", "Tomás Ferreira", "Sparks", "Lila Estraven",
            ]),
            ("Cafe", [
                "Sasha Pryce", "Reuben Ashford", "Phoebe Lund", "Fig",
            ]),
        ]
        for qual_name, vol_names in _QUALIFICATIONS:
            qual, created = Qualification.objects.get_or_create(name=qual_name)
            if created:
                counts["qualifications"] += 1
            for vol_name in vol_names:
                volunteer = volunteer_objects.get(vol_name)
                if volunteer:
                    VolunteerQualification.objects.get_or_create(
                        volunteer=volunteer,
                        qualification=qual,
                        defaults={
                            "granted_by": "seed_dev_data",
                            "granted_on": datetime.date(2023, 1, 1),
                        },
                    )

        # Set required_qualification on bar roles now that qualifications exist
        _bar_qual = Qualification.objects.filter(name="Bar").first()
        if _bar_qual:
            for _role_name in ("Bar Staff - Shift 1", "Bar Staff - Shift 2", "Bar Shadow"):
                Role.objects.filter(name=_role_name).update(
                    required_qualification=_bar_qual,
                    qualification_gate=Role.GATE_ADVISORY,
                )

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
                        defaults={
                            "start": showing_start,
                            "end": showing_start + datetime.timedelta(minutes=dur_minutes),
                        },
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
                if self._make_event_image(event, colour, event_data["name"], image_url=event_data.get("image_url"), image_path=event_data.get("image_path"), auto_crop=event_data.get("auto_crop")):
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

        # Programming queue — proposed / draft events a few months out
        self._seed_programming_queue(
            rooms_dict, list(volunteer_objects.values()), counts
        )

        # CMS pages
        if WAGTAIL_AVAILABLE:
            counts["cms_pages"] += self._seed_cms_pages()

        # Toolkit index links
        counts["index_links"] = self._seed_index_links()

        # Donation items
        from toolkit.labs.models import DonationItem

        for item in DONATION_ITEMS:
            _, created = DonationItem.objects.get_or_create(
                name=item["name"],
                defaults={
                    "category": item.get("category", ""),
                    "status": item.get("status", DonationItem.STATUS_WANTED),
                    "notes": item.get("notes", ""),
                    "internal_notes": item.get("internal_notes", ""),
                    "contact": item.get("contact", ""),
                    "display_order": item.get("display_order", 0),
                },
            )
            if created:
                counts["donation_items"] += 1

        # Consumable items (9.88)
        from toolkit.labs.models import ConsumableItem

        CONSUMABLE_ITEMS = [
            ("Hand soap", ConsumableItem.CATEGORY_CLEANING),
            ("Bin bags", ConsumableItem.CATEGORY_CLEANING),
            ("Washing detergent", ConsumableItem.CATEGORY_CLEANING),
            ("Dishwasher detergent", ConsumableItem.CATEGORY_CLEANING),
            ("Dishwasher rinse aid", ConsumableItem.CATEGORY_CLEANING),
            ("Washing up sponges", ConsumableItem.CATEGORY_CLEANING),
            ("Steel scrubbers", ConsumableItem.CATEGORY_CLEANING),
            ("Microfibre cloths", ConsumableItem.CATEGORY_CLEANING),
            ("Cling film", ConsumableItem.CATEGORY_KITCHEN),
            ("Steriliser tablets", ConsumableItem.CATEGORY_KITCHEN),
            ("Sesame Snaps", ConsumableItem.CATEGORY_SNACKS),
            ("Sesame Snaps (Chocolate)", ConsumableItem.CATEGORY_SNACKS),
            ("Dino Gummies", ConsumableItem.CATEGORY_SNACKS),
            ("Crisps (Lightly Salted)", ConsumableItem.CATEGORY_SNACKS),
            ("Crisps (Sea Salt & Malt Vinegar)", ConsumableItem.CATEGORY_SNACKS),
            ("Crisps (Rosemary & Sea Salt)", ConsumableItem.CATEGORY_SNACKS),
            ("Pens", ConsumableItem.CATEGORY_STATIONERY),
            ("Lamination sheets (A4)", ConsumableItem.CATEGORY_STATIONERY),
            ("Reams of paper (A4)", ConsumableItem.CATEGORY_STATIONERY),
            ("Reams of paper (A3)", ConsumableItem.CATEGORY_STATIONERY),
        ]
        for name, category in CONSUMABLE_ITEMS:
            _, created = ConsumableItem.objects.get_or_create(
                name=name,
                defaults={"category": category},
            )
            if created:
                counts["shopping_items"] += 1

        # Shopping need flags (9.88) — layered on top of ConsumableItem catalogue
        from toolkit.labs.models import NeedFlag, ProcurementPledge

        _vols = list(volunteer_objects.values())
        for flag_data in SHOPPING_FLAGS:
            item_name = flag_data["item"]
            try:
                item = ConsumableItem.objects.get(name=item_name)
            except ConsumableItem.DoesNotExist:
                continue
            # Only create if no open flag already exists for this item
            if NeedFlag.objects.filter(item=item, resolved_at__isnull=True).exists():
                continue
            pledge_idx = flag_data.get("pledged_by_index")
            flagger = _vols[0] if _vols else None
            flag = NeedFlag.objects.create(
                item=item,
                flagged_by=flagger,
                notes=flag_data.get("notes", ""),
            )
            counts["shopping_flags"] += 1
            if pledge_idx is not None and _vols and pledge_idx < len(_vols):
                ProcurementPledge.objects.get_or_create(
                    need_flag=flag,
                    defaults={
                        "pledged_by": _vols[pledge_idx],
                        "eta_notes": flag_data.get("pledge_eta_notes", ""),
                    },
                )

        # Jobs board (9.80)
        from toolkit.labs.models import Job
        from django.utils import timezone as tz

        for job_data in JOBS:
            if Job.objects.filter(title=job_data["title"]).exists():
                continue
            resolved = job_data.get("resolved", False)
            job = Job.objects.create(
                title=job_data["title"],
                area=job_data.get("area", ""),
                description=job_data.get("description", ""),
                plan_status=job_data.get("plan_status", ""),
                urgency=job_data.get("urgency", Job.URGENCY_LOW),
                safety_risk=job_data.get("safety_risk", False),
                skill_needed=job_data.get("skill_needed", False),
                keyholder_required=job_data.get("keyholder_required", False),
                location_type=job_data.get("location_type", Job.LOCATION_BUILDING),
                reporter_name=job_data.get("reporter_name", ""),
                resolved=resolved,
                resolved_at=tz.now() if resolved else None,
            )
            counts["jobs"] += 1

        # Building map notes (labs floorplan)
        from toolkit.labs.models import RoomNote

        for note_data in BUILDING_MAP_NOTES:
            _, created = RoomNote.objects.get_or_create(
                room_id=note_data["room_id"],
                defaults={"body": note_data["body"]},
            )
            if created:
                counts["map_notes"] += 1

        # Sample bulletin (9.95)
        from toolkit.labs.models import Bulletin

        Bulletin.objects.get_or_create(
            title="Keyholders list now open to all volunteers",
            defaults={
                "body": (
                    "You can now contact the keyholders list directly at "
                    "totally_real@list.name if you need a keyholder for an upcoming event. "
                    "No need to ask around individually."
                ),
                "author": None,
            },
        )

        # Seed bulletin_guidance on SiteConfiguration so the 'Post a bulletin'
        # form has useful example text in dev.
        from toolkit.diary.models import SiteConfiguration

        _BULLETIN_GUIDANCE = (
            "Use bulletins for short notices that are relevant to the whole volunteer community "
            "right now — things people need to know before their next shift, or time-sensitive "
            "updates about the building, programme, or online tools.\n\n"
            "Good examples:\n"
            "• Keyholders can now be contacted via the address totally_real@list.name\n"
            "• Password to Ticketsource has changed - see link section at the bottom of the toolkit homepage\n"
            "• Email lists are temporarily down\n\n"
            "Not a good fit for bulletins:\n"
            "• Long policy discussions (use the mailing list instead)\n"
            "• Event-specific notes (put them in the rota notes for that showing)\n"
            "• Things only relevant to one collective (post on your collective channel)\n\n"
            "Keep it short: two or three sentences is usually enough. If you need more space, "
            "you can signpost to something else, or consider using the email lists."
        )
        cfg, _ = SiteConfiguration.objects.get_or_create(pk=1)
        if not cfg.bulletin_guidance:
            cfg.bulletin_guidance = _BULLETIN_GUIDANCE
            cfg.save(update_fields=["bulletin_guidance"])

        # Star and Shadow runs a mixed programme (films, gigs, workshops, club
        # nights), so "date" reads better than the cinema-default "showing".
        # The model default stays "showing"/"Confirm" (cinema-first).
        cfg.occurrence_noun = "date"
        cfg.occurrence_noun_plural = "dates"
        cfg.confirm_label = "Publish & open rota"
        cfg.stats_training_tag_slugs = ["induction", "training-for-volunteers"]
        cfg.structured_cost_terms_enabled = True
        if not cfg.stats_programming_note:
            cfg.stats_programming_note = (
                "This is a guideline, not a hard rule. "
                "Talk to other programmers if you're interested in putting something on."
            )
        cfg.save(
            update_fields=[
                "occurrence_noun",
                "occurrence_noun_plural",
                "confirm_label",
                "stats_training_tag_slugs",
                "structured_cost_terms_enabled",
                "stats_programming_note",
            ]
        )

        # Community exchange items (9.79)
        from toolkit.labs.models import ExchangeItem

        _exchange_items = [
            {
                "name": "DeWalt 18V cordless drill",
                "listing_type": ExchangeItem.TYPE_LEND,
                "category": ExchangeItem.CATEGORY_TOOLS,
                "condition": ExchangeItem.CONDITION_GOOD,
                "owner_type": ExchangeItem.OWNER_VOLUNTEER,
                "owner_name": "Rex Hollis",
                "location_notes": "Bring to the next event and ask Rex",
                "notes": "Two batteries included. Charger needed overnight.",
                "status": ExchangeItem.STATUS_AVAILABLE,
            },
            {
                "name": "Folding workbench",
                "listing_type": ExchangeItem.TYPE_LEND,
                "category": ExchangeItem.CATEGORY_TOOLS,
                "condition": ExchangeItem.CONDITION_FAIR,
                "owner_type": ExchangeItem.OWNER_COLLECTIVE,
                "location_notes": "Workshop cupboard, left side",
                "notes": "Slightly wobbly on the left leg — tighten before use.",
                "status": ExchangeItem.STATUS_AVAILABLE,
            },
            {
                "name": "Jigsaw (electric)",
                "listing_type": ExchangeItem.TYPE_LEND,
                "category": ExchangeItem.CATEGORY_TOOLS,
                "condition": ExchangeItem.CONDITION_GOOD,
                "owner_type": ExchangeItem.OWNER_VOLUNTEER,
                "owner_name": "Nell Arundel",
                "location_notes": "DM Nell on the volunteers list",
                "status": ExchangeItem.STATUS_AVAILABLE,
            },
            {
                "name": "IKEA bookshelf (Billy, white, 80cm)",
                "listing_type": ExchangeItem.TYPE_GIVE,
                "category": ExchangeItem.CATEGORY_FURNITURE,
                "condition": ExchangeItem.CONDITION_GOOD,
                "owner_type": ExchangeItem.OWNER_VOLUNTEER,
                "owner_name": "Lila Estraven",
                "location_notes": "You'll need a car or van — too big to carry",
                "description": "Moving house, no room for it. In good nick, no damage.",
                "status": ExchangeItem.STATUS_AVAILABLE,
            },
            {
                "name": "Box of assorted books",
                "listing_type": ExchangeItem.TYPE_GIVE,
                "category": ExchangeItem.CATEGORY_BOOKS,
                "condition": ExchangeItem.CONDITION_GOOD,
                "owner_type": ExchangeItem.OWNER_VOLUNTEER,
                "owner_name": "Sasha Pryce",
                "location_notes": "Can bring to any event",
                "description": "Mostly fiction, some theory. See me at the bar to look through.",
                "status": ExchangeItem.STATUS_AVAILABLE,
            },
            {
                "name": "Chest freezer (under-counter, 60L)",
                "listing_type": ExchangeItem.TYPE_GIVE,
                "category": ExchangeItem.CATEGORY_KITCHEN,
                "condition": ExchangeItem.CONDITION_FAIR,
                "owner_type": ExchangeItem.OWNER_VOLUNTEER,
                "owner_name": "Jules Travers",
                "location_notes": "You collect — it's heavy",
                "description": "Works fine, just very loud at night. Ideal for a garage or workshop.",
                "status": ExchangeItem.STATUS_AVAILABLE,
            },
            {
                "name": "Roland MIDI keyboard (25-key)",
                "listing_type": ExchangeItem.TYPE_GIVE,
                "category": ExchangeItem.CATEGORY_AV,
                "condition": ExchangeItem.CONDITION_GOOD,
                "owner_type": ExchangeItem.OWNER_VOLUNTEER,
                "owner_name": "Tomás Ferreira",
                "location_notes": "Can bring to a rehearsal space or S+S event",
                "description": "USB-powered, works perfectly. I never use it.",
                "status": ExchangeItem.STATUS_AVAILABLE,
            },
            {
                "name": "Hand trowels (set of 3)",
                "listing_type": ExchangeItem.TYPE_GIVE,
                "category": ExchangeItem.CATEGORY_GARDEN,
                "condition": ExchangeItem.CONDITION_FAIR,
                "owner_type": ExchangeItem.OWNER_VOLUNTEER,
                "owner_name": "Cleo Marchetti",
                "location_notes": "Ask at bar or message via volunteers list",
                "status": ExchangeItem.STATUS_AVAILABLE,
            },
            {
                "name": "PA speaker (Behringer B112D)",
                "listing_type": ExchangeItem.TYPE_LEND,
                "category": ExchangeItem.CATEGORY_AV,
                "condition": ExchangeItem.CONDITION_GOOD,
                "owner_type": ExchangeItem.OWNER_COLLECTIVE,
                "location_notes": "Projection booth — ask a keyholder",
                "notes": "For small events only. Log your loan on the equipment sheet.",
                "status": ExchangeItem.STATUS_ON_LOAN,
            },
            {
                "name": "Sewing machine (Singer Simple)",
                "listing_type": ExchangeItem.TYPE_LEND,
                "category": ExchangeItem.CATEGORY_OTHER,
                "condition": ExchangeItem.CONDITION_GOOD,
                "owner_type": ExchangeItem.OWNER_VOLUNTEER,
                "owner_name": "Phoebe Lund",
                "location_notes": "Arrange collection with Phoebe",
                "description": "Basic home sewing machine. Good for repairs and simple projects.",
                "status": ExchangeItem.STATUS_AVAILABLE,
            },
            {
                "name": "Bread maker",
                "listing_type": ExchangeItem.TYPE_GIVE,
                "category": ExchangeItem.CATEGORY_KITCHEN,
                "condition": ExchangeItem.CONDITION_GOOD,
                "owner_type": ExchangeItem.OWNER_VOLUNTEER,
                "owner_name": "Remy Okafor",
                "location_notes": "Can bring to S+S",
                "description": "Used twice. Still in original box. Comes with recipe booklet.",
                "status": ExchangeItem.STATUS_CLAIMED,
            },
            {
                "name": "Potatoes (Community Kitchen surplus)",
                "listing_type": ExchangeItem.TYPE_SHARE,
                "category": ExchangeItem.CATEGORY_KITCHEN,
                "owner_type": ExchangeItem.OWNER_COLLECTIVE,
                "quantity": "about 10kg",
                "available_until": datetime.date.today() + datetime.timedelta(days=5),
                "location_notes": "Kitchen fridge/store — help yourself at any event",
                "description": "CK bought in bulk and won't get through them before next month's session. Please take some!",
                "status": ExchangeItem.STATUS_AVAILABLE,
            },
            {
                "name": "Crisps (past best before, perfectly fine)",
                "listing_type": ExchangeItem.TYPE_SHARE,
                "category": ExchangeItem.CATEGORY_KITCHEN,
                "owner_type": ExchangeItem.OWNER_COLLECTIVE,
                "quantity": "several multipacks",
                "location_notes": "Bar shelf — grab a bag",
                "description": "Best before was last week but they're completely fine. Mixed flavours.",
                "status": ExchangeItem.STATUS_AVAILABLE,
            },
            {
                "name": "Twin Peaks event badges",
                "listing_type": ExchangeItem.TYPE_SHARE,
                "category": ExchangeItem.CATEGORY_OTHER,
                "owner_type": ExchangeItem.OWNER_COLLECTIVE,
                "quantity": "about 30 left",
                "location_notes": "Box behind the bar — take one (or two)",
                "description": "Leftover from the Twin Peaks screening. Assorted designs. Volunteers first but take as many as you like.",
                "status": ExchangeItem.STATUS_AVAILABLE,
            },
        ]
        counts["exchange_items"] = 0
        for item_data in _exchange_items:
            if ExchangeItem.objects.filter(name=item_data["name"]).exists():
                continue
            owner_vol = None
            if item_data.get("owner_name"):
                owner_vol = volunteer_objects.get(item_data["owner_name"])
            ExchangeItem.objects.create(
                name=item_data["name"],
                listing_type=item_data["listing_type"],
                category=item_data["category"],
                condition=item_data.get("condition", ExchangeItem.CONDITION_GOOD),
                owner_type=item_data["owner_type"],
                owner_volunteer=owner_vol,
                location_notes=item_data.get("location_notes", ""),
                description=item_data.get("description", ""),
                notes=item_data.get("notes", ""),
                quantity=item_data.get("quantity", ""),
                available_until=item_data.get("available_until"),
                status=item_data["status"],
            )
            counts["exchange_items"] += 1

        # Historical past showings with FK-linked rota entries (volunteer stats / heatmap)
        self._seed_historical_shifts(volunteer_objects, counts)

        # Induction sessions and sign-ups
        self._seed_inductions(counts)

        # Film records (9.66)
        self._seed_film_records(counts)

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
                f"  Qualifications:  {counts['qualifications']} new\n"
                f"  Volunteers:      {counts['volunteers']} new\n"
                f"  Events:          {counts['events']} new\n"
                f"    of which queue: {counts['proposed_events']} proposed/draft\n"
                f"  Showings:        {counts['showings']} new\n"
                f"  Rota entries:    {counts['rota_entries']} new\n"
                f"  Images:          {counts['images']} new\n"
                f"  Event links:     {counts['event_links']} new\n"
                f"  CMS pages:       {counts['cms_pages']} new\n"
                f"  Index links:     {counts['index_links']} new\n"
                f"  Collectives:     {counts['collectives']} new\n"
                f"  Donation items:  {counts['donation_items']} new\n"
                f"  Shopping items:  {counts['shopping_items']} new\n"
                f"  Shopping flags:  {counts['shopping_flags']} new\n"
                f"  Jobs:            {counts['jobs']} new\n"
                f"  Map notes:       {counts['map_notes']} new\n"
                f"  Exchange items:  {counts['exchange_items']} new\n"
                f"  Film records:    {counts['film_records']} new\n"
                f"  Induction sessions: {counts['induction_sessions']} new\n"
                f"  Induction signups:  {counts['induction_signups']} new\n"
                f"  Induction requests: {counts['induction_requests']} new\n"
            )
        )

    def _seed_historical_shifts(self, volunteer_objects, counts):
        """Seed ~4 years of past confirmed showings with FK-linked volunteer rota entries.

        Volunteer stats / heatmap page uses RotaEntry.volunteer FK — the existing
        seed events use the free-text name field only, so show nothing on that page.
        This fills in a realistic history.

        Interesting patterns:
        - Most volunteers are active throughout 2022-2026
        - Every third volunteer has a quiet spell in 2024 (visible gap in their heatmap)
        - The last volunteer in the pool only joins from mid-2023
        - Roles cycle across all standard types for a varied role breakdown
        """
        now = timezone.now()
        today = now.date()
        history_start = datetime.date(2022, 1, 1)
        history_end = today - datetime.timedelta(days=14)

        # Include demo accounts (admin etc.) which are created after volunteer_objects
        vols = list(
            Volunteer.objects.select_related("member").filter(
                member__isnull=False
            ).exclude(member__name="")
        )
        if not vols:
            return

        role_names = [
            "Keyholder",
            "Projectionist - DCP",
            "Box Office - Admission Tickets",
            "Bar Staff - Shift 1",
            "Bar Staff - Shift 2",
            "Usher - Fire Trained",
            "Bar Shadow",
            "Cafe Staff",
        ]
        roles = []
        for rn in role_names:
            try:
                roles.append(Role.objects.get(name=rn))
            except Role.DoesNotExist:
                pass
        if not roles:
            roles = list(Role.objects.filter(standard=True)[:6])
        if not roles:
            return

        hist_event_names = [
            "Sunday Film Night",
            "Thursday Screening",
            "Late Show",
            "Community Event Night",
            "Shorts Programme",
        ]
        hist_events = []
        for name in hist_event_names:
            event, created = Event.objects.get_or_create(
                name=name,
                defaults={
                    "copy_summary": "",
                    "copy": "",
                    "film_information": "",
                    "pricing": "£7/£5/£3/£0",
                    "private": False,
                    "outside_hire": False,
                    "terms": "",
                    "duration": datetime.time(2, 0),
                },
            )
            if created:
                counts["events"] += 1
            hist_events.append(event)

        n_vols = len(vols)
        # Every third volunteer skips most of 2024
        quiet_2024_ids = {id(v) for v in vols[::3]}
        # One volunteer (second-to-last named, so demo accounts don't land here)
        # starts mid-2023 with no history before that
        late_joiner_id = id(vols[-2]) if n_vols > 2 else None

        current = history_start.replace(day=1)
        event_cycle_idx = 0

        while current <= history_end:
            year, month = current.year, current.month

            # Four showings per month: 2nd and 4th Thursday + 2nd and 4th Sunday
            showing_dates = []
            for weekday, ns in [(3, [2, 4]), (6, [2, 4])]:
                for n in ns:
                    d = _nth_weekday_of_month(year, month, weekday, n)
                    if d and d <= history_end:
                        showing_dates.append(d)

            for show_date in showing_dates:
                event = hist_events[event_cycle_idx % len(hist_events)]
                event_cycle_idx += 1

                showing_dt = timezone.make_aware(
                    datetime.datetime.combine(show_date, datetime.time(19, 0, 0))
                )
                showing, s_created = Showing.objects.get_or_create(
                    event=event,
                    start=showing_dt,
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

                # Assign ~12 FK-linked rota slots per showing: cycle through
                # the volunteer pool multiple times to give each vol ~3/month.
                offset = (event_cycle_idx * 7) % n_vols
                for slot_idx in range(12):
                    vol = vols[(offset + slot_idx) % n_vols]

                    if id(vol) == late_joiner_id and show_date < datetime.date(2023, 6, 1):
                        continue

                    # Quiet 2024 spell: skip Feb–Oct for this cohort
                    if id(vol) in quiet_2024_ids and year == 2024 and 2 <= month <= 10:
                        continue

                    role = roles[slot_idx % len(roles)]
                    _, re_created = RotaEntry.objects.get_or_create(
                        showing=showing,
                        volunteer=vol,
                        role=role,
                        defaults={
                            "required": True,
                            "name": vol.member.name,
                            "rank": 1,
                        },
                    )
                    if re_created:
                        counts["rota_entries"] += 1

            if month == 12:
                current = current.replace(year=year + 1, month=1)
            else:
                current = current.replace(month=month + 1)

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
                    copy=evt_data.get("copy", ""),
                    copy_summary=evt_data.get("copy_summary", ""),
                    terms=evt_data.get("terms", ""),
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
                    copy=evt_data.get("copy", ""),
                    copy_summary=evt_data.get("copy_summary", ""),
                    terms=evt_data.get("terms", ""),
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
                trailer_url=film.get("trailer_url", ""),
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
                trailer_url=film.get("trailer_url", ""),
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
                        copy=evt_data.get("copy", ""),
                        copy_summary=evt_data.get("copy_summary", ""),
                        terms=evt_data.get("terms", ""),
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
        copy="",
        copy_summary="",
        terms="",
    ):
        event, created = Event.objects.get_or_create(
            name=name,
            defaults={
                "copy_summary": copy_summary,
                "copy": copy,
                "film_information": "",
                "pricing": pricing,
                "private": False,
                "outside_hire": False,
                "terms": terms or copy,
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
                    defaults={
                        "start": showing_start,
                        "end": showing_start + datetime.timedelta(minutes=_dur_mins),
                    },
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
        trailer_url="",
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
                "terms": copy or copy_summary,
                "duration": datetime.time(2, 0),
                "trailer_url": trailer_url,
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
                    defaults={
                        "start": showing_start,
                        "end": showing_start + datetime.timedelta(minutes=120),
                    },
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

    def _seed_programming_queue(self, rooms_dict, vol_list, counts):
        """Seed proposed / draft events for the programming queue.

        These illustrate the queue's real-world states: events pencilled in
        2-3+ months ahead with varying amounts of detail, from a fully
        fleshed-out proposal down to a bare name with one placeholder date.
        Two of them carry several placeholder dates a programmer would later
        cancel once the plan firms up (the dates hold the room in the meantime,
        which is the whole point of putting them in early).

        All showings here are left unconfirmed — that is what "in the queue,
        not yet published" looks like. None are pre-cancelled: the intent is to
        give a programmer real placeholders to practise cancelling.
        """
        now = timezone.now()
        base = timezone.localtime(now)

        # weeks: offset from now. days: extra days (for back-to-back weekends).
        # A date with no "room" is deliberately left unbooked — a realistic gap.
        PROPOSED_EVENTS = [
            {
                "name": "Pleasure Activism — monthly reading group",
                "template": "Workshop",
                "status": "proposed",
                "booked_by": "Sasha Pryce",
                "tags": ["workshop"],
                "duration": 120,
                "created_days_ago": 21,
                "copy_summary": (
                    "A relaxed monthly reading group working through adrienne "
                    "maree brown's 'Pleasure Activism'. No prep needed — come "
                    "for any session."
                ),
                "copy": (
                    "We'll read a chapter a month and talk it through over tea. "
                    "Newcomers always welcome; you don't need to have read the "
                    "book. Step-free venue, gender-neutral toilets."
                ),
                "terms": "Free, donations welcome. Capacity 20.",
                "programming_notes": (
                    "Proposed at the last Monday meeting. Sasha to confirm it "
                    "doesn't clash with the existing book club before we lock "
                    "the dates."
                ),
                "dates": [{"weeks": 9, "hour": 18, "room": "Meeting"}],
            },
            {
                "name": "Repair Café (monthly trial)",
                "template": "Workshop",
                "status": "draft",
                "booked_by": "Cleo Marchetti",
                "tags": ["workshop"],
                "duration": 180,
                "created_days_ago": 10,
                "copy_summary": (
                    "Bring something broken — a lamp, a jumper, a toaster — and "
                    "fix it with help from volunteers, instead of binning it."
                ),
                "programming_notes": (
                    "Block-booked four monthly trial dates to hold the Venue "
                    "Space. We'll almost certainly drop the later ones once we "
                    "know how many fixers we can get — likely keeping just the "
                    "first one or two. Placeholders for now."
                ),
                "dates": [
                    {"weeks": 8, "hour": 13, "room": "Venue Space"},
                    {"weeks": 12, "hour": 13, "room": "Venue Space"},
                    {"weeks": 16, "hour": 13, "room": "Venue Space"},
                    {"weeks": 20, "hour": 13, "room": "Venue Space"},
                ],
            },
            {
                "name": "Noise night (working title)",
                "template": None,
                "status": "draft",
                "booked_by": "Sparks",
                "tags": ["music"],
                "duration": 180,
                "created_days_ago": 4,
                "programming_notes": (
                    "Pencilled in while I chase a headline act. Nothing "
                    "confirmed — title, line-up and door price all TBC. Will "
                    "firm up nearer the time."
                ),
                "dates": [{"weeks": 11, "hour": 20}],
            },
            {
                "name": "Trans Day of Visibility — film + panel",
                "template": "Film (DCP)",
                "status": "proposed",
                "booked_by": "Lila Estraven",
                "tags": ["film"],
                "duration": 150,
                "created_days_ago": 14,
                "copy_summary": (
                    "A screening followed by a panel discussion with local "
                    "trans and non-binary artists and organisers."
                ),
                "copy": "Film TBC — shortlisting now. Panel guests being confirmed.",
                "programming_notes": (
                    "Approved in principle at the meeting. Still needs a room "
                    "booked and the panel guests confirmed — no date clash, just "
                    "not booked yet."
                ),
                "dates": [{"weeks": 10, "hour": 19}],
            },
            {
                "name": "Benefit gig for the building fund",
                "template": "Gig",
                "status": "proposed",
                "booked_by": "Rex Hollis",
                "tags": ["music"],
                "duration": 240,
                "created_days_ago": 7,
                "copy_summary": (
                    "Three local bands playing to raise money for the roof "
                    "repairs. All proceeds to the building fund."
                ),
                "copy": "Line-up confirmed. Sound by the in-house PA. Bar open all night.",
                "terms": "",  # deliberately missing — publishing will fail until added
                "programming_notes": (
                    "Ready to go except it has no terms/pricing yet — confirming "
                    "it will fail until those are filled in. Flagged to Rex."
                ),
                "dates": [{"weeks": 13, "hour": 19, "room": "Venue Space"}],
            },
            {
                "name": "Experimental film weekender (early planning)",
                "template": None,
                "status": "draft",
                "booked_by": "Elia Silveira",
                "tags": ["film"],
                "duration": 180,
                "created_days_ago": 2,
                "programming_notes": (
                    "Very early — just holding a weekend in the diary. "
                    "Programme, guests and budget all TBC. Two placeholder dates "
                    "we'll likely thin out."
                ),
                "dates": [
                    {"weeks": 14, "days": 0, "hour": 18, "room": "Cinema"},
                    {"weeks": 14, "days": 1, "hour": 15, "room": "Cinema"},
                ],
            },
            # Dateless proposals — target_month set, no dates yet
            {
                "name": "Zine fair (date TBC)",
                "template": "Workshop",
                "status": "proposed",
                "booked_by": "Priya Narayan",
                "tags": ["workshop"],
                "duration": 300,
                "created_days_ago": 3,
                "target_month_offset_months": 3,
                "programming_notes": (
                    "Proposed at Monday meeting — everyone excited. Priya "
                    "checking maker availability before we lock a date. Probably "
                    "a Saturday afternoon."
                ),
            },
            {
                "name": "Late-night horror double bill",
                "template": "Film (DCP)",
                "status": "draft",
                "booked_by": "Kaz Tanaka",
                "tags": ["film"],
                "duration": 240,
                "created_days_ago": 1,
                "target_month_offset_months": 4,
                "programming_notes": (
                    "Halloween-adjacent. Kaz shortlisting titles. No room or "
                    "date agreed yet — just flagging so it lands in the right "
                    "month's planning."
                ),
            },
            {
                "name": "Community archive open day",
                "template": None,
                "status": "proposed",
                "booked_by": "Jo Afolabi",
                "tags": [],
                "duration": 360,
                "created_days_ago": 5,
                "target_month_offset_months": 5,
                "programming_notes": (
                    "Collaboration with the local history group. Date to be "
                    "agreed once they confirm their volunteer rota. Likely a "
                    "Sunday."
                ),
            },
        ]

        for spec in PROPOSED_EVENTS:
            template = None
            if spec.get("template"):
                template = EventTemplate.objects.filter(name=spec["template"]).first()

            dur_mins = spec.get("duration", 120)
            dur_time = datetime.time(dur_mins // 60, dur_mins % 60)

            target_month = None
            if spec.get("target_month_offset_months"):
                # Compute 1st of month N months from now.
                m = base.month - 1 + spec["target_month_offset_months"]
                target_month = datetime.date(
                    year=base.year + m // 12,
                    month=m % 12 + 1,
                    day=1,
                )

            defaults = {
                "programming_status": spec["status"],
                "programming_notes": spec.get("programming_notes", ""),
                "copy_summary": spec.get("copy_summary", ""),
                "copy": spec.get("copy", ""),
                "terms": spec.get("terms", ""),
                "pricing": spec.get("pricing", ""),
                "private": spec.get("private", False),
                "outside_hire": spec.get("outside_hire", False),
                "duration": dur_time,
                "target_month": target_month,
            }
            # Only pass template when set: Event.__init__ pre-fills from a
            # template kwarg and chokes on an explicit None.
            if template is not None:
                defaults["template"] = template

            event, created = Event.objects.get_or_create(
                name=spec["name"], defaults=defaults
            )
            if not created:
                continue
            counts["events"] += 1
            counts["proposed_events"] += 1

            for tag_name in spec.get("tags", []):
                tag = EventTag.objects.filter(name=tag_name).first()
                if tag:
                    event.tags.add(tag)

            # Backdate created_at (auto_now_add) so the queue's oldest-first
            # ordering is meaningful across the seeded proposals.
            days_ago = spec.get("created_days_ago")
            if days_ago:
                Event.objects.filter(pk=event.pk).update(
                    created_at=now - datetime.timedelta(days=days_ago)
                )

            for d in spec.get("dates", []):
                start = (
                    base + datetime.timedelta(weeks=d["weeks"], days=d.get("days", 0))
                ).replace(hour=d.get("hour", 19), minute=0, second=0, microsecond=0)

                room = rooms_dict.get(d["room"]) if d.get("room") else None
                if room is not None:
                    start = self._find_free_slot(room, start, dur_mins)

                showing, s_created = Showing.objects.get_or_create(
                    event=event,
                    start=start,
                    defaults={
                        "booked_by": spec.get("booked_by", "seed_dev_data"),
                        "confirmed": False,
                        "cancelled": d.get("cancelled", False),
                        "discounted": False,
                        "hide_in_programme": False,
                        "rota_notes": "",
                    },
                )
                if s_created:
                    counts["showings"] += 1
                    if room is not None and not d.get("cancelled", False):
                        RoomBooking.objects.get_or_create(
                            showing=showing,
                            room=room,
                            defaults={
                                "start": start,
                                "end": start + datetime.timedelta(minutes=dur_mins),
                            },
                        )
                        self._book_slot(room, start, dur_mins)

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

    def _seed_inductions(self, counts):
        from toolkit.inductions.models import (
            InductionSession,
            InductionSignup,
            InductionRequest,
            InductionsSettings,
        )

        cfg, _ = InductionsSettings.objects.get_or_create(pk=1)
        if not cfg.inductions_enabled:
            cfg.inductions_enabled = True
            cfg.save(update_fields=["inductions_enabled"])

        today = timezone.now().date()

        def _first_sunday_after_month_start(year, month):
            d = datetime.date(year, month, 1)
            while d.weekday() != 6:
                d += datetime.timedelta(days=1)
            return d

        y, m = today.year, today.month
        session_dates = []
        for _ in range(4):
            m += 1
            if m > 12:
                m = 1
                y += 1
            session_dates.append(_first_sunday_after_month_start(y, m))

        # Tapering signup counts — many for the soonest, trail off for later ones
        signup_counts = [14, 8, 4, 2]

        # New-to-the-community people signing up for group inductions
        _new_arrivals = [
            ("Jamie Thornton", "jamie.thornton@example.com"),
            ("Amara Ndiaye", "amara.ndiaye@example.com"),
            ("Felix Brauer", "felix.brauer@example.com"),
            ("Tanya Kulkarni", "tanya.kulkarni@example.com"),
            ("Ollie Pearce", "ollie.pearce@example.com"),
            ("Keisha Williams", "keisha.williams@example.com"),
            ("Seb Morales", "seb.morales@example.com"),
            ("Rosa Stein", "rosa.stein@example.com"),
            ("Marcus Webb", "marcus.webb@example.com"),
            ("Preethi Singh", "preethi.singh@example.com"),
            ("Callum Brady", "callum.brady@example.com"),
            ("Leila Farsi", "leila.farsi@example.com"),
            ("Tom Elliot", "tom.elliot@example.com"),
            ("Natasha Ivanova", "natasha.ivanova@example.com"),
            ("Diego Santos", "diego.santos@example.com"),
            ("Yemi Adekunle", "yemi.adekunle@example.com"),
            ("Hana Kobayashi", "hana.kobayashi@example.com"),
            ("Patrick O'Brien", "p.obrien@example.com"),
            ("Zoe Fletcher", "zoe.fletcher@example.com"),
            ("Sam Osei", "sam.osei@example.com"),
            ("Mia Chen", "mia.chen@example.com"),
            ("Jordan Nkosi", "jordan.nkosi@example.com"),
            ("Alice Roy", "alice.roy@example.com"),
            ("Ben Whitfield", "ben.whitfield@example.com"),
            ("Nia Davies", "nia.davies@example.com"),
            ("Oscar Lindgren", "oscar.lindgren@example.com"),
            ("Fatou Diallo", "fatou.diallo@example.com"),
            ("Charlie Brook", "charlie.brook@example.com"),
        ]

        signup_idx = 0
        for session_date, count in zip(session_dates, signup_counts):
            session_dt = timezone.make_aware(
                datetime.datetime.combine(session_date, datetime.time(14, 0))
            )
            title = f"Volunteer Induction — {session_date.strftime('%B %Y')}"

            session, created = InductionSession.objects.get_or_create(
                title=title,
                defaults={
                    "session_type": InductionSession.TYPE_REGULAR,
                    "date": session_dt,
                    "location": "Cinema, Star and Shadow",
                    "status": InductionSession.STATUS_OPEN,
                },
            )
            if created:
                counts["induction_sessions"] += 1

            for _ in range(count):
                name, email = _new_arrivals[signup_idx % len(_new_arrivals)]
                signup_idx += 1
                _, signup_created = InductionSignup.objects.get_or_create(
                    session=session,
                    email=email,
                    defaults={"name": name, "status": InductionSignup.STATUS_PENDING},
                )
                if signup_created:
                    counts["induction_signups"] += 1

        # 1:1 induction sessions and requests — access needs pathway
        _one_to_one_data = [
            {
                "title": "1:1 Induction — Alex",
                "date_offset_weeks": 3,
                "hour": 14,
                "location": "Meeting room, Star and Shadow",
                "request": {
                    "name": "Alex Mwangi",
                    "email": "alex.mwangi@example.com",
                    "access_needs": (
                        "I'm a wheelchair user and need to know which parts of the building "
                        "are accessible, where the accessible toilet is, and whether the "
                        "cinema space itself is step-free. I'd also like to understand what "
                        "roles are realistically available to me given mobility constraints."
                    ),
                    "rough_availability": "Weekday afternoons usually work best. Saturdays are OK too.",
                    "status": InductionRequest.STATUS_SCHEDULED,
                },
            },
            {
                "title": "1:1 Induction — Sam",
                "date_offset_weeks": 5,
                "hour": 11,
                "location": "Café area, Star and Shadow",
                "request": {
                    "name": "Sam Whitley",
                    "email": "sam.whitley@example.com",
                    "access_needs": (
                        "I'm autistic and find large group settings quite overwhelming. "
                        "A quieter one-to-one introduction would help a lot. I'd like to "
                        "walk through the building and meet a small number of people at a "
                        "time. Advance information about what to expect on the day would also "
                        "be really helpful."
                    ),
                    "rough_availability": "Weekend mornings, or Tuesday/Thursday afternoons.",
                    "status": InductionRequest.STATUS_SCHEDULED,
                },
            },
        ]

        for spec in _one_to_one_data:
            session_dt = timezone.make_aware(
                datetime.datetime.combine(
                    today + datetime.timedelta(weeks=spec["date_offset_weeks"]),
                    datetime.time(spec["hour"], 0),
                )
            )
            session, created = InductionSession.objects.get_or_create(
                title=spec["title"],
                defaults={
                    "session_type": InductionSession.TYPE_ONE_TO_ONE,
                    "date": session_dt,
                    "location": spec["location"],
                    "status": InductionSession.STATUS_OPEN,
                },
            )
            if created:
                counts["induction_sessions"] += 1

            req_data = spec["request"]
            req, req_created = InductionRequest.objects.get_or_create(
                email=req_data["email"],
                defaults={
                    "name": req_data["name"],
                    "access_needs": req_data["access_needs"],
                    "rough_availability": req_data.get("rough_availability", ""),
                    "status": req_data["status"],
                    "linked_session": session,
                },
            )
            if req_created:
                counts["induction_requests"] += 1
            elif req.linked_session_id != session.pk:
                req.linked_session = session
                req.save(update_fields=["linked_session"])

            # Create a signup in the session for this person
            _, signup_created = InductionSignup.objects.get_or_create(
                session=session,
                email=req_data["email"],
                defaults={"name": req_data["name"], "status": InductionSignup.STATUS_PENDING},
            )
            if signup_created:
                counts["induction_signups"] += 1

        # Pending and contacted requests in the queue (not yet scheduled)
        _unscheduled_requests = [
            {
                "name": "Bilal Chaudhry",
                "email": "bilal.chaudhry@example.com",
                "access_needs": (
                    "I have chronic fatigue and my energy levels vary a lot day to day. "
                    "I'd like to understand what the lowest-intensity roles look like and "
                    "whether I can commit on a flexible basis rather than to a regular rota. "
                    "Standing for long periods is difficult."
                ),
                "rough_availability": "I need to respond to how I'm feeling on the day — hard to book far ahead.",
                "status": InductionRequest.STATUS_PENDING,
            },
            {
                "name": "Miriam Okonkwo",
                "email": "miriam.okonkwo@example.com",
                "access_needs": (
                    "I'm DeafBlind and use a combination of tactile signing and close-up "
                    "written communication. I'll be bringing a support worker to my "
                    "induction. I'd like to find out whether any current volunteers have "
                    "BSL skills and what support the community can offer."
                ),
                "rough_availability": "Saturdays after 12 or Sundays.",
                "status": InductionRequest.STATUS_CONTACTED,
                "contacted_at": timezone.now() - datetime.timedelta(days=4),
            },
        ]

        for req_data in _unscheduled_requests:
            defaults = {
                "name": req_data["name"],
                "access_needs": req_data["access_needs"],
                "rough_availability": req_data.get("rough_availability", ""),
                "status": req_data["status"],
            }
            if req_data.get("contacted_at"):
                defaults["contacted_at"] = req_data["contacted_at"]
            req, req_created = InductionRequest.objects.get_or_create(
                email=req_data["email"],
                defaults=defaults,
            )
            if req_created:
                counts["induction_requests"] += 1

    def _seed_film_records(self, counts):
        """Create Film records with stored metadata and link them to matching Events.

        Uses hardcoded data so no TMDB API call is needed at seed time.
        TMDB IDs and poster paths are taken from the films already referenced in
        films.toml; they are correct as of 2025 but can be re-verified against
        https://www.themoviedb.org/ if needed.
        """
        from toolkit.diary.models import Film

        seed_films = [
            {
                "title": "Akira",
                "year": 1988,
                "director": "Katsuhiro Otomo",
                "runtime_minutes": 124,
                "countries": "JP",
                "languages": "Japanese",
                "overview": (
                    "A secret military project endangers Neo-Tokyo when it turns a biker "
                    "gang member into a rampaging psychic, and only two teenagers and a group "
                    "of psychics can stop him."
                ),
            },
            {
                "title": "La Haine",
                "year": 1995,
                "director": "Mathieu Kassovitz",
                "runtime_minutes": 98,
                "countries": "FR",
                "languages": "French",
                "overview": (
                    "After a chaotic night of rioting in a Paris suburb, three young friends "
                    "wander around waiting for news about a mutual friend seriously injured "
                    "while confronting police."
                ),
            },
            {
                "title": "Stalker",
                "year": 1979,
                "director": "Andrei Tarkovsky",
                "runtime_minutes": 163,
                "countries": "SU",
                "languages": "Russian",
                "overview": (
                    "Near a grey and unnamed city is the Zone, where the normal laws of physics "
                    "are victim to frequent anomalies. A Stalker guides two men into the Zone, "
                    "to an area where deep-seated desires are granted."
                ),
            },
            {
                "title": "Perfect Blue",
                "year": 1997,
                "director": "Satoshi Kon",
                "runtime_minutes": 81,
                "countries": "JP",
                "languages": "Japanese",
                "overview": (
                    "Rising pop star Mima quits singing to pursue acting. After she takes a role "
                    "on a detective show, her collaborators begin turning up murdered."
                ),
            },
            {
                "title": "Titane",
                "year": 2021,
                "director": "Julia Ducournau",
                "runtime_minutes": 108,
                "countries": "FR",
                "languages": "French",
                "overview": (
                    "A woman with a metal plate in her head from a childhood car accident "
                    "embarks on a bizarre journey, bringing her into contact with a firefighter "
                    "who has been reunited with his missing son."
                ),
            },
        ]

        for data in seed_films:
            film, created = Film.objects.get_or_create(
                title=data["title"],
                defaults={
                    "year": data.get("year"),
                    "director": data.get("director", ""),
                    "runtime_minutes": data.get("runtime_minutes"),
                    "countries": data.get("countries", ""),
                    "languages": data.get("languages", ""),
                    "media_type": Film.MEDIA_TYPE_FILM,
                    "overview": data.get("overview", ""),
                },
            )
            if created:
                counts["film_records"] += 1
            Event.objects.filter(name=data["title"], film__isnull=True).update(film=film)

    def _make_poster_image(self, event_name, bg_colour, width=600, height=900):
        from toolkit.diary.poster import make_poster_image
        return make_poster_image(event_name, bg_colour, width=width, height=height)

    def _make_event_image(self, event, colour, event_name="Event", image_url=None, image_path=None, auto_crop=None):
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

            # auto_crop: select a 2:3 vertical slice from landscape/square source images,
            # simulating a volunteer choosing which part of a wide image to show.
            if auto_crop and (image_url or image_path):
                orig_w, orig_h = img.size
                target_ratio = 2 / 3
                if orig_w / orig_h > target_ratio + 0.05:  # wider than 2:3
                    crop_h_px = orig_h
                    crop_w_px = min(int(orig_h * target_ratio), orig_w)
                    if auto_crop == "left":
                        crop_x_px = 0
                    elif auto_crop == "right":
                        crop_x_px = orig_w - crop_w_px
                    else:  # center
                        crop_x_px = (orig_w - crop_w_px) // 2
                    media_item.crop_x = round(crop_x_px / orig_w, 6)
                    media_item.crop_y = 0.0
                    media_item.crop_w = round(crop_w_px / orig_w, 6)
                    media_item.crop_h = 1.0
                    media_item.save(update_fields=["crop_x", "crop_y", "crop_w", "crop_h"])

            event.media.add(media_item)
            return media_item
        except Exception as e:
            self.stderr.write(f"Warning: could not create image for {event_name}: {e}")
            return None
