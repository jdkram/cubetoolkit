#!/usr/bin/env python3
"""
Fetch missing trailer URLs from TMDB for films in seed data.

Reads TMDB_API_KEY from a .env file at the repo root, queries the TMDB API
for any film with an empty trailer_url, and updates films.toml in place.
Existing trailer URLs are never overwritten.

Usage (from repo root):
    python3 toolkit/util/management/commands/seed_data/fetch_trailers.py
"""

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _find_repo_root(start: Path) -> Path:
    """Walk up from start until we find the repo root (has VERSION file)."""
    for parent in [start, *start.parents]:
        if (parent / "VERSION").exists():
            return parent
    # Fallback: N parents up from the script location
    return start.resolve().parents[5]


REPO_ROOT = _find_repo_root(Path(__file__).parent)
ENV_PATH = REPO_ROOT / ".env"
TOML_PATH = Path(__file__).parent / "films.toml"

TMDB_SEARCH_URL = "https://api.themoviedb.org/3/search/movie"
TMDB_VIDEOS_URL = "https://api.themoviedb.org/3/movie/{movie_id}/videos"

# Delay between API calls to be polite to TMDB
RATE_LIMIT_DELAY = 0.25

# ---------------------------------------------------------------------------
# API key loading
# ---------------------------------------------------------------------------


def _load_api_key() -> str:
    if ENV_PATH.exists():
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("TMDB_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    env_key = os.environ.get("TMDB_API_KEY", "").strip()
    if env_key:
        return env_key
    print(
        "Error: TMDB_API_KEY not found.\n"
        f"Please create {ENV_PATH} and add:\n"
        "    TMDB_API_KEY=your_key_here\n"
        "Or export it as an environment variable."
    )
    sys.exit(1)


# ---------------------------------------------------------------------------
# TMDB helpers
# ---------------------------------------------------------------------------


def _tmdb_get(url: str, api_key: str) -> dict:
    sep = "&" if "?" in url else "?"
    full_url = f"{url}{sep}api_key={api_key}"
    req = urllib.request.Request(full_url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def _search_movie(title: str, year: int | None, api_key: str) -> dict | None:
    query = urllib.parse.quote(title)
    url = f"{TMDB_SEARCH_URL}?query={query}"
    if year:
        url += f"&year={year}"
    data = _tmdb_get(url, api_key)
    results = data.get("results", [])
    if not results:
        return None
    # Prefer exact title match; otherwise take first result
    exact = [r for r in results if r.get("title", "").lower() == title.lower()]
    return exact[0] if exact else results[0]


def _pick_trailer(videos: list[dict]) -> str | None:
    """Pick the best YouTube trailer from a TMDB videos list."""
    yt_videos = [
        v for v in videos
        if v.get("site", "").lower() == "youtube" and v.get("key")
    ]
    if not yt_videos:
        return None

    def _score(v: dict) -> int:
        score = 0
        if v.get("type", "").lower() == "trailer":
            score += 10
        if v.get("official"):
            score += 5
        # Prefer higher resolution if reported
        size = v.get("size", 0)
        if isinstance(size, int):
            score += min(size // 100, 5)
        return score

    yt_videos.sort(key=_score, reverse=True)
    best = yt_videos[0]
    return f"https://www.youtube.com/watch?v={best['key']}"


def _fetch_trailer_for_film(film: dict, api_key: str) -> str | None:
    title = film.get("name", "").strip()
    info = film.get("film_information", "").strip()

    # Extract year from info string, e.g. "Dir. Foo, GB 1985" or "FR / US 2021"
    year = None
    year_match = re.search(r"\b(\d{4})\b", info)
    if year_match:
        year = int(year_match.group(1))

    movie = _search_movie(title, year, api_key)
    if movie is None:
        return None

    time.sleep(RATE_LIMIT_DELAY)
    videos_data = _tmdb_get(
        TMDB_VIDEOS_URL.format(movie_id=movie["id"]), api_key
    )
    videos = videos_data.get("results", [])
    return _pick_trailer(videos)


# ---------------------------------------------------------------------------
# TOML parsing / rewriting (std-lib only; tomllib can't write)
# ---------------------------------------------------------------------------


def _parse_toml_films(path: Path) -> tuple[list[dict], list[dict]]:
    """Return (sunday_films, thursday_films) using stdlib tomllib."""
    import tomllib
    with open(path, "rb") as f:
        data = tomllib.load(f)
    return data.get("sunday_films", []), data.get("thursday_films", [])


def _update_toml_file(path: Path, updates: dict[str, str]) -> None:
    """
    updates: {film_name: trailer_url}

    Re-read the raw TOML text and replace trailer_url = "" lines
    for the listed films, leaving everything else untouched.
    """
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    current_name = None
    out_lines = []
    changed = 0

    for line in lines:
        name_match = re.match(r'^name\s*=\s*"([^"]+)"', line.strip())
        if name_match:
            current_name = name_match.group(1)

        trailer_match = re.match(r'^trailer_url\s*=\s*""', line.strip())
        if trailer_match and current_name and current_name in updates:
            new_url = updates[current_name]
            # Preserve original indentation by replacing only the value part
            out_lines.append(re.sub(r'trailer_url\s*=\s*""', f'trailer_url = "{new_url}"', line))
            changed += 1
            continue

        out_lines.append(line)

    with open(path, "w", encoding="utf-8") as f:
        f.writelines(out_lines)

    print(f"    Updated {changed} trailer_url field(s) in {path.name}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    api_key = _load_api_key()
    sunday_films, thursday_films = _parse_toml_films(TOML_PATH)
    all_films = sunday_films + thursday_films

    # Build list of films needing a trailer
    needed = [f for f in all_films if not f.get("trailer_url", "").strip()]
    total = len(all_films)
    missing = len(needed)
    print(f"Films in {TOML_PATH.name}: {total}")
    print(f"Missing trailers: {missing}")
    print()

    if not needed:
        print("Nothing to do — every film already has a trailer_url.")
        return

    updates: dict[str, str] = {}
    found_count = 0
    not_found: list[str] = []

    for film in needed:
        title = film["name"]
        print(f"Searching: {title} … ", end="", flush=True)
        try:
            url = _fetch_trailer_for_film(film, api_key)
        except Exception as exc:
            print(f"ERROR ({exc})")
            not_found.append(title)
            continue

        if url:
            print(f"found → {url}")
            updates[title] = url
            found_count += 1
        else:
            print("not found")
            not_found.append(title)

        # Rate-limiting sleep after every request pair (search + videos)
        time.sleep(RATE_LIMIT_DELAY)

    if updates:
        print()
        _update_toml_file(TOML_PATH, updates)

    print()
    print("─" * 50)
    print(f"Found trailers:     {found_count} / {missing}")
    print(f"Still missing:      {len(not_found)}")
    if not_found:
        print("\nFilms with no trailer found:")
        for t in not_found:
            print(f"  - {t}")


if __name__ == "__main__":
    main()
