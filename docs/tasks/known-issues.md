# S&S Toolkit — Known Issues

Bugs and current system limitations.

**For work status:** [CURRENT_WORK.md](../../CURRENT_WORK.md)  
**For feature specs:** see the other files in [docs/tasks/](./)

---

## Current bugs

**Bug E** — Homepage list view layout broken by volunteer event info 🔵 S

The "list" view on the homepage is currently misaligned or layout-broken due to the addition of volunteer event/rota information. The extra data points (available slots, etc.) are likely pushing elements out of their containers or causing spacing issues in the compact list view.

**Bug F** — Grid view volunteer banners aesthetics 🟢 XS

The "volunteer only" banners in the grid view are currently not filling their cells. They should be made more aesthetically pleasing by extending them to span the full width of their grid containers.

**Bug B** — Wagtail `translation_key` column overflow 🔵 S

On MariaDB, `wagtailcore_page.translation_key` was `varchar(32)` but Wagtail 6 generates 36-character UUIDs. Creating CMS pages throws `DataError`. Fix: widen column to `varchar(36)` via migration. See CURRENT_WORK.md Done section for resolution details.

**Bug K** — Rota `&amp;` display glitch ✅ fixed 2026-03-02

**Root cause:** jeditable's `loaddata` option is NOT a value-transform callback. It provides extra POST parameters for a `loadurl` AJAX request. We don't use `loadurl`, so any function assigned to `loaddata` is silently ignored. The correct option is `data`: when set to a function, jeditable calls it with `$(element).html()` (raw innerHTML, Django-escaped) and uses the return value to populate the editor.

**Fix in `edit_rota.js`:** use `data: function(value) { ... }` with a regex decode of Django's 6 escape sequences (order matters — `&amp;` first):
```js
data: function(value) {
    return value
        .replace(/&amp;/g,  '&')
        .replace(/&lt;/g,   '<')
        .replace(/&gt;/g,   '>')
        .replace(/&quot;/g, '"')
        .replace(/&#x27;/g, "'")
        .replace(/&#39;/g,  "'");
}
```

**Server response must stay unescaped plain text** (`return HttpResponse(showing.rota_notes, ...)`). After save jeditable calls `$(self).html(result)`; the browser's innerHTML getter re-encodes `&` → `&amp;`, so the next `data` call sees `&amp;` and decodes correctly. If you add `escape()` to the response, jeditable's `.html()` double-encodes it (`&amp;` → `&amp;amp;`) and a spiral begins.

**Bug M** — Calendar edit view: simultaneous events in the same timeslot overwrite each other 🟠 L

On days with 6+ events scheduled at the same time, FullCalendar 3 renders later events on top of earlier ones rather than shrinking and tiling them side-by-side. The result is that some events become completely hidden and unreachable from the calendar view. Reproduce at `/diary/edit/calendar/` on a busy day (e.g. any of the three busy days in the seed data, currently at offsets +35, +70, and +105 from today).

Root cause: FullCalendar's column-based layout is not triggered when all events share the same time of day (all set to e.g. 19:00 with no explicit `end` time). The calendar needs each event's duration to be set so that FullCalendar can detect overlaps and split columns. With `Event.duration` now populated by `seed_dev_data`, this should improve — but busy days with many short events may still need explicit end-time rendering. A secondary fix may be needed on the FullCalendar event source view to emit `end` timestamps.

**Workaround:** Use the list view (`/diary/edit/`) on busy days — it shows all events regardless of overlap.

**Fix approach (not yet implemented):**
1. Ensure the FullCalendar event source JSON endpoint returns `end` for each event (computed from `start + Event.duration`).
2. Consider whether a day-grid view (rather than time-grid) is more appropriate for multi-room venues — though this loses time-of-day information.
3. If sticking with time-grid: add a `minTime`/`maxTime` and increase the minimum event height so short events remain clickable.

**Bug L** — Wheelchair-inaccessible role strikethrough too subtle 🟢 XS

The strikethrough symbol on the wheelchair icon (indicating a role is not wheelchair-accessible) is easy to miss — the line is thin and low-contrast. Users may sign up for a role they cannot perform without realising it has accessibility notes. Consider alternatives: a solid badge label ("not accessible"), a distinct colour overlay on the icon, a tooltip with explicit text, or a bolder visual indicator. The fix should be purely CSS/template — no data model change needed.

