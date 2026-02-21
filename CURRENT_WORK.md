# Current and Next Work

**Purpose:** Single source of truth for task status. Completed items stay here, struck through with a date — nothing moves to another file.

**Last updated:** 2026-02-21
**Current phase:** Phase 1 — Stable foundation
**See also:** [ROADMAP.md](docs/ROADMAP.md) (phases & milestones) · [TASKS.md](docs/TASKS.md) (design rationale & spec)

---

## Immediate blockers (fix first)

❌ **Bug E** — Homepage list view layout broken by volunteer event info 🔵 S

The addition of volunteer rota/event data has broken the compact "list" view layout on the homepage. Needs urgent fixing to restore site aesthetics.

❌ **Bug F** — Grid view volunteer banners aesthetics 🟢 XS

The "volunteer only" banners in the grid view are currently not filling their cells. Should span the full width of their grid containers.

---

## Phase 1: Next prioritized work (in order)

### 1. S+S feature porting (from `s+s` branch)

| Feature | Status | Notes |
|---------|--------|-------|
| ✅ `Volunteer.user` OneToOneField | Done 2026-02 | Each volunteer linked to Django `User` |
| ✅ Django admin integration | Done 2026-02 | Enabled in `INSTALLED_APPS` + `settings_ss.py` |
| ⚠️ Programmer permission group | Partial | `Programmers` group created by `seed_dev_data`; dedicated `create_programmer_permission` command missing |
| ✅ Rota role count limit increase (8 → 30) | Done 2026-02 | `MAX_COUNT_PER_ROLE` overridden in settings_ss.py; all enforcement points auto-parameterized |
| ❌ `SHOW_ARCHIVE_IMAGES` / `IMAGES_START_DATE` | Not started | Hide event images before configurable date |
| ❌ `Showing.rota_notes` field size | Not started | Extend from 1024 → 4096 characters |
| ❌ `Member.email` mandatory | Not started | Change from `blank=True` to `blank=False` |
| ❌ Panopticon user management in volunteer edit | Not started | Allow Panopticon users to grant Panopticon in `/volunteers/ID/edit` view |
| ❌ Custom Django admin `ModelAdmin` classes | Not started | Default list views only; need custom for User, Member, Volunteer, Room |
| ❌ Expired members view | Not started | `/members/expired/` endpoint |
| ❌ `view_diary_json` endpoint | Not started | Experimental; existed on `s+s` |
| ❌ Legacy URL redirects | Not started | Old website had different URL structure |
| ❌ `utils/mailoutomatic.py` | Not started | Standalone mailout scheduler |

### 2. Template comparison & alignment

❌ **Not started** — Compare S+S templates between `master` and `s+s` branches:
- `star_and_shadow_templates/view_event.html`
- `star_and_shadow_templates/view_showing_index.html`

```bash
git diff s+s origin/master -- star_and_shadow_templates/
```

**Size:** 🟢 XS–🔵 S (depends on diff size)

### 3. Open bugs

| ID | Bug | Size |
|----|-----|------|
| **C** | Rota text shows raw HTML entities (`&apos;`, `&quot;`) | 🔵 S |
| **E** | Volunteer login dropdown inaccessible on touch | 🔵 S |
| **F** | Time picker is a slider (bad UX — should be `<input type="time">`) | 🔵 S |

---

## Phase 2: Quick wins (independent — start any)

| # | Feature | Size | Notes |
|----|---------|------|-------|
| 9.9 | Break-even calculator for programmers | 🟢 XS | Pure JS; no database changes |
| 9.10.2 | Clone rota notes with event clone | 🟢 XS | Copy `rota_notes` during event clone |
| 9.12 | "Dormant" volunteer status | 🟢 XS | Add `status` field (active/dormant/retired) |
| 9.3↳ | Collapse rota notes by default | 🟢 XS | Show summary, expand button |
| 9.17↳ | `Role.accessibility_notes` field | 🟢 XS | Info-only field for role accessibility |
| 9.10.5 | Role timing notes field | 🟢 XS | Per-role start/end time in rota |
| 13.5 | Collectives directory (CMS-managed) | 🔵 S | Wagtail page with directory listing |

---

## Done ✅

Completed items stay here indefinitely — nothing moves to another file. Periodic sweeps can move old rows to [ARCHIVE.md](docs/ARCHIVE.md) in a batch (no rush).

| Item | Completed | Notes |
|------|-----------|-------|
| ~~Bug A — `/toolkit/` index page crashes~~ | 2026-02 | Fixed mailer URL namespace in `urls_flat.py` |
| ~~Bug B — Wagtail `translation_key` column overflow~~ | 2026-02 | Migration `0013_widen_page_translation_key.py` — widened column to varchar(36) |
| ~~Bug D — Clearing rota slot over-eager email prompt~~ | 2026-02 | `ROTA_CLEAR_EMAIL_PROMPT_ENABLED` setting added |
| ~~Bug G — Date/time picker clips behind navbar~~ | 2026-02 | Raised z-index in `edit_form.css` |
| ~~S+S initial bring-up bugs~~ | 2026-02 | POST-only logout, Font Awesome path, logo sizing, Bootstrap sourcemap, template caching |
| ~~`Volunteer.user` OneToOneField~~ | 2026-02 | Linked to Django `User`; `seed_dev_data` auto-creates accounts |
| ~~Django admin integration~~ | 2026-02 | `django.contrib.admin` enabled; `show_user_management: True` in `settings_ss.py` |
| ~~Rota role count limit 8 → 30~~ | 2026-02 | `MAX_COUNT_PER_ROLE` overridden; all enforcement points parameterized |
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
2. That's it — no other files need updating (unless it completes a whole phase milestone, in which case update [ROADMAP.md](docs/ROADMAP.md))

**Parallelizing work?**
- Blockers + Phase 1 items are dependent (do in order)
- Phase 2 quick wins are independent (start any)

---

## Size legend

| 🟢 | 🔵 | 🟡 | 🟠 | 🔴 |
|----|----|----|----|-----|
| 1–4h | 4–16h | 16–40h | 40–80h | 80–160h |

---

*Navigation: [ROADMAP.md](docs/ROADMAP.md) · [TASKS.md](docs/TASKS.md) · [CLAUDE.md](CLAUDE.md)*
