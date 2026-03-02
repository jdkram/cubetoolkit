# Claude Context — Cube Toolkit

## Orientation

This is the **Cube Toolkit** codebase — a Django app that manages events, members, and mailouts for the Cube Microplex cinema in Bristol. It also supports the Star and Shadow cinema via a separate settings layer.

Before doing anything else, read:
- [docs/ONBOARDING.md](docs/ONBOARDING.md) — project structure, apps, Django primer, how to run with Docker
- [docs/BRANCH_NOTES.md](docs/BRANCH_NOTES.md) — detailed audit of differences between the `master` and `s+s` branches

The current branch is **`master`** (Django 5.2 LTS, Wagtail 6.3, Python 3, no Celery).

---

## Django template comments — single line only

**Never write multi-line `{# ... #}` comments in Django templates.** Django's template engine does not strip them reliably when they span multiple lines, and the raw comment text leaks into the rendered HTML.

- ✅ `{# Short single-line comment #}` — safe
- ❌ `{# Multi-line\n   comment #}` — leaks into HTML output

If a comment needs more than one line, use multiple single-line `{# ... #}` tags, or put the explanation in a Python/view-layer code comment instead.

---

## Standing rule: keep docs/ in sync with the code

**After every code change, update the relevant docs.**

**Status tracking — one file only:**
- Bug fixes / features completed → mark ✅ + date in **[CURRENT_WORK.md](CURRENT_WORK.md)** (inline in the table, or add a row to the Done section). Do **not** also update TASKS.md.
- New features proposed → add to [docs/TASKS.md](docs/TASKS.md) section 9.x with sizing label (🟢 XS / 🔵 S / 🟡 M / 🟠 L / 🔴 XL / ⛔ XXL), and add a row to CURRENT_WORK.md.

**Spec — update when the system changes:**
- Data model changes → update [docs/SPEC.md](docs/SPEC.md) section 8 (data model) and ER diagram
- New external system dependencies → update [docs/SPEC.md](docs/SPEC.md) section 6 (external integrations)
- Workflow changes → update [docs/SPEC.md](docs/SPEC.md) section 4 (key workflows)
- Permission changes → update [docs/SPEC.md](docs/SPEC.md) section 2 (permission model)

Do not commit code changes without also committing the corresponding docs update in the same commit (or immediately following it).

---

## Git workflow: bundle and commit on your signal

**I will accumulate changes and commit when you ask me to.**

This gives you full control over batching related changes together and deciding the right moment to commit. When you suggest we should commit (e.g., "let's commit all this"), I will:

1. Display the files that will be staged
2. Show the proposed commit message(s)
3. Run `git commit` with your approval

If you want to adjust the commit message or split into multiple commits, just let me know.

---

## Current task: Port S+S-specific features from the `s+s` branch

The `s+s` branch was the Star and Shadow production branch but ran Django 2.2 (EOL). We have started fresh from `master` (which is far more modern) and ported the S+S-specific functionality across. Initial Docker setup and basic seed data are complete; focus is now on porting remaining features.

The `s+s` branch is available locally for reference (`git checkout s+s`, or inspect files with `git show s+s:path/to/file`). See [docs/BRANCH_NOTES.md](docs/BRANCH_NOTES.md) for full details on branch differences.

**For current task status, what's done, and what's next, see [CURRENT_WORK.md](CURRENT_WORK.md).** That is the single source of truth — do not track status anywhere else.

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

> ⚠️ **Source is baked in — always rebuild after code changes.**
> There is **no volume mount** for the source code. The files are copied into the image at build time.
> Running `docker compose exec toolkit ...` on a running container will use the **old version** of any file you have just edited.
> After *any* change to Python files, templates, or management commands, run:
> ```bash
> docker compose up --build -d
> ```
> before expecting to see the effect in the live dev site or via `manage.py` commands.

**To create initial users and seed sample data after first boot:**
```bash
docker compose exec toolkit /venv/bin/python3 manage.py configure_toolkit_users --password DevPassword1!
docker compose exec toolkit /venv/bin/python3 manage.py seed_dev_data
```

`configure_toolkit_users --password` creates all demo accounts non-interactively. Accounts created:

| Username | Tier | Password |
| --- | --- | --- |
| `admin` | Panopticon (superuser) | `DevPassword1!` |
| `programmer`, `programmer2` | Programmer | `DevPassword1!` |
| `volunteer` … `volunteer5` | Volunteer (rota only) | `DevPassword1!` |

Omit `--password` for production — it will prompt interactively for each new account and skip any that already exist.

**To run tests — ALWAYS inside the container, never locally.**

> ⚠️ **Do not attempt to run tests outside the container.** The project dependencies (including the `fixtures` test library, `mysqlclient`, and several C extensions) are only installed inside the Docker image. There is no local venv, and `tox` is not installed on the host. Every attempt to run tests locally will fail. Do not try to create a venv, install deps, or invoke `tox` or `python manage.py` directly on the host. The one and only way to run tests is:

```bash
docker compose exec toolkit /venv/bin/python3 manage.py test --settings=toolkit.test_settings
```

To run a specific test module or class:
```bash
docker compose exec toolkit /venv/bin/python3 manage.py test toolkit.diary.tests.test_edit_views --settings=toolkit.test_settings
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
| Current work / status / roadmap | [CURRENT_WORK.md](CURRENT_WORK.md) |
| System specification | [docs/SPEC.md](docs/SPEC.md) |
| Feature specs & design rationale | [docs/TASKS.md](docs/TASKS.md) |
