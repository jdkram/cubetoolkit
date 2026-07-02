import zoneinfo
from datetime import datetime, date, timedelta

from django.test import TestCase

import django.db
from django.core.exceptions import ValidationError
from toolkit.diary.models import (
    Showing,
    Event,
    EventBudgetLine,
    PrintedProgramme,
    EventTag,
    Role,
    Room,
    RoomBooking,
    SiteConfiguration,
    get_site_config,
    sync_budget_lines_for_event,
)

from .common import DiaryTestsMixin, NowPatchMixin

UTC = zoneinfo.ZoneInfo("UTC")


class ShowingModelSave(DiaryTestsMixin, NowPatchMixin, TestCase):
    def test_can_save_future_showing(self):
        self.e4s3.save()

    def test_can_amend_future_showing(self):
        self.e4s3.start = self._fake_now + timedelta(days=1)
        self.e4s3.save()

    def test_cannot_save_historic_showing(self):
        with self.assertRaisesMessage(
            django.db.utils.IntegrityError,
            "Can't update showings that start in the past",
        ):
            self.e2s1.save()

    def test_cannot_move_date_of_historic_showing(self):
        self.e2s1.start = self._fake_now + timedelta(days=1)
        with self.assertRaisesMessage(
            django.db.utils.IntegrityError,
            "Can't update showings that start in the past",
        ):
            self.e2s1.save()

    def test_cannot_move_showing_into_past(self):
        self.e4s3.start = self._fake_now - timedelta(days=1)
        with self.assertRaisesMessage(
            django.db.utils.IntegrityError,
            "Can't update showings that start in the past",
        ):
            self.e4s3.save()


class ShowingModelDelete(DiaryTestsMixin, NowPatchMixin, TestCase):
    def test_can_delete_future_showing(self):
        self.e4s3.delete()

    def test_cannot_delete_historic_showing(self):
        with self.assertRaisesMessage(
            django.db.utils.IntegrityError,
            "Can't delete showings that start in the past",
        ):
            self.e2s1.delete()

    def test_cannot_move_date_of_historic_showing_to_delete(self):
        self.e2s1.start = self._fake_now + timedelta(days=1)
        with self.assertRaisesMessage(
            django.db.utils.IntegrityError,
            "Can't delete showings that start in the past",
        ):
            self.e2s1.delete()

    def test_delete_unsaved_instance(self):
        s = Showing()
        with self.assertRaises(ValueError):
            s.delete()


class ShowingModelMethods(DiaryTestsMixin, NowPatchMixin, TestCase):
    def test_in_past_when_future(self):
        self.assertFalse(self.e4s3.in_past())

    def test_in_past_when_past(self):
        self.assertTrue(self.e2s1.in_past())

    def test_in_past_new_instance(self):
        s = Showing()
        self.assertFalse(s.in_past())

    def test_clone_rota_from_showing_copies_rota_notes(self):
        """clone_rota_from_showing should copy rota_notes from the source."""
        source = self.e4s3  # has rota_notes="Some notes about the Rota!"
        self.assertTrue(source.rota_notes)  # ensure fixture has notes

        dest = Showing(
            event=source.event,
            start=source.start + timedelta(days=7),
            booked_by="Test",
        )
        dest.save()
        dest.clone_rota_from_showing(source)

        dest.refresh_from_db()
        self.assertEqual(dest.rota_notes, source.rota_notes)


