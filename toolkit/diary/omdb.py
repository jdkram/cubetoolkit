# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 4.6"]; status: "#ai-input"
"""OMDb (Open Movie Database) API client for film/TV metadata lookup.

Uses stdlib urllib only — no extra dependencies.

Free tier: 1,000 requests/day. Get a key at https://www.omdbapi.com/apikey.aspx
OMDb is suitable for non-commercial use without a commercial licence.
"""
import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

OMDB_BASE = "https://www.omdbapi.com/"


def _get(params: dict, api_key: str) -> dict:
    """Make a GET request to the OMDb API. Raises urllib.error.URLError on failure."""
    params["apikey"] = api_key
    url = f"{OMDB_BASE}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def _na(value: Any) -> str:
    """Return empty string if value is 'N/A' or falsy, otherwise the value."""
    if not value or value == "N/A":
        return ""
    return value


def _parse_runtime(s: str) -> int | None:
    """Parse an OMDb runtime string like '82 min' to an integer, or None if absent/invalid."""
    if not s or s == "N/A":
        return None
    m = re.match(r"^(\d+)", s.strip())
    return int(m.group(1)) if m else None


def search_works(query: str, api_key: str) -> list[dict]:
    """Search for films and TV shows by title using OMDb search.

    Returns a list of result dicts with keys:
        imdb_id, media_type ('film'|'tv'), title, year, poster_url
    """
    data = _get({"s": query}, api_key)
    if data.get("Response") != "True":
        return []

    results = []
    for item in data.get("Search", []):
        omdb_type = item.get("Type", "")
        if omdb_type not in ("movie", "series"):
            # Skip episodes and other types
            continue

        raw_year = item.get("Year", "")
        # Year can be "2001" or "2001–2003" — take first 4 chars if digits
        year: int | None = None
        if raw_year and len(raw_year) >= 4 and raw_year[:4].isdigit():
            year = int(raw_year[:4])

        poster = item.get("Poster", "")
        results.append(
            {
                "imdb_id": item.get("imdbID", ""),
                "media_type": "film" if omdb_type == "movie" else "tv",
                "title": item.get("Title", ""),
                "year": year,
                "poster_url": "" if poster == "N/A" else (poster or ""),
            }
        )
    return results


def fetch_film_details(imdb_id: str, api_key: str) -> dict:
    """Fetch full structured metadata for a film or TV show by IMDb ID.

    Returns a dict with keys matching Film model fields:
        imdb_id, media_type, title, original_title, year,
        director, runtime_minutes, countries, languages,
        overview, poster_url
    """
    data = _get({"i": imdb_id, "plot": "short"}, api_key)

    omdb_type = data.get("Type", "movie")
    media_type = "film" if omdb_type == "movie" else "tv"

    raw_year = data.get("Year", "")
    year: int | None = None
    if raw_year and len(raw_year) >= 4 and raw_year[:4].isdigit():
        year = int(raw_year[:4])

    poster = data.get("Poster", "")

    return {
        "imdb_id": _na(data.get("imdbID", "")) or imdb_id,
        "media_type": media_type,
        "title": _na(data.get("Title", "")),
        "original_title": "",  # OMDb does not provide original title
        "year": year,
        "director": _na(data.get("Director", "")),
        "runtime_minutes": _parse_runtime(data.get("Runtime", "")),
        "countries": _na(data.get("Country", "")),
        "languages": _na(data.get("Language", "")),
        "overview": _na(data.get("Plot", "")),
        "poster_url": "" if poster == "N/A" else (poster or ""),
    }
