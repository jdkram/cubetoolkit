# Branch Notes

## `master` vs `s+s`

These are two long-diverged branches representing entirely different evolutionary trajectories of the same codebase. They share a common ancestor but have accumulated 152 commits unique to `s+s` and 241 commits unique to `master`, spanning 314 changed files.

**`master`** is the actively maintained Cube Microplex production branch: Django 5.2 LTS, Wagtail 6.x, Python 3 only, Docker/gunicorn deployment, no Celery.

**`s+s`** is a branch developed specifically for Star and Shadow Cinema: Django 2.2, Wagtail 2.12, Python 2/3 compatible (`six`), Apache/uWSGI deployment, Celery for async mailout.

### Framework and Python version

| | `master` | `s+s` |
|---|---|---|
| Django | 5.2 LTS | 2.2 |
| Wagtail | 6.3.x | 2.12 |
| Python | 3 only | 2 + 3 (`six`, `from __future__`) |
| URL routing | `re_path` / `path` | `url()` (`django.conf.urls`) |
| Wagtail imports | `wagtail.fields`, `wagtail.admin.panels` | `wagtail.core.fields`, `wagtail.admin.edit_handlers` |

`s+s` uses `super(ClassName, self)`, `%`/`.format()` strings, `@python_2_unicode_compatible`, `IOError`, and `six.*` throughout. These are all absent from `master`.

### Mailout architecture (biggest structural difference)

**`master`** has a dedicated `toolkit/mailer/` app:
- `MailoutJob` model with a state machine (PENDING → SENDING → SENT/FAILED/CANCELLED).
- `mailerd.py` — a standalone long-running daemon that polls for jobs and sends them. No Celery.
- htmx-powered job queue UI.
- `toolkit/__init__.py` is empty.

**`s+s`** uses Celery + Redis:
- `toolkit/celery.py` and `toolkit/members/tasks.py` define a `send_mailout` Celery task.
- `mailout_views.py` dispatches via `send_mailout.delay()`, polls progress via `AsyncResult`.
- `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` point at Redis.
- The `mailer/` app does not exist in `s+s`.

### Django admin

**`master`**: Django admin is not enabled (not in `INSTALLED_APPS`, no admin URLs).

**`s+s`**: Django admin is fully enabled. `toolkit/toolkit_auth/admin.py` registers `User`, `Member`, `Volunteer`, and `Room` with custom `list_display`. An "Administration backend" link appears in the toolkit index when `VENUE['show_user_management']` is true.

### Volunteer–User link

**`s+s`** adds a `Volunteer.user` OneToOneField:
- Creating a volunteer automatically creates a Django `User` and emails them their credentials.
- Retiring a volunteer sets `user.is_active = False`.
- A `Programmers` group is managed by the `create_programmer_permission` management command; volunteers with the `Programmer` role are added to it automatically.
- Several edit views require `toolkit.programmer` permission (not just `toolkit.write`).

**`master`** has no `Volunteer.user` field and no Programmers group.

### Deployment

| | `master` | `s+s` |
|---|---|---|
| Server | gunicorn | Apache + mod_wsgi |
| Containerisation | Docker (multi-stage, non-root user) | No Docker |
| Compose files | dev + production + staging | None |
| Fabric | 3.x (`@task` decorator) | 1.x (`from fabric.api import …`) |
| Fabric targets | Cube only | Cube + S+S production/staging |
| Requirements | `requirements/base.txt` + `dev.txt` | Single `requirements.txt` + `requirements_development.txt` |
| WSGI | `gunicorn` in base requirements | `libapache2-mod-wsgi` in Dockerfile |

### Key settings differences

| Setting | `master` | `s+s` |
|---|---|---|
| `DEBUG` default | `False` | `False` (but `True` in dev) |
| `MULTIROOM_ENABLED` | `False` | `True` (in `settings_ss.py`) |
| `HTML_MAILOUT_ENABLED` | `True` | `False` |
| `MAX_COUNT_PER_ROLE` | 16 | 8 |
| `TAGS_WITHOUT_TERMS` | present (meeting, training) | absent |
| `EDIT_INDEX_DEFAULT_USE_POPUPS` | `False` | `True` |
| `WAGTAILUSERS_PASSWORD_ENABLED` | `False` | `True` |
| Social links | Mastodon, Bluesky | Twitter |
| Celery settings | absent | `CELERY_BROKER_URL`, etc. |
| `django.contrib.admin` | absent | present |
| `toolkit.mailer` | present | absent |
| `crispy_forms` | present | absent |

`s+s` also has `settings_ss.py` (absent from `master`) with S+S venue details, `SHOW_ARCHIVE_IMAGES = False`, `IMAGES_START_DATE`, and `vols_admin_address`.

### Diary model differences

| | `master` | `s+s` |
|---|---|---|
| `Showing.rota_notes` max length | 1024 | 4096 |
| `Showing._original_start` tracking | yes | no |
| `Showing.clone_or_reset_rota()` | yes | no |
| `ShowingQuerySet.start_in_future/past()` | yes | no |
| `Event.terms_long_enough()` / `terms_required()` | yes | no |
| `Event.copy_plaintext` property | no | yes (uses `html2text`) |
| `EventTagQuerySet.contains_tag_to_not_need_terms()` | yes | no |

### Frontend libraries

