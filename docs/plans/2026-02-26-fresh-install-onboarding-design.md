`#ai-written`

# Design: Fresh-Install Onboarding Fixes

**Date:** 2026-02-26
**Scope:** Fix a migration crash on fresh databases, update ONBOARDING.md to be accurate and Linux-friendly, triage BUGS.txt into modern docs.

---

## Problems Being Solved

### 1. Fresh install migration crash (critical)

`content.0013_widen_page_translation_key` uses raw SQL to widen the `translation_key` column in `wagtailcore_page`. Its only declared dependency is `("content", "0012_alter_complexarticlepage_content")`. On a fresh database, Django's migration executor runs `content.0013` before `wagtailcore.0055_page_locale_fields`, which is the migration that creates `translation_key`. Result: MariaDB error `(1054, "Unknown column 'translation_key' in 'wagtailcore_page'")`, container crash-loops.

Additionally, the current raw SQL sets `NULL UNIQUE`, which reverses Wagtail 6.3's `NOT NULL` constraint and adds a redundant unique index.

### 2. ONBOARDING.md settings mismatch

The doc says Docker uses `toolkit.docker_settings` (Cube Microplex settings). The actual `docker-compose.yml` and `Dockerfile` use `toolkit.docker_settings_ss` (Star & Shadow settings). A developer reading the docs would be confused about which venue configuration they're running.

### 3. Docker prerequisites misleading on Linux

ONBOARDING.md says "Prerequisites: Docker and Docker Compose (both included in Docker Desktop)". On Linux, Docker Desktop is a separate (and optional) GUI product. The standard route is Docker Engine + Compose plugin via the distribution package manager. No guidance is given for Linux users.

### 4. ONBOARDING.md references BUGS.txt

The "Next Steps" section sends developers to `BUGS.txt`. That file is a legacy artifact from 2012–2016 (Django 1.8, Python 2.6, paths from the original Cube server). Active work tracking is in `CURRENT_WORK.md` and `TASKS.md`. The reference is wrong and the file is misleading as a source of current issues.

### 5. BUGS.txt active items not in modern docs

Several open items in `BUGS.txt` are not tracked in `TASKS.md`:
- Mailout entities and links are broken
- URL linkifier does not detect HTTPS (only HTTP)
- Form redirect pattern not applied everywhere (only members)
- Error handling missing for event save when image file is absent

---

## Design Decisions

### Migration fix: RunPython with INFORMATION_SCHEMA check

Replace `RunSQL` with `RunPython`. The Python function queries `INFORMATION_SCHEMA.COLUMNS` to check the current column width. If it is already ≥ 36, the migration does nothing (correct for fresh installs where Wagtail 6.3 creates the column properly). If it is < 36, it widens to `varchar(36) NOT NULL` (correct for old databases being upgraded from a pre-6.x install).

Dependencies updated to include `("wagtailcore", "0057_page_locale_fields_notnull")`, which is the migration that both creates and finalises `translation_key` (NOT NULL, uuid default). This ensures the column exists and is in its final form before our migration runs.

Reverse migration is a deliberate no-op: there is no safe way to narrow a column that may contain data, and the original reverse SQL had the same dependency problem.

### ONBOARDING.md: two-venue clarity

Add a short "Which venue are you developing for?" section near the top. S+S is the default (what `docker compose up --build` gives). Cube developers get a one-liner to switch: set `DJANGO_SETTINGS_MODULE=toolkit.docker_settings` in the environment or edit `docker-compose.yml`.

### ONBOARDING.md: Linux Docker install note

Replace the vague "Docker Desktop" prerequisite with a brief platform-aware note:
- Linux: install Docker Engine + Compose plugin (link to official docs)
- Mac/Windows: Docker Desktop covers both

### ONBOARDING.md: remove BUGS.txt reference

Replace the BUGS.txt pointer in "Next Steps" with pointers to `CURRENT_WORK.md` (current status) and `TASKS.md` (open bugs and features).

### BUGS.txt: append to TASKS.md with provenance note

Append the four active items from `BUGS.txt` to `docs/TASKS.md` under a clearly labelled section ("Imported from BUGS.txt — legacy, unverified"). Leave `BUGS.txt` in place as a historical artifact but remove the ONBOARDING.md reference to it.

---

## Files Changed

| File | Change |
|---|---|
| `toolkit/content/migrations/0013_widen_page_translation_key.py` | Replace `RunSQL` with `RunPython`; add `wagtailcore.0057` dependency |
| `docs/ONBOARDING.md` | Fix prerequisites (Linux), fix settings module name, add venue switch note, update Next Steps |
| `docs/TASKS.md` | Append BUGS.txt active items with provenance note |
| `CURRENT_WORK.md` | Log this work as completed |

---

## Out of Scope

- Rewriting `configure_toolkit_users` to be non-interactive (separate task)
- Addressing any of the legacy items from BUGS.txt beyond appending them to TASKS.md
- Docker install automation / Makefile / setup scripts
