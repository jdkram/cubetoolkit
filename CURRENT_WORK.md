# Current and Next Work

**Purpose:** Single source of truth for task status. Completed items stay here, struck through with a date — nothing moves to another file.

**Last updated:** 2026-03-02
**Current phase:** Phase 1 — Stable foundation
**See also:** [TASKS.md](docs/TASKS.md) (design rationale & feature specs)

---

## Immediate blockers (fix first)

None — all clear.

---

## Phase 1: Next prioritized work (in order)

### 1. S+S feature porting (from `s+s` branch)

| Feature | Status | Notes |
|---------|--------|-------|
| ✅ `Volunteer.user` OneToOneField | Done 2026-02 | Each volunteer linked to Django `User` |
| ✅ Django admin integration | Done 2026-02 | Enabled in `INSTALLED_APPS` + `settings_ss.py` |
| ✅ Programmer permission group | Done 2026-03-01 | `UserForm` gains a `programmer` BooleanField that syncs `Programmers` group membership on save. "Programmer" rota role removed from `ROLES` and event templates — it was a separate thing that caused confusion. |
| ✅ Rota role count limit increase (8 → 30) | Done 2026-02 | `MAX_COUNT_PER_ROLE` overridden in settings_ss.py; all enforcement points auto-parameterized |
| ✅ `SHOW_ARCHIVE_IMAGES` / `IMAGES_START_DATE` | Done 2026-02-28 | Hide event images before configurable date; see TASKS.md 9.27 for rationale |
| ✅ `Showing.rota_notes` field size | Done 2026-02-28 | Extended to 4096; migration `diary/0010` |
| ✅ `Member.email` mandatory | Done 2026-02-28 | `blank=False`; migration `members/0010`; 10 tests updated |
| ✅ Panopticon user management in volunteer edit | Done 2026-02-28 | `UserForm` (username/is_active/is_superuser) shown when `VENUE.show_user_management=True`; gated so Cube tests unaffected |
| ✅ Custom Django admin `ModelAdmin` classes | Done 2026-02-28 | `members/admin.py` (Member, Volunteer, User+VolunteerInline); `diary/admin.py` (Room, Role, EventTag, Event, Showing) |
| ✅ Expired members view | Done 2026-02-28 | `/members/expired/` endpoint; reuses `search_members_results.html` |
| ❌ `view_diary_json` endpoint | Not started | Experimental; existed on `s+s` |
| ❌ Legacy URL redirects | Not started | Old website had different URL structure |
| ❌ `utils/mailoutomatic.py` | Not started | Standalone mailout scheduler |

### 2. Template comparison & alignment

✅ **Done 2026-03-01** — All three S+S templates are ahead of `s+s` branch; nothing missing:

- `base_public.html` — IE8 cruft removed, Font Awesome updated, jQuery local, logo CSS fix, DEV watermark
- `view_event.html` — `site_custom.css` added, alt text bug fixed (`showing.event.name` → `event.name`)
- `view_showing_index.html` — `site_custom.css` added, RSS link removed, volunteer notice banner, `showing-internal` class, lock-icon badges on private events, `event_detail_url` routes volunteers to rota

### 3. Open bugs

| ID | Bug | Size |
| -- | --- | ---- |
| ~~**E**~~ | ~~Volunteer login dropdown inaccessible on touch~~ | ✅ 2026-03-02 — sidebar scrollbar fix resolved this |
| **M** | Calendar edit view: simultaneous events overwrite each other on busy days | 🟠 L |
| ~~**N**~~ | ~~Nav "Rota" link pointed at public `/diary/rota/` instead of edit `/diary/edit/rota/`~~ | ✅ 2026-03-02 |

---

## Phase 2: Quick wins (independent — start any)