**Bug O** — Volunteer rota: event-name links redirect to login 🟢 XS

In `edit_rota.html` the showing title links to `edit-event-details-view` (the Event Hub). That view requires `toolkit.write` permission (Programmer tier or above). When a basic volunteer clicks it they are bounced to the login page because they're not in the Programmers group.

**Fix:** add a permission conditional in the template:

- `{% if perms.toolkit.write or user.is_superuser %}` → link to `edit-event-details-view`
- else → link to `single-showing-view` (the public programme page for that showing)

The "↗" public link that already exists alongside the title stays unchanged.

**Bug P** — Event Tags page: pre-Bootstrap styling and confusing UX 🔵 S

`/diary/edit/eventtags/` uses old inline CSS that predates Bootstrap (grey body, dotted border, 400px fixed width). It doesn't match the visual language of the rest of the toolkit.

The interaction model is also unintuitive: users must first tick "Promoted" on a tag and then separately use drag handles to set order. Non-promoted tags show drag handles that do nothing. The mental model of "promoted = in menu" vs "sort order" is not explained in the UI.

**Fix approach:**

- Port styles to Bootstrap 4 card/table layout (consistent with the rest of the toolkit)
- Clarify the UI: non-promoted tags should either hide their handle or show a disabled state
- Consider explanatory text or labels making the "in menu" meaning clearer

**Bug Q** — Roles page: pre-Bootstrap styling 🔵 S

`/diary/edit/roles/` has the same vintage of inline CSS as Bug P (grey body, dotted border, 400px form box, raw `<table>` without Bootstrap classes). It also doesn't match the rest of the toolkit's design language.

**Fix:** Port to Bootstrap 4 card + table layout. No UX redesign needed — the table structure (name, standard, description, delete) is clear; just needs Bootstrap table classes and a card wrapper.

---

**Bug R** — Mobile: public-site sidebar always visible, not gated by hamburger 🟢 XS

**Root cause:** The Bug I fix (2026-02-26) applied `position: fixed; height: 100vh; overflow-y: auto` to `#sidebar` in `site_custom.css` with no media query. On desktop (≥ 1000px) this is correct: the sidebar is always visible. On mobile (< 1000px) it means the sidebar sits in the fixed stacking layer at `left: 0`, visible across the whole viewport regardless of whether the hamburger has been pressed. The S+S `background-color: #e3cae3` applied to both sidebar and grid means the sidebar's nav links show through any gap in the masonry tile layout.

**Symptom:** On the homepage and other public pages, scrolling through content reveals the sidebar nav (Programme, Support Us, etc.) as a persistent layer in the top-left of the screen. It should only appear when the hamburger button is tapped.

**Fix:**

1. In `site_custom.css`: add `left: -240px; z-index: 200; transition: left 0.3s ease;` to the `#sidebar` rule (no media query — applies at all widths). This moves the sidebar off-screen by default.
2. Wrap the existing `position: fixed; height: 100vh; overflow-y: auto` rule in `@media screen and (min-width: 1000px)` only — at desktop widths, sidebar should always be visible.
3. In `site-common.js`: update the hamburger click handler to toggle a `.sidebar-open` class on `#sidebar` (sets `left: 0`) in addition to the existing `.open-sidebar` toggle on `.grid`. Also update the swipe-to-close handler to remove `.sidebar-open` from `#sidebar`.
4. Add CSS: `#sidebar.sidebar-open { left: 0; }`.

---

**Bug S** — Login page: nav bar overlaps form on mobile; style inconsistent with admin 🟢 XS

**Two sub-issues:**

1. **Nav overlap on mobile:** `login.html` extends `base_public.html`, so the login card sits inside `.grid` below the `.navigation-wrap` (hamburger bar, ~50px). The `#mobile-menu-btn` is `position: absolute; z-index: 100` within that bar. On narrow phones the login card's top margin (40px) is close to or below the button, risking overlap.

2. **Style inconsistency:** The public site uses the sidebar/hamburger nav from `base_public.html`. After login, volunteers land on toolkit pages that use the Bootstrap top navbar from `base_admin.html`. The login page sits at this junction, extending the public template, so its navigation context feels inconsistent with what comes after.

**Fix options:**

