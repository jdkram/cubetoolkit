# Star and Shadow Toolkit — Development Roadmap

**TL;DR:** We have a working Django app managing events, volunteers, and members
for Star and Shadow Cinema. It needs some bugs fixed, some features ported from
an older branch, and a set of new features built in priority order. This document
is the short version. The full detail lives in [SPEC.md](SPEC.md).

---

## What the toolkit does today

- **Public programme** — lists events, dates, tags, images
- **Internal diary** — create/edit events and showings, manage the rota
- **Volunteer rota** — assign volunteers to roles per showing, view vacancies
- **Members database** — contact details, membership expiry, mailout consent
- **CMS** — Wagtail-powered content pages (About, Contact, etc.)

## What it doesn't do yet (the gap list)

The biggest gaps, in rough priority order:

1. Rota sign-up is **free text, not linked to accounts** — anyone can type any name
   into any slot, so you can't reliably email rota'd volunteers or verify who signed up
2. **No identity on rota entries** — a volunteer who drops out can't be automatically
   notified, and there's no "my upcoming shifts" view
3. **Volunteer induction** is entirely manual (paper/spreadsheet)
4. No **programming pipeline** — proposals are discussed in meetings, not tracked in the system
5. Multi-room **clash detection** isn't enforced
6. Film **distributor/rights** information isn't stored — new programmers have to start from scratch

---

## Size key

| Emoji | Size | Hours |
|---|---|---|
| 🟢 | XS | 1–4h |
| 🔵 | S | 4–16h |
| 🟡 | M | 16–40h |
| 🟠 | L | 40–80h |
| 🔴 | XL | 80–160h |

