# Changelog

Releases from the 2026 Star and Shadow porting effort only. Pre-2026 (legacy Cube Toolkit) history is preserved in git but is not divided into releases.

Each release below is tagged (`v2026.03.0` through `v2026.05.7`) and represents a **demo-able milestone** — a developer can check it out, run `docker compose up --build`, seed the data, and show users a coherent vertical slice of functionality.

---

## v2026.06.2 — Programmer UX Overhaul & Volunteer Data Tools

**Tagged at:** `2026.06.2` (2026-06-11)

A large batch in two parts. The first is a ground-up overhaul of the event creation and programming workflow: a redesigned new-event form, live template preview, configurable occurrence terminology, a programming queue for Monday meetings, and a set of contextual guidance tools (TicketSource guide, age ratings, confirm banner). The second improves how panopticons managing volunteer records work: a safer suspension UI, a proper data export with a GDPR audit trail, a qualification report, and a consolidated bulk-record page. The nav is reorganised around how people actually use the tool.

### What's new

**Event creation and programming workflow**

- **Programming queue** — `Event.programming_status` (draft / proposed / active / rejected) with a `/diary/edit/programming-queue/` view for Monday-meeting triage. Quick approve / return / skip actions. "Propose for meeting" button on the Event Hub. Queue nav link in Meta
- **New Event form redesign** — two-zone crispy layout: "Book it now" (name, template, dates, start time) vs "Details — amend any time". Selecting a template renders a live preview (rooms with colour pips, rota with counts, tags, pricing, flags). Auto-ticks private/outside-hire from the template. Uses multi-date flatpickr from the batch-add flow; `room` field dropped (rooms now come from the template automatically)
- **Default room bookings from event templates** — `EventTemplateRoom` through-model; auto-creates room bookings when a showing is added, skipping any rooms the programmer has manually selected
- **Multi-day room bookings** — `RoomBooking.date_offset` (-1/0/+1) for load-in and teardown slots; compact "Day" column on the Edit Showing room booking table
- **Venue-configurable occurrence terminology** — `occurrence_noun`, `occurrence_noun_plural`, `confirm_label` in `SiteConfiguration`. Defaults keep Cube language ("showing"/"showings"/"Confirm"); S+S seed data uses "date"/"dates"/"Publish & open rota". All hub headings, buttons, tooltips, and flash messages read from config
- **Event/showing UI simplification** — single-occurrence events presented as one thing (heading + one card) on the Event Hub; the plural showing list and "Confirm all" only appear once a second showing exists
- **Film template validation** — Film (DCP/MP4) templates pre-fill pricing, film_information, and terms with `[bracket]` placeholder text. Form rejects submission if any bracket placeholders remain unfilled
- **Edit Showing form layout** — switched to vertical layout (labels above fields); call-times grouped into one responsive row; status checkboxes in a named fieldset; bottom buttons in a flex action bar
- **Completeness checklist links** — checklist badges are now links to the relevant edit-form anchor, not just indicators
- **TicketSource setup guide** — collapsible 5-step guide injected after the `ticket_link` field in event edit. Guide text configurable in site settings (`ticket_link_guidance_html`); optional link to a full programming guide document (`film_programming_guide_url` in venue config)
- **"Ready to go live" confirm banner** — when all completeness checks pass but the showing is still unconfirmed, a green banner replaces the completeness bar. Single-occurrence events get an inline Confirm button; series events are pointed to "Confirm all"
- **Configurable age-rating scheme** — panopticons define their own age-rating vocabulary in site settings. BBFC defaults seeded (U/PG/12A/12/15/18). Old stored values (`all_ages`, `16_plus`, `18_plus`) fall back to their legacy display labels

**Programme and public site**

- **CSS Grid on programme index** — Masonry.js replaced with `display:grid`; uniform portrait cards (`aspect-ratio:2/3`); 1→2→3→4 column breakpoints
- **Configurable programme filter buttons** — `EventTag.filter_group` field; `PROGRAMME_FILTER_GROUPS` setting; AND-logic with text search; `?group=` URL persistence
- **Letterbox bars on image upload** — `bar_colour` field on `MediaItem`; Pillow pads uploaded images to the configured crop ratio using the chosen colour. Colour picker and Canvas dominant-colour swatches in the event edit form
- **RSS/Atom feed improvements** — 60-day lookahead (was 7); titles include date and time; descriptions prefer `copy_summary`; `item_pubdate` from `showing.created_at`
- **Open Graph tags** — `og:type`, `og:site_name`, `og:url`, `og:title`, `og:image` added to `base_public.html` as site defaults; event pages override with event-specific values
- **RSS autodiscovery** — `<link rel="alternate">` moved from the programme index to `base_public.html`, so it appears in `<head>` on all public pages

