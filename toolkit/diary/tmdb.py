# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 4.6"]; status: "#ai-input"
"""TMDB (The Movie Database) API client for film/TV metadata lookup.

Uses stdlib urllib only — no extra dependencies.

Attribution required by TMDB ToS:
    "This product uses the TMDB API but is not endorsed or certified by TMDB."

Free tier: 40 req/10s, no hard daily cap. Suitable for occasional programmer lookups.
"""
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p"


def _get(path: str, params: dict, api_key: str) -> dict:
    """Make a GET request to the TMDB API. Raises urllib.error.URLError on failure."""
    params["api_key"] = api_key
    url = f"{TMDB_BASE}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def search_works(query: str, api_key: str) -> list[dict]:
    """Search for films and TV shows by title using TMDB multi-search.

    Returns a list of result dicts with keys:
        tmdb_id, media_type ('film'|'tv'), title, original_title,
        year, director, poster_url
    """
    data = _get("/search/multi", {"query": query, "include_adult": "false"}, api_key)
    results = []
    for item in data.get("results", []):
        mt = item.get("media_type")
        if mt not in ("movie", "tv"):
            continue
        if mt == "movie":
            title = item.get("title", "")
            original_title = item.get("original_title", "")
            raw_date = item.get("release_date", "")
        else:
            title = item.get("name", "")
            original_title = item.get("original_name", "")
            raw_date = item.get("first_air_date", "")

        year = int(raw_date[:4]) if raw_date and len(raw_date) >= 4 else None
        poster_path = item.get("poster_path") or ""
        results.append(
            {
                "tmdb_id": item["id"],
                "media_type": "film" if mt == "movie" else "tv",
                "title": title,
                "original_title": original_title,
                "year": year,
                "director": "",  # not available in search results; fetched on detail
                "poster_url": f"{TMDB_IMAGE_BASE}/w92{poster_path}" if poster_path else "",
            }
        )
    return results


def fetch_film_details(tmdb_id: int, media_type: str, api_key: str) -> dict:
    """Fetch full structured metadata for a film or TV show.

    Returns a dict with keys matching Film model fields:
        tmdb_id, imdb_id, media_type, title, original_title, year,
        director, runtime_minutes, countries, languages, tmdb_certificate,
        overview, tmdb_poster_path
    """
    if media_type == "film":
        data = _get(
            f"/movie/{tmdb_id}",
            {"append_to_response": "credits,release_dates"},
            api_key,
        )
        title = data.get("title", "")
        original_title = data.get("original_title", "")
        raw_date = data.get("release_date", "")
        year = int(raw_date[:4]) if raw_date and len(raw_date) >= 4 else None
        runtime_minutes = data.get("runtime") or None
        countries = ", ".join(c["iso_3166_1"] for c in data.get("production_countries", []))
        languages = ", ".join(
            l["english_name"] for l in data.get("spoken_languages", [])
        )
        imdb_id = data.get("imdb_id", "") or ""
        director = _extract_director_film(data.get("credits", {}))
        certificate = _extract_uk_certificate_film(data.get("release_dates", {}))
    else:
        data = _get(
            f"/tv/{tmdb_id}",
            {"append_to_response": "credits,content_ratings"},
            api_key,
        )
        title = data.get("name", "")
        original_title = data.get("original_name", "")
        raw_date = data.get("first_air_date", "")
        year = int(raw_date[:4]) if raw_date and len(raw_date) >= 4 else None
        runtimes = data.get("episode_run_time") or []
        runtime_minutes = runtimes[0] if runtimes else None
        countries = ", ".join(data.get("origin_country", []))
        languages = ", ".join(
            l["english_name"]
            for l in data.get("spoken_languages", [])
        )
        imdb_id = data.get("external_ids", {}).get("imdb_id", "") or ""
        director = _extract_creator_tv(data)
        certificate = _extract_uk_certificate_tv(data.get("content_ratings", {}))

    return {
        "tmdb_id": tmdb_id,
        "imdb_id": imdb_id,
        "media_type": media_type,
        "title": title,
        "original_title": original_title,
        "year": year,
        "director": director,
        "runtime_minutes": runtime_minutes,
        "countries": countries,
        "languages": languages,
        "tmdb_certificate": certificate,
        "overview": data.get("overview", "") or "",
        "tmdb_poster_path": data.get("poster_path", "") or "",
    }


def _extract_director_film(credits: dict) -> str:
    """Return comma-joined names of crew members with job='Director'."""
    directors = [
        p["name"]
        for p in credits.get("crew", [])
        if p.get("job") == "Director"
    ]
    return ", ".join(directors)


def _extract_creator_tv(data: dict) -> str:
    """Return comma-joined names from created_by; fall back to crew directors."""
    creators = [p["name"] for p in data.get("created_by", [])]
    if creators:
        return ", ".join(creators)
    directors = [
        p["name"]
        for p in data.get("credits", {}).get("crew", [])
        if p.get("job") == "Director"
    ]
    return ", ".join(directors)


def _extract_uk_certificate_film(release_dates: dict) -> str:
    """Extract the UK (GB) certificate from TMDB film release_dates response."""
    for entry in release_dates.get("results", []):
        if entry.get("iso_3166_1") == "GB":
            for rd in entry.get("release_dates", []):
                cert = rd.get("certification", "").strip()
                if cert:
                    return cert
    return ""


def _extract_uk_certificate_tv(content_ratings: dict) -> str:
    """Extract the UK (GB) certificate from TMDB TV content_ratings response."""
    for entry in content_ratings.get("results", []):
        if entry.get("iso_3166_1") == "GB":
            rating = entry.get("rating", "").strip()
            if rating:
                return rating
    return ""


def poster_url(path: str, size: str = "w185") -> str:
    """Construct a full TMDB poster URL from a stored path."""
    if not path:
        return ""
    return f"{TMDB_IMAGE_BASE}/{size}{path}"
