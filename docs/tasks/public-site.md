# S&S Toolkit — Public Site & Programme

Feature specs for the public-facing programme, archive, images, feeds, and filter UI.

**For work status:** [CURRENT_WORK.md](../../CURRENT_WORK.md)

---

### 9.27 Archive image visibility control (`SHOW_ARCHIVE_IMAGES`) — ✅ Done 2026-02-28

**Problem being solved:**

The Star & Shadow has an event archive stretching back years, but systematic image uploads only began in May 2018. Events before that date have no images, so the public `view_event` page has a broken/empty image area for them. Worse, future scraped imports of old events could end up showing copyrighted images that hadn't been cleared for digital publication.

**Solution (implemented):**

Two settings control archive image visibility:

- `SHOW_ARCHIVE_IMAGES` (bool, default `True`) — when `True` (Cube default), images are always shown. When `False` (S+S default), images are hidden for events where every showing predates `IMAGES_START_DATE`.
- `IMAGES_START_DATE` (string, default `None`) — the cutoff date in `"%d %b %Y"` format (e.g. `"1 May 2018"`). Only relevant when `SHOW_ARCHIVE_IMAGES = False`.

**Logic (in `_show_archive_images()` in `public_views.py`):**

1. Authenticated users (volunteers) always see images regardless of settings.
2. If `SHOW_ARCHIVE_IMAGES` is `True`, always show.
3. Otherwise, parse `IMAGES_START_DATE` and show images only if **all** showings for the event start after the cutoff date.

The context variable `show_archive_images` is passed to the `view_event.html` template, which gates the image block: `{% if show_archive_images and media_item %}`.

**Files changed:**

- `toolkit/settings_common.py` — defaults: `SHOW_ARCHIVE_IMAGES = True`, `IMAGES_START_DATE = None`
- `toolkit/settings_starandshadow.py` — S+S overrides: `SHOW_ARCHIVE_IMAGES = False`, `IMAGES_START_DATE = "1 May 2018"`
- `toolkit/diary/public_views.py` — `_show_archive_images()` helper; `view_event` passes `show_archive_images` in context
- `star_and_shadow_templates/view_event.html` — gates image display on `show_archive_images`

---

### 9.28 Volunteer role tier labelling and GDPR danger indicators — ✅ Done 2026-03-02

**Problem:**

The `UserForm` on the volunteer edit page currently uses Django's raw field labels (`is_superuser`, `is_active`). This is confusing for admins who think in terms of venue-specific role tiers. The toolkit has three meaningful tiers:

- **User** — can log in and see/edit the rota
- **Programmer** — member of the `Programmers` group; can edit events, showings, members (read access to names/emails = GDPR-sensitive)
- **Panopticon** — `is_superuser=True`; full Django admin access (read/write to everything = high GDPR sensitivity)

The user form should use these names. Additionally, Programmer and Panopticon roles should carry a visible warning that granting them exposes GDPR-covered data (member names, emails, addresses) to the recipient.

**Proposed changes:**

1. Replace `is_superuser` label with "Panopticon access" (and possibly add a help text: "Full admin access. Exposes all member data — GDPR sensitive.")
2. Add a read-only display of "Programmer" group membership alongside the form (or make it editable).
3. Add a visual warning (e.g. a small ⚠ badge or red label) next to Programmer and Panopticon fields in `form_volunteer.html`.

**Implementation notes:**

- Cleanest option: override `UserForm.Meta.labels` and `UserForm.Meta.help_texts` rather than rewriting the form.
- For Programmer group membership, a `BooleanField` or a `CheckboxInput` backed by `volunteer.user.groups.filter(name="Programmers").exists()` can be added to `UserForm` as an extra non-model field with custom save logic.
- The warning copy should reference the venue's GDPR policy or contact address.

---

### 9.37 Public programme tag filtering and keyword search 🔵 S (8–16h)

**Goal:** Let site visitors filter the public programme by event tag or keyword, similar to the existing rota tag filter (9.10.1).

**Design principles:**

- The primary programme view should remain clean and uncluttered. Filters should be hidden behind a "Filter" label/button or collapsed by default — don't lead with a filter bar.
- Consider whether filters belong in the sidebar nav (always visible, space-efficient) or in a collapsible panel below the page header.
- Keyword search should be purely client-side (filtering visible elements) to avoid page reloads — similar to the existing volunteer table sort.

**Scope:**

- **Tag filter** — a multi-select tag list (or checkbox group) that shows/hides events by tag. Composes with keyword filter if both are active.
- **Keyword filter** — a text input that filters events by matching against title, copy summary, and tags. Case-insensitive, client-side JS.
- **URL persistence** — if tag or keyword filter is set, encode it in the URL (query string) so the URL can be shared or bookmarked with the filter active.
- **"Reset filters" link** — always visible when a filter is active; clears all filters.

