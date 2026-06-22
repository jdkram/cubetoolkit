# S&S Toolkit — Infrastructure & Tech Debt

Feature specs for accessibility, test coverage, backup, permission model redesign, and frontend library migration.

**For work status:** [CURRENT_WORK.md](../../CURRENT_WORK.md)

---

### 9.16 Alt text fields for images — ✅ Done 2026-03-02

**Goal:** Add structured alt text (alternative text) fields to all images across the toolkit, ensuring that screen reader users and people with images disabled can understand visual content.

#### Why this matters

Alt text is critical for web accessibility. When an image fails to load, or when a user relies on a screen reader, alt text provides the essential context that sighted users get from looking at the image. The toolkit uses images throughout:

- Event images in the public programme
- Volunteer portraits
- Venue/room images
- Logo and decorative graphics

Currently, images in the toolkit have no structured alt text field. Some may have caption text, but captions are not a substitute for alt text — they are supplementary.

#### Implementation scope

**Data model:**
- Add `alt_text = models.CharField(max_length=255, blank=True, default="")` to `MediaItem`
- Add a migration to create this field on existing `MediaItem` records

**Admin and form integration:**
- Expose `alt_text` in the Django admin `MediaItem` edit form
- If MediaItem is used inline in Event forms, expose the field there too

**Template updates:**
- Everywhere an image is displayed (event cards, volunteer profiles, etc.), ensure the `<img>` tag includes `alt="{{ media_item.alt_text }}"` from the database
- For decorative images (e.g. spacers or pure decoration), set `alt=""` explicitly to signal to screen readers that they can be skipped

**Seeding and backfill (optional enhancement):**
- Consider generating placeholder alt text for seed data images (e.g. "Poster for Community Kitchen Special event")
- For existing production images, alt text can be filled in incrementally as admins encounter them, or in a bulk backfill pass

#### Size breakdown

| Component | Size | Hours |
|---|---|---|
| `MediaItem.alt_text` field + migration | 🟢 XS | 2–3h |
| Admin form / inline form integration | 🟢 XS–🔵 S | 2–4h |
| Template updates (find all uses of images and update tags) | 🟢 XS–🔵 S | 2–4h |
| Seed data alt text | 🟢 XS | 1–2h |
| Documentation (how to set alt text, guidelines) | 🟢 XS | 1–2h |
| **Total** | **🔵 S** | **~8–16h** |

#### Related features

**Alt text guidance link (from volunteer request):**

Add a `ALT_TEXT_GUIDANCE_URL` setting (blank by default). If set, the alt text input field in the image upload form should show a small ⓘ tooltip or inline help link: *"Need help writing alt text? [Guide ↗]"* linking to the configured URL. For S&S this would point to the relevant page in our volunteer documentation. No hardcoded URL in the codebase — set in `settings_starandshadow.py`.

This feature intersects with section 9.17 (Inclusivity and accessibility). Once alt text fields are in place, all public-facing images will be accessible to screen reader users, a key accessibility requirement.

---

### 9.17 Inclusivity and accessibility 🟡 M (ongoing; audit 8–16h + incremental fixes)

Inclusivity is a core S&S principle. This section records specific commitments and areas requiring attention in the toolkit.

#### Screen reader compatibility

The public-facing site and internal toolkit should be usable with common screen readers (NVDA, VoiceOver, JAWS). Key requirements:

- Semantic HTML throughout: `<nav>`, `<main>`, `<section>`, `<h1>`–`<h6>` in logical order.
- All images have meaningful `alt` text (or `alt=""` for decorative images).
- Forms: every input has an associated `<label>` (not just placeholder text).
- Interactive elements (buttons, links) have descriptive text or `aria-label`.
- Rota tables: column and row headers marked with `<th scope="...">`.
- No information conveyed by colour alone (e.g. vacancy status should be text or icon, not just red/green).
- Focus indicators visible for keyboard navigation.

An accessibility audit (using the axe browser extension or a screen reader walkthrough) is recommended before any public launch. The Django admin and Wagtail CMS have good baseline accessibility; the legacy Bootstrap 4 templates need the most attention.

#### Colour-blind friendly modes