- Option A (minimal): Keep `base_public.html` extension; add `padding-top: 60px` to the `.grid` content area on mobile so the login card always clears the hamburger button.
- Option B (clean): Create a lightweight base template (e.g. `base_login.html`) with just the site logo centred, no navigation at all. This makes the login page clearly neutral — not the public site, not the admin.

Recommended: Option B for clear UX. Option A as a quick fix while the decision is made.

---

**Bug T** — Admin toolkit: mobile navbar overflow and layout issues 🔵 S

Three sub-issues:

**T1: Navbar brand image pushes toggler off-screen.** `base_admin.html` renders `<img height="40px">` with no `max-width`. If `VENUE.internal_header_img` is a wide landscape image, it overflows the navbar on narrow screens, pushing the Bootstrap collapse toggler off the right edge.

Fix: Add `max-width: 120px; width: auto; height: auto;` to the navbar brand `<img>`.

**T2: Body padding too large on mobile.** `base_admin.html` sets `body { padding: 5rem 1.4rem; }` globally. `5rem` top padding is meant to clear the fixed navbar (~56px ≈ 3.5rem), but 5rem overcompensates and wastes vertical space. `1.4rem` horizontal padding on a 375px viewport leaves ~330px usable width for content.

Fix: Add `@media (max-width: 576px) { body { padding: 3.5rem 0.5rem; } }` in the `base_admin.html` `<style>` block.

**T3: Rota controls bar overflows on narrow screens.** `edit_rota.html`'s `.rota-controls` bar contains two date inputs (each `width: 8em`) plus labels and three quick-select buttons. Although the controls use `flex-wrap`, the minimum combined width of date fields + labels (~320px) is already close to the usable content width after padding. On a 375px phone the controls are very cramped and may force a horizontal scroll.

Fix: Add a mobile media query in the `edit_rota.html` `<style>` block:

```css
@media screen and (max-width: 576px) {
    .rota-daterange input[type="text"] { width: 6em; }
    .rota-daterange label { display: none; }  /* "from" / "to" implied */
}
```

---

**Bug U** — Rota: excessive left indentation wastes horizontal space on mobile 🟢 XS

`ul.rota` inherits `padding: 0 0 0 40px` from the normalize reset in `static_pages.css` (line 202). Combined with `base_admin.html`'s `body { padding: 5rem 1.4rem }`, rota list items carry ~40px of blank left margin on mobile — roughly 12% of a 375px viewport.

`.showing_rota_notes` and `.event-links` both have `margin-left: 3em` (≈ 48px at typical font size), adding further waste.

**Fix:** Add to the `edit_rota.html` inline `<style>` block:

```css
@media screen and (max-width: 640px) {
    ul.rota { padding-left: 0; }
    .showing_rota_notes,
    .past_showing_rota_notes { margin-left: 0.5em; }
    .event-links { margin-left: 0.5em; }
}
```

---

**Bug V** — Tags/Roles admin: content overflows horizontally on narrow screens 🟢 XS

**V1: Tags page** (`edit_event_tags.html`): `#sortable li` is a flex row. The `.tag-options` child has `flex-shrink: 0`, preventing it from shrinking. On viewports under ~480px the combined content (drag handle + tag name + "Programme nav" label + checkbox + "Delete:" label + checkbox) overflows the card container. The `.card-body` has no `overflow-x: auto`, so it clips.

Fix: Add `overflow-x: auto` to `.card-body` in that template, or make `.tag-options` `flex-wrap: wrap` so it drops under the tag name on narrow screens.

**V2: Roles page** (`form_edit_roles.html`): The roles table has 7 columns; several have fixed widths (`width: 90px`, `width: 50px` × 4, `width: 60px`), totalling ~310px fixed before the name and description columns. On a 375px phone this table overflows by 100px+.

Fix: Wrap the `<table>` in `<div style="overflow-x: auto;">` inside the `card-body` div. This gives horizontal scrolling without restructuring the table.

---


## 8. Current limitations and known gaps

These are real limitations in the current system that a rewrite should address.

### 8.1 Rota is disconnected from volunteers
`RotaEntry.name` is free text. Volunteers are not linked to their rota slots.
Consequences:
- Can't email everyone signed up for a showing
- Can't see a volunteer's rota history
- Typos in names go undetected
- No way to confirm a volunteer is still active

**Solution spec — volunteer FK on RotaEntry** 🟡 M (~12–16h)

