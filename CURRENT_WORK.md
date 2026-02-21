# Current and Next Work

**Purpose:** Single source of truth for what to work on next. Updated after task completion.

**Last updated:** 2026-02-20
**Current phase:** Phase 1 — Stable foundation
**See also:** [ROADMAP.md](docs/ROADMAP.md) (overview) · [TASKS.md](docs/TASKS.md) (design rationale) · [ARCHIVE.md](docs/ARCHIVE.md) (completed work)

---

## Immediate blockers (fix first)

✅ **All resolved** — CMS page creation is now functional. See ARCHIVE.md for Bug B fix.

---

## Phase 1: Next prioritized work (in order)

### 1. S+S feature porting (from `s+s` branch)

**Status:** Mostly complete; a few gaps remain.

| Feature | Status | Notes |
|---------|--------|-------|
| ✅ `Volunteer.user` OneToOneField | Done | Each volunteer linked to Django `User` |
| ✅ Django admin integration | Done | Enabled in `INSTALLED_APPS` + `settings_ss.py` |
| ⚠️ Programmer permission group | Partial | `Programmers` group created by `seed_dev_data`, but dedicated `create_programmer_permission` command missing |
| ✅ Rota role count limit increase (8 → 30) | Done | MAX_COUNT_PER_ROLE overridden in settings_ss.py; all three enforcement points auto-parameterized |
| ❌ `SHOW_ARCHIVE_IMAGES` / `IMAGES_START_DATE` | Not started | Hide event images before configurable date |
| ❌ `Showing.rota_notes` field size | Not started | Extend from 1024 → 4096 characters |
| ❌ `Member.email` mandatory | Not started | Change from `blank=True` to `blank=False` |
| ❌ Panopticon user management in volunteer edit | Not started | Allow Panopticon users to grant Panopticon in `/volunteers/ID/edit` view |
| ❌ Custom Django admin `ModelAdmin` classes | Not started | Default list views only; need custom for User, Member, Volunteer, Room |
| ❌ Expired members view | Not started | `/members/expired/` endpoint |
| ❌ `view_diary_json` endpoint | Not started | Experimental; existed on `s+s` |
| ❌ Legacy URL redirects | Not started | Old website had different URL structure |
| ❌ `utils/mailoutomatic.py` | Not started | Standalone mailout scheduler |

**Next steps:** Pick off remaining items starting with the simplest (3-4 hour XS items). See [CLAUDE.md](CLAUDE.md) § "Step 1" for full breakdown.

---

### 2. Template comparison & alignment

**Status:** Not started

Compare S+S templates between `master` and `s+s` branches:
- `star_and_shadow_templates/view_event.html`
- `star_and_shadow_templates/view_showing_index.html`

```bash
git diff s+s origin/master -- star_and_shadow_templates/
```

Decide which version is correct or merge. `master` version (Wagtail 6 / Bootstrap 4) is the baseline.

**Size:** 🟢 XS–🔵 S (depends on diff size)

---

### 3. Open bugs (by size)

| ID | Bug | Size | Ref |
|----|-----|------|-----|
| **C** | Rota text shows raw HTML entities (`&apos;`, `&quot;`) | 🔵 S | ROADMAP.md § Bugs |
| **D** | Clearing rota slot over-eager email prompt | 🟢 XS | ✅ Fixed |
| **E** | Volunteer login dropdown inaccessible on touch | 🔵 S | ROADMAP.md § Bugs |
| **F** | Time picker is a slider (bad UX) | 🔵 S | ROADMAP.md § Bugs |

**Suggestion:** Do Bug D first (smallest); it's a simple settings flag (`ROTA_CLEAR_EMAIL_PROMPT_ENABLED`). Then tackle C/E/F as time allows.

---

## Phase 2: Quick wins available now

Independent features, good for parallel work or when larger tasks are blocked:

| # | Feature | Size | Notes |
|----|---------|------|-------|
| 9.9 | Break-even calculator for programmers | 🟢 XS | Pure JS; no database changes |
| 9.10.2 | Clone rota notes with event clone | 🟢 XS | Copy `rota_notes` during event clone |
| 9.12 | "Dormant" volunteer status | 🟢 XS | Add `status` field (active/dormant/retired) |
| 9.3↳ | Collapse rota notes by default | 🟢 XS | Show summary, expand button |
| 9.17↳ | `Role.accessibility_notes` field | 🟢 XS | Info-only field for role accessibility |
| 9.10.5 | Role timing notes field | 🟢 XS | Per-role start/end time in rota |
| 13.5 | Collectives directory (CMS-managed) | 🔵 S | Wagtail page with directory listing |

**See:** [ROADMAP.md](docs/ROADMAP.md) § "Quick wins" for full details.

---

## Decision tree for agents

**Starting a task?**
1. Check this file → pick from "Immediate blockers" or "Next prioritized" in order
2. Click the Ref link to TASKS.md for design details
3. Check [CLAUDE.md](CLAUDE.md) for immediate setup/context

**Just finished a task?**
1. Move it to [ARCHIVE.md](docs/ARCHIVE.md)
2. Update the status table above (move item or change ✅)
3. This file auto-reflects changes

**Parallelizing work?**
- Blockers + Phase 1 items are dependent (do in order)
- Phase 2 quick wins are independent (start any)
- Two developers? One does Bug B / S+S porting, other does quick wins

---

## Size legend

| Emoji | Hours | What it means |
|-------|-------|--------------|
| 🟢 | 1–4h | Quick, one-sitting work |
| 🔵 | 4–16h | Half-day to full day |
| 🟡 | 16–40h | Multi-day team effort |
| 🔵–🟠 | 4–80h | Series of tasks |

---

## Notes for maintainers

- Update this file **immediately after task completion** (before moving to ARCHIVE)
- Keep status indicators (✅/⚠️/❌) in sync with actual state
- Link to TASKS.md for the "why"; this file is the "what's next"
- If a task is blocked, update the note and move it to a future phase

---

*Navigation: [ROADMAP.md](docs/ROADMAP.md) · [TASKS.md](docs/TASKS.md) · [ARCHIVE.md](docs/ARCHIVE.md) · [CLAUDE.md](CLAUDE.md)*