The main risk areas are the event card grid and the rota (where colour is used to distinguish rooms and vacancy status):

- Room colour swatches should be supplemented with a short room name label.
- Vacancy/filled status in the rota must be expressed in text or icon, not colour only.
- A future CSS toggle for a high-contrast or colour-blind mode is desirable but not a near-term priority; fix "colour as sole indicator" issues first.

#### Neurodivergence awareness

The toolkit serves volunteers who may be autistic, ADHD, dyslexic, or otherwise neurodivergent. Design considerations:

**Information overload:**
- Avoid dense walls of text. Break content into labelled sections.
- The rota view is currently a wall of text (see 8.6); improving this benefits all users but especially those who find scanning large tables cognitively demanding.
- Use progressive disclosure: only show information relevant to the user's current task.

**Forgetting things:**
- Confirmation emails / in-app reminders for rota sign-ups (section 9.11) directly address this.
- Rota deadline warnings (section 9.2) help programmers who may not track deadlines well.
- A "shifts this week" digest — a simple weekly email listing all confirmed rota slots for the logged-in volunteer — is a low-effort, high-value feature for volunteers who struggle to remember commitments.

**Public discussions and meetings:**
- Some volunteers find open-floor meetings anxiety-inducing, particularly when they involve unexpected questions or perceived judgement.
- The toolkit can support asynchronous alternatives: comment threads on proposed events, structured written pitches, and asynchronous approvals via the programming queue (section 9.2), rather than requiring face-to-face attendance.
- Meeting minutes should be findable without requiring attendance.

**Injustice sensitivity:**
- Transparent, legible processes matter. If an event proposal is rejected, the system should record and display a clear reason (section 9.2 already specifies this).
- Avoid opaque system behaviour: error messages should be human and explain what happened; automated emails should have a clear sender and reason.

**Context and tone in messages:**
- System notification emails should include enough context that a volunteer who receives one weeks later can understand it without remembering what triggered it.
- Example: not *"Your shift has been updated"* but *"Your Keyholder slot for the Starcade showing on Friday 27 March has been removed by [admin name]."*

#### Wheelchair and physical accessibility for roles

Several volunteer roles involve spaces or tasks that may not currently be accessible to a volunteer using a wheelchair or with limited upper-body reach. These should be flagged on the Role definition so that:

1. The rota view can display an accessibility note alongside the role.
2. A volunteer can make an informed decision about signing up.

**Proposed field:** `Role.accessibility_notes` — a free-text field (blank by default). If set, displayed in the rota slot as a small note icon with tooltip. Example content:

| Role | Accessibility note |
|---|---|
| Keyholder | Requires access to key fob storage above the bar — not reachable from a wheelchair without assistance. |
| Bar Staff | The bar is accessible but some storage shelving is high; some tasks require assistance. |
| Cafe (Level 1/2) | The kitchen is not currently set up for use by someone who cannot reach above standard counter height without assistance. |
| Projectionist | The projection booth has step access and is not currently wheelchair accessible. |

These flags are **informational only** — the goal is transparency, not exclusion. The system must not prevent a volunteer from signing up for any role; it gives them the information to decide whether to ask for adjustments. Notes are set by admins via the role edit view.

**Implementation:** Add `accessibility_notes = models.TextField(blank=True, default="")` to `Role`. Update the role edit view. Show the note (if set) in the rota slot UI. 🟢 XS (2–4h)

### 9.19 Audit and fix page titles for accessibility and correctness 🟢 XS (1–2h)

**Goal:** Ensure all page `<title>` tags in templates are accurate, semantic, and accessible for screen readers and browser tabs.

**Current issue:** Some pages may have hardcoded venue names or incorrect titles. For example, the rota edit page title is `{{ VENUE.longname }} role rota`, which should correctly show "Star and Shadow role rota" on the S+S deployment, but may have shown "CUBE role rota" historically or on other deployments. More broadly, many page titles lack clear structure and don't distinguish between internal toolkit pages and public-facing content.

**Scope:** Audit all Django templates and update page titles to follow a consistent pattern:
- **Public pages:** `{{ event_name }} - {{ VENUE.longname }}`
- **Admin/internal pages:** `{{ page_name }} - {{ VENUE.longname }} Toolkit`
- **Rota pages:** `{{ VENUE.longname }} Rota - {{ date_range_if_applicable }}`

