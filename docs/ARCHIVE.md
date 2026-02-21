# Completed Tasks — Archive

**For current work and priorities, see:** [CURRENT_WORK.md](../CURRENT_WORK.md) · [ROADMAP.md](ROADMAP.md) · [TASKS.md](TASKS.md)

Tasks here are done. Active tasks are in [CURRENT_WORK.md](../CURRENT_WORK.md).

---

## Bugs fixed

### Bug A — `/toolkit/` index page crashes (mailer URL namespace) ✅ Fixed

Error: `NoReverseMatch` / `KeyError: 'mailer'`

Root cause: `toolkit/index/templates/toolkit_index.html` uses `{% url "mailer:jobs-list" %}` but `urls_flat.py` (the S&S URL file) did not include mailer URLs under the `mailer` namespace.

Fix applied: added to `urls_flat.py`:
```python
import toolkit.mailer.urls
re_path(r"^mailout/", include(toolkit.mailer.urls)),
```

### S+S port bugs fixed during initial bring-up (Feb 2026) ✅

A batch of bugs found during the first run of the S+S site on the `master`
branch (Django 5.2 + Wagtail 6.3):

- **POST-only logout (Django 5.x):** Django 5 dropped GET-based logout.
  Logout `<a href>` links caused a redirect loop. Changed all logout links
  to `<form method="post">` buttons throughout the public nav and programme
  templates.

- **Font Awesome 404:** `base_public.html` referenced the FA4 path
  (`css/font-awesome/css/font-awesome.min.css`) but the static directory
  serves FA5 (`css/fontawesome/…`). Updated to FA5 paths with v4 shims;
  also enables FA5 brands icons (Instagram, Mastodon, Bluesky etc.).

- **Logo clipping and squishing:** `nav-wrap` overrides from
  `programme_custom.css` and `event_custom.css` set the nav to 170px wide,
  but the logo `<img>` had hardcoded `width="175"`. The sidebar's
  `overflow-y: auto` forced horizontal overflow to clip. On the event page,
  `event.css` blanket `img { width: 100% }` squished the logo while the
  `height="168"` attr remained, distorting the aspect ratio. Fixed by
  removing hardcoded attrs, adding `.site-logo { width: auto; max-width:
  100%; height: auto }`.

- **Bootstrap sourceMappingURL 404:** The committed `bootstrap.min.css` had
  a trailing `/*# sourceMappingURL=…*/` comment pointing to a `.map` file
  not in the repo. Removed.

- **Template caching in dev container:** `settings_common.py` evaluates
  `TEMPLATES[0]["OPTIONS"]["debug"] = DEBUG` at import time, before
  `docker_settings_ss.py` overrides `DEBUG = True`. This meant the
  filesystem template loader cached templates in memory. Fixed by explicitly
  setting `TEMPLATES[0]["OPTIONS"]["debug"] = True` in `docker_settings_ss.py`.

### Bug G — Date/time picker clips behind navbar ✅ Fixed

Date/time picker widget rendered behind the Bootstrap navbar in the diary event edit view (z-index issue).

Fix applied: raised z-index in `edit_form.css` for the datepicker widget.

### Bug B — Wagtail `translation_key` column overflow ✅ Fixed

**Issue:** Creating pages via Wagtail admin (`/toolkit/cms/pages/add/…`) threw `MySQLdb.DataError: (1406, "Data too long for column 'translation_key' at row 1")`

**Root cause:** MariaDB column `wagtailcore_page.translation_key` was `varchar(32)`, but Wagtail 6 generates 36-character UUIDs with dashes (e.g., `550e8400-e29b-41d4-a716-446655440000`).

**Fix applied:** Created migration `toolkit/content/migrations/0013_widen_page_translation_key.py` using a `RunSQL` operation to alter the column from `varchar(32)` to `varchar(36)`. The migration includes a reverse SQL statement for rollback.

**Verification:**
- Migration applied successfully in Docker environment
- Column verified as `varchar(36)` using `SHOW COLUMNS FROM wagtailcore_page LIKE 'translation_key'`
- 36-character UUIDs can now be stored without overflow
- CMS page creation via admin is now functional

---

## System improvements ✅

### 8.13 Toolkit index links cannot carry descriptive text ✅ resolved

**Symptom:** The toolkit homepage (`/toolkit/`) supports user-managed link categories containing named links. The `IndexLink` model had only `text` (link label) and `link` (URL) fields — no way to add a note alongside a link. The result: credentials and instructions were embedded in link labels, e.g. *"Star and Shadow Wiki — login: Operations password: [redacted]"*, making them impossible to copy-paste and a security concern (credentials visible to all logged-in volunteers and embedded in the page source).

**Root cause:** `IndexLink` model had no description/notes field.

**Resolution:** Added `IndexLink.description` — a `TextField(blank=True)` — rendered as plain text below the link on the toolkit index page. The create/update forms include the field. Admins can migrate credentials out of link labels and into descriptions, where they render in a readable, selectable format.

**Migration:** `index/migrations/0003_indexlink_description.py`

**Recommendation going forward:** Store credentials in a password manager (e.g. Bitwarden, accessible to relevant collectives) and use the description field only for non-secret contextual notes. The description field is still visible to all logged-in volunteers — it is not a secrets store.

### 8.14 Volunteer table is slow to sort and slow to add new volunteers ✅ sorting resolved

**Symptom:** The volunteer summary table (`/members/volunteers/`) becomes
noticeably slow as the volunteer list grows. Two specific pain points:

1. **Re-sorting the table triggers a full server round-trip.** ✅ Fixed: the
   `volunteer_summary.html` template now uses vanilla JS click handlers on the
   Name and Inducted column headers to sort the already-loaded table in-place.
   No server request is made. Clicking the same header toggles asc/desc;
   a ▲/▼ indicator shows current sort direction.

2. **"Add new volunteer" is slow.** The flow involves a server POST, a
   redirect, and a full page reload of the volunteer list — meaning the
   volunteer list DB query runs again in full each time a volunteer is added.
   This compounds if admins are bulk-entering volunteers during an induction.

**Remaining fix (add volunteer):** Either (a) submit the add-volunteer form
via `fetch()` and append the new row to the existing table in-place, or (b)
accept the current POST-redirect-GET pattern but ensure the redirect lands on
a paginated or otherwise bounded query rather than loading every active
volunteer. Estimated effort: 🔵 S (4–8h) for the fetch approach.

### 8.15 Frontend debt cleanup — remove Respond.js ✅ resolved

**Issue:** `respond.min.js` (IE8 media query polyfill) was still shipped in the
public templates even though IE8 usage is effectively zero.

**Fix applied:** Deleted `toolkit/static_common/js/lib/respond.min.js` and removed
the `<script>` tag from both public base templates.

### 8.15 Frontend debt cleanup — remove IE8 conditional comments ✅ resolved

**Issue:** IE8 conditional comment blocks in the base templates were loading
obsolete Google Fonts requests.

**Resolution:** Verified the IE8 conditional blocks are no longer present in
the public and admin base templates.

### 8.15 Frontend debt cleanup — update jQuery UI ✅ resolved

**Issue:** jQuery UI 1.11.0 (2014) was outdated and no longer receiving
security patches.

**Fix applied:** Updated vendored jQuery UI assets to 1.13.3 (JS and Smoothness
theme CSS).

---

## Features implemented ✅

### 9.1 Volunteer programme view — see internal events when logged in ✅ implemented

**Goal:** Let volunteers see the full picture of what's happening at the venue,
including events that aren't listed publicly.

The current public programme only shows confirmed, non-private showings. But
the venue runs events that are meaningful to volunteers — internal meetings,
induction sessions, volunteer socials — and these are either hidden entirely or
given their own separate communication. Logged-in volunteers should see these
on the same programme page they'd share with the public, without a separate
internal calendar tool.

Features (all implemented):

- When browsing the programme while logged in, volunteer-only or internal events
  appear in-line with the rest of the listing, visually distinguished with a
  🔒 badge ("volunteer only" or "internal") and an amber left border
- The public version of the same URL remains unchanged — non-logged-in visitors
  see only the public programme
- No separate internal calendar URL needed; the main `/programme/` URL adapts
  to the session state
- Applies to any showing where `event.private=True` or `hide_in_programme=True`
- Volunteer-only event cards link to the rota (not the public event detail page,
  which would return a 404 for private events)
- The public site nav shows the user's display name and a **Sign out** link
  inside the Volunteer Toolkit sub-menu when a volunteer is logged in,
  confirming their session and allowing them to sign out without navigating
  away from the programme

### 9.8 Image copyright reminder ✅ implemented

**Goal:** Prompt programmers to verify image rights at the point of upload,
and give them easy access to guidance.

When a programmer uploads an image to an event, display a visible reminder
alongside the upload field — something like:

> Please make sure you have the right to use this image. See our
> [image copyright guidance](#) for help finding freely-licensed images.

The link points to a document in NextCloud (a plain configurable URL in
settings — no API required). This follows the same pattern as section 11.3:
a URL field, not an integration.

Implementation is minimal: one line of helper text and one settings variable
(`IMAGE_COPYRIGHT_GUIDANCE_URL`). If the URL is not configured, the reminder
appears without the link.

### 9.16 Live word counter for copy summary ✅ implemented

**Background:** The Film Programming Suggestions form requires a 25-word summary or pitch for each screening proposal. This wording is used unchanged for the print programme and submitted to *The Crack* and *NARC* magazines (see section 3.5). The `copy_summary` field on the event creation form should help programmers hit this target.

**Proposed UI behaviour on the event edit form:**

- Display a live word counter beneath the `copy_summary` textarea, updating as the user types.
- **Under 20 words:** neutral grey — no comment (still composing).
- **20–24 words:** amber — "Getting close to the 25-word limit".
- **25 words:** green — "25 words — perfect for the print programme and magazines".
- **Over 25 words:** red — "Over 25 words — the print version will need shortening".

The limit is a soft guideline, not a hard database constraint. The field should accept more than 25 words (some events genuinely need a longer summary for the website). The counter frames 25 as the target, not a ceiling.

**Implementation:** A small vanilla JS snippet on the event edit page; no new models or migrations required. The counter reads the textarea value on each `input` event, splits on whitespace, and updates a `<span>` coloured according to the thresholds.

**Size: 🟢 XS** (2–4h including tests and accessibility review)

---

---

## Environment / tooling ✅

| Task | Status |
|---|---|
| Docker dev environment (S&S settings) | ✅ Done |
| `seed_dev_data` management command | ✅ Done — 29 roles, 16 tags, 15 volunteers, 12 events |
| `seed_dev_data`: CMS nav structure | ✅ Done — About, Get Involved, Important Info section roots with article pages |
| Word counter for `copy_summary` field | ✅ Done |
| DEV SITE watermark on public pages | ✅ Done — fixed-position badge in `base_public.html`; remove before production |
| Volunteer Toolkit sub-menu in public nav | ✅ Done — links to toolkit/diary/rota + sign-out button when logged in |