| # | Feature | Size | Notes |
|----|---------|------|-------|
| ~~9.9~~ | ~~Break-even calculator for programmers~~ | ✅ 2026-03-02 | Collapsible panel in event edit form beneath terms; pure JS; Finance Collective threshold warnings; fill-level table |
| ~~9.10.2~~ | ~~Clone rota notes with event clone~~ | ✅ 2026-02-28 | `clone_rota_from_showing` now copies `rota_notes`; test added |
| 9.10.6 | Inline warning when rota notes carry to cloned showing | 🟢 XS | Template banner in clone form; see TASKS.md 9.10.6 option 2 |
| 9.10.7 | Port `add-showing` clone view from `s+s` | 🔵 S | Proper clone-booking block with date picker; replaces placeholder link; see TASKS.md 9.10.7 |
| 9.12 | "Dormant" volunteer status | 🟢 XS | Add `status` field (active/dormant/retired) |
| 9.3↳ | Collapse rota notes by default | 🟢 XS | Show summary, expand button |
| 9.17↳ | `Role.accessibility_notes` field | 🟢 XS | Info-only field for role accessibility |
| 9.10.5 | Role timing notes field | 🟢 XS | Per-role start/end time in rota |
| 13.5 | Collectives directory (CMS-managed) | 🔵 S | Wagtail page with directory listing |
| 9.20.1 | Test: datetime-local POST format end-to-end | 🟢 XS | POST with T-separator; unit-test `value_from_datadict` guard; see TASKS.md 9.20 Gap 1 |
| 9.20.2 | Test: `ROTA_CLEAR_EMAIL_PROMPT_ENABLED` in context | 🟢 XS | Two `@override_settings` tests; see TASKS.md 9.20 Gap 2 |
| 9.20.3 | Test: volunteer programme view (logged-in vs anonymous) | 🟢 XS | See TASKS.md 9.20 Gap 3 |
| 9.20.4 | Test: `IndexLink.description` field save/render | 🟢 XS | Extend existing create/edit tests; see TASKS.md 9.20 Gap 4 |
| 9.20.5 | Test: word counter script present in edit-event GET | 🟢 XS | One `assertContains`; see TASKS.md 9.20 Gap 5 |
| ~~9.18.3~~ | ~~Fix action button order: Edit → Clone → Delete~~ | ✅ 2026-02-28 | Delete moved to bottom of `form_showing.html`; Clone/add-date link added above it |
| 9.22 | External hire free-text field on rota | 🟢 XS | `RotaEntry.external_name` field; visible on rota view |
| 9.23 | "Films start on time" banner | 🟢 XS | `FILMS_START_ON_TIME` setting; conditional block in event detail template |
| 9.24 | Pronouns on hover for rota names | 🔵 S | `Volunteer.pronouns` field; tooltip on rota view/edit |
| 9.21 | Recurring events / clone-to-dates | 🟡 M | Multi-date clone UI; one Showing per date; see TASKS.md 9.21 |
| 9.25 | Tap to sign up on rota (mobile) | 🔵 S | Self-service slot claim for logged-in volunteers; see TASKS.md 9.25 |
| 9.26 | Event resource links (generalised rota links) | 🔵 S | `EventLink` model; named link chips on rota view; domain whitelist; see TASKS.md 9.26 |
| 9.28 | Volunteer role tier labelling + GDPR danger indicators | 🟢 XS | Rename `is_superuser` → "Panopticon access"; add Programmer field; ⚠ warning on sensitive roles; see TASKS.md 9.28 |
| ~~**Bug K**~~ | ~~Rota `&amp;` display glitch + security audit of loaddata decode~~ | ✅ 2026-03-02 | Fixed in `edit_rota.js`: use jeditable's `data` option (value-transform callback), not `loaddata` (which is POST params for `loadurl` AJAX — never fired here). Regex decode of Django's 6 escape sequences. Server returns unescaped plain text — do NOT call `escape()` there, browser re-encodes on innerHTML read. See TASKS.md Bug K for full jeditable encoding archaeology. |
| **Bug L** | Wheelchair strikethrough too subtle | 🟢 XS | CSS/template only; consider bolder indicator, badge, or tooltip; see TASKS.md Bug L |
| 9.16 | Alt text fields for event images | 🔵 S | `MediaItem.alt_text` field; admin + form; templates; `ALT_TEXT_GUIDANCE_URL` setting + tooltip; see TASKS.md 9.16 |
| 9.29 | Role management — "other role" limit + role-change behaviour | 🟡 M | Design needed first (design questions in TASKS.md 9.29) |
| 9.30 | Outside hire enhancements — tooltip, hire name, external crew field | 🔵 S | `Event.hire_name` + `Event.external_crew_notes`; reveal on checkbox; rota surface; see TASKS.md 9.30 |
| 9.31 | Beginner-friendly rota slot highlighting | 🟢 XS | Filter in filterline; auto-tag roles containing "extra hands"; see TASKS.md 9.31 |
| 9.32 | Rota past-date navigation | 🟢 XS | Design decision needed (read-only past vs blocked); see TASKS.md 9.32 |
| 9.33 | S&S spaces: seed data (9 rooms) + diary column-per-room view | 🟡 M | Seed data 🟢 XS quick win; column view is 🟡 M; see TASKS.md 9.33 |
| 9.34 | "Showing" terminology review | 🟢 XS | Design discussion with collective; "Session" or "Date" candidate; see TASKS.md 9.34 |
| ~~9.35~~ | ~~1-click top nav access to Diary + Rota edit~~ | ✅ 2026-03-02 | Diary + Rota promoted to top-level nav items; Toolkit dropdown kept for home + sign out |
| 9.36 | Vacancies page as email generation tool | 🔵 S | Filtered view → pre-filled email draft → urgency flag; see TASKS.md 9.36 |
| 9.37 | Public programme tag filtering + keyword search | 🔵 S | Collapsible filter panel; client-side JS; URL persistence; see TASKS.md 9.37 |
| 9.38 | Toolkit page: last login display + diary/edit pre/post title hide | 🟢 XS | Two independent template tweaks; see TASKS.md 9.38 |
| 9.39 | Quick create event for keyholders | 🔵 S | Minimal form; auto-apply template; `private=True` default; see TASKS.md 9.39 |
| 9.40 | Setup time + final closing time on showings | 🟢 XS | `Showing.setup_time` + `closing_time` TimeFields; rota display; see TASKS.md 9.40 |
| 9.41 | Clickable legend room filter (calendar) | 🔵 S | Multi-select checkboxes in key sidebar; client-side `eventRender` filter; `sessionStorage` persistence; see TASKS.md 9.41 |
| 9.42 | Tests: diary edit list view | 🟢 XS | `rooms` no None sentinel; month heading in thead; empty-day blank time cell; see TASKS.md 9.42 |
| 9.43 | Room management UI | 🔵 S | Create/edit/delete rooms from toolkit UI (not just Django admin); name, colour picker, is_primary; see TASKS.md 9.43 |
| 9.45 | Password management in volunteer profile | 🔵 S | "Set/change password" + "send reset email" inline in Permissions card; removes Django admin detour; see TASKS.md 9.45 |
| ~~9.46~~ | ~~Login page styling~~ | ✅ 2026-03-02 | Extends `base_public.html`; login, logout + password reset templates styled with centered card layout; friendly titles; `site_custom.css` moved into `base_public.html` so all descendants get nav styling; see TASKS.md 9.46 |

