# Cube Toolkit — Developer Onboarding

This doc is for people new to the project who want to get a local dev environment running and understand how the codebase is structured. It assumes no prior Django experience.

---

## TL;DR

```bash
# 1. Clone and enter the repo
git clone https://github.com/jdkram/sns-toolkit.git
cd sns-toolkit

# 2. Build and start (wait until you see "Starting development server at http://0.0.0.0:8000/")
docker compose up --build
```

Once you see `Starting development server at http://0.0.0.0:8000/` in the output, open a second terminal and run:

```bash
cd sns-toolkit

# 3. Create accounts and seed data
docker compose exec toolkit /venv/bin/python3 manage.py configure_toolkit_users --password DevPassword1!
docker compose exec toolkit /venv/bin/python3 manage.py seed_dev_data
docker compose exec toolkit /venv/bin/python3 manage.py seed_labs_data
```

Visit [http://localhost:8000](http://localhost:8000). Log in at [http://localhost:8000/auth/login](http://localhost:8000/auth/login) — username `admin`, password `DevPassword1!`.

> If you start with `docker compose up --build -d` (detached), wait for migrations to finish before running the seed commands: `docker compose logs -f toolkit` and wait for the "Starting development server" line.

---

## What Is This?

Cube Toolkit is the internal web application that powers [Cube Microplex](https://www.cubecinema.com/) and [Star and Shadow Cinema](https://www.starandshadow.org.uk/), both volunteer-run cinemas. It handles:

- **Event diary** — scheduling events, managing showings, volunteer rotas
- **Member database** — tracking members, volunteers, and mailout subscriptions
- **Email mailouts** — composing and sending programme announcements to members
- **CMS** — public-facing content pages, powered by [Wagtail](https://wagtail.org/)

It's a [Django](https://www.djangoproject.com/) application backed by a MariaDB (MySQL-compatible) database.

---

## Getting Started

### Prerequisites

- [Git](https://git-scm.com/)
- [Docker](https://docs.docker.com/engine/install/) and the [Compose plugin](https://docs.docker.com/compose/install/)

**Linux (Mint, Ubuntu, Debian):** Install Docker Engine and the Compose plugin via your package manager or the official install script. Docker Desktop is optional and not required. Follow [the official Linux install guide](https://docs.docker.com/engine/install/ubuntu/) for your distro, then [add your user to the `docker` group](https://docs.docker.com/engine/install/linux-postinstall/) so you can run `docker` without `sudo`. **You will need to log out and back in for the group change to take effect.**

**Mac / Windows:** [Docker Desktop](https://docs.docker.com/desktop/) includes everything you need.

### 1. Clone the repository

```bash
git clone https://github.com/jdkram/sns-toolkit.git
cd sns-toolkit
```

### Which venue are you developing for?

This repo powers two venues. The default Docker setup runs **Star and Shadow Cinema** settings (`toolkit.docker_settings_ss`).

If you are developing for **Cube Microplex** instead, edit `docker-compose.yml` and change:

```yaml
DJANGO_SETTINGS_MODULE: "toolkit.docker_settings_ss"
```

to:

```yaml
DJANGO_SETTINGS_MODULE: "toolkit.docker_settings"
```

Everything else in this guide applies to both venues.

### 2. Build and start the services

```bash
docker compose up --build
```

This builds the app image and starts two containers:
- `toolkit` — the Django web app, served by Django's development server on port 8000
- `mariadb` — the database

On first run, the app container will automatically run database migrations before starting. Give it ~30 seconds.

### 3. Open the app

Visit [http://localhost:8000](http://localhost:8000)

You'll see the diary (event list), which is public. The internal toolkit is at [http://localhost:8000/toolkit/](http://localhost:8000/toolkit/) and requires a login.

### 4. Create demo user accounts and seed sample data

Run these two commands in a separate terminal:

```bash
# Create demo accounts at each permission tier
docker compose exec toolkit /venv/bin/python3 manage.py configure_toolkit_users --password DevPassword1!

# Populate the database with sample events, volunteers, and roles
docker compose exec toolkit /venv/bin/python3 manage.py seed_dev_data

# Populate labs app data (collectives, jobs, donations, room notes)
# Run after seed_dev_data — it depends on rooms being present
docker compose exec toolkit /venv/bin/python3 manage.py seed_labs_data
```

`configure_toolkit_users --password` creates all demo accounts non-interactively. Log in at [http://localhost:8000/auth/login](http://localhost:8000/auth/login) with any of these:

| Username | Permission tier | What they can do |
| --- | --- | --- |
| `admin` | **Panopticon** (superuser) | Everything — edit events, manage roles, volunteers, members, Wagtail CMS |
| `programmer`, `programmer2` | **Programmer** | Edit events, manage templates and tags; cannot manage roles, volunteers, or members |
| `volunteer` … `volunteer5` | **Volunteer** | Edit the rota only |

> **Password for all dev accounts:** `DevPassword1!`
> These are intentionally the same password — for local development only. Never use `--password` in production.

For production setup (interactive password prompts per account):

```bash
docker compose exec toolkit /venv/bin/python3 manage.py configure_toolkit_users
```

### 5. Stop the services

```bash
docker compose down
```

Data persists across restarts in Docker volumes (`media_data` and `mariadb_data`). To wipe everything and start fresh:

```bash
docker compose down --volumes
```

### Useful Docker commands

```bash
# View logs
docker compose logs -f

# Open a Python shell inside the container
docker compose exec toolkit /venv/bin/python manage.py shell

# Run a management command
docker compose exec toolkit /venv/bin/python manage.py <command>

# Run the test suite (see Testing section)
docker compose exec toolkit /venv/bin/python manage.py test --settings=toolkit.test_settings
```

### Edit / reload cycle

The source code is bind-mounted into the container, so the running container always sees your local files directly. No rebuild is needed for most changes — the development server auto-reloads.

| What changed | What to do |
|---|---|
| Python files (views, models, forms…) | Nothing — Django reloads automatically |
| Templates (`.html`) | Nothing — debug mode disables template caching |
| CSS or JS (static files) | Nothing — the dev server serves static files directly from source |
| New Python dependency | `docker compose up --build -d` (must rebuild) |
| Dockerfile or `tk_run.sh` | `docker compose up --build -d` (must rebuild) |

**Running management commands:**

```bash
# Seed dev data (--wipe clears existing data first)
docker compose exec toolkit /venv/bin/python3 manage.py seed_dev_data --wipe

# Run migrations (happens automatically on start, but you can trigger manually)
docker compose exec toolkit /venv/bin/python3 manage.py migrate
```

---

## A Minimal Django Primer

If you've never used Django, here's the mental model you need. You can skip this if you're familiar.

Django organises code into **apps** — self-contained modules, each responsible for a feature area. An app typically contains:

| File | Purpose |
|---|---|
| `models.py` | Python classes that map to database tables. Each class is a table; each attribute is a column. |
| `views.py` | Functions (or classes) that handle HTTP requests and return responses. |
| `urls.py` | A list of URL patterns that map URLs to view functions. |
| `forms.py` | Classes that handle HTML form parsing, validation, and rendering. |
| `templates/` | HTML files with `{{ variable }}` and `{% tag %}` syntax for dynamic content. |
| `tests/` | Automated tests. |
| `migrations/` | Auto-generated files that track changes to models and apply them to the database. Never edit these by hand. |

**How a request flows:**

```
Browser → URL router (urls.py) → View function (views.py)
                                       ↕
                                 Models (models.py) ↔ Database
                                       ↓
                                 Template (templates/) → HTML response
```

**Settings** live in `toolkit/settings_*.py` files. Django reads whichever one is pointed to by the `DJANGO_SETTINGS_MODULE` environment variable. In Docker, this is set to `toolkit.docker_settings_ss`.

**Migrations:** whenever someone changes a model, they run `manage.py makemigrations` to generate a migration file, then `manage.py migrate` to apply it. The Docker entrypoint runs `migrate` automatically on startup, so you shouldn't need to think about this for day-to-day dev.

---

## Project Structure

```
sns-toolkit/                  # Repo root
├── toolkit/                  # The Django project (all Python code lives here)
│   ├── diary/                # App: event scheduling and volunteer rotas
│   ├── members/              # App: member and volunteer database
│   ├── mailer/               # App: email mailout system
│   ├── content/              # App: Wagtail CMS pages
│   ├── index/                # App: the internal dashboard/index page
│   ├── labs/                 # App: experimental / work-in-progress features
│   ├── toolkit_auth/         # App: login/logout and auth decorators
│   ├── util/                 # Shared utilities (image processing, context processors)
│   │
│   ├── settings_common.py    # Settings shared across all environments
│   ├── settings_ss.py        # Star & Shadow venue config (imported by docker_settings_ss.py)
│   ├── docker_settings_ss.py # Docker settings for Star & Shadow (default)
│   ├── docker_settings.py    # Docker settings for Cube Microplex
│   ├── devserver_settings.py # Settings for running locally without Docker
│   ├── test_settings.py      # Settings for the test suite (uses SQLite)
│   │
│   ├── urls.py               # Top-level URL router
│   └── static_common/        # CSS/JS shared across apps
│
├── templates/                # Base HTML templates
├── star_and_shadow_templates/ # S+S-specific template overrides
├── media/                    # User-uploaded files (images, PDFs, etc.)
├── containerconfig/
│   └── tk_run.sh             # Docker container entrypoint script
│
├── requirements/
│   ├── base.txt              # Core Python dependencies
│   ├── dev.txt               # Adds dev tools (debug toolbar, black, fabric)
│   └── docker.txt            # Adds gunicorn, mysqlclient
│
├── Dockerfile                    # Multi-stage Docker build
├── docker-compose.yml            # Dev environment (app + database)
├── docker-compose.override.yml   # Dev overrides (applied automatically)
├── docker-compose-production.yml # Production deployment
├── manage.py                     # Django's CLI tool (always use this to run commands)
└── VERSION                       # Canonical version string
```

---

## The Django Apps in Detail

### `diary` — Events and Rotas

This is the largest and most central app. It manages:

- **Events** — a film screening, a gig, a meeting, etc.
- **Showings** — a specific date/time for an event (one event can have multiple showings)
- **Roles** — volunteer jobs for a showing (e.g. "Box Office", "Projectionist")
- **Rota entries** — which volunteer is doing which role for which showing
- **Media items** — images attached to events
- **Event tags** — categorisation (e.g. "film", "live music")
- **Event templates** — reusable defaults for recurring events

Key files:
- [toolkit/diary/models.py](toolkit/diary/models.py) — all the data models (start here to understand the domain)
- [toolkit/diary/public_views.py](toolkit/diary/public_views.py) — the public-facing event listing
- [toolkit/diary/edit_views.py](toolkit/diary/edit_views.py) — the event editing interface (login required)
- [toolkit/diary/urls.py](toolkit/diary/urls.py) — URL routing for diary views

URL prefixes: `/programme/` (public), `/diary/` (editing interface)

### `members` — Member and Volunteer Database

Manages people who are members or volunteers. Key concepts:

- **Members** — people with a mailing list subscription and optionally a membership
- **Volunteers** — a subset of members who take on roles in the rota
- **Training records** — tracks which volunteers are trained for which tasks

Key files:
- [toolkit/members/models.py](toolkit/members/models.py) — Member, Volunteer, TrainingRecord models
- [toolkit/members/member_views.py](toolkit/members/member_views.py) — search, view, edit members
- [toolkit/members/volunteer_views.py](toolkit/members/volunteer_views.py) — volunteer rota interface

URL prefixes: `/members/`, `/volunteers/`

Note: the page to add a new member is IP-restricted (only accessible from within the venue's network). This is configured via `CUBE_IP_ADDRESSES` in settings.

### `mailer` — Email Mailouts

Handles sending programme announcement emails to the member list.

- **MailoutJob** — represents a mailout task, with a state machine: `PENDING → SENDING → SENT` (or `CANCELLED`/`FAILED`)
- A background daemon (`mailerd`) picks up pending jobs and sends them
- In production, `mailerd` runs as a separate container (see `docker-compose-production.yml`)

Key files:
- [toolkit/mailer/models.py](toolkit/mailer/models.py) — MailoutJob model and state machine
- [toolkit/mailer/sender.py](toolkit/mailer/sender.py) — email sending logic
- [toolkit/mailer/mailerd.py](toolkit/mailer/mailerd.py) — background daemon

URL prefix: `/mailout/`

### `content` — Wagtail CMS

Public-facing content pages (About, Contact, etc.) managed through [Wagtail](https://wagtail.org/), a Django-based CMS. The Wagtail admin is at `/cms/`.

### `index` — Internal Dashboard

The internal toolkit homepage at `/toolkit/`. Just a list of navigation links organised into categories (`IndexLink`, `IndexCategory` models).

### `labs` — Experimental Features

Work-in-progress or venue-specific features under active development. URL prefix: `/labs/`

### `toolkit_auth` — Authentication

Login/logout views and custom decorators used throughout the codebase to protect views. URL prefix: `/auth/`

---

## URL Map

```
/                         → Default diary view (public)
/programme/               → Public event listings
/diary/                   → Event editing (login required)
/members/                 → Member database (login required)
/volunteers/              → Volunteer rota (login required)
/mailout/                 → Mailout scheduling (login required)
/toolkit/                 → Internal dashboard (login required)
/labs/                    → Experimental features (login required)
/auth/login               → Login page
/cms/                     → Wagtail CMS admin
/doc/                     → Wagtail documents
/pages/                   → Wagtail public pages
/id/<id>/                 → Single event by ID (public)
/health/                  → Health check endpoint
```

The full routing is in [toolkit/urls.py](toolkit/urls.py).

---

## Permission Tiers

The toolkit has three access levels. When testing locally, use the corresponding demo account:

| Tier | Demo username | Django representation | What they see |
| --- | --- | --- | --- |
| **Volunteer** | `volunteer` … `volunteer5` | `diary.change_rotaentry` permission | Rota editing only. Cannot create/edit events or see member data. |
| **Programmer** | `programmer`, `programmer2` | `toolkit.write` + `toolkit.read` + `change_rotaentry`; member of `Programmers` group | Full diary editing: create/edit events and showings, manage templates and tags, see copy/terms reports. Cannot manage roles, volunteers, or members. |
| **Panopticon** | `admin` | `is_superuser = True` + all of the above | Everything: Programmer access plus role management, volunteer/member data, Wagtail CMS. |

**Key gate:** The "Edit roles" page (`/diary/edit/roles/`) requires `is_superuser`. Role deletion cascades silently to all rota assignments — it's too destructive for the Programmer tier.

The Programmer tier is granted by ticking the `Programmer` checkbox on a volunteer's profile (Panopticon only). This automatically adds the user to the `Programmers` Django group.

See [SPEC.md §2](SPEC.md#2-who-can-access-what--permission-model) for the full picture, and [TASKS.md §9.49](TASKS.md#949--permission-model-collective-ratification-needed-️) for the governance questions still awaiting collective ratification.

---

## Settings

Settings are layered. `settings_common.py` defines everything, and environment-specific files import it and override what they need.

| File | Used when |
|---|---|
| `docker_settings_ss.py` | Running in Docker for **Star and Shadow** — the default for `docker compose up` |
| `docker_settings.py` | Running in Docker for **Cube Microplex** |
| `devserver_settings.py` | Running locally without Docker |
| `test_settings.py` | Running the test suite (SQLite, fast password hashing) |
| `settings_ss.py` | Base Star and Shadow config (imported by `docker_settings_ss.py`) |

The Docker settings expect these environment variables (with defaults from `docker-compose.yml`):

| Variable | Default | Purpose |
|---|---|---|
| `DB_NAME` | `toolkit` | Database name |
| `DB_USER` | `toolkit` | Database user |
| `DB_PASSWORD` | `devserver_db_password` | Database password |
| `DB_HOST` | `mariadb` | Database hostname |
| `DB_PORT` | `3306` | Database port |
| `SECRET_KEY` | `really_bad_django_secret_key` | Django secret key (change in production!) |

---

## Running Tests

All tests must be run inside the Docker container. The project dependencies (including C extensions and `mysqlclient`) are only installed inside the image — do not try to run tests on the host.

```bash
# Run the full test suite
docker compose exec toolkit /venv/bin/python manage.py test --settings=toolkit.test_settings

# Run a specific app's tests
docker compose exec toolkit /venv/bin/python manage.py test toolkit.diary --settings=toolkit.test_settings

# Run a specific test file
docker compose exec toolkit /venv/bin/python manage.py test toolkit.members.tests.test_members --settings=toolkit.test_settings
```

Tests are in `toolkit/*/tests/` directories. The `diary` and `members` apps have the most extensive suites.

### Code formatting

The project uses [black](https://black.readthedocs.io/) with a line length of 79 characters. Run it before committing:

```bash
docker compose exec toolkit /venv/bin/black --line-length 79 toolkit/
```

To check formatting without making changes:

```bash
docker compose exec toolkit /venv/bin/black --line-length 79 --check toolkit/
```

---

## How Docker Works Here

The [Dockerfile](Dockerfile) uses a multi-stage build:

1. **`base` stage** — Debian with Python and runtime system libraries
2. **`build` stage** — adds build tools and compiles Python dependency wheels
3. **`run` stage** — final image; copies wheels from build stage, installs them, copies app code; runs `collectstatic` to bake static files into the image

The entrypoint script is [containerconfig/tk_run.sh](containerconfig/tk_run.sh). It:
1. Waits for the database to be available
2. Runs `manage.py migrate` to apply any pending migrations
3. Starts either `runserver` (dev), `gunicorn` (production), or `mailerd` (background email daemon)

**In development**, `docker-compose.yml` uses `tk_run runserver` — Django's built-in development server. This serves static files directly from source (no `collectstatic` step needed) and auto-reloads on code changes.

`docker-compose.override.yml` is applied automatically on top of `docker-compose.yml`. It adds extra bind mounts for `toolkit/` and `star_and_shadow_templates/` so that Python and template changes propagate into the running container immediately.

**In production**, `docker-compose-production.yml` uses `gunicorn` for the web app and `mailerd` in a separate container for sending email.

---

## Releases and Versioning

The project uses **calendar versioning**: `YYYY.MM.N` — year, month, sequence number within that month (e.g. `2026.03.1`). There's no semantic meaning to the numbers; the version just records when something was shipped.

### Where the version lives

The canonical version string is in the [`VERSION`](../VERSION) file at the repo root. It's read by `settings_common.py` and exposed to templates via the `venue` context processor as `{{ VERSION }}`. The dev watermark on the public site (`DEV · 2026.03.1`) is populated from this.

### Cutting a release

1. **Update `VERSION`** to the new version string:

   ```bash
   echo "2026.04.1" > VERSION
   ```

2. **Commit it** alongside any other changes for the release:

   ```bash
   git add VERSION
   git commit -m "chore(release): 2026.04.1"
   ```

3. **Tag the commit:**

   ```bash
   git tag v2026.04.1
   ```

4. **Push both the commit and the tag:**

   ```bash
   git push origin sns_2026_overhaul
   git push origin v2026.04.1
   ```

5. **Create a GitHub Release** (optional but useful for a changelog):

   Go to the repo on GitHub → **Releases** → **Draft a new release** → choose the tag you just pushed → write a short summary of what changed → **Publish release**.

---

## Key Concepts and Patterns

**Custom QuerySet methods on models:** Rather than scattering filtering logic across views, models define named query methods. For example, `Showing.objects.public().start_in_future()` chains filters to get upcoming public showings. Look for `QuerySet` subclasses in `models.py` files.

**Read-only model protection:** Some database records (system `Role` objects, standard `EventTag` objects) are marked `read_only = True`. The model's `save()` and `delete()` methods check this flag and silently block changes. This is an application-level guard, not a database constraint.

**Multi-venue support:** The project powers both Cube Microplex and Star & Shadow by swapping settings files. Feature flags like `MULTIROOM_ENABLED` and `MEMBERSHIP_EXPIRY_ENABLED` toggle venue-specific behaviour. The `VENUE` dict in `settings_common.py` holds venue-specific strings (name, email addresses, social media links).

**S+S template overrides:** Star & Shadow uses `star_and_shadow_templates/` to override specific base templates. Django's template loader checks this directory first when `docker_settings_ss.py` is active.

**Legacy copy:** Events imported from the old Perl system have a `legacy_copy` flag. The diary display code applies special regex-based processing to fix their HTML.

**Wagtail:** The CMS is a largely self-contained Django app managed separately from the custom apps above. If you need to understand it, the [Wagtail docs](https://docs.wagtail.org/) are the place to start.

---

## Troubleshooting

### "Duplicate column name" / migration crash on startup

**Symptom:** The `toolkit` container starts, runs `manage.py migrate`, and immediately crashes with an error like:

```text
django.db.utils.OperationalError: (1060, "Duplicate column name 'user_id'")
  Applying members.0009_volunteer_user...
```

The container then restarts and crashes again in a loop.

**Cause:** The MariaDB volume contains a stale `django_migrations` table from a previous development session — possibly one where a migration was renamed or replaced. Django sees the migration as unapplied (no record in `django_migrations`) and tries to run it, but the column or table already exists in the database from the old run.

**Fix:** Wipe the database volume and start fresh. In a dev environment this is safe — just re-run the seed command afterwards:

```bash
# Stop containers and delete volumes (wipes the database)
docker compose down --volumes

# Rebuild and start — migrations run clean from scratch
docker compose up --build

# Once running, recreate users and seed data
docker compose exec toolkit /venv/bin/python3 manage.py configure_toolkit_users --password DevPassword1!
docker compose exec toolkit /venv/bin/python3 manage.py seed_dev_data
docker compose exec toolkit /venv/bin/python3 manage.py seed_labs_data
```

### Archive view fails with `SELECT command denied … mysql.time_zone`

**Symptom:** Visiting `/programme/archive/` throws:

```
OperationalError: (1142, "SELECT command denied to user 'starandshadow'@'localhost' for table `mysql`.`time_zone`")
```

**Cause:** `USE_TZ = True` is set in `settings_common.py`. Django's generic archive views do timezone-aware date queries; on MariaDB/MySQL this translates to `CONVERT_TZ()` calls which read from the `mysql.time_zone` system tables. The app DB user doesn't have `SELECT` permission on those tables, or they haven't been populated.

**Fix (run as root on the database server):**

```bash
# Populate the system timezone tables from the OS (skip if already done)
mysql_tzinfo_to_sql /usr/share/zoneinfo | sudo mysql -u root mysql

# Grant read access to the app user
sudo mysql -u root -e "GRANT SELECT ON mysql.time_zone TO 'starandshadow'@'localhost'; FLUSH PRIVILEGES;"
```

In Docker dev (the DB container's root user has no password by default):

```bash
docker compose exec mariadb mariadb -u root -e "GRANT SELECT ON mysql.time_zone TO 'toolkit'@'%'; FLUSH PRIVILEGES;"
```

This is a one-time server configuration step that must be re-applied any time the database is rebuilt or the DB user is recreated.

---

## Next Steps

- Browse the diary models: [toolkit/diary/models.py](toolkit/diary/models.py)
- Read through a view to see the request/response pattern: [toolkit/diary/public_views.py](toolkit/diary/public_views.py)
- Look at a test to understand how the app is exercised: [toolkit/diary/tests/](toolkit/diary/tests/)
- Check [CURRENT_WORK.md](../CURRENT_WORK.md) for open bugs and current priorities
- Check [docs/TASKS.md](TASKS.md) for detailed task descriptions and feature specs