Add `RotaEntry.volunteer = ForeignKey(Volunteer, null=True, blank=True, on_delete=models.SET_NULL)`. Nullable so: (a) existing entries without a match keep `volunteer=None`, (b) external hires (task 9.22) stay as `volunteer=None` permanently.

Implementation steps, in order:

1. **Migration**: add the nullable FK column.
2. **Port name coercion from s+s** (`edit_views.py` `edit_rota_entry` view): when a non-superuser submits a non-empty rota slot, ignore the typed text and set `rota_entry.volunteer = request.user.volunteer`. Superusers retain free-text mode. This must land *before* the backfill migration, otherwise the backfill data is polluted with arbitrary strings.
3. **Backfill migration**: case-insensitive name match over existing `RotaEntry.name` values → `Volunteer.member.name`. Skip and log: entries with ambiguous matches (two volunteers share a name); entries with no match (typos, anonymised volunteers). This is best-effort.
4. **GDPR anonymisation update** (`volunteer_views.py:592`): primary path becomes `RotaEntry.objects.filter(volunteer=v).update(volunteer=None, name="")`. Keep the existing text-match sweep as fallback for legacy entries where the FK was never set.
5. **Pronouns tooltip update** (`edit_views.py:1380`): currently builds a name→pronouns dict and does a text lookup. Post-FK, entries with `volunteer` set go direct to `entry.volunteer.member.personal_pronouns`. Dict fallback remains for legacy entries.
6. **Display**: `edit_rota.html` and `view_rota.html` currently render `entry.name`. Post-FK, prefer `entry.volunteer.member.name` when FK is set.

**Design questions to answer before starting:**

1. **Name field retention**: keep `RotaEntry.name` as a separate field (used for external hires and legacy display), or derive it from the FK when set? Keeping it is simpler but creates two sources of truth. The safest path: keep the field, write it on sign-up from `volunteer.member.name`, and accept that it drifts if the member later changes their name.
2. **Superuser auto-link**: if a superuser types a name matching a volunteer, should the system attempt to link the FK? Convenient but adds a lookup on every save.
3. **Existing coercion gap**: master currently accepts any text from any user (coercion was never ported from s+s). Porting coercion should be a separate PR *before* the FK migration, so the backfill starts from a clean baseline.

**Unblocks**: 9.25 (tap-to-sign-up), 8.10 (volunteer workload view), "my schedule" view, reliable email to showing sign-ups, reliable GDPR erasure.

### 8.2 Volunteer induction is entirely manual
The Google Form → manual entry process has no automation. Names from the form
must be copy-pasted. There is no audit trail of who inducted whom.

### 8.3 Volunteer self-service is partial
Volunteers can log in, view the rota, and sign up for slots via an
interactive click-to-edit interface at `/diary/edit/rota/`. This is gated by
the `diary.change_rotaentry` Django model permission.

**Name coercion (S&S branch only, not yet on master):** when a volunteer
clicks a slot and submits any non-empty text, the server ignores what was
typed and instead saves `request.user.volunteer.member.name` — i.e. the
logged-in user's own name. This prevents volunteers from writing each other's
names into slots. Submitting an empty value clears the slot. Any volunteer
with the permission can clear any slot, including one filled by someone else
— there is no ownership check on deletion. Superusers (Panopticon) bypass the
coercion and can write any text freely.

This coercion logic exists on the `s+s` branch but has not yet been ported
to `master`, where the rota edit view currently accepts and saves whatever
text is submitted verbatim.

Editing a volunteer's own profile (`/volunteers/N/edit/`) requires
`toolkit.write` (Panopticon level) — there is no self-editing exception in
the current code.

There is no "my schedule" view — a volunteer cannot see a filtered list of
only the showings they are signed up for.

### 8.4 No reserve/standby slots
If someone drops out of a rota role, there's no mechanism for reserves. This
is handled informally (e.g. messaging the volunteers list).

### 8.5 Email list is managed externally
The link between "volunteers in the Toolkit" and "members of the Simplelists
mailing list" is entirely manual. There is no synchronisation.

A compounding problem: the volunteer list and the mailing list are two
separate systems with no shared identifier, but in practice one person's
presence on a training-specific mailing list (e.g. the bar volunteers list)
is often managed as a side-effect of their induction. When someone attends a
bar induction, they are added to the bar mailing list by the person running
the session — but this is a manual step that depends on whoever ran the
session remembering to do it. There is no record in the toolkit of which
lists someone is on.