**Tag analysis prerequisite:** Before building the filter, review the current tag set against real events on the live site to confirm tags are useful, well-populated, and not redundant. Some tags may be too granular or too broad to be useful for public filtering. This is a research task (browse live event archive, count usage per tag, identify gaps) — schedule as a separate session. See also: what tag taxonomy would best serve a public "filter by tag" feature?

**Related:** 9.10.1 (rota tag filter), event tag model

---

### 9.57 — Placeholder image generator for new events 🟢 XS (2–4h)

**Context:** See 8.16. When a programmer creates an event without uploading a poster, the programme grid shows a blank where the image should be. This is jarring, especially for recurring events (café, film club) where a poster may never exist.

**Proposed:** Add a "Generate placeholder image" button to the event edit page. On click, it calls a small Django view that runs the same `_make_poster_image` logic from `seed_dev_data` — gradient background derived from the event's first tag, event name stretched bold across the frame — and attaches the result as a `MediaItem` on the event.

**Implementation sketch:**
- Extract `_make_poster_image` (and `_find_bold_font`) from `seed_dev_data.py` into a shared utility, e.g. `toolkit/diary/poster.py`
- Add a POST view `generate_event_poster(event_id)` behind `diary.change_event` permission
- Wire up a button in the event edit template, next to the existing media upload widget
- The bundled font at `seed_data/fonts/DejaVuSans-Bold.ttf` works at runtime; the view should use it directly rather than looking up system fonts

**Out of scope for this ticket:** custom colour picker, font choice, or text override — the generated image is a placeholder, not a design tool.

---

### 9.58 — Rethink how recurring events appear on the programme 🟡 M (design first)

**Context:** The current data model has a single `Event` with multiple `Showing` objects — one per occurrence. The public programme grid (`view_showing_index.html`) groups showings by event: one card per event, all dates listed underneath. The list view shows each showing individually in chronological order.

**The problem:** For recurring events like the Sunday café or weekly film screenings, the grid shows one card with a wall of dates stacked in the `start_and_pricing` block. This conflates "what this event is" with "when it's happening next" — which works for a one-off film but is confusing for a rolling programme.

**Options to consider:**

1. **One card per showing (current list behaviour, applied to grid):** Every showing gets its own card. The café appears 52 times in a year view. Clean and consistent, but noisy for recurring events and would need pagination or a shorter default window.

2. **One card per event, show only the next upcoming showing date:** The card says "Next: Sunday 5 April, 12:00" rather than listing all dates. Cleaner, but hides the full schedule.

3. **Separate "recurring event" model:** Distinguish one-offs from recurring series. A `RecurringSeries` has a schedule rule (e.g. "every Sunday") and generates `Showing` objects on demand. The grid shows the series with its next date; a detail page shows the full schedule. This is the most correct model but a significant migration.

4. **Hybrid: show first N upcoming showings per card:** Show the next 2–3 dates on the card with a "see all dates" link. Reasonable middle ground; no model changes needed.

**Recommendation:** Options 1 or 4 are achievable without model changes. Option 2 requires a small template change. Option 3 is the right long-term answer but needs collective input on what "recurring" means — fixed schedule vs ad-hoc.

**Design questions for the collective:**
- Is the café genuinely the same event each week, or is each Sunday its own thing?
- Should a cancelled café Sunday affect the recurring series or just that occurrence?
- Do we want to show programme history (past showings of the same event) on the event detail page?

Do not implement until the data model question (option 3 vs not) is settled — the wrong choice now creates migration debt.

---

### 9.59 — Programmer-defined crop region for index/listing images 🟡 M (16–30h)

**Context:** Event images are stored at their full uploaded aspect ratio (portrait, landscape, square — whatever the programmer chose). The public programme index (`view_showing_index.html`) displays these as thumbnails via `easy_thumbnails`' `indexview` alias (`600×0` — scales to 600px wide, proportional height). This means portrait posters appear very tall in the grid and landscape banners appear very short; the grid becomes visually uneven.

The current live S+S site sidesteps this by serving all images square (800×800 with implicit crop). That works but destroys context — the top of a tall poster may be chopped off, cutting out the film title. The Cube site has the same problem with its `indexview` alias.

**The right solution:** let the programmer choose a crop region at upload time, similar to how Wagtail handles focal points. The stored image remains uncropped (so the event detail page shows the full poster), but the index thumbnail uses the chosen crop.