**Why this matters:**
- Browser tabs show only the first ~60 characters of a title — make them count
- Screen reader users rely on page titles to understand page context
- Clear titles reduce navigation confusion, especially when many tabs are open
- Consistency improves maintainability

**Files to review:**
- `toolkit/diary/templates/*.html` (edit_rota.html, view_rota.html, form_*.html)
- `toolkit/members/templates/*.html` (volunteer views)
- `toolkit/index/templates/*.html` (toolkit homepage)
- `toolkit/content/templates/*.html` (CMS pages)
- `star_and_shadow_templates/*.html` (S+S-specific templates)

**Implementation:** Update all `{% block title %}` tags to follow the pattern above, ensuring they use `{{ VENUE.longname }}` or similar venue variable rather than hardcoded strings.

---

### 9.20 Test coverage improvements 🟢 XS–🔵 S

**Background:** We have been moving quickly and several recent features and bug fixes lack adequate test coverage. This section collects the known gaps and the specific tests needed to close them. The overall test count is 372; the goal is to add targeted tests without inflating count artificially.

**What cannot be tested in Django's test runner:**

The following fixes are CSS or client-side JS only and have no server-visible behaviour to assert:

- Bug G — z-index change in `edit_form.css` (date/time picker behind navbar)
- Bug H — role icon nowrap fix in `edit_rota.html` / `edit_rota.js` (purely DOM manipulation)
- Bug C — HTML entity decode in rota editor (`loaddata` JS callback in `edit_rota.js`)

For these, manual visual verification in the browser is the only practical check.

---

**Gap 1: datetime-local POST format not tested end-to-end** 🟢 XS (1–2h)

Relates to: Bug F fix in `form_widgets.py`