Consequences:
- A volunteer who is bar-trained may not be on the bar mailing list if
  their induction was not followed up correctly
- If someone leaves and re-joins, they may not be re-added to specialist
  lists during their return induction, unless whoever runs it explicitly
  checks
- Someone may want to stop receiving emails from a list (e.g. bar) while
  remaining active in that role — but there is no clean way to distinguish
  "unsubscribed from list" from "no longer qualified"
- Over time, mailing lists accumulate former volunteers who have never been
  removed — making them less useful and noisier

### 8.6 Rota view is a wall of text
The rota view shows all events in a date range with all their role slots and
rota notes. There's no filtering, grouping, or visual hierarchy. Large rota
notes dominate the view.

### 8.7 No programming pipeline / approval process ✅ Partially addressed (2026-06-05)

**MVP delivered:** `Event.programming_status` (draft/proposed/active/rejected) + `Event.programming_notes` + programming queue view at `/diary/edit/programming-queue/`. Programmers can propose events for Monday meetings; queue shows pending items; quick approve/return/skip actions for Programmer+. See task 9.113 for full spec.

**Still open:** no Finance Collective threshold flag, no etiquette guide link, no TMDB integration. See §9.2 for the full pipeline roadmap.

~~Events go straight from "created" to "confirmed" without any formal approval step. Proposed events are reviewed in Monday meetings (often added on to meetings that are primarily about other things), but there's no standard process for them hitting the system first.~~

### 8.8 Training records are too rigid to model real role requirements
The current training record system tries to fit all role qualifications into a
single model: a logged event with a trainer name, a date, and a role. Records
expire after 12 months and must be re-logged. This overhead means records are
not maintained, and as a result the system is not used as a gate on role
sign-up at all.

The deeper problem is that the real qualification requirements (see rule 13)
are fundamentally different in kind, and a single model cannot represent them:

- **Induction-granted certificates** (food hygiene level 1) are delivered
  in-house as part of the monthly café induction. The gate is the induction
  itself — a boolean, like bar. The level 1 certificate is an outcome of
  attending, not something obtained separately.
- **External certificates** (food hygiene level 2) need a record of the
  certificate itself — issuing body, expiry date — not an internal training
  log. Expiry genuinely matters here and should be surfaced.
- **Internal tiered training** (projectionist levels) needs a progression
  model, not a flat list of records. Level 2 implies level 1; re-logging
  after 12 months makes no sense for a skill that doesn't expire.
- **Informal shadow-based progression** (sound/tech) should not be
  formalised at all. A lightweight "this volunteer is comfortable with this
  role" flag, set by the volunteer or a coordinator, is sufficient.
- **Induction gates** (bar) are binary — you have had the induction or you
  haven't. A single boolean per volunteer is the right model, not a
  timestamped log.
- **Nomination processes** (keyholder) are social and governance decisions,
  not training events. The system should record the outcome (this person is a
  keyholder) without trying to model the process that led there.

A rewrite should model these as distinct types rather than forcing them
through a single `TrainingRecord` schema. Hard gates (bar induction, food
hygiene cert) can block sign-up. Soft signals (sound/tech comfort flag) can
inform but not block. Keyholder status is a property of the volunteer record,
not a training record at all.

It's worth noting a real world pain point caused by this: Community Kitchen log their food hygiene level 2 certificates, which were agreed by policy to need refreshing every 2 years. Jonny wrote a spreadsheet for logging these, but this was never widely adopted in a way that would have been much easier if a culture of recording training was baked in from the start, and the toolkit had a frictionless ready-baked solution, as opposed to the (rather snazzy, if I do say so myself) google sheet that highlights when people are close to needing refreshers.

### 8.9 Training records expire silently
There's no notification or dashboard view highlighting volunteers whose
training has lapsed or is about to lapse. (This is a secondary issue given
8.8 — solve the friction problem first.) See 8.8 example at the end of Community Kitchen certs.

### 8.10 No view of volunteer workload
There's no way to see how many hours or shifts any given volunteer has
committed to, or to spot volunteers who are over-stretched or disengaged. Or invite dormant volunteers to re-induct (or want to be removed from the system, helping with good GDPR compatible processes?).

