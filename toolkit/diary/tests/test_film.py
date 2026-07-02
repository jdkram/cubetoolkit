# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 4.6"]; status: "#ai-input"
"""Tests for Film model, OMDb client, and film link/unlink views (9.66)."""
import json
import urllib.error
from io import BytesIO
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from django.test import TestCase, override_settings
from django.urls import reverse

from toolkit.diary.models import Event, EventTag, Film, MediaItem
from toolkit.diary.tests.common import DiaryTestsMixin
import toolkit.diary.omdb as omdb_module


# ---------------------------------------------------------------------------
# Film model
# ---------------------------------------------------------------------------


class FilmModelTests(TestCase):

    def test_str_with_year(self):
        f = Film(title="Seacoal", year=1985)
        self.assertEqual(str(f), "Seacoal (1985)")

    def test_str_without_year(self):
        f = Film(title="Untitled Local Film")
        self.assertEqual(str(f), "Untitled Local Film")

    def test_generate_film_information_full(self):
        f = Film(
            title="Seacoal",
            year=1985,
            director="Amber Collective",
            runtime_minutes=82,
            countries="GB",
        )
        result = f.generate_film_information()
        self.assertEqual(result, "Dir. Amber Collective, GB, 1985, 82 mins")

    def test_generate_film_information_partial(self):
        f = Film(title="Twin Peaks", year=1990, director="David Lynch, Mark Frost")
        result = f.generate_film_information()
        self.assertEqual(result, "Dir. David Lynch, Mark Frost, 1990")

    def test_generate_film_information_empty(self):
        f = Film(title="Something")
        self.assertEqual(f.generate_film_information(), "")

    def test_poster_url_stored(self):
        f = Film(title="X", poster_url="https://example.com/poster.jpg")
        self.assertEqual(f.poster_url, "https://example.com/poster.jpg")

    def test_poster_url_empty(self):
        f = Film(title="X")
        self.assertEqual(f.poster_url, "")

    def test_multiple_films_without_imdb_id(self):
        Film.objects.create(title="Local Film A")
        Film.objects.create(title="Local Film B")
        # Both have imdb_id="" — should not violate any uniqueness constraint
        self.assertEqual(Film.objects.count(), 2)

    def test_media_type_choices(self):
        f_film = Film(title="X", media_type=Film.MEDIA_TYPE_FILM)
        f_tv = Film(title="Y", media_type=Film.MEDIA_TYPE_TV)
        self.assertEqual(f_film.media_type, "film")
        self.assertEqual(f_tv.media_type, "tv")


# ---------------------------------------------------------------------------
# OMDb client
# ---------------------------------------------------------------------------


def _make_http_error(data: dict, code: int = 401):
    """Return an HTTPError (as urlopen() raises for non-2xx) with a JSON body."""
    return urllib.error.HTTPError(
        url="https://www.omdbapi.com/",
        code=code,
        msg="Unauthorized",
        hdrs=None,
        fp=BytesIO(json.dumps(data).encode()),
    )


def _make_response(data: dict):
    """Return a mock urllib response yielding JSON."""
    mock = MagicMock()
    mock.__enter__ = lambda s: s
    mock.__exit__ = MagicMock(return_value=False)
    mock.read.return_value = json.dumps(data).encode()
    return mock


MOCK_SEARCH_RESPONSE = {
    "Search": [
        {"Title": "Seacoal", "Year": "1985", "imdbID": "tt0090186", "Type": "movie", "Poster": "https://example.com/seacoal.jpg"},
        {"Title": "Twin Peaks", "Year": "1990–1991", "imdbID": "tt0098936", "Type": "series", "Poster": "https://example.com/twinpeaks.jpg"},
        {"Title": "Some Episode", "Year": "1990", "imdbID": "tt0000001", "Type": "episode", "Poster": "N/A"},
    ],
    "totalResults": "3",
    "Response": "True",
}

MOCK_MOVIE_DETAIL = {
    "Title": "Seacoal", "Year": "1985", "Rated": "15",
    "Runtime": "82 min", "Director": "Amber Collective",
    "Country": "United Kingdom", "Language": "English",
    "Plot": "A film about coal.", "Poster": "https://example.com/seacoal.jpg",
    "imdbID": "tt0090186", "Type": "movie", "Response": "True",
}

MOCK_TV_DETAIL = {
    "Title": "Twin Peaks", "Year": "1990–1991", "Rated": "TV-MA",
    "Runtime": "47 min", "Director": "David Lynch, Mark Frost",
    "Country": "United States", "Language": "English",
    "Plot": "A damn fine show.", "Poster": "https://example.com/twinpeaks.jpg",
    "imdbID": "tt0098936", "Type": "series", "Response": "True",
}