class ShowingModelCustomQueryset(DiaryTestsMixin, TestCase):
    def test_manager_public(self):
        records = list(Showing.objects.public())
        # From the fixtures, there are 4 showings that are confirmed and not
        # private / hidden
        self.assertEqual(len(records), 4)
        for showing in records:
            self.assertTrue(showing.confirmed)
            self.assertFalse(showing.hide_in_programme)
            self.assertFalse(showing.event.private)

    def test_queryset_public(self):
        # Difference here is that we get a queryset, then use the public()
        # method on that (rather than using the public() method directly on
        # the manager)
        records = list(Showing.objects.all().public())
        # From the fixtures, there are 4 showings that are confirmed and not
        # private / hidden
        self.assertEqual(len(records), 4)
        for showing in records:
            self.assertTrue(showing.confirmed)
            self.assertFalse(showing.hide_in_programme)
            self.assertFalse(showing.event.private)

    def test_manager_not_cancelled(self):
        records = list(Showing.objects.not_cancelled())
        # From the fixtures, there are 7 showings that aren't cancelled
        self.assertEqual(len(records), 9)
        for showing in records:
            self.assertFalse(showing.cancelled)

    def test_manager_confirmed(self):
        records = list(Showing.objects.confirmed())
        # From the fixtures, there are 7 showings that are confirmed:
        self.assertEqual(len(records), 8)
        for showing in records:
            self.assertTrue(showing.confirmed)

    def test_manager_date_range(self):
        start = datetime(2013, 4, 2, 12, 0, tzinfo=UTC)
        end = datetime(2013, 4, 4, 12, 0, tzinfo=UTC)
        records = list(Showing.objects.start_in_range(start, end))
        # Expect 2 showings in this date range:
        self.assertEqual(len(records), 2)
        for showing in records:
            self.assertTrue(showing.start < end)
            self.assertTrue(showing.start > start)

    def test_queryset_chaining(self):
        start = datetime(2000, 4, 2, 12, 0, tzinfo=UTC)
        end = datetime(2013, 9, 1, 12, 0, tzinfo=UTC)
        records = list(
            Showing.objects.all()
            .public()
            .not_cancelled()
            .start_in_range(start, end)
            .confirmed()
        )
        self.assertEqual(len(records), 3)
        for showing in records:
            self.assertTrue(showing.confirmed)
            self.assertFalse(showing.hide_in_programme)
            self.assertFalse(showing.event.private)
            self.assertFalse(showing.cancelled)
            self.assertTrue(showing.start < end)
            self.assertTrue(showing.start > start)
            self.assertTrue(showing.confirmed)


class EventModelNonLegacyCopy(TestCase):
    def setUp(self):
        self.sample_copy = (
            "<p>Simple &amp; tidy HTML/unicode \u00a9\u014dpy\n</p>\n"
            "<p>With a <a href='http://example.com/foo/'>link!</a>"
            "<p>And another! <a href='https://example.com/bar/'>link!</a>"
            " and some equivalent things; &pound; &#163; \u00a3<br></p>"
        )
        self.event = Event(
            name="Test event", legacy_copy=False, copy=self.sample_copy
        )
        self.event.save()

    def test_simple(self):
        # Test copy goes in and out without being mangled
        reloaded = Event.objects.get(id=self.event.pk)
        self.assertEqual(reloaded.copy, self.sample_copy)

    def test_html_copy(self):
        # nh3 sanitization normalises attribute quotes, adds rel="noopener
        # noreferrer" to links, and decodes unnecessary HTML entities.
        expected = (
            "<p>Simple &amp; tidy HTML/unicode \u00a9\u014dpy\n</p>\n"
            '<p>With a <a href="http://example.com/foo/" rel="noopener noreferrer">link!</a></p>'
            '<p>And another! <a href="https://example.com/bar/" rel="noopener noreferrer">link!</a>'
            " and some equivalent things; \u00a3 \u00a3 \u00a3<br></p>"
        )
        self.assertEqual(self.event.copy_html, expected)


class EventModelLegacyCopy(TestCase):
    def setUp(self):
        self.sample_copy = (
            "Simple &amp; tidy legacy \u00a9\u014dpy\n\n"
            "With an unardorned link: http://example.com/foo/"
            " https://example.com/foo/"
            " and some equivalent things; &pound; &#163; \u00a3..."
            " and <this> \"'<troublemaker>'\""
        )
        self.event = Event(
            name="Test event", legacy_copy=True, copy=self.sample_copy
        )
        self.event.save()

    def test_simple(self):
        # Test copy goes in and out without being mangled
        reloaded = Event.objects.get(id=self.event.pk)
        self.assertEqual(reloaded.copy, self.sample_copy)

    def test_html_copy(self):
        # nh3 sanitization: adds rel="noopener noreferrer" to links, decodes
        # unnecessary HTML entities (&pound; -> £), and strips unknown tags
        # (<this>, <troublemaker>) while keeping their text content.
        expected = (
            "Simple &amp; tidy legacy \u00a9\u014dpy <br><br>"
            "With an unardorned link: "
            '<a href="http://example.com/foo/" rel="noopener noreferrer">http://example.com/foo/</a>'
            ' <a href="https://example.com/foo/" rel="noopener noreferrer">https://example.com/foo/</a>'
            " and some equivalent things; \u00a3 \u00a3 \u00a3..."
            " and  \"''\""
        )
        self.assertEqual(self.event.copy_html, expected)