| | `master` | `s+s` |
|---|---|---|
| Font Awesome | 6.x (split CSS, woff2) | 4.x (single CSS + LESS) |
| Bootstrap | 4.6 (`bootstrap.bundle.min.js`) | 3.x (separate JS + vendor files) |
| jQuery | 3.5.1 | 1.11.1 |
| htmx | yes (mailer UI) | no |
| IE compatibility scripts | no | yes |

### Features unique to `s+s`

- Volunteer–User link with auto user creation and welcome emails
- Django admin with custom volunteer/member interfaces
- Celery + Redis async mailout
- Star and Shadow Fabric deploy targets
- `settings_ss.py` venue configuration
- Image cut-off date (`SHOW_ARCHIVE_IMAGES` / `IMAGES_START_DATE`)
- Expired members view (`/members/expired/`)
- `view_diary_json` endpoint (experimental)
- `keep_vols_from_csv_retire_everyone_else` management command
- `create_programmer_permission` management command
- `utils/mailoutomatic.py` standalone script
- Legacy URL redirects for S+S's old website structure
- `rota vacancies` email template
- `serverconfig/toolkit_uwsgi_star_shadow_staging.py`

### Features unique to `master`

- `toolkit/mailer/` app (daemon-based mailout, job queue, htmx UI)
- `Member.personal_pronouns` field
- `TAGS_WITHOUT_TERMS` + `Event.terms_long_enough()` / `terms_required()`
- `Showing.clone_or_reset_rota()` and original-start tracking
- `view_terms_report_csv` endpoint
- `show_on_programme_page` on CMS pages (links from programme listing)
- Wagtail 6.x page models (`FieldPanel` replacing `ImageChooserPanel`, `page_description`, `serve_preview`)
- Fabric 3.x, Docker-based deployment throughout
- `tox.ini` for test orchestration
- `DEFAULT_AUTO_FIELD = "AutoField"` (suppresses Django 3.2+ warning)
- `WAGTAILUSERS_PASSWORD_ENABLED = False` (lockdown)
- Logout via POST form (CSRF-safe); `s+s` uses a GET link

---

## `s+s` vs `s+s+nosix`

`origin/s+s+nosix` is a **strict linear descendant** of `origin/s+s` — it contains every commit from `s+s` plus five additional commits. `s+s` has no commits that are not also present in `s+s+nosix`.

### What the "nosix" commits do

The five extra commits remove all Python 2 support and the [`six`](https://pypi.org/project/six/) compatibility library from the codebase.

| Commit | Message |
|--------|---------|
| `19ea122` | Remove python2 support |
| `ebf766f` | Remove python2 compatibility shim ('six') |
| `ac09a4b` | Delete incorrect comment |
| `3cd1ca0` | Set black requirement to match formatting |
| `047d8d1` | Format |

### Files changed (23 files, net −27 lines)

#### Dependencies and tooling

- **`requirements.txt`** — `six` removed entirely.
- **`requirements_development.txt`** — `black` bumped from `21.11b1` to `22.3.0`.
- **`bootstrap.sh`** — the `-2` flag (for selecting Python 2) removed; Python 3 is now the only supported runtime.

#### Application code

| File | Change |
|------|--------|
| `toolkit/settings_common.py` | `import six.moves` → plain `range()` |
| `toolkit/util/__init__.py` | `six.binary_type` → `bytes` |
| `toolkit/diary/edit_prefs.py` | `six.iteritems()` → `.items()` |
| `toolkit/diary/edit_views.py` | `six.moves.range()` → `range()` |
| `toolkit/diary/forms.py` | `six.iteritems()` → `.items()`, `six.moves.range()` → `range()` |
| `toolkit/diary/mailout_views.py` | `six.text_type()` → `str()` |
| `toolkit/diary/models.py` | `from six.moves import html_parser` → `import html.parser as html_parser`; `six.iteritems()` → `.items()` |
| `toolkit/diary/templatetags/noprefix_url.py` | `import six.moves.urllib` → `import urllib` |
| `toolkit/members/member_views.py` | Unused `import six` removed |
| `toolkit/members/volunteer_views.py` | `six.iteritems()` → `.items()` |
| `toolkit/util/management/commands/delete_all_members.py` | `from django.utils.six.moves import input` removed (Python 3 `input` is a builtin) |

#### Tests

| File | Change |
|------|--------|
| `toolkit/diary/tests/test_edit_views.py` | `six.iteritems()` → `.items()`, `six.moves.range()` → `range()` |
| `toolkit/diary/tests/test_feeds.py` | `import six.moves.urllib` → `import urllib` |
| `toolkit/diary/tests/test_public_views.py` | Black formatting only |
| `toolkit/members/tests/test_mailout_task.py` | Python 2 decode shim (`if six.PY2: body = body.decode(...)`) removed |
| `toolkit/members/tests/test_members.py` | `from six.moves import urllib` → `import urllib` |
| `toolkit/members/tests/test_volunteers.py` | Black formatting only |

#### Black-only reformats (no logic change)

`toolkit/diary/daterange.py`, `toolkit/diary/templatetags/showing_date_format.py`, `toolkit/util/management/commands/import_legacy_documents.py` — blank line added after module docstring.

### Which branch to use?

Use **`s+s+nosix`**. It is a strict superset of `s+s` and requires only Python 3, which is all current deployment targets support. `s+s` exists as the pre-cleanup snapshot for reference.