**Design options:**

1. **Focal point only (simplest):** Programmer picks a focal point (x, y) on the image. The thumbnail generator always centres its crop on that point. `easy_thumbnails` supports this via the `crop` option + a source anchor. Small form widget needed.

2. **Explicit crop box:** Programmer drags a rectangle on the image to define the crop region. More control, higher implementation cost. Similar to Wagtail's image crop UI.

3. **Free-form crop per alias:** Different crops for `indexview` vs `editpreview` vs future sizes. Most flexible, most complex — probably overkill.

**Recommended approach:** Option 1 (focal point). Store `media_item.focal_x` and `media_item.focal_y` as floats (0.0–1.0, relative coordinates). Update `indexview` alias to use `crop="smart"` or a custom thumbnailer that honours the focal point. Default (no focal point set) falls back to centre-crop.

**Data model change needed:**
- Add `focal_x`, `focal_y` to `MediaItem` (nullable floats, `null=True, blank=True`)
- Migration required

**Form change needed:**
- In the media upload widget on the event edit page, add a simple click-to-set-focal-point UI (JS overlay on the image preview)

**Template/thumbnail change:**
- Update `indexview` alias to use crop mode
- Custom thumbnail tag may be needed if `easy_thumbnails` can't be given per-item focal points via aliases alone (its built-in focal-point support is limited)

**Out of scope for this ticket:** full Wagtail-style drag-crop UI, per-alias crop regions, or changes to the event detail view (which should always show the full uncropped image).

---

### 9.147 — Age rating filter on public programme (progressive reveal for "Film" group) 🔵 S (6–10h)

**Context:** The programme filter bar (`view_showing_index.html`, see `prog_index()` in `public_views.py`) already has a group-type filter row driven by `EventTag.filter_group` — buttons for Film / Event / etc, built from `filter_groups` and `tag_filter_map_json` in the view context. There's a separate day-of-week filter row underneath. Both are client-side JS filters over the rendered cards; no server round-trip.

`SiteConfiguration.age_rating_choices` already exists (a configurable JSONField of value/label pairs, BBFC-style by default — `U`, `PG`, `12A`, etc, see `event.py:472` `Event.get_age_rating_display()` equivalent) and is set per-event. So the data is already there; this ticket is purely about exposing it as a filter.

**Goal:** Let visitors filter the programme by age rating, but only surface the control once they've selected the "Film" group filter — keeping the default filter bar uncluttered for people just browsing what's on.

**Explicitly out of scope:** genre filtering. Flagged but deliberately not pursued — tag/genre data quality isn't there yet, and part of the venue's appeal is showing a genre-defying mishmash rather than letting people filter themselves into a narrower comfort zone. Revisit only if someone commits to maintaining clean genre tagging.

**Proposed approach:**
- Server side: add an `age_rating` row to the existing tag-filter-style context data, or simply emit the set of distinct age ratings present in the current showings queryset (`Event.objects.values_list("age_rating", flat=True).distinct()`) alongside `filter_groups`.
- Client side: a new filter-button row, same `prog-filter-btn` pattern as the existing day-of-week row, but hidden (`display: none` or a `hidden` attribute) until `data-filter-group="film"` (or whatever slug the Film group resolves to) becomes active. Toggle visibility in the same JS that currently handles `data-filter-group` clicks.
- Filtering logic: extend the existing client-side card-filtering JS to also check `data-age-rating` on each card, the same way it already checks `data-filter-group` and `data-dow-filter`.

**Design note:** the reveal should animate or at least appear without a layout jump that scrolls the page — a sudden new row above the card grid is jarring. A simple slide-down or fade-in on the new row, or reserving the vertical space with `visibility: hidden` rather than `display: none`, avoids this.

**Sizing:** mostly front-end — extending an existing JS filtering pattern rather than building new infrastructure, hence S not M.

---

### 9.62 — Mailing list subscriptions as a proper toolkit Django view 🔵 S (3–6h)

**Context:** The current "Working groups" page at `/toolkit/working-groups/` is a live Wagtail `ComplexArticlePage` with `show_in_menus=False` (unlisted — access by URL only). It embeds mailing list signup forms via `raw_html` blocks — almost certainly Mailman subscription form embeds. It has been live since 2017 and is widely shared in rota notes and at inductions.

**Update (May 2026):** The `/toolkit/working-groups/` URL is confirmed login-gated on the live site — the entire `/toolkit/` prefix requires authentication. The auth concern below is no longer a driver for this migration; the remaining problems still stand.