class PrintedProgrammeModelTests(TestCase):
    def test_month_ok(self):
        pp = PrintedProgramme(programme="/foo/bar", month=date(2010, 2, 1))
        pp.save()

        pp = PrintedProgramme.objects.get(pk=pp.pk)
        self.assertEqual(pp.month, date(2010, 2, 1))

    def test_month_normalised(self):
        pp = PrintedProgramme(programme="/foo/bar", month=date(2010, 2, 2))
        pp.save()

        pp = PrintedProgramme.objects.get(pk=pp.pk)
        self.assertEqual(pp.month, date(2010, 2, 1))


class EventPricingFromTemplate(DiaryTestsMixin, TestCase):
    def test_set_pricing_from_template(self):
        # No pricing specified when creating the event, and pricing specified
        # in the template:
        new_event = Event(
            name="Event Title",
            template=self.tmpl1,
        )
        self.assertEqual(new_event.pricing, "Entry: \u00a35 / \u20ac10")
        new_event.save()
        self.assertEqual(new_event.pricing, "Entry: \u00a35 / \u20ac10")

    def test_dont_set_pricing_from_template(self):
        # Pricing specified when creating the event, and pricing specified in
        # the template:
        new_event = Event(
            name="Event Title",
            pricing="Actual pricing",
            template=self.tmpl1,
        )
        self.assertEqual(new_event.pricing, "Actual pricing")
        new_event.save()
        self.assertEqual(new_event.pricing, "Actual pricing")

    def test_cant_set_pricing_from_template(self):
        # Pricing specified when creating the event, and no pricing specified
        # in the template:
        new_event = Event(
            name="Event Title",
            pricing="Actual pricing",
            template=self.tmpl3,
        )
        self.assertEqual(new_event.pricing, "Actual pricing")
        new_event.save()
        self.assertEqual(new_event.pricing, "Actual pricing")

    def test_set_from_template_no_pricing(self):
        # No pricing specified when creating the event, and no pricing
        # specified in the template:
        new_event = Event(
            name="Event Title",
            template=self.tmpl3,
        )
        self.assertEqual(new_event.pricing, "")
        new_event.save()
        self.assertEqual(new_event.pricing, "")

    def test_no_template(self):
        # Pricing specified when creating the event, and no pricing specified
        # in the template:
        new_event = Event(
            name="Event Title",
            pricing="Actual pricing",
        )
        self.assertEqual(new_event.pricing, "Actual pricing")
        new_event.save()
        self.assertEqual(new_event.pricing, "Actual pricing")


class EventTagsFromTemplate(DiaryTestsMixin, TestCase):
    def test_set_one_tag_from_template(self):
        new_event = Event(
            name="Event Title",
            template=self.tmpl1,
        )
        new_event.save()
        # Tags shouldn't have been set yet:
        self.assertEqual(new_event.tags.count(), 0)

        new_event.reset_tags_to_default()

        self.assertEqual(new_event.tags.count(), 1)
        self.assertEqual(new_event.tags.all()[0].name, "tag one")
        self.assertEqual(new_event.tags.all()[0].slug, "tag-one")

    def test_set_two_tags_from_template(self):
        new_event = Event(
            name="Event Title",
            template=self.tmpl2,
        )
        new_event.save()
        # Tags shouldn't have been set yet:
        self.assertEqual(new_event.tags.count(), 0)

        new_event.reset_tags_to_default()

        self.assertEqual(new_event.tags.count(), 2)
        self.assertEqual(new_event.tags.all()[0].name, "tag one")
        self.assertEqual(new_event.tags.all()[0].slug, "tag-one")
        self.assertEqual(new_event.tags.all()[1].name, "tag three")
        self.assertEqual(new_event.tags.all()[1].slug, "tag-three")

    def test_set_no_tags_from_template(self):
        new_event = Event(
            name="Event Title",
            template=self.tmpl3,
        )
        new_event.save()
        # Tags shouldn't have been set yet:
        self.assertEqual(new_event.tags.count(), 0)

        new_event.reset_tags_to_default()

        # Still no tags
        self.assertEqual(new_event.tags.count(), 0)

    def test_set_tags_no_template(self):
        # No template set, call reset_tags
        new_event = Event(
            name="Event Title",
        )
        new_event.save()
        self.assertEqual(new_event.tags.count(), 0)

        new_event.reset_tags_to_default()

        self.assertEqual(new_event.tags.count(), 0)


