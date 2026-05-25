# Changelog

Releases from the 2026 Star and Shadow porting effort only. Pre-2026 (legacy Cube Toolkit) history is preserved in git but is not divided into releases.

Each release below is tagged (`v2026.03.0` through `v2026.05.5`) and represents a **demo-able milestone** — a developer can check it out, run `docker compose up --build`, seed the data, and show users a coherent vertical slice of functionality.

---

## v2026.05.5 — Community & Public

**Tagged at:** `49d5e7d3` (2026-05-23)

The public site and volunteer community layer come alive. Bootstrap 5, a full accessibility pass, and new social features make the toolkit feel like a modern app.

### What's new

- **Bootstrap 5 upgrade** — 4.0.0-beta → 5.3.8 across the whole admin surface
- **WCAG 2.1 AA pass** — skip-to-main link, keyboard focus outlines, mobile menu as a real `<button>` with `aria-expanded`, visually-hidden labels, message type text prefixes (colour is no longer the sole differentiator)
- **Volunteer opt-in directory** — volunteers choose what to share (name style, pronouns, email, phone, access rider, collectives); card grid with search; Panopticon-only emergency contact fields
- **Collectives** — external links, invite-only flag, join/leave; public directory page at `/collectives/` (no login required)
- **Operational bulletins** — notice board with dashboard banner, pinned posts, configurable expiry, role-based post permissions
- **Public site keyword search** — client-side filter on the programme page with URL persistence and clear button
- **Event metadata** — trailer URL and age restriction fields, doors time surfaced on public event pages
- **Navigation restructure** — Meta-programming, Members, Volunteers menus; clearer tier gating
- **Wagtail 7.4.1** — upgraded from 6.3.8 with Star and Shadow admin branding
- **Rota shift highlights** — green for your shifts, amber for starred events; "My shifts" filter checkbox
- **Loft inventory** — photo uploads linked to floorplan rooms

### How to demo

1. `git checkout v2026.05.5`
2. `docker compose up --build -d`
3. `docker compose exec toolkit /venv/bin/python3 manage.py configure_toolkit_users --password password`
4. `docker compose exec toolkit /venv/bin/python3 manage.py seed_dev_data`
5. Log in as `admin` / `password` (Panopticon tier)

| Page to show | URL | What to point out |
|---|---|---|
| Dashboard | `/toolkit/` | Rota gaps, unconfirmed showings, bulletins banner, widget toggles |
| Volunteer directory | `/toolkit/volunteers/directory/` | Cards with access riders, collectives, search |
| Collectives | `/collectives/` | Public page (log out first to show it needs no auth) |
| Programme search | `/programme/` | Keyword search in the top row |
| Event detail | `/programme/<slug>/` | Trailer link, age restriction, bold next showing |
| Rota | `/diary/edit/rota/` | "My shifts" filter, green/amber highlights |

### State of the code

- 664 tests passing
- 44 migrations in `diary`, 15 in `members`, 13 in `labs`
- All new models have admin inlines where relevant

### Known rough edges

- Public keyword search is client-side only (no server-side fallback for users with JS disabled)
- Bulletins have no email digest yet
- Volunteer directory has no Simplelists integration (9.87 deferred)
- Bootstrap 5 migration touched a lot of templates — some edge-case styling may have regressed

---

## v2026.05.3 — Multi-room & Dashboard

**Tagged at:** `3014b659` (2026-05-16)

Multi-room events stop polluting the diary with fake duplicates, and the homepage becomes an operational cockpit.

### What's new

- **RoomBooking through-model** — a showing can book multiple rooms with independent start/end times and notes; non-blocking clash detection surfaces amber warnings when confirmed bookings overlap
- **Diary list multiroom view** — room show/hide columns, rows grouped by room booking start time, "Other" column for minor-room bookings
- **Panopticon rota signup** — superusers can sign up other volunteers by name on the rota
- **Homepage dashboard** — six widgets: upcoming shifts, starred events, new since last login, rota gaps, unconfirmed showings, upcoming training/inductions
- **Widget toggles** — per-browser show/hide checkboxes persisted in localStorage
- **Rota gap thresholds** — configurable via SiteConfiguration (how many missing slots before a showing appears on the dashboard)

### How to demo

Log in as `admin`.

| Page | URL | What to point out |
|---|---|---|
| Dashboard | `/toolkit/` | Gaps card, unconfirmed card, training card |
| Showings list | `/diary/edit/` | Multi-room events grouped by booking time, room columns |
| Add showing | `/diary/edit/<event_id>/showing/` | Advanced room panel with SVG map, clash warning on save |
| Rota | `/diary/edit/rota/` | Panopticon can sign up others by clicking empty slots |

### State of the code

- 515 tests passing at this tag
- RoomBooking model with `clash.py` advisory module

### Known rough edges

- Dashboard widgets are server-rendered on every request (no caching)
- Clash detection is advisory only — it warns but does not block save
- Multi-room time-grouping in the diary list can be visually dense on busy days