**Volunteer records**

- **Volunteer CSV export with GDPR audit trail** — full export page replaces the one-click download. Five field-group checkboxes; contact and address groups badged as "personal data" with a GDPR reminder. Every export logged to `ExportAuditLog` (user, timestamp, groups selected); audit log viewable at `/volunteers/view/export/audit/`
- **Qualification report** — `/volunteers/qualification-report/` lists all qualifications, holder counts, granted-on/by dates, and which roles gate on each (blocking / advisory badges). Replaces the old role report; old URL redirects
- **Bulk-record page consolidation** — group-training and bulk-qualification-award forms merged into `/volunteers/bulk-record/` behind a type selector, with inline explanation of the difference
- **Suspension UX overhaul** — "Suspended" removed from the volunteer status radio entirely. A dedicated Suspension card (red/amber border, consequence text, Suspend / Lift button) handles the action separately. Prevents a suspended volunteer being accidentally reinstated via a routine profile edit

**Site management**

- **Nav overhaul** — Labs dropdown renamed Community, expanded with all community-facing tools. Website slimmed to public-facing items only. Members and Volunteers merged into People (superuser). Admin absorbed into Meta. Roles and donation management opened to Programmer tier
- **Roles table improvements** — rota sign-up count shown per role; inline JS rename warning shows how many rota entries will be retroactively updated when a role name is changed. Roles page opened to Programmer+
- **Access levels table in site settings** — read-only table in the Panopticon site settings page listing every toolkit feature and its current access tier (colour-coded by tier). Groundwork for runtime configurability (9.124 Phase 2)

**Bug fixes**

- Copy summary index: private and hidden showings suppressed; "Closed for private event." text removed
- Nav dropdown hover highlight constrained to text width
- Archive search regrouped by `start.date` (was `start.day`, which bucketed events from different months together)
- wsgi.py restored after accidental deletion; dangling vendor symlinks removed from static tree

### How to demo

1. `git checkout v2026.06.2`
2. `docker compose up --build -d`
3. `docker compose exec toolkit /venv/bin/python3 manage.py configure_toolkit_users --password password`
4. `docker compose exec toolkit /venv/bin/python3 manage.py seed_dev_data`
5. Log in as `admin` / `password`

| Page to show | URL | What to point out |
|---|---|---|
| Programming queue | `/diary/edit/programming-queue/` | Draft/proposed events; quick triage actions |
| New event | `/diary/edit/event/add/` | Zoned form; template live preview; multi-date flatpickr |
| Edit event | `/diary/edit/event/<id>/` | TicketSource guide; age-rating dropdown; confirm banner |
| Site settings | `/diary/edit/siteconfiguration/` | Terminology; age ratings; ticket link guidance; access levels |
| Programme index | `/programme/` | CSS Grid layout; filter buttons |
| Volunteer export | `/volunteers/view/export/` | Field-group checkboxes; GDPR badges |
| Export audit log | `/volunteers/view/export/audit/` | Per-export log |
| Qualification report | `/volunteers/qualification-report/` | Qual holders; role gates |
| Bulk record | `/volunteers/bulk-record/` | Type selector: training vs qual award |
| Volunteer profile | `/volunteers/<pk>/edit/` | Suspension card; no Suspended in status radio |
| Roles | `/diary/edit/roles/` | Entries count; rename warning |

### State of the code

- 57 migrations in `diary`, 24 in `members`

### Known rough edges

- `film_programming_guide_url` in venue config is empty by default — the TicketSource guide link is hidden until set
- Access levels table is read-only; runtime configurability deferred to 9.124 Phase 2
- Exchange photos still not resized on upload

---

## v2026.06.1 — Community Tools & Safety Improvements

**Tagged at:** `2026.06.1` (2026-06-01)

A batch of community-facing Labs features alongside hardening work: a tool/item exchange, lost and found, role qualification gates, and a Docker boot-time safety net that catches misconfigured upload directories before they cause runtime errors.

### What's new