All estimates use **£400/day** as a reference rate (mid-career UK freelance).
These aren't a budget — they're an acknowledgement of what volunteer developers
donate. Full cost estimates are in [SPEC.md § 15](SPEC.md#15-development-roadmap).

---

## Phase 1 — Stable foundation *(in progress)*

Get a working local dev environment, fix the critical bugs, port the S&S-specific
features from the old branch.

### Bugs

| # | Bug | Size | Status |
|---|---|---|---|
| A | `/toolkit/` index crashes — missing `mailer` URL namespace | 🟢 XS | ✅ Fixed |
| B | Wagtail page creation crashes — `translation_key` column too short on MariaDB | 🔵 S | Open |
| C | Rota text fields show raw HTML entities (`&apos;`, `&quot;`) | 🔵 S | Open (may be s+s-specific) |
| D | Clearing a rota slot prompts to email all volunteers (over-eager) | 🟢 XS | Open |
| E | Volunteer login dropdown inaccessible on some touch devices | 🔵 S | Open |
| F | Time picker is a slider (poor UX — should be `<input type="time">`) | 🔵 S | Open |
| G | Date/time picker clips behind navbar | 🟢 XS | ✅ Fixed |

### S&S features to port from the old branch

| Task | Size | Status |
|---|---|---|
| `Volunteer.user` OneToOneField (auto-create user on volunteer add) | 🟠 L | Open |
| Django admin + ModelAdmin classes | 🟡 M | Open |
| Programmer permission group (`create_programmer_permission` command) | 🟢 XS | Open |
| Name coercion in rota edit (fill in logged-in user's name) | 🟢 XS | Open |
| `SHOW_ARCHIVE_IMAGES` / `IMAGES_START_DATE` settings | 🟢 XS | Open |
| `Showing.rota_notes` field: extend 1024 → 4096 chars | 🟢 XS | Open |
| `Member.email` mandatory | 🟢 XS | Open |

### Environment / tooling

| Task | Size | Status |
|---|---|---|
| Docker dev environment (S&S settings) | 🟢 XS | ✅ Done |
| `seed_dev_data` management command | 🔵 S | Open |

---

## Phase 2 — Feature development

Once Phase 1 is stable. Items marked **⚠ blocks others** should go first.

### Quick wins (start here — all independent, no prerequisites)

| # | Feature | Size | Hours | Notes |
|---|---|---|---|---|
| 9.1 | Volunteer programme view — internal events visible when logged in | 🟢 XS | 1–2h | ✅ Done |
| 9.8 | Image copyright reminder on event image upload | 🟢 XS | 1h | ✅ Done |
| 9.9 | Break-even calculator for programmers | 🟢 XS | 2–4h | Pure JS, no server changes |
| 9.10.2 | Clone rota notes with event clone | 🟢 XS | 2h | Copy `rota_notes` on clone |
| 9.10.5 | Role timing notes field | 🟢 XS | 2–4h | Optional note per rota slot |
| 9.12 | "Dormant" volunteer status | 🟢 XS | 2–4h | Add `dormant` state to volunteer |
| 9.3↳ | Collapse rota notes by default | 🟢 XS | 2–4h | JS toggle |
| 13.5 | Collectives directory (CMS-managed) | 🔵 S | 4–16h | Opt-in directory of collectives |

### Medium features (independent of account/FK work)

| # | Feature | Size | Hours | Notes |
|---|---|---|---|---|
| 9.2 | Event programming pipeline | 🟡–🟠 M–L | 30–50h | Draft state, queue, approval, cost fields, Finance Collective flag |
| 9.7 | Room booking — multi-room + clash detection | 🟠 L | 40–80h | `RoomBooking` model; independent of volunteer accounts |
| 9.10.1 | Filter rota by tag | 🔵 S | 4–8h | Query filter + dropdown in rota header |
| 9.10.3 | Rota vacancy report | 🔵 S | 4–8h | Management report: open slots in upcoming showings |
| 9.10.4 | Calendar `.ics` export | 🔵 S | 4–8h | Public programme feed (personal feed needs 8.1) |
| 9.14 | Film rights report tracker | 🟡 M | 16–28h | Auto-detect films; D+1/4/8 reminder emails; one-click confirm |
| 9.15 | Film metadata + distributors + screening report | 🟡 M | 23–40h | `FilmLicensing` + `Distributor` models; OMDb lookup |

### Foundational work (⚠ unblocks many other things)

| # | Feature | Size | Hours | Unblocks |
|---|---|---|---|---|
| 8.1 | Link `RotaEntry` to `Volunteer` (FK) | 🟠 L | 40–80h | Volunteer self-service, comms, wellbeing dashboard |
| Vol. accounts | `Volunteer.user` OneToOneField (full self-service) | 🟠 L | 30–50h | Self-service rota, induction, comms |

### Large features (after foundational work)

| # | Feature | Size | Hours | Depends on |
|---|---|---|---|---|
| 9.2 | Account-linked rota sign-up ("my shifts" view, drop-out notification, reminders) | 🔴 XL | 80–150h | 8.1 + accounts |
| 9.4 | Volunteer induction workflow | 🟠 L | 40–75h | Accounts |
| 9.5 | Wellbeing dashboard | 🟠 L | 40–80h | 8.1 + accounts |
| 9.6 | Communication improvements (email by showing/role, vacancy alerts) | 🟠–🔴 L–XL | 60–120h | 8.1 + accounts |
| 8.5 | Email list sync (Simplelists API or migration) | 🟠–🔴 L–XL | 40–120h | — |
| 8.8 | Qualification model redesign | 🟠 L | 40–60h | — |
| 9.13 | GDPR data purge + SAR tooling | 🟠 L | 40–80h | — |

---

## Suggested next actions

**For a developer picking this up for the first time:**

1. Run `docker compose up --build` → site should boot
2. Run `manage.py configure_toolkit_users` → create your admin login
3. Run `manage.py seed_dev_data` → populate with sample data *(not yet written)*
4. Read [ONBOARDING.md](ONBOARDING.md) for codebase orientation
5. Pick a 🟢 XS item from the quick wins list above

**Immediate priorities:**

- Bug B (Wagtail `translation_key` crash) — blocks CMS page creation
- `seed_dev_data` command — without it, new contributors can't explore the app
- `Volunteer.user` OneToOneField port — foundational for self-service features

---

*Full technical specification: [SPEC.md](SPEC.md) — ~3,500 lines covering data model, workflows, business rules, all proposed features with implementation notes, cost estimates, and migration guide.*