class EventTagTests(TestCase):
    def test_can_delete_not_readonly(self):
        tag = EventTag(name="test", slug="test", read_only=False)
        tag.save()
        pk = tag.pk

        tag.delete()

        self.assertEqual(EventTag.objects.filter(id=pk).count(), 0)

    def test_cant_delete_readonly(self):
        tag = EventTag(name="test", slug="test", read_only=True)
        tag.save()
        pk = tag.pk

        tag.delete()

        self.assertEqual(EventTag.objects.filter(id=pk).count(), 1)
        tag = EventTag.objects.get(id=pk)
        self.assertEqual(tag.name, "test")

    def test_can_edit_not_readonly(self):
        tag = EventTag(name="test", slug="test", read_only=False)
        tag.save()
        pk = tag.pk
        # Try to edit:
        tag.name = "crispin"
        tag.sort_order = 0xBAD
        tag.save()

        tag = EventTag.objects.get(id=pk)
        self.assertEqual(tag.name, "crispin")
        self.assertEqual(tag.sort_order, 0xBAD)

    def test_can_change_to_readonly(self):
        tag = EventTag(name="test", slug="test", read_only=False)
        tag.save()
        pk = tag.pk

        tag = EventTag.objects.get(id=pk)
        self.assertFalse(tag.read_only)

        tag.read_only = True
        tag.save()

        tag = EventTag.objects.get(id=pk)
        self.assertTrue(tag.read_only)

        tag.name = "crispin"
        self.assertFalse(tag.save())

    def test_cant_edit_most_of_readonly(self):
        tag = EventTag(name="test", slug="test", read_only=True)
        tag.save()
        pk = tag.pk
        # Try to edit:
        tag.name = "crispin"
        tag.slug = "bert"
        tag.read_only = False
        self.assertFalse(tag.save())

        tag = EventTag.objects.get(id=pk)
        # Things shouldn't change:
        self.assertEqual(tag.name, "test")
        self.assertEqual(tag.slug, "test")
        self.assertEqual(tag.promoted, False)
        self.assertEqual(tag.read_only, True)

    def test_can_edit_readonly_promotion(self):
        tag = EventTag(
            name="test",
            slug="test",
            read_only=True,
            sort_order=1,
            promoted=False,
        )
        tag.save()
        pk = tag.pk
        # Try to edit:
        tag.name = "crispin"
        tag.promoted = True
        tag.read_only = False
        tag.sort_order = 0xF00BA
        self.assertFalse(tag.save())

        tag = EventTag.objects.get(id=pk)
        # Most things shouldn't change:
        self.assertEqual(tag.name, "test")
        self.assertEqual(tag.slug, "test")
        self.assertEqual(tag.read_only, True)
        # Promoted and sort values should:
        self.assertEqual(tag.promoted, True)
        self.assertEqual(tag.sort_order, 0xF00BA)

    def test_clean_case(self):
        tag = EventTag(name="BIGlettersHERE")
        tag.clean()
        self.assertEqual(tag.name, "biglettershere")
        self.assertEqual(tag.slug, "biglettershere")

    def test_slugify(self):
        tag = EventTag(name="with space", slug="")
        tag.clean()
        self.assertEqual(tag.name, "with space")
        self.assertEqual(tag.slug, "with-space")

        tag = EventTag(name="with&ampersand")
        tag.clean()
        self.assertEqual(tag.name, "with&ampersand")
        self.assertEqual(tag.slug, "withampersand")

        tag = EventTag(name="with?questionmark")
        tag.clean()
        self.assertEqual(tag.name, "with?questionmark")
        self.assertEqual(tag.slug, "withquestionmark")

        tag = EventTag(name="with#hash")
        tag.clean()
        self.assertEqual(tag.name, "with#hash")
        self.assertEqual(tag.slug, "withhash")

    def test_reject_blank(self):
        tag = EventTag(name="")
        self.assertRaises(ValidationError, tag.full_clean)

    def test_must_be_unique(self):
        t1 = EventTag(name="jim", slug="jim")
        t1.save()

        t2 = EventTag(name="jim!", slug="jim")
        self.assertRaises(django.db.IntegrityError, t2.save)