The problems with the current setup:
- It lives in the CMS, which makes it awkward to maintain consistently and easy to accidentally publish to the nav
- It belongs in the toolkit proper alongside other volunteer-only pages, not hidden in the Wagtail tree

**What to build:**

A new Django view at `/toolkit/mailing-lists/` (or `/toolkit/working-groups/` if we want to preserve the existing URL) that:

1. Requires `@login_required` (redirects to `/auth/login/` like all other toolkit views)
2. Renders a page listing all mailing lists volunteers can subscribe to
3. Embeds the same Mailman subscription form(s) currently in the Wagtail page — either as an `<iframe>` or as raw form HTML — so the behaviour is identical to today's page from a volunteer perspective

The view should be:
- Added to `toolkit/index/views.py` or a new `toolkit/content/views.py`
- Registered in `urls_flat.py` under `/toolkit/mailing-lists/` with `login_required`
- Rendered by a template at `star_and_shadow_templates/mailing_lists.html` (or toolkit template dir)

**IndexLink update:** Update the `IndexLink` record (id=5, currently pointing at the Wagtail URL) to point to the new Django URL. This is a DB change — either a migration or a manual admin edit.

**Wagtail page:** Once the Django view is live and the `IndexLink` is updated, the old Wagtail page (id=31, `/toolkit/working-groups/`) can be unpublished via the CMS. Do not delete it immediately — keep it as a draft for a few weeks in case any bookmarked URLs need redirecting.

**Optional redirect:** Add a Wagtail redirect (via the Wagtail admin Redirects panel) from `/toolkit/working-groups/` → `/toolkit/mailing-lists/` so old bookmarks don't 404.

**What the template needs:**
- Page title: "Mailing lists" or "Working group mailing lists"
- Brief intro (1–2 sentences): what the lists are, that you can unsubscribe at any time
- The subscription form embed(s) — inspect the current Wagtail page source on the live site to extract the exact form HTML before migrating

**Out of scope for this ticket:** actually managing list membership from the toolkit (showing which lists a volunteer is subscribed to, one-click subscribe/unsubscribe). That would require a Mailman API integration — a separate, larger ticket.

**Related:**
- The `Micro-projects (form)` Wagtail page (`/toolkit/micro-projects/`, `EmailFormPage`, id=71) is also unlisted and volunteer-facing — same problem, probably worth a similar migration once this one is done

---

### 9.102 — Replace Masonry.js with CSS Grid on the programme index 🔵 S (6–10h)

**Problem.**

The programme index uses Masonry.js to pack `.showing` cards into a waterfall layout. This causes several compounding problems:

- **Reading order is broken.** Masonry fills columns top-to-bottom, so the visual sequence diverges from the DOM/chronological order. A card in column 2, row 1 may be chronologically earlier than a card at the bottom of column 1 — visually it reads as later. For a cinema programme where "what's on next?" is the primary question, this is a significant UX failure.
- **Accessibility.** Screen readers follow DOM order (chronological); sighted users follow visual column order. These diverge — a violation of WCAG 1.3.2 (meaningful sequence) and a practical failure for keyboard navigation.
- **Fragility.** Every filter operation, image load, and resize requires a Masonry relayout call. The absolute-positioning Masonry applies to items creates opaque interactions with padding and image sizing (demonstrated during the June 2026 mobile UX session).
- **No span/feature cards.** The index view never used `grid-item--width2/3`, so none of Masonry's editorial-collage capability is actually in play — the only reason it's being used is to avoid whitespace from variable card heights.

**Proposed solution: CSS Grid (Option A).**

Replace Masonry with a standard CSS Grid. Cards flow left-to-right and wrap to the next row. Column count adjusts at breakpoints using `auto-fill`/`minmax`. Card height is determined by content — no JS, no relayout, no absolute positioning.

```css
.programme {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 1rem;
}
```

Visual order = DOM order = chronological. Full-width posters on mobile are trivial. No JS needed for layout.

**Migration scope.**

| Area | Change |
|---|---|
| `site-common.js` | Remove Masonry init, `imagesLoaded` relayout, and `$('.programme').masonry(masonry_opts)` in the grid/list switcher. Remove `$(window).load` layout call. |
| `view_showing_index.html` | Remove `.showing-sizer` and `.gutter-sizer` sizing divs |
| `programme.js` | Remove `$(".programme").masonry("layout")` call after filter |
| `programme.css` | Replace `.showing-sizer`, `.gutter-sizer`, and all Masonry-dependent breakpoint rules with a CSS Grid declaration. Remove `position: relative` on `.programme` (no longer needed to contain absolutely-positioned children). |
| `base_public.html` / `view_showing_index.html` | No change needed — `masonry.pkgd.min.js` and `imagesloaded.pkgd.min.js` can be removed from the `<script>` block once the migration is confirmed stable. |