class OmdbClientTests(TestCase):

    @patch("urllib.request.urlopen")
    def test_search_filters_to_film_and_tv(self, mock_urlopen):
        mock_urlopen.return_value = _make_response(MOCK_SEARCH_RESPONSE)
        results = omdb_module.search_works("seacoal", "fake-key")
        self.assertEqual(len(results), 2)  # episode filtered out
        self.assertEqual(results[0]["imdb_id"], "tt0090186")
        self.assertEqual(results[0]["media_type"], "film")
        self.assertEqual(results[1]["media_type"], "tv")

    @patch("urllib.request.urlopen")
    def test_search_poster_url(self, mock_urlopen):
        mock_urlopen.return_value = _make_response(MOCK_SEARCH_RESPONSE)
        results = omdb_module.search_works("seacoal", "fake-key")
        self.assertEqual(results[0]["poster_url"], "https://example.com/seacoal.jpg")
        self.assertEqual(results[1]["poster_url"], "https://example.com/twinpeaks.jpg")

    @patch("urllib.request.urlopen")
    def test_search_na_poster_becomes_empty(self, mock_urlopen):
        resp = {"Search": [{"Title": "X", "Year": "2000", "imdbID": "tt9999999", "Type": "movie", "Poster": "N/A"}], "Response": "True"}
        mock_urlopen.return_value = _make_response(resp)
        results = omdb_module.search_works("x", "fake-key")
        self.assertEqual(results[0]["poster_url"], "")

    @patch("urllib.request.urlopen")
    def test_search_false_response_returns_empty(self, mock_urlopen):
        mock_urlopen.return_value = _make_response({"Response": "False", "Error": "Movie not found!"})
        results = omdb_module.search_works("zzznoresult", "fake-key")
        self.assertEqual(results, [])

    @patch("urllib.request.urlopen")
    def test_fetch_film_details(self, mock_urlopen):
        mock_urlopen.return_value = _make_response(MOCK_MOVIE_DETAIL)
        details = omdb_module.fetch_film_details("tt0090186", "fake-key")
        self.assertEqual(details["title"], "Seacoal")
        self.assertEqual(details["director"], "Amber Collective")
        self.assertEqual(details["imdb_id"], "tt0090186")
        self.assertEqual(details["runtime_minutes"], 82)
        self.assertEqual(details["countries"], "United Kingdom")
        self.assertEqual(details["media_type"], "film")
        self.assertEqual(details["poster_url"], "https://example.com/seacoal.jpg")

    @patch("urllib.request.urlopen")
    def test_fetch_tv_details(self, mock_urlopen):
        mock_urlopen.return_value = _make_response(MOCK_TV_DETAIL)
        details = omdb_module.fetch_film_details("tt0098936", "fake-key")
        self.assertEqual(details["title"], "Twin Peaks")
        self.assertEqual(details["director"], "David Lynch, Mark Frost")
        self.assertEqual(details["runtime_minutes"], 47)
        self.assertEqual(details["media_type"], "tv")

    def test_parse_runtime_normal(self):
        self.assertEqual(omdb_module._parse_runtime("82 min"), 82)

    def test_parse_runtime_na(self):
        self.assertIsNone(omdb_module._parse_runtime("N/A"))

    def test_parse_runtime_empty(self):
        self.assertIsNone(omdb_module._parse_runtime(""))

    @patch("urllib.request.urlopen")
    def test_verify_api_key_accepts_valid_key(self, mock_urlopen):
        mock_urlopen.return_value = _make_response(MOCK_MOVIE_DETAIL)
        omdb_module.verify_api_key("real-key")  # should not raise

    @patch("urllib.request.urlopen")
    def test_verify_api_key_rejects_invalid_key(self, mock_urlopen):
        # OMDb signals a bad key with an HTTP 401, not a 200 + JSON body —
        # urlopen() raises HTTPError before we ever see a "normal" response.
        mock_urlopen.side_effect = _make_http_error(
            {"Response": "False", "Error": "Invalid API key!"}
        )
        with self.assertRaises(omdb_module.OmdbAuthError):
            omdb_module.verify_api_key("bad-key")

    @patch("urllib.request.urlopen")
    def test_verify_api_key_rate_limit_is_not_treated_as_invalid(self, mock_urlopen):
        # OMDb's daily-quota-exhausted response looks identical to an invalid
        # key (401 + same JSON shape) except for the Error text — a quota hit
        # must not be reported to the user as "this key is wrong".
        mock_urlopen.side_effect = _make_http_error(
            {"Response": "False", "Error": "Request limit reached!"}
        )
        with self.assertRaises(omdb_module.OmdbRateLimitError):
            omdb_module.verify_api_key("real-key")

    @patch("urllib.request.urlopen")
    def test_verify_api_key_ignores_unrelated_errors(self, mock_urlopen):
        # A valid key but a "not found" style error (200 + Response: False)
        # should not raise OmdbAuthError.
        mock_urlopen.return_value = _make_response(
            {"Response": "False", "Error": "Incorrect IMDb ID."}
        )
        omdb_module.verify_api_key("real-key")  # should not raise

    @patch("urllib.request.urlopen")
    def test_verify_api_key_propagates_network_errors(self, mock_urlopen):
        mock_urlopen.side_effect = URLError("timed out")
        with self.assertRaises(URLError):
            omdb_module.verify_api_key("real-key")