- **Community exchange** — volunteers can list items to lend (borrow and return), give away (free to a good home), or share (help yourself). Filterable card grid with status lifecycle (available / on loan / missing / all gone / withdrawn). Gated behind a `community_exchange_enabled` site setting
- **Role qualification gates** — panopticons define named qualifications (e.g. "Bar", "Projection"), grant them per-volunteer on the profile page, and attach them to roles as advisory (warns on sign-up) or blocking (refuses with 403) gates. Panopticons always bypass
- **Lost & found log** — sequential human-readable IDs (L-001 format), photo upload, tabbed list, detail/claim/dispose/printable-label workflow, overdue flagging from a configurable `lost_and_found_retain_days` site setting
- **General training flag** — `general_training_enabled` site setting gates GST nudges in the volunteer list, profile Key dates row, training report, and training form
- **Mobile programme improvements** — keyword search bar merged into the volunteer-notice row; dismissible volunteer notice; one card per showing in the grid view
- **Collectives public directory** — `public_copy` and `listed_publicly` fields on `Collective`; public-facing `/collectives/` page (no login required)
- **Docker upload directory safety net** — `check_media_dirs` management command scans all model upload paths at container startup and refuses to start if any are missing or unwritable
- **Bug fixes** — rolling login activity windows (30/365 days, replacing calendar month/year); Changing Places label position on building floorplan; pre-existing site config test data out of sync with current fields

### How to demo

1. `git checkout v2026.06.1`
2. `docker compose up --build -d`
3. `docker compose exec toolkit /venv/bin/python3 manage.py configure_toolkit_users --password password`
4. `docker compose exec toolkit /venv/bin/python3 manage.py seed_dev_data`
5. Log in as `admin` / `password`

| Page to show | URL | What to point out |
|---|---|---|
| Community exchange | `/labs/exchange/` | Card grid; Add item; mark on loan / returned / all gone |
| Site settings | `/diary/edit/siteconfiguration/` | Toggle `community_exchange_enabled` |
| Role qualifications | `/diary/edit/roles/` | Qualification field + gate dropdown on each role |
| Volunteer profile | `/volunteers/<pk>/edit/` | Grant qualifications section (Panopticon only) |
| Lost & found | `/labs/lost-and-found/` | Log, list, detail, printable label |

### State of the code

- 808 tests passing
- 55 migrations in `diary`, 23 in `members`, 22 in `labs`

### Known rough edges

- Exchange photos are stored but not resized — very large uploads may be slow to serve
- Qualification gates require panopticons to manually maintain grants; no bulk import yet
- Simplelists integration for collectives mailing lists (9.87) still deferred

---

## v2026.05.7 — Volunteer Lifecycle & Maintenance

**Tagged at:** `2026.05.7` (2026-05-30)

The volunteer record grows up. A single `status` now governs the whole lifecycle — who can log in, who appears on the rota, who has been retired or anonymised — replacing the tangle of separate on/off flags that could quietly drift out of sync. Around it sits a set of maintenance tools: a pool-health dashboard, automatic dormancy, an emergency suspension lever, and a self-running scheduler that handles the nightly and weekly housekeeping.

### What's new

- **Volunteer status lifecycle** — a volunteer's status (Active / Dormant / Retired / Suspended / Anonymised) is now the single source of truth for whether they can log in and appear on the rota. The old separate `active` and `login_inactive` flags are gone, so the two can no longer disagree
- **Emergency suspension (safeguarding)** — Panopticon users can suspend a volunteer instantly: it blocks login, drops any live session, and clears their future shifts (past shifts are preserved). Reinstating restores access but not the cleared shifts
- **Anonymised status** — GDPR-erased accounts now carry their own status, so they no longer linger in the active volunteer pool or the maintenance lists showing as "Retired"
- **Pool-health dashboard** — `/volunteers/view/pool-health/` lists dormant volunteers (with re-induction badges) and long-inactive accounts that are candidates for anonymisation
- **Automatic dormancy** — a nightly sweep marks long-inactive volunteers Dormant (never retires or deletes them), and now correctly catches accounts that have never logged in
- **Returning-volunteer welcome** — a dormant volunteer who logs back in gets a "welcome back" card with one-click "I'm back" reactivation and an induction nudge; the rota force-highlights beginner-friendly roles for them
- **Guarded bulk purge command** — `purge_stale_volunteers` reuses the shared anonymisation logic; dry-run by default, requires `--apply` plus a typed `"anonymise N volunteers"` phrase matching the live count
- **Configurable weekly digest day** — the volunteer digest email's send day is now a site setting (or can be disabled entirely)
- **Maintenance scheduler** — a new `scheduler` container runs the dormancy sweep (03:00) and the weekly digest (09:00) automatically; no host cron needed
- **Event hub ↔ edit form parity** — trailer URL, age restriction, and the approval metadata now appear on the event hub, matching the edit form (21 fields on both)
- **TMDB trailer fetcher** — a helper that populates trailer URLs in seed data from The Movie Database
- **Clash detection fix** — open-ended room bookings are now treated conservatively as clashes rather than silently ignored
- **Dependency pinning** — Docker builds install from a fully pinned `requirements/docker.lock` for reproducible images

