# Cinema Toolkit

A Django application for managing events, volunteer rotas, member databases, and a CMS for volunteer-run cinemas. Currently deployed for [Star and Shadow Cinema](https://www.starandshadow.org.uk/) (Newcastle upon Tyne).

Forked from [BenMotz/cubetoolkit](https://github.com/BenMotz/cubetoolkit/).

## Quick start

```bash
docker compose up --build
```

See [docs/ONBOARDING.md](docs/ONBOARDING.md) for full setup instructions including demo accounts and seed data.

## Apps

| App | What it does |
|---|---|
| `diary` | Event scheduling, showings, volunteer rotas, the public programme, and the mailout system |
| `members` | Volunteer and member database, training records, GDPR anonymisation |
| `labs` | Collectives, bulletins, donations, community exchange, jobs board, shopping list |
| `mailer` | Email job queue and delivery daemon |
| `content` | Wagtail CMS for public-facing pages (About, Get Involved, etc.) |
| `index` | Internal admin dashboard |
| `toolkit_auth` | Login/logout, permission decorators |
| `util` | Shared utilities, image processing, management commands |

## Venue configuration

Venue-specific settings (name, logo, email addresses, social media, feature flags) live in `toolkit/settings_<venue>.py`. The Star and Shadow config is in `toolkit/settings_starandshadow.py`. To adapt for another venue, copy that file and update the `VENUE` dict.

## Documentation

| File | What it covers |
|---|---|
| [docs/ONBOARDING.md](docs/ONBOARDING.md) | Developer setup, Docker, project structure, running tests |
| [docs/SPEC.md](docs/SPEC.md) | System specification: data model, workflows, permission model |
| [docs/TASKS.md](docs/TASKS.md) | Index of feature specs; full specs in [docs/tasks/](docs/tasks/) split by domain |
| [CURRENT_WORK.md](CURRENT_WORK.md) | Current priorities, in-progress work, and completed items |

## License

Copyright Ben Motz and other contributors. Distributed under the GNU Affero General Public License (see LICENSE).

Excludes some images which are copyright their respective organisations (see LICENSE for details). Third-party JS/CSS libraries in `toolkit/static_common/` and `toolkit/diary/static/` are under their own licences.