# ---------------------------------------------------------------------------
# OMDb search view
# ---------------------------------------------------------------------------


class OmdbSearchViewTests(DiaryTestsMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.client.login(username="admin", password="T3stPassword!")

    def test_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("omdb-search") + "?q=seacoal")
        self.assertEqual(response.status_code, 302)

    @override_settings(OMDB_API_KEY="")
    def test_no_api_key_returns_503(self):
        response = self.client.get(reverse("omdb-search") + "?q=seacoal")
        self.assertEqual(response.status_code, 503)
        data = json.loads(response.content)
        self.assertIn("error", data)

    @override_settings(OMDB_API_KEY="fake-key")
    @patch("urllib.request.urlopen")
    def test_search_returns_results(self, mock_urlopen):
        mock_urlopen.return_value = _make_response(MOCK_SEARCH_RESPONSE)
        response = self.client.get(reverse("omdb-search") + "?q=seacoal")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["imdb_id"], "tt0090186")

    @override_settings(OMDB_API_KEY="fake-key")
    @patch("urllib.request.urlopen", side_effect=URLError("timeout"))
    def test_omdb_error_returns_502(self, mock_urlopen):
        response = self.client.get(reverse("omdb-search") + "?q=seacoal")
        self.assertEqual(response.status_code, 502)

    @override_settings(OMDB_API_KEY="fake-key")
    @patch("urllib.request.urlopen")
    def test_rate_limit_hit_returns_friendly_503(self, mock_urlopen):
        mock_urlopen.side_effect = _make_http_error(
            {"Response": "False", "Error": "Request limit reached!"}
        )
        response = self.client.get(reverse("omdb-search") + "?q=seacoal")
        self.assertEqual(response.status_code, 503)
        data = json.loads(response.content)
        self.assertIn("daily search limit", data["error"])
        self.assertIn("manually", data["error"])

    @override_settings(OMDB_API_KEY="fake-key")
    @patch("urllib.request.urlopen")
    def test_rejected_key_returns_panopticon_pointer_503(self, mock_urlopen):
        mock_urlopen.side_effect = _make_http_error(
            {"Response": "False", "Error": "Invalid API key!"}
        )
        response = self.client.get(reverse("omdb-search") + "?q=seacoal")
        self.assertEqual(response.status_code, 503)
        data = json.loads(response.content)
        self.assertIn("Panopticon", data["error"])

    @override_settings(OMDB_API_KEY="fake-key")
    def test_empty_query_returns_empty_list(self):
        response = self.client.get(reverse("omdb-search") + "?q=")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content), [])


# ---------------------------------------------------------------------------
# Link / unlink film views
# ---------------------------------------------------------------------------


