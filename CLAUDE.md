# Claude Context — Cube Toolkit

## Orientation

This is the **Cube Toolkit** codebase — a Django app that manages events, members, and mailouts for the Cube Microplex cinema in Bristol. It also supports the Star and Shadow cinema via a separate settings layer.

Before doing anything else, read:
- [docs/ONBOARDING.md](docs/ONBOARDING.md) — project structure, apps, Django primer, how to run with Docker
- [docs/BRANCH_NOTES.md](docs/BRANCH_NOTES.md) — detailed audit of differences between the `master` and `s+s` branches

The current branch is **`master`** (Django 5.2 LTS, Wagtail 6.3, Python 3, no Celery).

---

## Standing rule: keep docs/ in sync with the code

**After every code change, update the relevant docs.**

- Bug fixes → mark resolved in [docs/TASKS.md](docs/TASKS.md) (move completed item to [docs/ARCHIVE.md](docs/ARCHIVE.md)); update [docs/ROADMAP.md](docs/ROADMAP.md) status table
- New features implemented → mark ✅ in [docs/TASKS.md](docs/TASKS.md), move to [docs/ARCHIVE.md](docs/ARCHIVE.md)
- New features proposed → add to [docs/TASKS.md](docs/TASKS.md) section 9.x with sizing label (🟢 XS / 🔵 S / 🟡 M / 🟠 L / 🔴 XL / ⛔ XXL)
- Data model changes → update [docs/SPEC.md](docs/SPEC.md) section 8 (data model) and ER diagram
- New external system dependencies → update [docs/SPEC.md](docs/SPEC.md) section 6 (external integrations)
- Workflow changes → update [docs/SPEC.md](docs/SPEC.md) section 4 (key workflows)
- Permission changes → update [docs/SPEC.md](docs/SPEC.md) section 2 (permission model)

Do not commit code changes without also committing the corresponding docs update in the same commit (or immediately following it).

---

## Current task: get the Star and Shadow site running on `master`

The `s+s` branch was the Star and Shadow production branch but ran Django 2.2 (EOL). The decision was made to start fresh from `master` (which is far more modern) and port the S+S-specific functionality across, rather than attempt a Django upgrade on the old branch.

The `s+s` branch is still available locally for reference (`git checkout s+s`, or inspect files with `git show s+s:path/to/file`).

### Step 1: Create `docker_settings_ss.py` ✓ done

`settings_ss.py` already exists and correctly sets all S+S venue config and feature flags (`MULTIROOM_ENABLED = True`, `MEMBERSHIP_EXPIRY_ENABLED = True`, etc.) — but it inherits from `settings_common.py`, which means it uses hardcoded database config and is not docker-friendly.

Create `toolkit/docker_settings_ss.py` that layers docker-specific config on top of the S+S settings:

```python
# toolkit/docker_settings_ss.py
import os

from toolkit.settings_ss import *

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.environ.get("DB_NAME", "toolkit"),
        "USER": os.environ.get("DB_USER", "toolkit"),
        "PASSWORD": os.environ.get("DB_PASSWORD", "devserver_db_password"),
        "HOST": os.environ.get("DB_HOST", "mariadb"),
        "PORT": os.environ.get("DB_PORT", "3306"),
        "CONN_MAX_AGE": 10,
        "OPTIONS": {
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

SECRET_KEY = os.environ.get("SECRET_KEY", "insecure-dev-secret-key-change-in-production")

# Log to console only inside the container
del LOGGING["handlers"]["file"]
LOGGING["loggers"]["toolkit"]["handlers"] = ["console"]
LOGGING["root"] = {
    "handlers": ["console"],
    "level": "DEBUG",
}
```

### Step 2: Update `docker-compose.yml` to use S+S settings ✓ done

The `docker-compose.yml` on `master` currently points at the Cube settings. Update the `toolkit` service environment to use the new S+S docker settings:

```yaml
DJANGO_SETTINGS_MODULE: toolkit.docker_settings_ss
```

Also note: `master` doesn't use Celery (it uses a custom `mailerd` daemon), so the `REDIS_URL` environment variable in docker-compose is not needed and the Redis service doesn't exist here. Don't add one.

After these two steps (both done), `docker compose up --build` should boot the S+S site.

Note: `wsgi.py` was also updated to use `os.environ.setdefault` instead of hardcoding `toolkit.settings`, so the `DJANGO_SETTINGS_MODULE` env var now correctly overrides it for gunicorn too. The Dockerfile symlink and collectstatic step were updated to point at `docker_settings_ss.py`.

### Known bugs found during first login (fix before step 3 features)

Two 500 errors were triggered immediately after first login (18 Feb 2026):

**Bug A: `/toolkit/` index page crashes — missing mailer URL namespace**

Error: `KeyError: 'mailer'` / `NoReverseMatch`

Root cause: `toolkit/index/templates/toolkit_index.html` line 79 uses
`{% url "mailer:jobs-list" %}`. The Cube URL file (`urls.py`) includes mailer
URLs under the `mailer` namespace, but the S+S URL file (`urls_flat.py`) does
not. Fix: add to `urls_flat.py`:

```python
import toolkit.mailer.urls
# ...
re_path(r"^mailout/", include(toolkit.mailer.urls)),
```

**Bug B: Wagtail CMS page creation crashes — `translation_key` column too short**

Error: `MySQLdb.DataError: (1406, "Data too long for column 'translation_key' at row 1")`

Triggered by: `/toolkit/cms/pages/add/content/basicarticlepage/2/`

Root cause: Wagtail's `translation_key` field on the `wagtailcore_page` table is
a UUIDField. In MariaDB with strict mode (`STRICT_TRANS_TABLES`), Django's
UUIDField stores as varchar(32) (no dashes), but Wagtail 6 appears to generate a
36-char UUID string (with dashes), which overflows the column. This may be a
Wagtail/MariaDB compatibility bug, or a schema mismatch from the migration run.

Investigation steps:

1. Check the column definition: `docker compose exec mariadb mariadb -u toolkit -p toolkit -e "SHOW COLUMNS FROM wagtailcore_page LIKE 'translation_key';"`
2. Search Wagtail issue tracker for "translation_key MariaDB DataError"
3. Possible fixes: disable strict mode for UUIDs, or set `WAGTAIL_I18N_ENABLED = False` if the field is only used by i18n features

---

### Step 3: Port S+S-specific features from the `s+s` branch (ongoing)

These features exist on the `s+s` branch but not on `master`. They need to be evaluated and ported in priority order. See [BRANCH_NOTES.md](BRANCH_NOTES.md) for full details on each.

**High priority (core S+S functionality):**

1. **`Volunteer.user` OneToOneField** — On `s+s`, every volunteer has a linked Django `User`. Creating a volunteer auto-creates a user and emails them credentials. Retiring a volunteer sets `user.is_active = False`. This is the biggest structural difference. On `master`, there is no `Volunteer.user` field.

2. **Django admin** — On `s+s`, `django.contrib.admin` is enabled in `INSTALLED_APPS` with custom `ModelAdmin` classes for `User`, `Member`, `Volunteer`, and `Room`. The toolkit index shows an "Administration backend" link when `VENUE['show_user_management']` is `True` (which it is in `settings_ss.py`).

3. **Programmer permission group** — The `create_programmer_permission` management command (`toolkit/toolkit_auth/management/commands/create_programmer_permission.py`) creates a `Programmers` group. Volunteers assigned the `Programmer` role are added to this group automatically.

**Medium priority (settings/display tweaks):**

4. **`SHOW_ARCHIVE_IMAGES` / `IMAGES_START_DATE`** — `s+s` hides event images for showings before a configurable date. Add these to `settings_ss.py` on master:
   ```python
   SHOW_ARCHIVE_IMAGES = False
   IMAGES_START_DATE = "1 May 2018"
   ```
   Check `toolkit/diary/public_views.py` on master to see if it already reads `IMAGES_START_DATE` (it may not — the setting was added on `s+s`).

5. **`Showing.rota_notes` field size** — On `s+s` this was extended from 1024 to 4096 characters. On `master` it is still 1024. Check whether the live S+S database has entries longer than 1024 chars before migrating.

6. **`Member.email` mandatory** — On `s+s`, email is mandatory on the `Member` model. On `master` it is `blank=True`. This matters if you're importing S+S member data.

**Lower priority (can be added later):**

7. **Expired members view** — `/members/expired/` exists on `s+s`, not on `master`.
8. **`view_diary_json` endpoint** — Experimental, existed on `s+s`.
9. **Legacy URL redirects** — S+S's old website had a different URL structure; some redirects existed in `s+s`.
10. **`utils/mailoutomatic.py`** — Standalone script that auto-sends mailouts on a schedule. Exists on `s+s`, not on `master`.

### Step 4: Compare S+S templates (not done yet)

The `star_and_shadow_templates/` directory exists on both branches but differs in two files:
- `star_and_shadow_templates/view_event.html`
- `star_and_shadow_templates/view_showing_index.html`

Compare them with:
```bash
git diff s+s origin/master -- star_and_shadow_templates/
```

Decide which version is correct (or merge them). The `master` version should be treated as the baseline since it's built for Wagtail 6 / Bootstrap 4.

---

## Docker setup on `master`

**How master's Docker works** (different from what was built on `s+s`):

- Multi-stage Dockerfile: `base` → `build` (compiles wheels) → `run` (lean final image)
- Non-root user (`toolkit:toolkit`)
- Runs via gunicorn, not Django's dev server
- Entrypoint: `containerconfig/tk_run.sh` — accepts `gunicorn` or `mailerd` as argument
- Settings file: symlinks `toolkit/settings.py` → `toolkit/docker_settings.py` at build time
- Static files: collected during Docker build (`collectstatic` in `RUN` step)
- Requirements split into `requirements/base.txt`, `requirements/dev.txt`, `requirements/docker.txt`

**To build and run the Cube site:**
```bash
docker compose up --build
```

**To run the S+S site (after Step 1 and 2 above):**
```bash
# Change DJANGO_SETTINGS_MODULE in docker-compose.yml, then:
docker compose up --build
```