**What stays the same.**

- The list/grid switcher still works — the grid view is toggled with `show()`/`hide()` as before, the Masonry relayout call is simply dropped.
- The search filter still works — `filter-hidden` toggling `display:none` on cards is unaffected by the layout method.
- The S+S visual identity is unchanged. Clean grid may actually suit the site's typographic character better than the waterfall.

**Aesthetic trade-off.**

The main loss is the "editorial collage" feel of variable-height packing. The gain is visual clarity and a layout that actually communicates chronological order. The list view remains for users who want strict sequencing; the grid view's job is scannable visual browsing, and a clean grid does that well.

**Approach: branch and trial.**

Implement on a feature branch (`grid-layout-trial` or similar) so the visual result can be reviewed against the live Masonry version before merging. No model/migration changes needed — pure CSS/JS/template work.

**Size estimate:** 🔵 S (6–10h) — mostly CSS cleanup; the logic changes are small.

---

### 9.103 — Subtle event-type tints on programme cards 🟢 XS (1–2h)

**Problem.**
All programme cards look identical at a glance. A very subtle background tint per event category would help volunteers and audiences quickly scan the programme by type (film vs music vs cafe vs workshop) without visual clutter.

**Approach.**
CSS attribute selector on the existing `data-tags` attribute already rendered on each `.showing` card. No model changes, no template changes, pure CSS.

```css
.showing[data-tags~="film"]        { background: rgba(210, 225, 248, 0.62); }
.showing[data-tags~="music"]       { background: rgba(238, 215, 248, 0.62); }
.showing[data-tags~="cafe"]        { background: rgba(215, 245, 222, 0.62); }
.showing[data-tags~="workshop"]    { background: rgba(250, 242, 215, 0.62); }
.showing[data-tags~="performance"] { background: rgba(248, 218, 228, 0.62); }
.showing[data-tags~="party"]       { background: rgba(252, 232, 212, 0.62); }
```

**Priority:** First matching tag in `data-tags` wins. If an event has both `film` and `workshop`, `film` wins because it appears first in the attribute (tags are in insertion order).

**Specificity note:** These selectors have specificity 0,2,0 (class + attribute). `.showing-internal` (also 0,2,0) must be declared AFTER these rules so internal events always override the type tints. Currently correct in `programme.css`.

**Size estimate:** 🟢 XS — already implemented. Included here as documentation and in case of future tuning.

---

### 9.104 — Programme RSS/Atom feed 🔵 S (4–8h)

**Why it matters.**
RSS is the lowest-friction way for regulars to follow the programme without checking the website or joining a mailing list. Jonny specifically values this. Feed readers (Feedly, NetNewsWire, self-hosted aggregators) pick up new showings automatically.

**Proposed feed.**
A standard Atom feed (`/programme/feed/` or `/diary/feed/`) of upcoming public showings, ordered by start date. Per item:

| Field | Source |
|---|---|
| Title | `{event.name}` — `{showing.start|date:"l j F, H:i"}` |
| Link | `single-event-view` URL |
| Published | `showing.created` (or event date added) |
| Updated | Latest of event/showing save times |
| Summary | `event.copy_summary` |
| Content | `event.copy_html` |

**Out of scope (MVP):** per-tag filtered feeds, iCal (separate feature 9.10.4).

**Django implementation:** use `django.contrib.syndication.views.Feed` — no extra dependencies. Subclass `Feed`, override `items()`, `item_title()`, `item_link()`, `item_description()`. Wire into the S+S URL conf. Add `<link rel="alternate" type="application/rss+xml">` to `<head>` in `base_public.html`.

**Size estimate:** 🔵 S (4–8h) — the syndication framework handles most of the boilerplate.

---

### 9.105 — Configurable programme filter buttons 🔵 S (8–14h)

**Problem.**
The programme page has a text search box but no way to quickly narrow to a broad category (film, music, cafe, meeting). The existing `type-view` links in the nav sidebar are too hidden to be useful for casual browsing. Tag colour tints (9.103) were tried but made the page visually noisy without adding enough navigational value.

**Goal.**
Add a row of filter buttons above the programme grid -- **All | Film | Music | Cafe | Meeting** (or whatever groups the venue configures) -- that filter cards client-side, working alongside the text search (AND logic). Panopticon users control which buttons appear, and which tags map to which button, via the existing `/diary/edit/eventtags/` page.

---

**Model change: `EventTag.filter_group`.**

Add a nullable `CharField` to `EventTag`:

```python
filter_group = models.CharField(
    max_length=50,
    null=True,
    blank=True,
    help_text="If set, this tag contributes to the named filter group on the public programme page.",
)
```

The allowed values are not enforced at the DB level; they are validated against `settings.PROGRAMME_FILTER_GROUPS` (see below). A tag with `filter_group=None` does not appear in any filter button. Multiple tags can share a `filter_group` value (e.g. "party" and "music" both map to "music"), so the buttons are coarser than the full tag vocabulary.

---

**Settings: `PROGRAMME_FILTER_GROUPS`.**

Add to `settings_common.py` (overridable per venue):

```python
# Ordered list of (slug, label) pairs that appear as programme filter buttons.
# Only groups that have at least one active tag assigned to them are rendered.
PROGRAMME_FILTER_GROUPS = [
    ("film",    "Film"),
    ("music",   "Music"),
    ("cafe",    "Cafe"),
    ("meeting", "Meeting"),
]
```

The slug must match values used in `EventTag.filter_group`. The label is the button text. Order determines button order. Venues can add, remove, or rename groups by overriding this setting.

The edit view should validate `filter_group` values against this list (or present only the valid choices in the dropdown, derived from the setting at form-render time).

---

**Edit view: `/diary/edit/eventtags/`.**

Add `filter_group` to the formset's `fields` tuple. In the template, add a "Filter group" `<select>` dropdown column to the tag row, alongside the existing "Nav" checkbox. Options:

```
— (none)
Film
Music
Cafe
Meeting
```

The choices are generated from `settings.PROGRAMME_FILTER_GROUPS` at render time, so adding a new group to settings immediately makes it selectable without a code change.

The form field should use a `ChoiceField` or `TypedChoiceField` with the empty choice as `("", "—")`. A custom `ModelForm` for `EventTag` will be needed to build the choices dynamically from settings rather than hardcoding them.

---

**Programme view: pass filter group map to template.**

In `public_views.py`, query active tags that have a `filter_group` set:

```python
from django.conf import settings

filter_tags = (
    EventTag.objects
    .filter(archived=False, filter_group__isnull=False)
    .exclude(filter_group="")
    .values("slug", "filter_group")
)
# Build slug → group dict for JS
tag_filter_map = {t["slug"]: t["filter_group"] for t in filter_tags}
# Build ordered list of groups that actually have tags, preserving settings order
configured_groups = settings.PROGRAMME_FILTER_GROUPS  # [(slug, label), ...]
active_group_slugs = set(tag_filter_map.values())
filter_groups = [(slug, label) for slug, label in configured_groups if slug in active_group_slugs]
```

Pass `filter_groups` and `tag_filter_map` to the template context.

---

**Template: render filter buttons.**

In `view_showing_index.html` (S+S override), add a button row inside `.programme-filter-bar`, before or after the search input:

```html
{% if filter_groups %}
<div class="programme-tag-filters" role="group" aria-label="Filter by type">
    <button type="button" class="prog-filter-btn prog-filter-btn--active" data-filter-group="">All</button>
    {% for slug, label in filter_groups %}
    <button type="button" class="prog-filter-btn" data-filter-group="{{ slug }}">{{ label }}</button>
    {% endfor %}
</div>
{% endif %}
```

Emit the tag→group map as an inline script so the JS can use it without a fetch:

```html
<script>window.PROG_TAG_FILTER_MAP = {{ tag_filter_map|json_script_value }};</script>
```

