Cube Toolkit
============

Django application powering [Cube Microplex](https://www.cubecinema.com/) (Bristol)
and [Star and Shadow Cinema](https://www.starandshadow.org.uk/) (Newcastle).
Handles event scheduling, volunteer rotas, member database, and a CMS.

Quick start
-----------

```bash
docker compose up --build
```

See [docs/ONBOARDING.md](docs/ONBOARDING.md) for full setup instructions.

Documentation
-------------

| File | What it covers |
| --- | --- |
| [docs/ONBOARDING.md](docs/ONBOARDING.md) | Developer setup: Docker, project structure, running tests |
| [docs/SPEC.md](docs/SPEC.md) | Full system specification: what it does, data model, workflows, design decisions |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Development roadmap: bugs, feature priorities, sizing |
| [docs/TASKS.md](docs/TASKS.md) | Detailed task descriptions for open bugs and features |
| [docs/ARCHIVE.md](docs/ARCHIVE.md) | Completed tasks |
| [docs/BRANCH_NOTES.md](docs/BRANCH_NOTES.md) | Differences between the `master` and `s+s` branches |
| [docs/SEED_DATA.md](docs/SEED_DATA.md) | Reference data for `manage.py seed_dev_data` |

License
-------

Copyright Ben Motz and other contributors. Distributed under the GNU Affero license (see LICENSE).

Excludes:

- `/toolkit/members/static/members/cube_microplex_logo.gif`
- `/toolkit/members/static/members/default_mugshot.gif`
- `/toolkit/diary/static/diary/diary_edit_list_header.gif`
- `toolkit/content/static/content/logo.gif`

(These images are copyright Cube Cinema Ltd.)

Third-party code under their own licenses:

- `toolkit/static_common/js/lib/`
- `toolkit/static_common/css/lib/`
- `toolkit/diary/static/diary/js/lib/`