class RoleTests(TestCase):
    def test_can_delete_not_readonly(self):
        role = Role(name="Role One")
        role.save()
        pk = role.pk

        role.delete()

        self.assertEqual(Role.objects.filter(id=pk).count(), 0)

    def test_cant_delete_readonly(self):
        role = Role(name="Role One", read_only=True)
        role.save()
        pk = role.pk

        role.delete()
        self.assertEqual(Role.objects.filter(id=pk).count(), 1)

        role_re = Role.objects.get(id=pk)
        self.assertEqual(role_re.name, "Role One")

    def test_can_edit_not_readonly(self):
        role = Role(name="Role One")
        role.save()
        pk = role.pk

        # Try to edit:
        role.name = "Some other thing"
        role.save()

        role = Role.objects.get(id=pk)
        self.assertEqual(role.name, "Some other thing")

    def test_can_change_to_readonly(self):
        role = Role(name="Role One", read_only=False)
        role.save()
        pk = role.pk

        role = Role.objects.get(id=pk)
        self.assertFalse(role.read_only)

        role.read_only = True
        role.save()

        role = Role.objects.get(id=pk)
        self.assertTrue(role.read_only)

        role.name = "Whatever"
        self.assertFalse(role.save())

    def test_cannot_change_from_readonly(self):
        role = Role(name="Role One", read_only=True, standard=False)
        role.save()
        pk = role.pk

        role = Role.objects.get(id=pk)
        role.read_only = False
        role.standard = True
        role.save()

        role = Role.objects.get(id=pk)
        self.assertEqual(role.name, "Role One")
        self.assertEqual(role.read_only, True)
        # Can only chang role.standard if nothing else is fiddled with
        # (i.e. atomic?)
        self.assertEqual(role.standard, False)

    def test_cannot_change_name_when_readonly(self):
        role = Role(name="Role One", read_only=True, standard=False)
        role.save()
        pk = role.pk

        role = Role.objects.get(id=pk)
        role.name = "Rick"
        role.save()

        role = Role.objects.get(id=pk)
        self.assertEqual(role.name, "Role One")
        self.assertEqual(role.read_only, True)
        self.assertEqual(role.standard, False)

    def test_can_change_standard_when_readonly(self):
        role = Role(name="Role One", read_only=True, standard=False)
        role.save()
        pk = role.pk

        role = Role.objects.get(id=pk)
        role.standard = True
        role.save()

        role = Role.objects.get(id=pk)
        self.assertEqual(role.name, "Role One")
        self.assertEqual(role.read_only, True)
        self.assertEqual(role.standard, True)

    def test_cant_edit_readonly_name(self):
        role = Role(name="Role One", read_only=True)
        role.save()
        pk = role.pk
        # Try to edit:
        role.name = "Not a womble"
        self.assertFalse(role.save())

        role = Role.objects.get(id=pk)
        self.assertEqual(role.name, "Role One")

    def test_cant_unprotect_readonly_role(self):
        role = Role(name="Role One", read_only=True)
        role.save()
        pk = role.pk

        role = Role.objects.get(id=pk)
        role.read_only = False
        role.save()

        role = Role.objects.get(id=pk)
        self.assertTrue(role.read_only)

    def test_reject_blank(self):
        role = Role(name="")
        self.assertRaises(ValidationError, role.full_clean)

    def test_must_be_unique(self):
        r1 = Role(name="Roller")
        r1.save()

        r2 = Role(name="Roller")
        self.assertRaises(django.db.IntegrityError, r2.save)