(Use Django's `json_script` template tag or a custom filter to safely serialise the dict.)

---

**JS: extend filter logic.**

Extend `programme.js` to track an active filter group alongside the text search term. The two conditions are ANDed: a card is visible only if it matches both.

```js
var activeGroup = "";  // "" = All

function cardMatchesGroup(card, group) {
    if (!group) { return true; }
    var tags = (card.dataset.tags || "").split(" ");
    var map  = window.PROG_TAG_FILTER_MAP || {};
    return tags.some(function (slug) { return map[slug] === group; });
}

function applyFilter(term, group) {
    // group defaults to current activeGroup if not passed
    if (group === undefined) { group = activeGroup; }
    activeGroup = group;
    term = (term || "").toLowerCase().trim();
    // ... existing logic plus:
    document.querySelectorAll(".programme > .showing").forEach(function (card) {
        var textMatch  = !term || (card.dataset.searchText || "").toLowerCase().indexOf(term) !== -1;
        var groupMatch = cardMatchesGroup(card, group);
        card.classList.toggle("filter-hidden", !(textMatch && groupMatch));
    });
    // ... sync inputs, reset buttons, URL params (add ?group= alongside ?search=)
    updateFilterButtons(group);
}

function updateFilterButtons(group) {
    document.querySelectorAll(".prog-filter-btn").forEach(function (btn) {
        btn.classList.toggle("prog-filter-btn--active", btn.dataset.filterGroup === group);
    });
}
```

Wire button clicks:

```js
document.querySelectorAll(".prog-filter-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
        applyFilter(currentSearchTerm(), this.dataset.filterGroup);
    });
});
```

Restore group from URL on load (e.g. `?group=film`).

---

**CSS: button styles.**

Add to `programme.css`. Buttons should feel like tabs or toggle chips, not primary actions. Suggested approach: pill-shaped, neutral background, bold text on active, no heavy border:

```css
.programme-tag-filters {
    display: flex;
    gap: 0.4rem;
    flex-wrap: wrap;
}

.prog-filter-btn {
    padding: 0.2rem 0.75rem;
    border-radius: 999px;
    border: 1px solid #ccc;
    background: #f5f5f5;
    cursor: pointer;
    font-size: 0.875rem;
}

.prog-filter-btn--active {
    background: #222;
    color: #fff;
    border-color: #222;
}
```

---

**Disable colour tints (9.103).**

Comment out the six `.showing[data-tags~="..."]` tint rules in `programme.css`. Keep them in place -- they may be revived as an accessibility option. The `filter_group` mapping provides enough tag-type signal via the filter buttons without needing the tints.

---

**Migration.**

Standard `makemigrations diary` + `migrate`. The new field is nullable with `blank=True`, so no data migration is needed and existing rows default to `None`.

After migrating, run `seed_dev_data` (or manually assign groups in the admin) to set `filter_group` on the seed tags so the buttons appear in development.

---

**Out of scope for this task.**
- Making filter buttons appear in the mobile nav search bar (can be added later)
- Accessibility option to re-enable colour tints per user preference
- Per-venue button label overrides beyond what `PROGRAMME_FILTER_GROUPS` already covers

---

**Size estimate:** 🔵 S (8–14h) — model + migration + form + view + template + JS. Most complexity is in the JS filter extension and wiring the settings-driven choices into the form cleanly.

---

### 9.106 — Varied alt text in seed data for accessibility testing 🟢 XS (1–2h)

**Problem.**
`seed_dev_data.py` currently sets `alt_text=f"Placeholder image for {event_name}"` for every media item -- all identical in structure, none descriptive enough to test accessibility tooling meaningfully.

**Goal.**
Replace the uniform placeholder with a small pool of varied mock alt texts so screen reader testing, automated WCAG audits (axe, WAVE), and manual keyboard walkthroughs have something realistic to work with. Accuracy doesn't matter -- variety and plausible length do.

**Approach.**
Define a list of ~15--20 fake but varied alt texts in `seed_dev_data.py` (e.g. "Black and white film still of two figures in a doorway", "Hand-drawn poster with bold yellow type on red", "Photograph of a band on a small stage, crowd in foreground") and assign them round-robin or randomly to seed media items. Some should be intentionally long, some short, a few blank (to test the missing-alt-text case in audits).

**Size estimate:** 🟢 XS (1--2h) — pure seed data change, no model or migration needed.

---

### 9.107 — Auto-compress images on upload 🟢 XS (2–4h)

**Problem.**
Volunteers upload high-resolution images (camera raws, unoptimised scans) that can be many megabytes. These inflate storage and slow down page loads, especially on the programme index where many images are loaded together.

**Goal.**
When a new `MediaItem` image is saved and the file exceeds the configured size limit, automatically recompress it server-side before storing. The limit should be readable from `SiteConfiguration` (new field `max_upload_image_kb`, default 5120 KB / 5 MB). If the file is already under the limit, leave it untouched.

**Proposed approach.**
Override `MediaItem.save()` (or use a `post_save` signal) to open the image with Pillow, re-save as JPEG at a quality that brings the file under the threshold, and replace the `ImageField` file in-place. A simple binary search on quality (start at 85, step down until under limit) works well enough for the MVP. Preserve the original format for PNG files used as logos (detect by extension or format); only compress JPEG/non-alpha uploads.

**SiteConfiguration change.**
Add `max_upload_image_kb = models.PositiveIntegerField(default=5120)` + migration. Expose in the Panopticon site settings form. Set to `0` to disable compression entirely.

**Out of scope (MVP).**
- Re-encoding existing images retroactively
- WebP conversion
- Preserving EXIF metadata (strip it — privacy benefit too)
- Per-event or per-upload overrides

**Size estimate:** 🟢 XS (2–4h) — Pillow is already a dependency; main work is the save hook, the SiteConfiguration field, and one or two tests.

---

### 9.130 — Printed programme archive: season model + gallery view 🟡 M (12–20h)

**Context.** The current `PrintedProgramme` model stores one PDF per calendar month (`month` DateField, unique). S+S publishes programmes by season (typically covering 2–3 months), so the month-per-record model forces a mismatch: either one month gets the file and others are blank, or the same PDF is uploaded multiple times.

Separately, the archive is not currently exposed as a public-facing gallery. The data exists but there's no browsable index with thumbnails.

**Part 1: Season model.**

Replace the `month` DateField with `start_month` + `end_month` DateFields (both stored as the 1st of the month, as now). The `unique` constraint on `month` becomes a constraint that season ranges do not overlap. The `month_in_range` queryset method becomes `seasons_overlapping(start, end)`.

The admin upload form changes to pick a start month and an end month (defaulting to the same month for backwards compatibility). No data loss — existing records gain `end_month = start_month`.

Migration: rename column + add `end_month`. Existing rows: `end_month = month` (i.e. single-month seasons for everything already uploaded).

**Part 2: Gallery view.**

Add a public-facing gallery page at `/programme-archive/` (or under the existing public diary URLs). Each season entry shows:
- A thumbnail of the first page of the PDF (generated on upload using `pdf2image` / `poppler`, stored as a `thumbnail` ImageField)
- Season label (e.g. "Spring 2025 · Feb–Apr")
- Designer credit if present
- Download link for the PDF

Thumbnails generated on `save()` via Pillow + pdf2image. If pdf2image is not available (lightweight server), skip thumbnail and show a placeholder icon instead — make this graceful, not a hard dependency.

The gallery can also be embedded on the public programme page, replacing or supplementing the current inline link.

**Admin edit page.** The existing `/diary/edit/printed-programmes/` edit flow gains the start/end month pickers and thumbnail preview.

**Out of scope (MVP).**
- Pagination (archive grows slowly — a flat list is fine for years)
- Per-season notes shown publicly (keep notes as internal-only)
- Multi-file upload or ZIP export

**Size estimate:** 🟡 M (12–20h) — model migration is straightforward; thumbnail generation adds a new dependency and error-handling surface; gallery template is moderate work.

---

### 9.133 — Day-of-week colour motifs on programme cards 🟢 XS (2–4h)

**Problem.** On a busy programme grid it's hard to see at a glance which day a block of events falls on. Type tints (9.103) exist for event categories, but there's no visual cue for day of week.

**Goal.** Add a subtle rainbow-band accent — one colour per day of the week — so audiences can scan "all Sunday events" without reading every date line.

**Approach.**

1. In the template, add `data-dow="{{ showing.start|date:"w" }}"` to each `.showing` card (Sunday=0, Saturday=6 — Django's `date:"w"` format).
2. In `programme.css`, add a small coloured accent per day. The user proposed a rainbow treatment; a natural mapping: Mon=violet, Tue=indigo/blue, Wed=green, Thu=yellow, Fri=orange, Sat=red, Sun=magenta. The accent should be low-key — a 3–4px left border stripe, or a small coloured corner swatch — so it doesn't compete with the type tints (9.103) or the event image.
3. A small legend ("Mon Tue Wed…" with matching colour swatches) should appear somewhere near the filter row on the programme page so the system is learnable.

**Design decision to make at implementation time:** left border stripe vs. corner swatch vs. day label badge. Explore visually before committing.

**No model changes. No view changes (beyond the template `data-dow` attribute). Pure CSS + one template tweak.**

**Related:** 9.103 (type tints), 9.134 (more filters panel — days of week as filter option)

---

### 9.134 — "More filters" panel for the programme 🔵 S (6–12h)

**Problem.** The current filter bar gives only category buttons (Film, Music, Cafe…) and a text search. There's no way to filter by day of week, date range, or other dimensions.

**Goal.** A "More filters" button (beside the existing filter buttons) that opens a compact panel with additional filter options. Primary use case: filter by day of week (e.g. "show me everything on Sundays").

**Scope for MVP.**

- Day-of-week checkboxes (Mon–Sun). Selecting one or more days hides cards for non-matching days. AND logic with the existing tag filter and search.
- "More filters" button with a count badge when filters are active (e.g. "More filters (2)").
- Filters persist in URL params (or `sessionStorage` for simplicity — pick at implementation time).
- "Clear all" resets both category and day filters.

**Out of scope (MVP):** date range picker, price filter, room filter.

**Related:** 9.105 (existing filter buttons), 9.133 (day colour motifs — filter and colour system should use the same day mapping)

---

