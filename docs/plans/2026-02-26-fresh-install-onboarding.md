`#ai-written`

# Fresh-Install Onboarding Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix a crash that prevents the app starting on a fresh database, and update ONBOARDING.md to be accurate and Linux-friendly.

**Architecture:** Four independent changes: (1) fix a broken migration dependency, (2) patch ONBOARDING.md for accuracy, (3) append legacy BUGS.txt items to TASKS.md, (4) log in CURRENT_WORK.md. No schema changes visible to users. The migration fix is the critical blocker — it must land first so the app can start.

**Tech Stack:** Django migrations (RunPython), MariaDB INFORMATION_SCHEMA, Markdown docs.

**Design doc:** [docs/plans/2026-02-26-fresh-install-onboarding-design.md](2026-02-26-fresh-install-onboarding-design.md)

---

## Task 1: Fix content.0013 migration

**The bug:** `content.0013_widen_page_translation_key` declares only one dependency: `("content", "0012_alter_complexarticlepage_content")`. It uses raw SQL to ALTER `wagtailcore_page.translation_key`, but that column is created by `wagtailcore.0055_page_locale_fields`. On a fresh database Django runs `content.0013` before `wagtailcore.0055`, so the column doesn't exist yet and MariaDB raises `(1054, "Unknown column 'translation_key'")`. The container then crash-loops forever.

**Files:**
- Modify: `toolkit/content/migrations/0013_widen_page_translation_key.py`

**Current content of the file (for reference):**
```python
from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ("content", "0012_alter_complexarticlepage_content"),
    ]
    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE wagtailcore_page MODIFY COLUMN translation_key varchar(36) NULL UNIQUE;",
            reverse_sql="ALTER TABLE wagtailcore_page MODIFY COLUMN translation_key varchar(32) NULL UNIQUE;",
        ),
    ]
```

**Step 1: Understand why RunPython is better here**

The RunSQL approach has two problems beyond the missing dependency:
- It changes the column to `NULL`, reversing Wagtail's `NOT NULL` constraint
- It adds a `UNIQUE` constraint that is already managed by Wagtail's own migrations

The RunPython approach queries `INFORMATION_SCHEMA.COLUMNS` first. If the column is already ≥ 36 chars wide (fresh Wagtail 6.3 install), it does nothing. If it is < 36 (old database being upgraded), it widens it, preserving `NOT NULL`.

**Step 2: Rewrite the migration**

Replace the entire file content with:

```python
# ai-written
# Migration to fix Wagtail 6 translation_key column overflow.
# On existing databases the column may be varchar(32), which is too narrow for
# 36-character UUIDs. Fresh installs with Wagtail 6.3 already have the right
# size, so this migration is a no-op for them.
#
# Uses RunPython with an INFORMATION_SCHEMA check so it is safe to run on
# both old and fresh databases.

from django.db import migrations


def widen_translation_key_if_needed(apps, schema_editor):
    """Widen wagtailcore_page.translation_key to varchar(36) if needed."""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT CHARACTER_MAXIMUM_LENGTH
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME   = 'wagtailcore_page'
              AND COLUMN_NAME  = 'translation_key'
            """
        )
        row = cursor.fetchone()
        if row is None:
            # Column does not exist at all — nothing to do (should not happen
            # given the wagtailcore.0057 dependency, but be defensive).
            return
        current_length = row[0]
        if current_length is not None and current_length >= 36:
            # Already wide enough; fresh Wagtail 6.3 installs land here.
            return
        cursor.execute(
            """
            ALTER TABLE wagtailcore_page
            MODIFY COLUMN translation_key varchar(36) NOT NULL
            """
        )


def reverse_noop(apps, schema_editor):
    # Cannot safely narrow a column that may contain data; this is intentional.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0012_alter_complexarticlepage_content"),
        # translation_key is created by 0055 and made NOT NULL by 0057.
        # Depend on 0057 so our ALTER runs after the column is in its final form.
        ("wagtailcore", "0057_page_locale_fields_notnull"),
    ]

    operations = [
        migrations.RunPython(
            widen_translation_key_if_needed,
            reverse_noop,
        ),
    ]
```

**Step 3: Verify the migration runs cleanly on a fresh database**

```bash
docker compose down --volumes
docker compose up --build
```

Watch the logs. Expected output (no crash):
```
toolkit-1  | Running database migrations
toolkit-1  |   Applying content.0013_widen_page_translation_key... OK
toolkit-1  | [wsgi:info] Starting gunicorn
```

The container should stay up (not restart). Give it ~60 seconds for MariaDB to initialise and migrations to run.

