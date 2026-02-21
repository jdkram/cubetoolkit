# Star and Shadow Toolkit — Development Roadmap

**TL;DR:** Working Django app for events, volunteers, members. Needs bugs fixed, S&S features ported, then feature development.

**For current work and priorities, see:** [CURRENT_WORK.md](../CURRENT_WORK.md) · [TASKS.md](TASKS.md) (design details) · [ARCHIVE.md](ARCHIVE.md) (completed)

---

## What the toolkit does today

- **Public programme** — events, dates, tags, images
- **Internal diary** — create/edit events and showings, manage the rota
- **Volunteer rota** — assign volunteers to roles per showing, view vacancies
- **Members database** — contact details, membership expiry, mailout consent
- **CMS** — Wagtail-powered content pages (About, Contact, etc.)

## Size key

| Emoji | Size | Hours | Cost equivalent |
|---|---|---|---|
| 🟢 | XS | 1–4h | £50–200 |
| 🔵 | S | 4–16h | £200–800 |
| 🟡 | M | 16–40h | £800–2,000 |
| 🟠 | L | 40–80h | £2,000–4,000 |
| 🔴 | XL | 80–160h | £4,000–8,000 |

Cost basis: **£400/day (~£50/hour)** — mid-career UK freelance rate. Not a budget —
an acknowledgement of what volunteers are donating. Estimates assume a developer
familiar with the codebase; expect 2–3× longer when learning the stack.

---

## Phase 1 — Stable foundation *(in progress)*

### Bugs

| # | Bug | Size | Status |
|---|---|---|---|
| A | `/toolkit/` index crashes — missing `mailer` URL namespace | 🟢 XS | ✅ Fixed |
| B | Wagtail page creation crashes — `translation_key` column too short on MariaDB | 🔵 S | Open |
| C | Rota text fields show raw HTML entities (`&apos;`, `&quot;`) | 🔵 S | Open (may be s+s-specific) |
| D | Clearing a rota slot prompts to email all volunteers (over-eager) | 🟢 XS | ✅ Fixed |
| E | Volunteer login dropdown inaccessible on some touch devices | 🔵 S | Open |
| F | Time picker is a slider (poor UX — should be `<input type="time">`) | 🔵 S | Open |
| G | Date/time picker clips behind navbar | 🟢 XS | ✅ Fixed |

**See [CURRENT_WORK.md](../CURRENT_WORK.md) for current priorities and details.

### S&S features to port from the `s+s` branch

