from django.test import TestCase, override_settings
from django.urls import reverse

from toolkit.diary.forms import SiteConfigurationForm
from toolkit.diary.models import EventTag, SiteConfiguration, get_site_config
from toolkit.diary.tests.common import DiaryTestsMixin


class SiteConfigurationModelTests(DiaryTestsMixin, TestCase):
    def test_load_creates_singleton_on_first_call(self):
        SiteConfiguration.objects.all().delete()
        # Ensure a stale cached copy from another test doesn't hide the bug
        from django.core.cache import cache

        cache.delete(SiteConfiguration._CACHE_KEY)

        config = get_site_config()

        self.assertEqual(config.pk, 1)
        self.assertEqual(SiteConfiguration.objects.count(), 1)

    def test_subsequent_load_returns_same_singleton(self):
        first = get_site_config()
        first.max_count_per_role = 42
        first.save()

        second = get_site_config()
        self.assertEqual(second.pk, 1)
        self.assertEqual(second.max_count_per_role, 42)
        self.assertEqual(SiteConfiguration.objects.count(), 1)

    def test_save_always_uses_pk_one(self):
        config = SiteConfiguration(pk=99, max_count_per_role=12)
        config.save()
        self.assertEqual(config.pk, 1)

    def test_delete_is_a_noop(self):
        config = get_site_config()
        config.delete()
        self.assertTrue(SiteConfiguration.objects.filter(pk=1).exists())