The `JQueryDateTimePicker.value_from_datadict()` method converts `"YYYY-MM-DDTHH:MM"` (what `<input type="datetime-local">` submits) to `"YYYY-MM-DD HH:MM"` (what Django's `DateTimeField` can parse). The existing POST tests in `test_edit_views.py` still submit the old `"dd/mm/YYYY HH:MM"` format, so the conversion path is never exercised.

**Tests to add** in `toolkit/diary/tests/test_edit_views.py`:

- In `EditShowing._test_edit_showing_common`: add a parallel POST test that submits `start` as `"2013-08-15T19:30"` (datetime-local format) and asserts the saved `Showing.start` is identical to the result of the current old-format test. This confirms `value_from_datadict` conversion is correct.
- Consider a direct unit test of `JQueryDateTimePicker.value_from_datadict()` covering: (a) T-format string, (b) no-T string passthrough, (c) Python `datetime` object passthrough (the guard added for the mailout view).

---

**Gap 2: `ROTA_CLEAR_EMAIL_PROMPT_ENABLED` not verified in context** 🟢 XS (1h)

Relates to: Bug D fix in `edit_views.py` and `settings_common.py`

The setting is passed to the rota editor template as `rota_clear_email_prompt_enabled` and then read by JavaScript. No test verifies that this context key exists or reflects the setting value.

**Tests to add** in `toolkit/diary/tests/test_edit_rota.py`:

- `test_rota_edit_context_prompt_enabled`: `@override_settings(ROTA_CLEAR_EMAIL_PROMPT_ENABLED=True)`, GET rota-edit view, assert `response.context["rota_clear_email_prompt_enabled"]` is `True`.
- `test_rota_edit_context_prompt_disabled`: same but `False`, assert it comes through as `False`.

---

**Gap 3: volunteer programme view has no tests** 🟢 XS (2–3h)

Relates to: 9.1 volunteer programme view

The feature that lets logged-in volunteers see internal events alongside the public programme has zero test coverage. The filtering logic (which events are shown to whom) should be tested.

**Tests to add** in a new `test_public_views.py` section or in the existing `test_public_views.py` (toolkit/diary/tests):

- `test_programme_anonymous_user_sees_only_public_events`: GET programme view without login, assert internal/volunteer-only events not present.
- `test_programme_logged_in_volunteer_sees_internal_events`: Login as a volunteer user, GET programme view, assert volunteer-only events appear in addition to public events.
- `test_programme_logged_in_non_volunteer_sees_only_public`: Login as a non-volunteer staff user, assert internal events are not shown (if that's the intended behaviour — confirm from code).

---

**Gap 4: `IndexLink.description` field not tested** 🟢 XS (1h)

Relates to: 8.13 `IndexLink.description` field added in migration 0003

The description field was added to the model and included in the form, but the existing `test_create_link` and `test_edit_link` tests in `toolkit/index/tests.py` don't include or assert on the description field.

**Tests to add** in `toolkit/index/tests.py`:

- Extend `test_create_link` to POST with a `description` value and assert it's saved on the `IndexLink` object.
- Extend `test_edit_link` similarly for update.
- Optionally assert the description is rendered on the index page for logged-in users (if the template shows it).

---

**Gap 5: word counter JS initialisation not verified** 🟢 XS (30min)

Relates to: the live word counter for `copy_summary` (implemented 2026-02)

Backend validation (minimum word count) is tested in `test_edit_views.py` via `@override_settings(PROGRAMME_EVENT_TERMS_MIN_WORDS=5)`. The JS-side counter is not testable, but we could verify the template at least includes the counter script block.

**Tests to add** in `toolkit/diary/tests/test_edit_views.py`:

- In the existing edit-event GET test, add an `assertContains` for a distinctive fragment of the word-counter JS (e.g. `id="word-count"` or the initialisation function name) to ensure the template renders the counter block.

---

### 9.42 — Tests for diary edit list view 🟢 XS

**Context:** The edit diary list view (`/diary/edit`) was restructured into per-month `<table>` blocks. The view change also removed the `None` sentinel from the `rooms` context list. No tests cover this view's HTML output or the rooms context.

**Tests needed:**
- `rooms` context contains only `Room` objects (no `None` sentinel)
- Response contains a `<th class="month-heading">` element with the expected month name
- Empty days (no showings) render a row with a blank time cell (second `<td>`) so columns stay aligned
- Multiroom: one `<th class="room-col">` per room in the thead
- Single-room: thead contains a generic "Event" header instead

---

### 9.46 — Login page styling 🟢 XS

**Context:** The login page (`/toolkit/login/`) extends `base.html` rather than the S+S `base_public.html`, so it renders with no site branding, nav, fonts, or layout — a jarring blank-page experience for volunteers coming from the public site.

**Fix:**

- Change [toolkit/toolkit_auth/templates/login.html](toolkit/toolkit_auth/templates/login.html) to `{% extends "base_public.html" %}` and drop the `login.css` import (or keep it for form-specific sizing).
- Check the password reset flow (`password_reset`, `password_reset_done`, `password_reset_confirm`, `password_reset_complete`) — these likely have the same problem and should be swept at the same time.
- The login form itself is minimal (`{{ form.as_p }}` + submit); add a small centred card layout so the form doesn't float raw in a wide content area.
- Title text: change "Login required" to something friendlier, e.g. "Volunteer sign in".

---

### 9.70 — Nightly production database backup 🟢 XS (2–4h)

**Goal:** Automate a nightly compressed backup of the production MySQL database on xtreamlab_jorn, with rolling retention, so that any accidental or unauthorised data change can be detected and reversed.

#### Background

The production DB is currently backed up manually and infrequently (two snapshots exist in `~/code/sns-live-toolkit/backups/` as of April 2026). The gap between backups means that changes to records — including financial terms on events — can go undetected. A nightly automated backup closes this window and provides a reliable rollback point.

The existing manual dump procedure is documented in `~/notes/Community/Star and Shadow/servers.md`.

#### Implementation

**1. MySQL credentials file on the server**

Create `/home/users/starandshadow/.my.cnf` on xtreamlab_jorn:

```ini
[mysqldump]
user=starandshadow
password=<production password>
```

Set permissions: `chmod 600 ~/.my.cnf`. This allows `mysqldump` to run without a password prompt, safe for cron use.

**2. Backup script**

Create `/home/users/starandshadow/bin/sns_backup.sh`:

```bash
#!/bin/bash
set -euo pipefail

BACKUP_DIR="/home/users/starandshadow/backups/db"
DB_NAME="starandshadow"
DATE=$(date +%Y-%m-%d)
FILE="$BACKUP_DIR/sns_production_${DATE}.sql.gz"
RETAIN_DAYS=30

mkdir -p "$BACKUP_DIR"
mysqldump --single-transaction "$DB_NAME" | gzip > "$FILE"

# Rolling retention: delete backups older than RETAIN_DAYS
find "$BACKUP_DIR" -name "sns_production_*.sql.gz" -mtime +$RETAIN_DAYS -delete

echo "Backup complete: $FILE"
```

`--single-transaction` acquires a consistent snapshot without locking tables (safe for InnoDB).

**3. Cron entry**

Add via `crontab -e` on xtreamlab_jorn as user `starandshadow`:

```
0 3 * * * /home/users/starandshadow/bin/sns_backup.sh >> /home/users/starandshadow/logs/sns_backup.log 2>&1
```

Runs at 03:00 daily (low-traffic window). Appends stdout/stderr to a log file for manual inspection if needed.

**4. Verify**

After deploying, run the script manually once and confirm the `.sql.gz` lands in `BACKUP_DIR` and can be decompressed cleanly:

```bash
zcat "$FILE" | head -20
```

#### Scope

This is an infrastructure task on xtreamlab_jorn, not a code change in the toolkit repo. It requires SSH access and knowledge of the production MySQL password. Coordinate with Marcus (Xtreamlab) before running — the backup user and `.my.cnf` placement should be confirmed against their server policy.

#### Optional follow-up

A separate cron or manual pull from Jonny's local machine can rsync the latest backup down to `~/code/sns-live-toolkit/backups/` for offline analysis. Use the existing rsync pattern from servers.md.

#### Interim solution (April 2026)

While the server-side setup awaits the Marcus conversation, a nightly backup is running from Jonny's desktop PC via `~/bin/sns_backup.sh`. It SSHes into jorn, pipes `mysqldump --single-transaction` output back through gzip, and stores compressed backups in `~/code/sns-live-toolkit/backups/` with 30-day rolling retention. Logs go to `~/.local/share/sns_backup/sns_backup.log`.

Prerequisites for this to work: `~/.my.cnf` must exist on jorn with credentials (see script header for setup steps). The desktop drive is LUKS-encrypted so no credentials are stored locally.

Crontab entry (user crontab on desktop, `crontab -e`):
```
0 3 * * * /home/jdkram/bin/sns_backup.sh
```

For Anacron catch-up on missed runs, copy the script to `/etc/cron.daily/sns-backup` (requires sudo; runs as root).

---

### 9.117 — Bootstrap 4 / Bootstrap 5 mismatch audit 🟡 M

**Context:** `CRISPY_TEMPLATE_PACK = "bootstrap4"` in `settings_common.py` but the actual Bootstrap CSS/JS is v5.3.8. This means crispy-rendered form widgets use BS4 class names that BS5 doesn't style.

**Already fixed (2026-06-08):**
- `RadioSelect` widget on `entry_mode` — bypassed crispy forms entirely; card UI rendered as plain HTML in the template
- `form-row` → `row` in `edit_event_links.html` and `edit_event_template_detail.html` (layout break: columns were unstyled blocks)
- `font-weight-bold` → `fw-bold` in `edit_event_links.html`, `edit_event_template_detail.html`, `view_rota_vacancies.html`

**Still needs a pass:**
- Audit all templates for remaining BS4 utility classes: `ml-*`/`mr-*` → `ms-*`/`me-*`, `pl-*`/`pr-*` → `ps-*`/`pe-*`, `text-left`/`text-right` → `text-start`/`text-end`, `float-left`/`float-right` → `float-start`/`float-end`, `custom-select` → `form-select`
- Consider upgrading to `crispy-bootstrap5` package + `CRISPY_TEMPLATE_PACK = "bootstrap5"` to fix the root cause (crispy would then generate BS5-compatible HTML for checkboxes, selects, etc.)
- Any checkbox or select widgets rendered via crispy forms may be visually unstyled

---

