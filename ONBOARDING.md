# Cube Toolkit — Developer Onboarding

This doc is for people new to the project who want to get a local dev environment running and understand how the codebase is structured. It assumes no prior Django experience.

---

## What Is This?

Cube Toolkit is the internal web application that powers [Cube Microplex](https://www.cubecinema.com/), a volunteer-run cinema in Bristol. It handles:

- **Event diary** — scheduling events, managing showings, volunteer rotas
- **Member database** — tracking members, volunteers, and mailout subscriptions
- **Email mailouts** — composing and sending programme announcements to members
- **CMS** — public-facing content pages, powered by [Wagtail](https://wagtail.org/)

It's a [Django](https://www.djangoproject.com/) application backed by a MariaDB (MySQL-compatible) database.

---

## Getting Started with Docker

Docker is the recommended way to run the app locally. You don't need to install Python, MySQL, or any other dependencies on your machine.

**Prerequisites:** [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/) (both included in Docker Desktop).

### 1. Build and start the services

```bash
docker compose up --build
```

This builds the app image and starts two containers:
- `toolkit` — the Django web app, served by gunicorn on port 8000
- `mariadb` — the database

On first run, the app container will automatically run database migrations before starting. Give it ~30 seconds.

### 2. Open the app

Visit [http://localhost:8000](http://localhost:8000)

You'll see the diary (event list), which is public. The internal toolkit is at [http://localhost:8000/toolkit/](http://localhost:8000/toolkit/) and requires a login.

### 3. Create an admin user

In a separate terminal:

```bash
docker compose exec toolkit /venv/bin/python manage.py createsuperuser
```

Follow the prompts. You can then log in at [http://localhost:8000/auth/login](http://localhost:8000/auth/login).

### 4. Stop the services

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

**Settings** live in `toolkit/settings_*.py` files. Django reads whichever one is pointed to by the `DJANGO_SETTINGS_MODULE` environment variable. In Docker, this is set to `toolkit.docker_settings`.

**Migrations:** whenever someone changes a model, they run `manage.py makemigrations` to generate a migration file, then `manage.py migrate` to apply it. The Docker entrypoint runs `migrate` automatically on startup, so you shouldn't need to think about this for day-to-day dev.

---

## Project Structure

```
cubetoolkit/
├── toolkit/                  # The Django project (all Python code lives here)
│   ├── diary/                # App: event scheduling and volunteer rotas
│   ├── members/              # App: member and volunteer database
│   ├── mailer/               # App: email mailout system
│   ├── content/              # App: Wagtail CMS pages
│   ├── index/                # App: the internal dashboard/index page
│   ├── toolkit_auth/         # App: login/logout and auth decorators
│   ├── util/                 # Shared utilities (image processing, context processors)
│   │
│   ├── settings_common.py    # Settings shared across all environments
│   ├── docker_settings.py    # Overrides for Docker (reads DB config from env vars)
│   ├── devserver_settings.py # Overrides for running locally without Docker
│   ├── test_settings.py      # Overrides for the test suite (uses SQLite)
│   ├── settings_ss.py        # Variant config for the Star & Shadow venue
│   │
│   ├── urls.py               # Top-level URL router
│   └── static_common/        # CSS/JS shared across apps
│
├── templates/                # Base HTML templates
├── media/                    # User-uploaded files (images, PDFs, etc.)
├── containerconfig/
│   └── tk_run.sh             # Docker container entrypoint script
│
├── requirements/
│   ├── base.txt              # Core Python dependencies
│   ├── dev.txt               # Adds dev tools (debug toolbar, black, fabric)
│   └── docker.txt            # Adds gunicorn, mysqlclient
│
├── Dockerfile                # Multi-stage Docker build
├── docker-compose.yml        # Dev environment (app + database)
├── manage.py                 # Django's CLI tool (always use this to run commands)
├── runtests                  # Shortcut script to run the test suite
└── tox.ini                   # Test automation config (runs black + tests)
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
- [toolkit/diary/models.py](toolkit/diary/models.py) — all the data models (739 lines; start here to understand the domain)
- [toolkit/diary/public_views.py](toolkit/diary/public_views.py) — the public-facing event listing
- [toolkit/diary/edit_views.py](toolkit/diary/edit_views.py) — the event editing interface (login required)
- [toolkit/diary/urls.py](toolkit/diary/urls.py) — URL routing for diary views

URL prefixes: `/programme/` (public), `/diary/` (editing interface)

### `members` — Member and Volunteer Database

Manages people who are members or volunteers of the Cube. Key concepts:

- **Members** — people with a mailing list subscription and optionally a membership
- **Volunteers** — a subset of members who take on roles in the rota
- **Training records** — tracks which volunteers are trained for which tasks

Key files:
- [toolkit/members/models.py](toolkit/members/models.py) — Member, Volunteer, TrainingRecord models
- [toolkit/members/member_views.py](toolkit/members/member_views.py) — search, view, edit members
- [toolkit/members/volunteer_views.py](toolkit/members/volunteer_views.py) — volunteer rota interface

URL prefixes: `/members/`, `/volunteers/`

Note: the page to add a new member is IP-restricted (only accessible from within the Cube's network). This is configured via `CUBE_IP_ADDRESSES` in settings.

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
/auth/login               → Login page
/cms/                     → Wagtail CMS admin
/pages/                   → Wagtail public pages
/id/<id>/                 → Single event by ID (public)
```

The full routing is in [toolkit/urls.py](toolkit/urls.py).

---

## Settings

Settings are layered. `settings_common.py` defines everything, and environment-specific files import it and override what they need.

| File | Used when |
|---|---|
| `docker_settings.py` | Running in Docker (reads `DB_*` and `SECRET_KEY` from environment) |
| `devserver_settings.py` | Running locally without Docker |
| `test_settings.py` | Running the test suite (SQLite, fast password hashing) |
| `settings_ss.py` | Deploying for the Star & Shadow venue |

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

The test suite uses SQLite (not MariaDB) so it doesn't need Docker:

```bash
# If you have a local Python venv set up:
./runtests

# From inside Docker:
docker compose exec toolkit /venv/bin/python manage.py test --settings=toolkit.test_settings

# Run a specific app's tests:
./runtests toolkit.diary

# Run a specific test file:
./runtests toolkit.members.tests.test_members
```

Run `tox` to replicate what CI does (formatting check + full test suite):

```bash
tox
```

Tests are in `toolkit/*/tests/` directories. The `diary` and `members` apps have the most extensive suites.

### Code formatting

The project uses [black](https://black.readthedocs.io/) with a line length of 79 characters. Run it before committing:

```bash
black --line-length 79 toolkit/
```

---

## How Docker Works Here

The [Dockerfile](Dockerfile) uses a multi-stage build:

1. **`base` stage** — Debian with Python and runtime system libraries
2. **`build` stage** — adds build tools and compiles Python dependency wheels
3. **`run` stage** — final image; copies wheels from build stage, installs them, copies app code

The entrypoint script is [containerconfig/tk_run.sh](containerconfig/tk_run.sh). It:
1. Waits for the database to be available
2. Runs `manage.py migrate` to apply any pending migrations
3. Starts either `gunicorn` (web app) or `mailerd` (background email daemon)

In development (`docker-compose.yml`), only the web app runs. In production (`docker-compose-production.yml`), the mailerd daemon runs in a separate container.

---

## Key Concepts and Patterns

**Custom QuerySet methods on models:** Rather than scattering filtering logic across views, models define named query methods. For example, `Showing.objects.public().start_in_future()` chains filters to get upcoming public showings. Look for `QuerySet` subclasses in `models.py` files.

**Read-only model protection:** Some database records (system `Role` objects, standard `EventTag` objects) are marked `read_only = True`. The model's `save()` and `delete()` methods check this flag and silently block changes. This is an application-level guard, not a database constraint.

**Multi-venue support:** The project can also power the Star & Shadow venue by using `settings_ss.py` instead of the default settings. Feature flags like `MULTIROOM_ENABLED` and `MEMBERSHIP_EXPIRY_ENABLED` toggle venue-specific behaviour. The `VENUE` dict in `settings_common.py` holds venue-specific strings (name, email addresses, social media links).

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
docker compose exec toolkit /venv/bin/python3 manage.py createsuperuser
docker compose exec toolkit /venv/bin/python3 manage.py seed_dev_data
```

> **Note:** `createsuperuser` requires an interactive terminal; run it in a real shell,
> not piped. Alternatively, use the Django shell:
>
> ```bash
> docker compose exec toolkit /venv/bin/python3 manage.py shell -c "
> from django.contrib.auth.models import User
> u, _ = User.objects.get_or_create(username='admin')
> u.set_password('admin'); u.is_staff = True; u.is_superuser = True; u.save()
> "
> ```

---

## Next Steps

- Browse the diary models: [toolkit/diary/models.py](toolkit/diary/models.py)
- Read through a view to see the request/response pattern: [toolkit/diary/public_views.py](toolkit/diary/public_views.py)
- Look at a test to understand how the app is exercised: [toolkit/diary/tests/](toolkit/diary/tests/)
- Check [BUGS.txt](BUGS.txt) for known issues and pending work