### 4. Medium and large Phase 2 features

Full specs in [TASKS.md](docs/TASKS.md). Suggested order:

1. **Quick wins** (above) — independent, low risk, good for onboarding
2. **8.1 + volunteer accounts** — foundational; unblocks self-service rota, comms, induction, wellbeing
3. **9.2 Programming pipeline** — independent of accounts; auto-populate programmer slot pays off immediately
4. **9.7 Room booking** — independent; addresses live operational clashes
5. **9.4 Induction + 9.5 Wellbeing** — build once accounts foundation is stable
6. **9.14 Film rights tracker** — independent; blacklisting risk is real; deliver basic version first
7. **9.6 Comms + 8.5 Email sync** — largest cluster; scope depends on mailing list provider decisions

---

## Done ✅

Completed items stay here. When the Done section gets unwieldy, old rows can be deleted — they're preserved in git history.

| Item | Completed | Notes |
|------|-----------|-------|
| ~~Event edit workflow overhaul (Phases A–C)~~ | 2026-02-28 | Phase A: rota notes in showing edit. Phase B: popup mode removed. Phase C: Event Hub (`edit-event-details-view`) — showing cards with confirm/cancel, add-showing form, completeness bar; `update_showing_status` endpoint; add_event/EditEventView/delete_showing redirect to hub; 380 tests pass |
| ~~Event Hub: surface all fields + tooltips~~ | 2026-02-28 | All event fields now always visible (with "—" fallback); `outside_hire`/`private` split into separate Yes/No rows; Bootstrap 4 tooltip ⓘ on every field label + action badges; Private/Confirm/Unconfirm tooltips explain consequences |
| ~~Rota event links → Event Hub~~ | 2026-02-28 | `edit_rota.html`: `edit-event-details` → `edit-event-details-view` so rota event-name links open the hub, not the bare edit form |
| ~~Bug J — Calendar broken by jQuery 3.5 htmlPrefilter~~ | 2026-02-28 | `jQuery.htmlPrefilter = function(html) { return html; };` added in `edit_event_calendar_index.html` before `init_calendar_view`; restores pre-3.5 no-op so FullCalendar 3.x index-based seg correlation works; fixed on both `sns_2026_overhaul` (commit `e756658`) and `feature/event-edit-overhaul` (commit `c8f6ee1`) |
| ~~`Showing.rota_notes` field size 1024 → 4096~~ | 2026-02-28 | Migration `diary/0010_widen_rota_notes` |
| ~~`Member.email` mandatory~~ | 2026-02-28 | `blank=False`; migration `members/0010_make_email_mandatory`; 10 tests updated |
| ~~9.18.3 — Fix action button order~~ | 2026-02-28 | Delete moved to bottom of `form_showing.html`; Clone/add-date link added above it |
| ~~9.10.2 — Clone rota notes with event clone~~ | 2026-02-28 | `clone_rota_from_showing` now copies `rota_notes`; model test added |
| ~~Bug H — Rota role icons orphan onto new line~~ | 2026-02-28 | `edit_rota.html`: wrap last word + badge in `white-space:nowrap` span |
| ~~Bug F — Time picker is a slider~~ | 2026-02-28 | `JQueryDateTimePicker` → `type="datetime-local"` + flatpickr 4.6.13; desktop gets calendar+time popup; mobile defers to native OS picker |
| ~~Bug C — Rota text shows raw HTML entities~~ | 2026-02-28 | `edit_rota.js`: `loaddata` callback decodes entities before populating the inline editor |
| ~~Bug I — Sidebar nav overflows viewport~~ | 2026-02-26 | `#sidebar` `position:fixed; height:100vh; overflow-y:auto` + `#site-nav` `position:relative; top:auto` in `site_custom.css`; root cause: absolutely-positioned children don't contribute to scroll height |
| ~~Fresh install migration crash (`content.0013`)~~ | 2026-02-26 | Added `wagtailcore.0057` dependency; replaced `RunSQL` with safe `RunPython` (INFORMATION_SCHEMA check) |
| ~~ONBOARDING.md accuracy pass~~ | 2026-02-26 | Linux Docker prereqs, venue clarity (S+S default/Cube opt-in), corrected settings table, removed BUGS.txt ref |
| ~~CSS style inconsistency across public views~~ | 2026-02-26 | Extracted shared overrides into `site_custom.css`; removed `font-size: inherit` that made programme-page nav links too large; `programme_custom.css`, `static_pages_custom.css`, `event_custom.css` slimmed to page-specific rules only |
| ~~Bug I seed data~~ | 2026-02-26 | Six extra top-level nav pages added to `seed_dev_data` to reproduce sidebar overflow in dev |
| ~~Homepage list view layout broken by volunteer event info~~ | 2026-02-26 | `.list .volunteer-badge` strips box styling to fit compact inline text |
| ~~Grid view volunteer banners not filling cells~~ | 2026-02-26 | `.showing .volunteer-badge` set to `display: block; width: 100%` |
| ~~BUGS.txt triage~~ | 2026-02-26 | Active items appended to TASKS.md |
| ~~Bug A — `/toolkit/` index page crashes~~ | 2026-02 | Fixed mailer URL namespace in `urls_flat.py` |
| ~~Bug B — Wagtail `translation_key` column overflow~~ | 2026-02 | Migration `0013_widen_page_translation_key.py` — widened column to varchar(36) |
| ~~Bug D — Clearing rota slot over-eager email prompt~~ | 2026-02 | `ROTA_CLEAR_EMAIL_PROMPT_ENABLED` setting added |
| ~~Bug G — Date/time picker clips behind navbar~~ | 2026-02 | Raised z-index in `edit_form.css` |
| ~~S+S initial bring-up bugs~~ | 2026-02 | POST-only logout, Font Awesome path, logo sizing, Bootstrap sourcemap, template caching |
| ~~`Volunteer.user` OneToOneField~~ | 2026-02 | Linked to Django `User`; `seed_dev_data` auto-creates accounts |
| ~~Django admin integration~~ | 2026-02 | `django.contrib.admin` enabled; `show_user_management: True` in `settings_ss.py` |
| ~~Rota role count limit 8 → 30~~ | 2026-02 | `MAX_COUNT_PER_ROLE` overridden; all enforcement points parameterized |
| ~~9.33 — Calendar key overhaul~~ | 2026-03-01 | `Room.is_primary` field + migration; vivid red/blue/yellow primary rooms, pastel secondary rooms; `_is_light_colour()` auto-applies black `textColor` (Café yellow); CSS filter approach dropped — colours stored directly; historic colour removed, red nowIndicator line replaces it; collapsible sticky sidebar key on both views; list view restructured to per-month `<table>` blocks (`<h2>` outside table fixes colspan vertical-line breaks), IDEAS removed, room header gets full-width colour stripe via `border-bottom`, empty-day rows use full column structure; 380 tests pass |
| ~~9.1 Volunteer programme view~~ | 2026-02 | Logged-in volunteers see internal events inline with public programme |
| ~~9.8 Image copyright reminder~~ | 2026-02 | `IMAGE_COPYRIGHT_GUIDANCE_URL` setting; reminder shown on upload |
| ~~9.16 Live word counter for `copy_summary`~~ | 2026-02 | Vanilla JS; 25-word target with colour coding |
| ~~8.13 `IndexLink.description` field~~ | 2026-02 | `TextField` added; migration `0003` |
| ~~8.14 Volunteer table sort (in-place JS)~~ | 2026-02 | Click headers to sort without page reload |
| ~~8.15 jQuery UI 1.11 → 1.13.3~~ | 2026-02 | Drop-in update |
| ~~8.15 Remove Respond.js and IE8 blocks~~ | 2026-02 | Deleted polyfill and conditional comment blocks |
| ~~8.15 jQuery 2.1.3 → 3.5.1 (public site)~~ | 2026-02 | Replaced CDN with local vendor |
| ~~8.15 HTTP → HTTPS Google Fonts~~ | 2026-02 | Fixed in `base_admin.html` |
| ~~Docker dev environment (S&S settings)~~ | 2026-02 | |
| ~~`seed_dev_data` management command~~ | 2026-02 | 29 roles, 16 tags, 15 volunteers, 12 events |

---

## Agent instructions

**Starting a task?**
1. Pick from "Immediate blockers" or "Phase 1" in order above
2. See [TASKS.md](docs/TASKS.md) for design rationale
3. See [CLAUDE.md](CLAUDE.md) for setup/context

**Just finished a task?**
1. Mark it ✅ + date in its table above, or add a row to the Done section
2. That's it — no other files need updating

**Parallelizing work?**
- Blockers + Phase 1 items are dependent (do in order)
- Phase 2 quick wins are independent (start any)

---

## Size legend

| 🟢 | 🔵 | 🟡 | 🟠 | 🔴 |
|----|----|----|----|-----|
| 1–4h | 4–16h | 16–40h | 40–80h | 80–160h |

---

*Navigation: [TASKS.md](docs/TASKS.md) · [SPEC.md](docs/SPEC.md) · [CLAUDE.md](CLAUDE.md)*