class RoomBookingModelTests(TestCase):
    def setUp(self):
        self.room_a = Room.objects.create(name="Cinema", colour="#CC2200")
        self.room_b = Room.objects.create(name="Café", colour="#FFD700")
        self.event = Event.objects.create(name="Test Event", duration="02:00:00")
        self.showing = Showing.objects.create(
            event=self.event,
            start=datetime(2026, 6, 1, 19, 0, tzinfo=zoneinfo.ZoneInfo("UTC")),
            booked_by="Tester",
            confirmed=True,
        )

    def _make_booking(self, room, start_offset_hours=0, end_offset_hours=None):
        base = datetime(2026, 6, 1, 19, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))
        start = base + timedelta(hours=start_offset_hours)
        end = base + timedelta(hours=end_offset_hours) if end_offset_hours is not None else None
        return RoomBooking.objects.create(showing=self.showing, room=room, start=start, end=end)

    def test_primary_room_returns_first_by_start(self):
        self._make_booking(self.room_b, start_offset_hours=1)
        self._make_booking(self.room_a, start_offset_hours=0)
        self.assertEqual(self.showing.primary_room, self.room_a)

    def test_primary_room_returns_none_when_no_bookings(self):
        self.assertIsNone(self.showing.primary_room)

    def test_rooms_display_single(self):
        self._make_booking(self.room_a)
        self.assertEqual(self.showing.rooms_display, "Cinema")

    def test_rooms_display_multiple_ordered_by_start(self):
        self._make_booking(self.room_b, start_offset_hours=1)
        self._make_booking(self.room_a, start_offset_hours=0)
        self.assertEqual(self.showing.rooms_display, "Cinema, Café")

    def test_rooms_display_empty_when_no_bookings(self):
        self.assertEqual(self.showing.rooms_display, "")

    def test_str(self):
        rb = self._make_booking(self.room_a)
        self.assertIn("Cinema", str(rb))


class ClashDetectionTests(TestCase):
    def setUp(self):
        self.room = Room.objects.create(name="Cinema", colour="#CC2200")
        self.other_room = Room.objects.create(name="Café", colour="#FFD700")
        self.event = Event.objects.create(name="Test Event", duration="02:00:00")
        UTC = zoneinfo.ZoneInfo("UTC")

        self.showing_a = Showing.objects.create(
            event=self.event,
            start=datetime(2026, 6, 1, 19, 0, tzinfo=UTC),
            booked_by="A",
            confirmed=True,
        )
        self.showing_b = Showing.objects.create(
            event=self.event,
            start=datetime(2026, 6, 1, 20, 0, tzinfo=UTC),
            booked_by="B",
            confirmed=True,
        )
        self.UTC = UTC

    def _book(self, showing, room, start_hour, end_hour=None):
        UTC = self.UTC
        start = datetime(2026, 6, 1, start_hour, 0, tzinfo=UTC)
        end = datetime(2026, 6, 1, end_hour, 0, tzinfo=UTC) if end_hour else None
        return RoomBooking.objects.create(showing=showing, room=room, start=start, end=end)

    def test_overlapping_bookings_detected(self):
        from toolkit.diary.clash import find_clashes
        rb_a = self._book(self.showing_a, self.room, 19, 21)
        rb_b = self._book(self.showing_b, self.room, 20, 22)
        clashes = find_clashes(rb_b)
        self.assertIn(rb_a, clashes)

    def test_non_overlapping_bookings_not_detected(self):
        from toolkit.diary.clash import find_clashes
        rb_a = self._book(self.showing_a, self.room, 19, 20)
        rb_b = self._book(self.showing_b, self.room, 20, 22)
        clashes = find_clashes(rb_b)
        self.assertNotIn(rb_a, clashes)

    def test_self_excluded_from_clashes(self):
        from toolkit.diary.clash import find_clashes
        rb = self._book(self.showing_a, self.room, 19, 21)
        clashes = find_clashes(rb)
        self.assertNotIn(rb, clashes)

    def test_different_room_not_flagged(self):
        from toolkit.diary.clash import find_clashes
        rb_a = self._book(self.showing_a, self.other_room, 19, 21)
        rb_b = self._book(self.showing_b, self.room, 19, 21)
        clashes = find_clashes(rb_b)
        self.assertNotIn(rb_a, clashes)

    def test_unconfirmed_showing_not_flagged(self):
        from toolkit.diary.clash import find_clashes
        unconfirmed = Showing.objects.create(
            event=self.event,
            start=datetime(2026, 6, 1, 19, 0, tzinfo=self.UTC),
            booked_by="U",
            confirmed=False,
        )
        rb_a = self._book(unconfirmed, self.room, 19, 21)
        rb_b = self._book(self.showing_b, self.room, 19, 21)
        clashes = find_clashes(rb_b)
        self.assertNotIn(rb_a, clashes)

    def test_open_ended_existing_booking_treated_as_clash(self):
        from toolkit.diary.clash import find_clashes
        rb_a = self._book(self.showing_a, self.room, 19)  # no end — open-ended
        rb_b = self._book(self.showing_b, self.room, 20, 22)
        clashes = find_clashes(rb_b)
        self.assertIn(rb_a, clashes)