**To create initial users after first boot:**
```bash
docker compose exec toolkit /venv/bin/python3 manage.py configure_toolkit_users
```

**To run tests:**
```bash
docker compose exec toolkit /venv/bin/python3 manage.py test --settings=toolkit.test_settings
# Or locally:
tox
```

---

## Step 5: Create a `seed_dev_data` management command

A Django management command that populates the database with realistic but anonymised sample data, so developers can exercise the app without needing a copy of the live database.

**Source material:** `sample_html_from_current_site/` contains two saved HTML pages from the live S+S site (captured 18 Feb 2026):

- `Star and Shadow Programme.html` — the public programme page, showing events with titles, dates, tags, and copy snippets. Events visible include: Volunteer Hangout (party tag), Volunteer Induction (volunteer + induction tags), Seeking A Friend For The End Of The World (film tag), and more across February–March 2026.

- `Star and Shadow role rota.html` — the internal rota view, showing showings with their full role lists and rota notes. Real volunteer first+last names are visible and **must be anonymised**. The rota notes text is operational, not personal, and can be kept verbatim or lightly edited.

**Data to extract and seed:**

1. **Roles** — from the rota HTML, the following role names appear (strip the trailing `-N` suffix which is just the slot number):
   - Keyholder, Bar Shadow, Bar Staff - Shift 1, Box Office - Admission Tickets, Programmer, Projectionist (trained shadowing), Projectionist - Video/DVD, Usher - Fire Trained, Facilitator, Facilitator Shadow, Minute taker, Inductor - 1 (trained), Inductor - 2 (shadowing), Trainee (inducted)
   - Mark `Keyholder` and `Programmer` as `standard=True` (appears on the main rota list)

2. **EventTags** — from programme nav and event tags in the HTML:
   `film`, `music`, `workshop`, `exhibition`, `performance`, `meeting`, `induction`, `volunteer`, `party`, `training-for-volunteers`, `online`, `subtitles`, `closed-captions`

3. **Volunteers** — create ~15 volunteers with plausible but fictional names (drawn from the feel of the S+S community: a mix of everyday British names, international names, nicknames). Real names seen in the HTML — Joseph De-Haan, Jacob Easton, Siobhan Redmond, Rachel Heads, seth, Ana Barbir, Lydia Wildey, Joseph Goin, Ivan Flores, Nadia Murphy, Mark Loveridge — should be replaced with different invented names. Create corresponding `Member` records (required by the data model).

4. **Events and Showings** — create ~10 events spread across a 6-week window centred on `now + 2 weeks` (so the diary always has upcoming events). Use event titles and copy from the programme HTML as inspiration, lightly adapted. Assign 1–2 showings per event. Apply appropriate tags.

5. **Rota entries** — for each showing, create `RotaEntry` records assigning fictional volunteers to appropriate roles. Leave a few slots deliberately empty (realistic). Use the rota HTML's assignments as the template for which roles go with which event types.

6. **Rota notes** — populate `Showing.rota_notes` with text drawn verbatim or lightly adapted from the rota HTML. The notes in the source are characterful and reflect the real S+S voice well:
   - *"Opening the venue for all volunteers to use as they will. Workshop, print room..."*
   - *"A chill get together for all volunteers, perfect if you are new or experienced."*
   - *"Please feel free to join us all and share your experiences of volunteering..."*

**Command location:** `toolkit/util/management/commands/seed_dev_data.py`

**Command behaviour:**

- Should be idempotent: running it twice should not duplicate data (use `get_or_create` throughout)
- Should print a summary of what was created
- Should be safe to run against an empty database after `migrate`
- Add a `--wipe` flag that clears existing diary/member data before seeding (useful for resetting dev state)

**Usage after first boot:**

```bash
docker compose exec toolkit /venv/bin/python3 manage.py configure_toolkit_users
docker compose exec toolkit /venv/bin/python3 manage.py seed_dev_data
```

---

## Key file locations

| Purpose | File |
|---|---|
| Cube docker settings | [toolkit/docker_settings.py](toolkit/docker_settings.py) |
| S+S settings (venue config, feature flags) | [toolkit/settings_ss.py](toolkit/settings_ss.py) |
| S+S docker settings | [toolkit/docker_settings_ss.py](toolkit/docker_settings_ss.py) |
| Shared base settings | [toolkit/settings_common.py](toolkit/settings_common.py) |
| Container entrypoint | [containerconfig/tk_run.sh](containerconfig/tk_run.sh) |
| Dev docker compose | [docker-compose.yml](docker-compose.yml) |
| S+S-specific templates | [star_and_shadow_templates/](star_and_shadow_templates/) |
| Branch comparison | [docs/BRANCH_NOTES.md](docs/BRANCH_NOTES.md) |
| System specification | [docs/SPEC.md](docs/SPEC.md) |
| Development roadmap | [docs/ROADMAP.md](docs/ROADMAP.md) |
| Open tasks / bugs | [docs/TASKS.md](docs/TASKS.md) |