class SiteConfigurationViewTests(DiaryTestsMixin, TestCase):
    url = property(lambda self: reverse("edit-site-configuration"))

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.url)

    def test_volunteer_forbidden(self):
        self.client.login(username="rota_editor", password="T3stPassword!3")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_programmer_forbidden(self):
        self.client.login(username="read_only", password="T3stPassword!1")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_panopticon_can_get_form(self):
        self.client.login(username="admin", password="T3stPassword!")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Site configuration")
        self.assertContains(response, "max_count_per_role")

    def test_panopticon_can_save_changes(self):
        self.client.login(username="admin", password="T3stPassword!")
        config = get_site_config()
        post_data = {
            "films_start_on_time": "on",
            "films_start_on_time_banner_text": "Films start at the listed time.",
            "rota_show_tags": "on",
            "rota_clear_email_prompt_enabled": "on",
            "rota_clear_email_prompt_text": config.rota_clear_email_prompt_text,
            "vols_email": "",
            "show_archive_images": "on",
            "images_start_date": "",
            "occurrence_noun": config.occurrence_noun,
            "occurrence_noun_plural": config.occurrence_noun_plural,
            "confirm_label": config.confirm_label,
            "breakeven_guidance_note": "",
            "breakeven_fc_standard_threshold": str(
                config.breakeven_fc_standard_threshold
            ),
            "breakeven_fc_music_threshold": str(config.breakeven_fc_music_threshold),
            "max_count_per_role": "20",
            "max_showing_dates_shown": str(config.max_showing_dates_shown),
            "programme_copy_summary_max_chars": str(
                config.programme_copy_summary_max_chars
            ),
            "programme_event_terms_min_words": str(
                config.programme_event_terms_min_words
            ),
            "programme_media_max_size_mb": str(config.programme_media_max_size_mb),
            "thumbnail_crop_width": str(config.thumbnail_crop_width),
            "thumbnail_crop_height": str(config.thumbnail_crop_height),
            "programme_accent_colour": config.programme_accent_colour,
            "mailout_details_days_ahead": str(config.mailout_details_days_ahead),
            "mailout_listings_days_ahead": str(config.mailout_listings_days_ahead),
            "calendar_slot_min_hour": str(config.calendar_slot_min_hour),
            "membership_length_days": str(config.membership_length_days),
            "default_training_expiry_months": str(
                config.default_training_expiry_months
            ),
            "general_training_enabled": "on",
            "volunteer_dormancy_days": str(config.volunteer_dormancy_days),
            "volunteer_never_logged_in_grace_days": str(
                config.volunteer_never_logged_in_grace_days
            ),
            "volunteer_purge_days": str(config.volunteer_purge_days),
            "volunteer_digest_day": str(config.volunteer_digest_day),
            "last_gasp_email_subject": "",
            "last_gasp_email_body": "",
            "last_gasp_cooldown_days": str(config.last_gasp_cooldown_days),
            "rota_gap_min_missing": str(config.rota_gap_min_missing),
            "rota_gap_min_pct": str(config.rota_gap_min_pct),
            "programming_min_event_shifts": str(config.programming_min_event_shifts),
            "stats_training_tag_slugs": [],  # MultipleChoiceField; empty = no tags excluded
            "image_copyright_guidance_url": "",
            "alt_text_guidance_url": "",
            "access_rider_guidance_url": "",
            "ticket_link_guidance_html": "",
            "film_programming_guide_url": "",
            "lost_and_found_retain_days": str(config.lost_and_found_retain_days),
            "bulletin_default_expiry_days": str(config.bulletin_default_expiry_days),
            "bulletin_guidance": "",
            "bulletin_post_permission": config.bulletin_post_permission,
            "perm_diary_read": config.perm_diary_read,
            "perm_diary_calendar": config.perm_diary_calendar,
            "perm_programming_queue_read": config.perm_programming_queue_read,
            "perm_programming_queue_write": config.perm_programming_queue_write,
            "perm_event_templates": config.perm_event_templates,
            "perm_event_tags": config.perm_event_tags,
            "perm_roles": config.perm_roles,
            "perm_rooms": config.perm_rooms,
            "perm_diary_reports": config.perm_diary_reports,
            "perm_printed_programmes": config.perm_printed_programmes,
            "perm_rota_vacancies": config.perm_rota_vacancies,
            "perm_donations_manage": config.perm_donations_manage,
            "eventlink_extra_allowed_domains": "",
            "community_exchange_enabled": "",
            "age_rating_choices_value_0": "U",
            "age_rating_choices_label_0": "U — Universal",
            "age_rating_choices_value_1": "PG",
            "age_rating_choices_label_1": "PG — Parental Guidance",
            "structured_cost_terms_enabled": "",
            "structured_cost_required": "",
            "suspension_email_subject": "",
            "suspension_email_body": "",
            "collectives_intro": "",
            "collectives_mailing_list_signup_url": "",
            "donations_intro": "",
            "show_donations_in_public_nav": "",
            "banner_active": "",
            "banner_level": config.banner_level,
            "banner_text": "",
            "banner_dismissible": "on",
            "omdb_api_key": "",
            "certificate_lookup_url": "",
        }
        response = self.client.post(self.url, post_data)
        self.assertEqual(response.status_code, 302)

        reloaded = get_site_config()
        self.assertTrue(reloaded.films_start_on_time)
        self.assertEqual(
            reloaded.films_start_on_time_banner_text, "Films start at the listed time."
        )
        self.assertEqual(reloaded.max_count_per_role, 20)

    def test_permission_fields_are_inside_form_element(self):
        # Guards against the bug where the Access Levels table was outside </form>,
        # causing perm_* fields to be silently dropped on POST and saves to appear
        # to work while actually reverting to DB values.
        self.client.login(username="admin", password="T3stPassword!")
        response = self.client.get(self.url)
        content = response.content.decode()
        perm_pos = content.find('name="perm_diary_read"')
        # rfind: the main config </form> is the last one on the page; find() would
        # hit the nav logout form first and give a false failure.
        form_close_pos = content.rfind("</form>")
        self.assertGreater(perm_pos, 0, "perm_diary_read input not found in page")
        self.assertGreater(
            form_close_pos,
            perm_pos,
            "perm_diary_read appears after </form> — the Access Levels table must be inside the form element",
        )