class AgeRestrictionDisplayTests(TestCase):
    def setUp(self):
        cfg = SiteConfiguration.load()
        cfg.age_rating_choices = [
            {"value": "U", "label": "U — Universal"},
            {"value": "15", "label": "15"},
            {"value": "18", "label": "18"},
        ]
        cfg.save()

    def tearDown(self):
        # Reset so other test classes pick up a clean config.
        SiteConfiguration.objects.all().delete()

    def _event(self, value):
        e = Event(name="Test", age_restriction=value)
        e.save()
        return e

    def test_blank_returns_empty_string(self):
        e = self._event("")
        self.assertEqual(e.get_age_restriction_display(), "")

    def test_site_config_label_returned(self):
        e = self._event("15")
        self.assertEqual(e.get_age_restriction_display(), "15")

    def test_site_config_full_label_returned(self):
        e = self._event("U")
        self.assertEqual(e.get_age_restriction_display(), "U — Universal")

    def test_legacy_all_ages_falls_back(self):
        e = self._event("all_ages")
        self.assertEqual(e.get_age_restriction_display(), "All ages welcome")

    def test_legacy_18_plus_falls_back(self):
        e = self._event("18_plus")
        self.assertEqual(e.get_age_restriction_display(), "18+ only")

    def test_unknown_value_returns_raw(self):
        e = self._event("FSK 16")
        self.assertEqual(e.get_age_restriction_display(), "FSK 16")