class LinkFilmViewTests(DiaryTestsMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.client.login(username="admin", password="T3stPassword!")

    @override_settings(OMDB_API_KEY="fake-key")
    @patch("urllib.request.urlopen")
    def test_link_via_omdb_creates_film_and_sets_fk(self, mock_urlopen):
        mock_urlopen.return_value = _make_response(MOCK_MOVIE_DETAIL)
        url = reverse("link-film", kwargs={"event_id": self.e1.pk})
        response = self.client.post(url, {"imdb_id": "tt0090186", "media_type": "film"})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["success"])
        self.e1.refresh_from_db()
        self.assertIsNotNone(self.e1.film)
        self.assertEqual(self.e1.film.imdb_id, "tt0090186")
        self.assertEqual(self.e1.film.title, "Seacoal")

    @override_settings(OMDB_API_KEY="fake-key")
    @patch("urllib.request.urlopen")
    def test_link_same_imdb_id_reuses_existing_film(self, mock_urlopen):
        mock_urlopen.return_value = _make_response(MOCK_MOVIE_DETAIL)
        url = reverse("link-film", kwargs={"event_id": self.e1.pk})
        self.client.post(url, {"imdb_id": "tt0090186", "media_type": "film"})
        count_before = Film.objects.count()
        # Link same film to a different event
        mock_urlopen.return_value = _make_response(MOCK_MOVIE_DETAIL)
        url2 = reverse("link-film", kwargs={"event_id": self.e2.pk})
        self.client.post(url2, {"imdb_id": "tt0090186", "media_type": "film"})
        self.assertEqual(Film.objects.count(), count_before)

    def test_link_manual_creates_film_without_imdb_id(self):
        url = reverse("link-film", kwargs={"event_id": self.e1.pk})
        response = self.client.post(url, {
            "title": "Local Film",
            "year": "2023",
            "director": "Local Director",
            "media_type": "film",
        })
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["success"])
        self.e1.refresh_from_db()
        self.assertIsNotNone(self.e1.film)
        self.assertEqual(self.e1.film.imdb_id, "")
        self.assertEqual(self.e1.film.title, "Local Film")

    def test_link_returns_suggested_film_information(self):
        url = reverse("link-film", kwargs={"event_id": self.e1.pk})
        response = self.client.post(url, {
            "title": "Local Film",
            "year": "2023",
            "director": "Director",
            "runtime_minutes": "90",
            "countries": "GB",
            "media_type": "film",
        })
        data = json.loads(response.content)
        self.assertIn("suggested_film_information", data)
        self.assertIn("Director", data["suggested_film_information"])

    @override_settings(OMDB_API_KEY="fake-key")
    @patch("urllib.request.urlopen")
    def test_link_via_omdb_rate_limited_gives_friendly_error(self, mock_urlopen):
        mock_urlopen.side_effect = _make_http_error(
            {"Response": "False", "Error": "Request limit reached!"}
        )
        url = reverse("link-film", kwargs={"event_id": self.e1.pk})
        response = self.client.post(url, {"imdb_id": "tt0090186", "media_type": "film"})
        self.assertEqual(response.status_code, 503)
        data = json.loads(response.content)
        self.assertNotIn("success", data)
        self.assertIn("daily request limit", data["error"])
        self.assertIn("manually", data["error"])
        self.e1.refresh_from_db()
        self.assertIsNone(self.e1.film)

    def test_unlink_clears_film_fk(self):
        film = Film.objects.create(title="Test Film")
        self.e1.film = film
        self.e1.save()
        url = reverse("unlink-film", kwargs={"event_id": self.e1.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["success"])
        self.e1.refresh_from_db()
        self.assertIsNone(self.e1.film)

    def test_volunteer_cannot_link(self):
        self.client.login(username="read_only", password="T3stPassword!1")
        url = reverse("link-film", kwargs={"event_id": self.e1.pk})
        response = self.client.post(url, {"title": "X", "media_type": "film"})
        self.assertEqual(response.status_code, 302)  # redirect to login


# ---------------------------------------------------------------------------
# Event hub film section
# ---------------------------------------------------------------------------


class EventHubFilmTests(DiaryTestsMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.client.login(username="admin", password="T3stPassword!")

    def test_hub_shows_film_section_when_linked(self):
        film = Film.objects.create(
            title="Seacoal", year=1985, director="Amber Collective"
        )
        self.e1.film = film
        self.e1.save()
        url = reverse("edit-event-details-view", kwargs={"event_id": self.e1.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Screened work")
        self.assertContains(response, "Seacoal")
        self.assertContains(response, "Amber Collective")

    def test_hub_omits_film_section_when_no_film(self):
        url = reverse("edit-event-details-view", kwargs={"event_id": self.e1.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Screened work")


# ---------------------------------------------------------------------------
# Completeness bar — film details check
# ---------------------------------------------------------------------------


class FilmCompletenessTests(DiaryTestsMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.client.login(username="admin", password="T3stPassword!")
        self.film_tag = EventTag.objects.create(
            name="film", slug="film", read_only=True, promoted=True
        )

    def test_film_badge_shown_when_film_tag_and_no_film_linked(self):
        self.e1.tags.add(self.film_tag)
        url = reverse("edit-event-details-view", kwargs={"event_id": self.e1.pk})
        response = self.client.get(url)
        self.assertContains(response, "Film details not linked")

    def test_film_badge_absent_when_film_linked(self):
        film = Film.objects.create(title="Seacoal")
        self.e1.tags.add(self.film_tag)
        self.e1.film = film
        self.e1.save()
        url = reverse("edit-event-details-view", kwargs={"event_id": self.e1.pk})
        response = self.client.get(url)
        self.assertNotContains(response, "Film details not linked")

    def test_film_badge_absent_when_no_film_tag(self):
        # Event has no "film" tag — check should not appear even without a Film
        url = reverse("edit-event-details-view", kwargs={"event_id": self.e1.pk})
        response = self.client.get(url)
        self.assertNotContains(response, "Film details not linked")