class FilmsStartOnTimeBannerTests(DiaryTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        # Make sure the singleton matches the assumption of each test
        from django.core.cache import cache

        cache.delete(SiteConfiguration._CACHE_KEY)

        # Create a "film" tag and add it to e2 for banner tests
        self.film_tag = EventTag(name="film", slug="film", read_only=False)
        self.film_tag.save()
        self.e2.tags.add(self.film_tag)

    def _post_event_with_showing(self):
        # The fixture event self.e2 has at least one showing — use it
        return self.e2

    def test_banner_hidden_when_setting_off(self):
        event = self._post_event_with_showing()
        config = get_site_config()
        config.films_start_on_time = False
        config.save()

        url = reverse("single-event-view", kwargs={"event_id": event.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "films-start-on-time")

    def test_banner_shown_with_custom_text_when_setting_on(self):
        event = self._post_event_with_showing()
        config = get_site_config()
        config.films_start_on_time = True
        config.films_start_on_time_banner_text = "Punctuality matters."
        config.save()

        url = reverse("single-event-view", kwargs={"event_id": event.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # The default Cube view_event.html doesn't render the banner — but the
        # context variables should be populated correctly.
        self.assertEqual(
            response.context["films_start_on_time"], True
        )
        self.assertEqual(
            response.context["films_start_on_time_banner_text"],
            "Punctuality matters.",
        )

    def test_banner_hidden_when_no_film_tag(self):
        # Event without "film" tag should not show banner even when setting is on
        # Use e4 (has showings) but clear its tags first
        event_without_film_tag = self.e4
        event_without_film_tag.tags.clear()
        config = get_site_config()
        config.films_start_on_time = True
        config.films_start_on_time_banner_text = "Films start promptly."
        config.save()

        url = reverse("single-event-view", kwargs={"event_id": event_without_film_tag.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["films_start_on_time"], False
        )


class SiteConfigurationConsistencyTests(DiaryTestsMixin, TestCase):
    """Assert that the three places listing SiteConfiguration fields stay in sync.

    If you add a field to the model, you must also add it to
    SiteConfigurationForm.Meta.fields and to the field_groups in the
    edit_site_configuration view — or this test will tell you which is missing.
    """

    def _get_form_fields(self):
        return set(SiteConfigurationForm.Meta.fields)

    def _get_view_fields(self):
        self.client.login(username="admin", password="T3stPassword!")
        response = self.client.get(reverse("edit-site-configuration"))
        self.assertEqual(response.status_code, 200)
        # grouped_fields is [(label, [BoundField, ...]), ...]; extract names via .name
        grouped_fields = response.context["grouped_fields"]
        fields_in_groups = {bound_field.name for _label, fields in grouped_fields for bound_field in fields}
        # permission_rows renders perm_* form fields outside grouped_fields
        permission_rows = response.context["permission_rows"]
        fields_in_perm_table = {
            row["field"].name for _feature, row in permission_rows if row["field"] is not None
        }
        return fields_in_groups | fields_in_perm_table

    def _get_model_fields(self):
        excluded = {"id"}
        return {
            f.name
            for f in SiteConfiguration._meta.get_fields()
            if not f.is_relation and f.name not in excluded
        }

    def test_form_fields_match_model_fields(self):
        form_fields = self._get_form_fields()
        model_fields = self._get_model_fields()
        self.assertEqual(
            form_fields,
            model_fields,
            msg=(
                f"SiteConfigurationForm.Meta.fields is out of sync with the model.\n"
                f"  In model but not form: {model_fields - form_fields}\n"
                f"  In form but not model: {form_fields - model_fields}"
            ),
        )

    def test_view_field_groups_match_form_fields(self):
        form_fields = self._get_form_fields()
        view_fields = self._get_view_fields()
        self.assertEqual(
            view_fields,
            form_fields,
            msg=(
                f"field_groups in edit_site_configuration view is out of sync with SiteConfigurationForm.\n"
                f"  In form but not view: {form_fields - view_fields}\n"
                f"  In view but not form: {view_fields - form_fields}"
            ),
        )