class EventBudgetLineSyncTests(TestCase):
    """sync_budget_lines_for_event(): row auto-creation and derivation (9.149)."""

    def tearDown(self):
        SiteConfiguration.objects.all().delete()

    def _event(self, **kwargs):
        e = Event(name="Test event", **kwargs)
        e.save()
        return e

    def test_untagged_event_gets_other_public_event_template(self):
        event = self._event()
        sync_budget_lines_for_event(event)
        categories = set(
            event.budget_lines.filter(
                direction=EventBudgetLine.DIRECTION_OUTGOING
            ).values_list("category", flat=True)
        )
        self.assertIn("Cafe & bar", categories)
        self.assertNotIn("Programming", categories)  # film-only category

    def test_film_tagged_event_gets_film_template(self):
        EventTag(name="film", slug="film").save()
        event = self._event()
        event.tags.set([EventTag.objects.get(slug="film")])
        sync_budget_lines_for_event(event)
        categories = set(
            event.budget_lines.filter(
                direction=EventBudgetLine.DIRECTION_OUTGOING
            ).values_list("category", flat=True)
        )
        self.assertIn("Programming", categories)
        self.assertNotIn("Acts/ Performers", categories)

    def test_music_filter_group_tagged_event_gets_music_gig_template(self):
        EventTag(name="music", slug="music", filter_group="music").save()
        event = self._event()
        event.tags.set([EventTag.objects.get(slug="music")])
        sync_budget_lines_for_event(event)
        categories = set(
            event.budget_lines.filter(
                direction=EventBudgetLine.DIRECTION_OUTGOING
            ).values_list("category", flat=True)
        )
        self.assertIn("Fees", categories)
        self.assertIn("Acts/ Performers", categories)

    def test_income_category_always_created(self):
        event = self._event()
        sync_budget_lines_for_event(event)
        self.assertTrue(
            event.budget_lines.filter(
                direction=EventBudgetLine.DIRECTION_INCOME,
                category="Ticket sales",
            ).exists()
        )

    def test_sync_is_idempotent(self):
        event = self._event()
        sync_budget_lines_for_event(event)
        count_after_first = event.budget_lines.count()
        sync_budget_lines_for_event(event)
        self.assertEqual(event.budget_lines.count(), count_after_first)

    def test_hire_fee_derived_from_deal_terms(self):
        event = self._event(
            cost_type=Event.COST_TYPE_PERFORMER_FEE,
            cost_total_gbp="150.00",
        )
        EventTag(name="music", slug="music", filter_group="music").save()
        event.tags.set([EventTag.objects.get(slug="music")])
        sync_budget_lines_for_event(event)
        line = event.budget_lines.get(
            category="Acts/ Performers", item="Hire fee"
        )
        self.assertEqual(str(line.estimate_gbp), "150.00")
        self.assertEqual(line.estimate_source, EventBudgetLine.SOURCE_DEAL_TERMS)

    def test_manual_override_survives_resync_even_if_source_changes(self):
        event = self._event(
            cost_type=Event.COST_TYPE_PERFORMER_FEE,
            cost_total_gbp="150.00",
        )
        EventTag(name="music", slug="music", filter_group="music").save()
        event.tags.set([EventTag.objects.get(slug="music")])
        sync_budget_lines_for_event(event)
        line = event.budget_lines.get(
            category="Acts/ Performers", item="Hire fee"
        )
        line.estimate_gbp = "200.00"
        line.estimate_source = EventBudgetLine.SOURCE_MANUAL
        line.save()

        event.cost_total_gbp = "999.00"
        event.save()
        sync_budget_lines_for_event(event)

        line.refresh_from_db()
        self.assertEqual(str(line.estimate_gbp), "200.00")

    def test_derived_row_updates_when_source_value_changes(self):
        event = self._event(
            cost_type=Event.COST_TYPE_PERFORMER_FEE,
            cost_total_gbp="150.00",
        )
        EventTag(name="music", slug="music", filter_group="music").save()
        event.tags.set([EventTag.objects.get(slug="music")])
        sync_budget_lines_for_event(event)

        event.cost_total_gbp = "999.00"
        event.save()
        sync_budget_lines_for_event(event)

        line = event.budget_lines.get(
            category="Acts/ Performers", item="Hire fee"
        )
        self.assertEqual(str(line.estimate_gbp), "999.00")

    def test_late_licence_fee_derived_from_site_default(self):
        cfg = get_site_config()
        cfg.late_licence_fee_gbp = "75.00"
        cfg.save()
        EventTag(name="music", slug="music", filter_group="music").save()
        event = self._event()
        event.tags.set([EventTag.objects.get(slug="music")])
        sync_budget_lines_for_event(event)
        line = event.budget_lines.get(
            category="Fees", item="Late night licence"
        )
        self.assertEqual(str(line.estimate_gbp), "75.00")
        self.assertEqual(line.estimate_source, EventBudgetLine.SOURCE_SITE_DEFAULT)

    def test_retagging_adds_new_rows_without_deleting_old(self):
        EventTag(name="film", slug="film").save()
        EventTag(name="music", slug="music", filter_group="music").save()
        event = self._event()
        event.tags.set([EventTag.objects.get(slug="film")])
        sync_budget_lines_for_event(event)
        film_line = event.budget_lines.get(
            category="Programming", item="Licence"
        )
        film_line.actual_gbp = "42.00"
        film_line.save()

        event.tags.set([EventTag.objects.get(slug="music")])
        sync_budget_lines_for_event(event)

        film_line.refresh_from_db()
        self.assertEqual(str(film_line.actual_gbp), "42.00")
        self.assertTrue(
            event.budget_lines.filter(
                category="Acts/ Performers", item="Hire fee"
            ).exists()
        )

    def test_ad_hoc_item_not_touched_by_sync(self):
        event = self._event()
        sync_budget_lines_for_event(event)
        adhoc = EventBudgetLine.objects.create(
            event=event,
            direction=EventBudgetLine.DIRECTION_OUTGOING,
            category="Misc.",
            item="Skip hire",
            estimate_gbp="60.00",
            estimate_source=EventBudgetLine.SOURCE_MANUAL,
            order=999,
        )
        sync_budget_lines_for_event(event)
        adhoc.refresh_from_db()
        self.assertEqual(str(adhoc.estimate_gbp), "60.00")

    def test_ordering(self):
        event = self._event()
        sync_budget_lines_for_event(event)
        lines = list(event.budget_lines.all())
        directions = [line.direction for line in lines]
        # All outgoing rows sort before incoming (Meta.ordering =
        # ["direction", "order", "pk"], and "incoming" > "outgoing" alphabetically).
        self.assertEqual(
            directions,
            sorted(directions),
        )