### 8.11 Room booking model is too simple for multi-room events
A `Showing` has a single optional `room` field. This works for a simple
screening in one room, but many events at S&S require multiple rooms at
different times within the same event — for example:

- Venue access from 4pm for general setup
- Cinema booth from 6pm for tech and AV prep
- Cinema itself from 7pm to 9pm for the event proper

The current system has no way to express this. The workarounds in use are:

1. **Create multiple events** — programmers book each room as a separate diary
   entry, cluttering the programme with fake events and disconnecting the rota
   from the real event.
2. **Create multiple showings of the same event** — slightly better, but the
   programme then shows the same event listed multiple times at different
   times, which is confusing publicly and internally.
3. **Do nothing** — the room bookings are informal or forgotten, leading to
   undetected clashes when two events assume they have access to the same
   space at the same time.

There is also no clash detection: the system does not warn when two confirmed
showings overlap in the same room.

### 8.12 Collectives are not modelled in the toolkit

The Star and Shadow operates through a network of informal working groups and
collectives — Bar Collective, Programming Collective, Technical Collective,
and various others — which self-assemble around a shared interest and operate
with significant autonomy. These are not captured anywhere in the toolkit.

**Current state:**

- Groups communicate primarily through mailing lists managed in
  [Simplelists](https://simplelists.com/). Creating or administering a list
  requires knowing someone who has Simplelists admin access — a small and
  informally defined group. There is no self-service route.
- There is no central directory of which collectives exist, what they do, or
  who is in them. This is sometimes intentional: groups may prefer not to
  be publicly findable.
- There is one collective listed in the info pages via Wagtail, accessible from the public site: Community Kitchen. A solution could have a "public copy" blurb about the collectives which would massively help prospective volunteers get a sense of how the cinema works, and if they'd like to join. Collectives that people might not assume operate out of a cinema - Community Kitchen, print room, library - might all benefit from being more visible, and we might get new folks approaching us for inductions because they're interested in those aspects.
- A volunteer wanting to contact, say, the Tech Collective has no
  in-system way of discovering who is in it or how to reach them. They must
  ask around in person or via the general mailing list.

**A specific pain point — new programmers and keyholders:**

A newly onboarded programmer must arrange keyholding cover for their event.
Keyholders are an informal group of long-standing trusted volunteers; there is
no list in the toolkit, and no automated way to request one. In practice:

- The programmer must know (or be pointed to) individual keyholders by name
- They make contact directly, often via personal messages or the general list
- Keyholders agree or decline based on personal availability and their
  relationship with the programmer

This friction might not be entirely accidental. Having to personally approach
keyholders — and earn their willingness to vouch for a showing — is a
lightweight form of community vetting. Any feature that automates this away
entirely should be considered carefully. The right response may be to make the
*list* of keyholders visible in the toolkit (so new programmers know who to
approach) while leaving the actual agreement as a human interaction.

**What the toolkit could usefully do:**

- Expose a read-only directory of active collectives and their public contact
  points (e.g. mailing list address), where the collective has opted in to
  being listed
- Allow a Role to be flagged as `keyholder_capable`, making it easy to surface
  that list without building a full collectives model
- Note: full collective membership management (join requests, mailing list
  sync, governance) would be a large feature (🔴 XL or ⛔ XXL) and is not
  recommended as an early priority

### 8.15 Frontend library debt — legacy and EOL dependencies

Several vendored and CDN-referenced frontend libraries are outdated, some
critically so. Audited February 2026.

#### 🔴 Critical — CVEs / confirmed EOL

| Library | Version in use | Issue |
| --- | --- | --- |
| CKEditor | 4.7.3 | ✅ resolved. Replaced with Quill 2.0.3 (vendored). `HtmlTextarea` widget re-pointed to `js/lib/quill/quill.js` + `css/lib/quill.snow.css`; `htmltextarea.html` rewritten. Old `static_common/js/lib/ckeditor/` directory deleted. |
| jQuery (public site) | 2.1.3 via Google CDN | ✅ resolved. Replaced CDN reference with locally vendored `jquery.min.js` (3.5.1) in both `templates/base_public.html` and `star_and_shadow_templates/base_public.html`. No external dependency, no EOL version. |
| Google Fonts (all templates) | HTTP URL | ✅ resolved. Fixed `http://` → `https://` in `base_admin.html` (live request) and removed dead IE8 conditional comment blocks containing `http://` from all three base templates. |

#### 🟠 High — Abandoned or no longer receiving security patches

| Library | Version in use | Issue |
| --- | --- | --- |
| jQuery UI | 1.11.0 (2014) | ✅ Resolved. Updated to 1.13.3 (current LTS, drop-in). Long-term: replace datepicker with native `<input type="date">`. |
| Bootstrap | 4.6.2 | No longer maintained. BS5 breaks `data-toggle` → `data-bs-toggle`, `mr-auto` → `ms-auto`, `sr-only` → `visually-hidden`. Migration is entangled with django-crispy-forms (see below). Effort: 🟠 L. |
| Chosen | 1.1.0 | ✅ resolved. `ChosenSelectMultiple` now extends plain `SelectMultiple` with no custom Media or template. `volunteer_training_report.html` updated to use native `.change()` instead of `.chosen()`. All Chosen static files and `chosenselectmultiple.html` template deleted. |

#### 🟡 Medium — Outdated pins or frozen libraries

| Library | Version in use | Issue |
| --- | --- | --- |
| FullCalendar | 3.5.1 (2017) | Superseded by v6 (no jQuery, TypeScript, ESM). Improving the calendar edit view would warrant this upgrade; it is a large migration. Effort: 🔴 XL. |
| Moment.js | bundled in FC | Frozen (maintenance-only). Automatically resolved if FullCalendar is upgraded to v6. |
| html2text | 3.200.3 (2015) | ✅ resolved. Unpinned in `requirements/base.txt`; pip will now resolve the current release. |
| django-crispy-forms | <1.13 | EOL; v2.x separates template packs. Migrate to `crispy-forms>=2.0` + `crispy-bootstrap5`. Entangled with Bootstrap 5 upgrade above. |
| mysqlclient | 2.1.0 | ✅ resolved. Updated constraint to `>=2.2.0,<3` in `requirements/docker.txt`. |

#### 🟢 Low — Dead code to delete

- `respond.min.js` — IE8 media-query polyfill. IE8 is <0.01% of users. ✅ Removed
  (file deleted; script tag removed from both public base templates).
- IE8 conditional comments — `<!--[if lte IE 8]>` blocks in `base_public.html`
  and `base_admin.html` load six redundant Google Fonts requests that no browser
  will ever make. ✅ Removed (no longer present in templates).
- `wysihtml5.css` — WYSIHTML5 has been unmaintained since ~2014; verify it is not
  referenced anywhere and delete it. ✅ Deleted 2026-03-03 (confirmed unreferenced).

#### Recommended order of attack

1. ✅ HTTP → HTTPS on admin Google Fonts
2. ✅ jQuery 2.1.3 → 3.7+ on public site (local vendor)
3. ✅ Unpin `html2text` and `mysqlclient`
4. ✅ CKEditor 4 → Quill 2 (security-critical)
5. ✅ jQuery UI 1.11 → 1.13
6. ✅ Delete Respond.js and IE8 conditional comment blocks
7. ✅ Delete `wysihtml5.css`
8. ✅ Chosen → native `<select multiple>`
9. Bootstrap 4 → 5 + `crispy-forms` 2.x (batch together) — Effort: 🟠 L
10. FullCalendar 3 → 6 (large; do when calendar editing needs attention) — Effort: 🔴 XL

### 8.16 No default image when creating an event

When a programmer creates a new event without uploading a poster, the event has no image and appears imageless on the public programme grid. This is more noticeable at S&S than at the Cube because the PVSL licence means film posters often can't be published until shortly before the event.

**Partial solution already in the codebase:** `seed_dev_data` includes `_make_poster_image` — a bold typographic poster generator that takes the event name and a tag-derived colour, renders it at 800×450 with a gradient background, and stretches each line of text to fill the full frame width. It produces something that looks intentional rather than broken.

This could be wired up as an on-demand tool for programmers: a button on the event edit page ("Generate placeholder image") that calls a view invoking the same logic and attaches the result as a `MediaItem`. The bundled `DejaVuSans-Bold.ttf` in `seed_data/fonts/` is available to the server at runtime.

**Not yet implemented.** See 9.57 for the proposed feature spec.

---

---