| Task | Size | Status |
|---|---|---|
| `Volunteer.user` OneToOneField (auto-create user on volunteer add) | 🟠 L | Open |
| Django admin + ModelAdmin classes | 🟡 M | Open |
| Panopticon user management in `/volunteers/ID/edit` view | 🟢 XS | Open |
| Programmer permission group (`create_programmer_permission` command) | 🟢 XS | Open |
| Name coercion in rota edit (fill in logged-in user's name) | 🟢 XS | Open |
| `SHOW_ARCHIVE_IMAGES` / `IMAGES_START_DATE` settings | 🟢 XS | Open |
| `Showing.rota_notes` field: extend 1024 → 4096 chars | 🟢 XS | Open |
| `Member.email` mandatory | 🟢 XS | Open |

### Environment / tooling

| Task | Size | Status |
|---|---|---|
| Docker dev environment (S&S settings) | 🟢 XS | ✅ Done |
| `seed_dev_data` management command | 🔵 S | ✅ Done |

---

## Phase 2 — Feature development

Once Phase 1 is stable. Items marked **⚠ blocks others** should go first.

### Quick wins (independent, no prerequisites)

| # | Feature | Size | Status |
|---|---|---|---|
| 9.1 | Volunteer programme view — internal events visible when logged in | 🟢 XS | ✅ Done |
| 9.8 | Image copyright reminder on event image upload | 🟢 XS | ✅ Done |
| 9.16 | Live word counter for `copy_summary` field | 🟢 XS | ✅ Done |
| 9.9 | Break-even calculator for programmers | 🟢 XS | Open |
| 9.10.2 | Clone rota notes with event clone | 🟢 XS | Open |
| 9.10.5 | Role timing notes field | 🟢 XS | Open |
| 9.12 | "Dormant" volunteer status | 🟢 XS | Open |
| 9.3↳ | Collapse rota notes by default | 🟢 XS | Open |
| 9.17↳ | Role.accessibility_notes field | 🟢 XS | Open |
| 13.5 | Collectives directory (CMS-managed) | 🔵 S | Open |

### Medium features (independent of account/FK work)

| # | Feature | Size | Notes |
|---|---|---|---|
| 9.2 | Event programming pipeline | 🟡–🟠 M–L | Draft state, queue, approval, cost fields, Finance flag |
| 9.7 | Room booking — multi-room + clash detection | 🟠 L | `RoomBooking` model |
| 9.10.1 | Filter rota by tag | 🔵 S | Query filter + dropdown |
| 9.10.3 | Rota vacancy report | 🔵 S | Management report |
| 9.10.4 | Calendar `.ics` export | 🔵 S | Public programme feed |
| 9.14 | Film rights report tracker | 🟡 M | Auto-detect + reminder emails + dashboard |
| 9.15 | Film metadata + distributors + screening report | 🟡 M | `FilmLicensing` + `Distributor` models |

### Foundational work (⚠ unblocks many other things)

| Feature | Size | Unblocks |
|---|---|---|
| Link `RotaEntry` to `Volunteer` (FK, item 8.1) | 🟠 L | Volunteer self-service, comms, wellbeing |
| `Volunteer.user` OneToOneField (full self-service) | 🟠 L | Self-service rota, induction, comms |

### Large features (after foundational work)

| # | Feature | Size | Depends on |
|---|---|---|---|
| 9.2 | Account-linked rota sign-up ("my shifts", drop-out, reminders) | 🔴 XL | 8.1 + accounts |
| 9.4 | Volunteer induction workflow | 🟠 L | Accounts |
| 9.5 | Wellbeing dashboard | 🟠 L | 8.1 + accounts |
| 9.6 | Communication improvements | 🟠–🔴 L–XL | 8.1 + accounts |
| 8.5 | Email list sync (Simplelists API or migration) | 🟠–🔴 L–XL | — |
| 8.8 | Qualification model redesign | 🟠 L | — |
| 9.13 | GDPR data purge + SAR tooling | 🟠 L | — |

---

## Suggested next actions

**For a developer picking this up for the first time:**

1. Run `docker compose up --build` → site should boot
2. Create admin user (see [ONBOARDING.md](ONBOARDING.md))
3. Run `manage.py seed_dev_data` → populate with sample data
4. Read [ONBOARDING.md](ONBOARDING.md) for codebase orientation
5. Pick a 🟢 XS item from the quick wins list above

**Immediate priorities (as of Feb 2026):**

- Bug B (Wagtail `translation_key` crash) — blocks CMS page creation
- `Volunteer.user` OneToOneField port — foundational for self-service features
- Pick off 🟢 XS quick wins (9.9, 9.12, rota UX items) while foundation work proceeds

---

## Phase 2 sequencing rationale

1. **Quick wins first** — 9.9, 9.12, rota UX items (2–8h each). Independent,
   high visibility, good for new developers getting familiar with the codebase.

2. **8.1 + volunteer accounts** — foundational, unblock large cluster of features.
   Accept that the data migration will need human review to match free-text names.

3. **9.2 programming pipeline** — independent of accounts work, addresses real
   operational pain, auto-populate pays off immediately.

4. **9.7 room booking** — independent, addresses live operational clashes.

5. **9.4 induction + 9.5 wellbeing** — build once accounts foundation is solid.

6. **9.14 film rights tracker** — independent, high operational importance
   (blacklisting risk is real). Deliver basic version first.

7. **9.6 comms + 8.5 email sync** — largest remaining cluster; scope depends
   on mailing list provider decisions.

---

*Full task detail: [docs/TASKS.md](TASKS.md) · Completed work: [docs/ARCHIVE.md](ARCHIVE.md)*
*Technical specification: [docs/SPEC.md](SPEC.md)*