### How to demo

1. `git checkout v2026.05.7`
2. `docker compose up --build -d`
3. `docker compose exec toolkit /venv/bin/python3 manage.py configure_toolkit_users --password password`
4. `docker compose exec toolkit /venv/bin/python3 manage.py seed_dev_data`
5. Log in as `admin` / `password`

| Page to show | URL | What to point out |
|---|---|---|
| Pool health | `/volunteers/view/pool-health/` | Dormant list with re-induction badges; purge candidates |
| Volunteer profile | `/volunteers/<pk>/edit/` | Status radios with plain-English consequences; Suspend (Panopticon only) |
| Dashboard (as dormant volunteer) | `/toolkit/` | Welcome-back card with one-click "I'm back" |
| Event hub | `/diary/edit/<event_id>/` | Trailer URL, age restriction, approval metadata rows |
| Site settings | `/diary/edit/siteconfiguration/` | Dormancy / grace / purge day thresholds; digest send day |
| Purge command | `purge_stale_volunteers` (dry-run) inside the container | Report of stale accounts; `--apply` needs the typed phrase |

### State of the code

- 782 tests passing
- 51 migrations in `diary`, 21 in `members`, 16 in `labs`
- New `scheduler` container in `docker-compose.yml`; build installs from `requirements/docker.lock`

### Known rough edges

- Role sign-up is still not gated by training/inductions (specced as 9.100; needs collective buy-in)
- The pool-health dashboard is read-only reporting plus the purge command — no in-page bulk actions yet (9.96)
- Volunteer directory has no Simplelists integration (9.87 deferred)

---

## v2026.05.6 — Operations & Polish

**Tagged at:** `46492067` (2026-05-29)

A polish release focused on day-to-day operational friction: cancelled events no longer vanish, the shopping list keeps the building stocked, and every form field now explains itself.

### What's new

- **Shared shopping list** — volunteers flag when consumables run out, pledge to restock them, and mark them done. Supplier records with account-holder pointers live in Django admin
- **Shopping in the weekly digest** — open shopping needs appear in the volunteer email alongside shifts and new programme
- **Cancelled showings stay visible** — they now show a clear CANCELLED badge on the public programme and the rota instead of disappearing entirely
- **Form field tooltips** — every field on the showing edit form (confirmed, cancelled, sold out, setup time, doors time, etc.) has a Bootstrap tooltip explaining exactly what it does
- **Site settings expansion** — break-even thresholds, rota clear-slot prompt text, and volunteers list email are all configurable without redeploying
- **Diary edit list stability** — fixed column widths stop the table jumping when event names are long; quick-add (+) links in the Other rooms column
- **Room map UX** — the SVG floorplan dims non-bookable areas and copies the last room's start/end time when adding a new booking
- **Toolkit homepage** — all link-card sections are collapsible and remember their state; shopping dashboard widget; Access Levels moved into the Labs dropdown
- **Clash detection fix** — open-ended room bookings no longer trigger false-positive overlap warnings

### How to demo

1. `git checkout v2026.05.6`
2. `docker compose up --build -d`
3. `docker compose exec toolkit /venv/bin/python3 manage.py configure_toolkit_users --password password`
4. `docker compose exec toolkit /venv/bin/python3 manage.py seed_dev_data`
5. Log in as `admin` / `password`

| Page to show | URL | What to point out |
|---|---|---|
| Shopping list | `/labs/shopping/` | Flag an item, pledge to get it, mark restocked |
| Event hub (cancelled) | `/diary/edit/<event_id>/` | Cancel a showing; see it still appears on the rota with a badge |
| Showing edit | `/diary/edit/<event_id>/showing/<showing_id>/` | Hover over the ⓘ icons next to field labels |
| Site settings | `/diary/edit/siteconfiguration/` | Two-column layout; break-even thresholds; rota prompt text |
| Dashboard | `/toolkit/` | Collapse/expand link cards; shopping widget if items are flagged |
| Digest preview | Run `send_volunteer_digest --dry-run` inside the container | See the shopping section alongside shifts and programme |

### State of the code

- 755 tests passing
- 47 migrations in `diary`, 15 in `members`, 14 in `labs`
- All new models have admin inlines where relevant

### Known rough edges

- Public keyword search is still client-side only
- Volunteer directory has no Simplelists integration (9.87 deferred)
- Shopping list has no email notifications beyond the weekly digest

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