**Step 4: Confirm the app is reachable**

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/
```

Expected: `200` (the public diary page)

**Step 5: Create admin user and seed dev data**

```bash
docker compose exec toolkit /venv/bin/python3 manage.py shell -c "
from django.contrib.auth.models import User
User.objects.create_superuser(username='admin', password='admin', email='admin@example.test')
"
docker compose exec toolkit /venv/bin/python3 manage.py seed_dev_data
```

Both commands should complete without errors.

**Step 6: Commit (do not commit yet — bundle with doc changes in Task 4)**

---

## Task 2: Update ONBOARDING.md

**Files:**
- Modify: `docs/ONBOARDING.md`

The following four changes are all in ONBOARDING.md. Make them in order.

### 2a: Fix the Docker prerequisites section

Find this text near the top:

```
**Prerequisites:** [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/) (both included in Docker Desktop).
```

Replace with:

```
**Prerequisites:** [Docker](https://docs.docker.com/engine/install/) and the [Compose plugin](https://docs.docker.com/compose/install/).

- **Linux (Mint, Ubuntu, Debian):** Install Docker Engine and the Compose plugin via your package manager or the official install script. Docker Desktop is optional and not required.
  - Quickest route: follow [the official Linux install guide](https://docs.docker.com/engine/install/ubuntu/) for your distro, then [add your user to the `docker` group](https://docs.docker.com/engine/install/linux-postinstall/) so you can run `docker` without `sudo`. **You will need to log out and back in for the group change to take effect.**
- **Mac / Windows:** [Docker Desktop](https://docs.docker.com/desktop/) includes everything you need.
```

### 2b: Add a venue note before "Build and start the services"

Find the line `### 1. Build and start the services` and insert before it:

```markdown
### Which venue are you developing for?

This repo powers two venues. The default Docker setup runs **Star and Shadow** settings (`toolkit.docker_settings_ss`).

If you are developing for **Cube Microplex** instead, edit `docker-compose.yml` and change:

```yaml
DJANGO_SETTINGS_MODULE: "toolkit.docker_settings_ss"
```

to:

```yaml
DJANGO_SETTINGS_MODULE: "toolkit.docker_settings"
```

Everything else in this guide applies to both venues.

```

### 2c: Fix the settings table

Find this block in the Settings section:

```
| `docker_settings.py` | Running in Docker (reads `DB_*` and `SECRET_KEY` from environment) |
```

Replace the description:

```
| `docker_settings.py` | Running in Docker for **Cube Microplex** (reads `DB_*` and `SECRET_KEY` from environment) |
| `docker_settings_ss.py` | Running in Docker for **Star and Shadow** — the default for `docker compose up` |
```

Note: add the `docker_settings_ss.py` row if it is not already present. Check the table first.

### 2d: Update the Next Steps section

Find:

```
- Check [BUGS.txt](BUGS.txt) for known issues and pending work
```

Replace with:

```
- Check [CURRENT_WORK.md](../CURRENT_WORK.md) for open bugs and current priorities
- Check [docs/TASKS.md](TASKS.md) for detailed task descriptions and feature specs
```

---

## Task 3: Append BUGS.txt active items to TASKS.md

**Files:**
- Modify: `docs/TASKS.md`

Read `BUGS.txt` to get the exact wording of the four open items. Then append the following section at the very end of `docs/TASKS.md`:

```markdown
---

## Imported from BUGS.txt

The following items were in `BUGS.txt`, a legacy notes file from 2012–2016. They have not been verified against the current codebase. Triage and close as appropriate.

**Mailout entities and links broken** — Mailout body entities and links are described as "somewhat broken". Nature of the breakage not documented. 🔵 S

**URL linkifier does not detect HTTPS** — The code that auto-links URLs in programme copy detects `http://` but not `https://`. A unit test should accompany any fix. 🟢 XS

**Form redirect after submit not universal** — The pattern of redirecting after a successful POST (to prevent duplicate submission on reload) was applied to the members forms but not everywhere else. 🔵 S

**Event save error handling for missing image** — If an event is saved and the associated image file is missing on disk, the error is not handled gracefully. 🟢 XS
```

---

## Task 4: Update CURRENT_WORK.md and commit everything

**Files:**
- Modify: `CURRENT_WORK.md`

Add a row to the Done section:

```markdown
| ~~Fresh install migration crash (`content.0013`)~~ | 2026-02-26 | Added `wagtailcore.0057` dependency; replaced `RunSQL` with safe `RunPython` |
| ~~ONBOARDING.md accuracy pass~~ | 2026-02-26 | Linux Docker prereqs, venue clarity, remove BUGS.txt ref, fix settings table |
| ~~BUGS.txt triage~~ | 2026-02-26 | Active items appended to TASKS.md; ONBOARDING.md ref removed |
```

Then commit everything together:

```bash
git add \
  toolkit/content/migrations/0013_widen_page_translation_key.py \
  docs/ONBOARDING.md \
  docs/TASKS.md \
  docs/plans/2026-02-26-fresh-install-onboarding-design.md \
  docs/plans/2026-02-26-fresh-install-onboarding.md \
  CURRENT_WORK.md

git commit -m "$(cat <<'EOF'
fix: fresh install migration crash + onboarding doc accuracy

- content.0013: add wagtailcore.0057 dependency; replace RunSQL with
  RunPython that checks INFORMATION_SCHEMA before ALTERing, safe for
  both fresh and existing databases
- ONBOARDING.md: Linux-specific Docker install guidance, venue switch
  note (S+S default / Cube opt-in), corrected settings table, remove
  stale BUGS.txt reference
- TASKS.md: append legacy BUGS.txt active items with provenance note
- CURRENT_WORK.md: log all changes

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Verification Checklist

After the commit, do a final smoke-test to confirm everything works end-to-end:

```bash
# Wipe all state
docker compose down --volumes

# Rebuild and start
docker compose up --build -d

# Wait ~60 seconds, then check logs for migration success and gunicorn start
docker compose logs toolkit | grep -E "OK|ERROR|gunicorn"

# Create admin and seed
docker compose exec toolkit /venv/bin/python3 manage.py shell -c "
from django.contrib.auth.models import User
User.objects.create_superuser(username='admin', password='admin', email='admin@example.test')
"
docker compose exec toolkit /venv/bin/python3 manage.py seed_dev_data

# Hit the public page
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/
# Expected: 200

# Hit the login page
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/auth/login
# Expected: 200
```

Log in at http://localhost:8000/auth/login with `admin` / `admin` and verify the toolkit dashboard is accessible.