---

## v2026.05.0 — Volunteer Accounts

**Tagged at:** `c50d581e` (2026-05-13)

The biggest infrastructure release. Rota entries are now linked to Volunteer accounts, unlocking per-user features, GDPR compliance, and a rebuilt vacancies tool.

### What's new

- **RotaEntry → Volunteer FK (8.1 MVP)** — non-superuser sign-ups automatically link to the signed-in volunteer; tap-to-sign-up and tap-to-clear on mobile
- **GDPR anonymisation** — Panopticon-only action that overwrites all PII across Member, Volunteer, and User records; requires typing the volunteer's name to confirm
- **Dormant volunteer status** — active / dormant / retired; status badges and filter links on the volunteer list
- **Rota polish** — critical slot highlighting (keyholder, programmer), toggleable badge visibility, past-date navigation up to 31 days back, slot time trimming in calendar, mobile button labels
- **Vacancies rebuild** — Bootstrap cards with urgency colours, role filter pills, "Draft email" button that generates plain text and copies to clipboard
- **Quick create** — keyholders can create a "Building Open" event in three fields (date, opens, closes)
- **Rota deep links** — event detail and hub pages link directly to a specific showing's month on the rota, with amber highlight and scroll offset
- **Pronouns on hover** — rota name span shows pronouns tooltip when set (reuses existing `Member.personal_pronouns`)
- **Collectives directory** — colour picker and print view
- **Hire name** — outside-hire events can show the hirer's name

### How to demo

Log in as `volunteer` (volunteer tier) to show tap-to-sign-up, then as `admin` to show Panopticon features.

| Page | URL | What to point out |
|---|---|---|
| Rota | `/diary/edit/rota/` | Tap a slot to claim; tap your name to clear; past-date nav arrows |
| Vacancies | `/diary/edit/vacancies/` | Urgent red cards, role pills, "Draft email" button |
| Volunteer list | `/toolkit/volunteers/` | Dormant badge, "Show dormant" filter |
| Anonymise | `/toolkit/volunteers/<pk>/anonymise/` | (Admin only) Name-confirmation step before wiping PII |
| Quick create | `/diary/edit/event/open` | (Keyholder+) Three-field form |

### State of the code

- 435+ tests passing
- `RotaEntry.volunteer` nullable FK with `SET_NULL`
- `AnonymisationLog` model records who performed each anonymisation (no PII stored)

### Known rough edges

- No backfill migration for legacy rota names — production name-to-volunteer mapping is deferred
- Calendar slot trimming requires a view rebuild to apply (navigate away and back)
- Vacancies page loads all future showings — may need pagination for very busy venues

---

## v2026.04.0 — Calendar & Operations

**Tagged at:** `8d79a658` (2026-04-28)

The calendar is modernised, the rota is polished, and new operational tools (building map, jobs board, donations) give volunteers self-service utilities beyond the diary.

### What's new

- **FullCalendar 6 migration** — jQuery-free FC6.1.20 with GPL-licensed scheduler bundles; resource timeline week + month views showing rooms as rows
- **Calendar filtering** — time-of-day, tag, status (unconfirmed / private / outside hire / cancelled), and room filters with a visual key integrated into the filterline
- **3-day view** — defaults on mobile; compact button labels on narrow screens
- **Building map** — interactive SVG floorplan at `/labs/floorplan/`; click a room to add/edit a note; amber highlight on rooms with notes
- **Jobs board** — off-rota maintenance schedule with urgency sorting, safety risk flags, skill needed, keyholder required, claim/unclaim
- **Donations wishlist** — traffic-light status badges (got it / on order / still need), category grouping, internal manage page with expandable drill-down
- **"Add to calendar" widget** — per-showing .ics download, Google Calendar, and Outlook.com links on both public event pages and volunteer rota
- **Event approval metadata** — meeting / standing / not recorded with conditional meeting-specific fields
- **Room management** — add/edit rooms with colour picker and delete guard
- **Password management** — Panopticon-only "Send reset email" and direct "Set password" on volunteer profile
- **Volunteer profile overhaul** — two-column layout, access rider fields, role tier labelling with GDPR danger-zone indicators
- **Placeholder poster generator** — typographic poster with colour picker, AJAX preview, attaches as MediaItem on save
- **EventTemplateLink** — links defined on templates are copied to new events automatically
- **Infrastructure hardening** — Docker health checks, resource limits, WhiteNoise cache-busting

### How to demo

| Page | URL | What to point out |
|---|---|---|
| Calendar | `/diary/calendar/` | Resource timeline week view, filter bar, 3-day button on mobile |
| Building map | `/labs/floorplan/` | Click Cinema room → side panel → add note |
| Jobs | `/labs/jobs/` | Red/orange urgency, claim button |
| Donations | `/labs/donations/` | Traffic-light badges; internal manage page at `/labs/donations/manage/` |
| Rota | `/diary/edit/rota/` | Day-group headers, badge toggle checkboxes in filterline |
| Event edit | `/diary/edit/<id>/` | Break-even calculator panel, approval metadata section |

