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

## Current task: Port S+S-specific features from the `s+s` branch

The `s+s` branch was the Star and Shadow production branch but ran Django 2.2 (EOL). We have started fresh from `master` (which is far more modern) and ported the S+S-specific functionality across. Initial Docker setup and basic seed data are complete; focus is now on porting remaining features.

The `s+s` branch is available locally for reference (`git checkout s+s`, or inspect files with `git show s+s:path/to/file`). See [docs/BRANCH_NOTES.md](docs/BRANCH_NOTES.md) for full details on branch differences.

**Bug B** (Wagtail CMS page creation crash) is tracked in [docs/TASKS.md](docs/TASKS.md) and must be resolved before adding content via the CMS admin.

---

## Step 1: Port S+S-specific features (ongoing)

These features exist on the `s+s` branch but not on `master`. They need to be evaluated and ported in priority order.

### ✅ Already completed

1. **`Volunteer.user` OneToOneField** — Each volunteer now has a linked Django `User`. The `seed_dev_data` command auto-creates user accounts for all seed volunteers.

2. **Django admin integration** — `django.contrib.admin` is enabled in `INSTALLED_APPS` and configured in `settings_ss.py` with `"show_user_management": True`.

### ⚠️ Partially implemented

1. **Programmer permission group** — The `Programmers` group is created and populated by `seed_dev_data`, but the dedicated `create_programmer_permission` management command does not exist yet (current implementation is embedded in seed_dev_data).

### ❌ Not yet implemented

1. **`SHOW_ARCHIVE_IMAGES` / `IMAGES_START_DATE`** — Settings to hide event images before a configurable date. Not yet added to `settings_ss.py` or `toolkit/diary/public_views.py`.

2. **`Showing.rota_notes` field size** — Currently limited to 1024 characters; was extended to 4096 on `s+s`. Check live database before extending.

3. **`Member.email` mandatory** — Currently `blank=True`; should be `blank=False` for S+S to enforce email on all members.

4. **Custom Django admin `ModelAdmin` classes** — Django admin is enabled but uses default list views, not custom admin classes for User, Member, Volunteer, and Room.

5. **Expired members view** — `/members/expired/` view exists on `s+s`, not on `master`.

6. **`view_diary_json` endpoint** — Experimental endpoint from `s+s`, not yet on `master`.

7. **Legacy URL redirects** — S+S's old website had different URL structure; some redirects existed on `s+s`.

8. **`utils/mailoutomatic.py`** — Standalone script for automatic mailout scheduling. Exists on `s+s`, not on `master`.

---

## Step 2: Compare and align S+S templates

The `star_and_shadow_templates/` directory exists on both branches but differs in two files:
- `star_and_shadow_templates/view_event.html`
- `star_and_shadow_templates/view_showing_index.html`

Compare versions with:
```bash
git diff s+s origin/master -- star_and_shadow_templates/
```

Decide which version is correct or merge them. The `master` version is the baseline (built for Wagtail 6 / Bootstrap 4).

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

**To build and run:**
```bash
docker compose up --build
```

**To create initial users and seed sample data after first boot:**
```bash
docker compose exec toolkit /venv/bin/python3 manage.py configure_toolkit_users
docker compose exec toolkit /venv/bin/python3 manage.py seed_dev_data
```

**To run tests:**
```bash
docker compose exec toolkit /venv/bin/python3 manage.py test --settings=toolkit.test_settings
# Or locally:
tox
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