### State of the code

- 350+ tests passing
- All S+S-specific templates aligned with master; no template content missing from the `s+s` branch

### Known rough edges

- Rota entries still use free-text names (Volunteer FK work begins in the next release)
- Jobs board and donations are MVP — no email notifications or due-date reminders yet
- Calendar filtering is client-side; very large date ranges may need server-side pagination later

---

## v2026.03.0 — Foundation

**Tagged at:** `1be4d650` (2026-04-01)

The legacy Cube Toolkit codebase has been ported to a Dockerized Django 5.2 / Wagtail 6.3 stack running Star and Shadow settings. The core diary / rota / programme loop works end-to-end.

### What's new

- **Docker setup** — multi-stage Dockerfile, dev hot-reload via `runserver` with bind-mounted source, non-root `toolkit:toolkit` user
- **Star and Shadow settings layer** — `settings_ss.py` and `docker_settings_ss.py` with S+S venue details, `MULTIROOM_ENABLED=True`, social links, etc.
- **S+S public templates** — `star_and_shadow_templates/` with IE8 cruft removed, Font Awesome 6, local jQuery, logo fixes, DEV watermark
- **Volunteer → User link** — `Volunteer.user` OneToOneField; auto-creates Django User on volunteer add; retirement deactivates the account
- **Programmer permission group** — separate from rota roles; managed via `UserForm` BooleanField; gates template access and event approval features
- **Django admin** — enabled in `INSTALLED_APPS`; custom `ModelAdmin` for Member, Volunteer, User, Room, Role, EventTag, Event, Showing
- **seed_dev_data** — management command with TOML data files creating realistic events, volunteers, showings, and rota entries
- **Event Hub overhaul** — all event fields surfaced with tooltips; event type, copy, terms, film info, pricing, notes
- **Break-even calculator** — collapsible panel on event edit; pure JS; Finance Collective threshold warnings
- **EventTemplate overhaul** — copy, terms, film info, per-role counts; inline role formset with JS "add row"
- **Event resource links (9.26)** — `EventLink` model with domain whitelist; up to 3 links per event; chip display on rota and hub
- **Role badge flags (9.17)** — beginner-friendly, wheelchair-inaccessible, keyholder-only; editable in roles page
- **Alt text fields (9.16)** — `MediaItem.alt_text` with guidance link; all 7 image tags updated with fallback
- **Login styling (9.46)** — login, logout, and all four password-reset templates extend a minimal S+S-branded base
- **Volunteer programme view (9.1)** — logged-in volunteers see private events with a lock badge; film banner for tagged events
- **Rota UX overhaul** — filters, tag badges, role icons, end-time display, event links surfaced as chips
- **Nav overhaul (9.35)** — flat links, permission-gated Diary entry, POST logout form, sign-out styled as button
- **SiteConfiguration singleton** — runtime settings (MAX_COUNT_PER_ROLE, ROTA_CLEAR_EMAIL_PROMPT_ENABLED, etc.) without redeploy

### How to demo

| Page | URL | What to point out |
|---|---|---|
| Programme | `/programme/` | Public events; log in as volunteer to see private events with lock badge |
| Rota | `/diary/edit/rota/` | Day headers, role badges, filterline |
| Event Hub | `/diary/edit/<id>/` | All fields visible, break-even calculator panel |
| Add event | `/diary/edit/event/new/` | Templates pre-populate fields; role counts from template |
| Toolkit index | `/toolkit/` | Tier-aware link grid (All / Programmer+ / Panopticon only) |
| Django admin | `/admin/` | (Admin only) Member, Volunteer, Event, Showing management |

### State of the code

- 280+ tests passing
- All Phase 1 S+S porting items from CURRENT_WORK.md complete; nothing missing from the `s+s` branch

### Known rough edges

- Calendar still on FullCalendar 3.5.1 (migration to FC6 is the next release)
- Static files served via basic Whitenoise (no cache-busting yet — D.1 comes next)
- Rota entries use free-text names (no Volunteer FK yet)

---

## How to check out a release

```bash
# See all releases
git tag -l -n1

# Check out a specific release
git checkout v2026.04.0

# Run it
docker compose up --build -d
docker compose exec toolkit /venv/bin/python3 manage.py configure_toolkit_users --password password
docker compose exec toolkit /venv/bin/python3 manage.py seed_dev_data
```

> **Note:** `seed_dev_data` is idempotent. Running it again on an existing database will skip already-created records.

---

## Versioning

This project uses [CalVer](https://calver.org/) (`YYYY.MM.N`). Tags follow the form `vYYYY.MM.N`. The canonical version string lives in [`VERSION`](VERSION) at the repo root.

For full release and versioning workflow, see [`docs/ONBOARDING.md`](docs/ONBOARDING.md).
