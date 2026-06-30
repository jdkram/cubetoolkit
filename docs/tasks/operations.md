# S&S Toolkit — Community Tools & Operations

Feature specs for community tools (donations, tool library, shopping list, bulletins, lost & found) and operational dashboards.

**For work status:** [CURRENT_WORK.md](../../CURRENT_WORK.md)

---

### 9.49 — Permission model: collective ratification needed ⚠️

**Status:** Implemented (2026-03-02) but the underlying decisions are developer judgement calls, not collectively agreed policy. This needs explicit ratification before the system is used in production by real programmers.

**What was implemented and why:**

The three-tier model (Volunteer / Programmer / Panopticon) already existed. What changed:

- **Programmers can now access event templates and tags** (previously Panopticon-only). Rationale: programmers set up events, so they should be able to manage the templates that power them.
- **Role editing is now Panopticon-only** (previously shared with anyone who had `toolkit.write`). Rationale: deleting a role silently cascades and destroys rota history across all events — too destructive to leave ungated.
- **Volunteersare shown the "Rota" section only** (no diary editing, no meta-programming). The existing `change_rotaentry` permission gate is unchanged.

**Questions for the collective — please discuss and confirm or reject each:**

1. **Should Programmers be able to edit event templates?**
   Current answer: yes. Alternative: Panopticon-only, or require a separate approval step before a template change takes effect.

2. **Should Programmers be able to edit event tags?**
   Current answer: yes (same gate as templates: `toolkit.write`). Tags affect how events are categorised and filtered publicly — is that something any programmer should change freely?

3. **Should role editing remain Panopticon-only?**
   Current answer: yes. Rationale: deletion is irreversible and cascades silently. If the collective believes programmers should be able to add new roles (but not delete), that would require a code change to split add vs. delete gating.

4. **Should Programmers be able to see copy/terms reports?**
   Current answer: yes. These are editorial views useful for checking copy quality before print. No personal data is exposed.

5. **Is the "Panopticon" label appropriate?**
   This is internal jargon. The toolkit now surfaces it to users on the index page ("Access level: Panopticon"). Does the collective want a different label for the superuser tier — e.g. "Coordinator" or "Admin"?

6. **Who decides who gets Programmer access?**
   Currently: any Panopticon user can grant it (via the volunteer profile form). Is this right, or should it require a collective decision?

**What to do with the answers:**
Once ratified, update SPEC.md §2 to remove the "needs ratification" note, and document the agreed policy. If any decisions change, adjust the permission gates in `edit_views.py` and `toolkit_index.html` accordingly.

---

### 9.51 — Working groups subscribe/unsubscribe page 🔴 XL

**What exists on the live S&S site:**

`https://www.starandshadow.org.uk/toolkit/working-groups/` serves a page with a short intro and a form with three fields:

- **Full Name**
- **Email**
- **List** — a dropdown of working group mailing lists (e.g. Technical, Bar, Programming, Volunteer rota, etc.), with a "daily digest summary format" option
- Submit buttons: **Subscribe** and **Unsubscribe**

This feature is **not in Wagtail** — it lives under the `/toolkit/` URL space which Wagtail does not manage. It is likely a bespoke Django view + template, probably backed by Mailman or a similar mailing list manager, or possibly by the existing `toolkit.members` mailout infrastructure.

**What we don't know yet (needs investigation with current S&S devs):**

1. What mailing list backend does this talk to? (Mailman, Listmonk, direct SMTP to a list address, something else?)
2. Where is the list of working groups configured — hardcoded in a template, in a Django model, or in the mailing list backend itself?
3. Is there member/subscriber data in the existing system that needs migrating?
4. Is the form authenticated (logged-in users only) or anonymous (anyone with the URL)?
5. Does the current form do any deduplication against the `Member` table, or is it entirely separate?

**Likely implementation path (once the above is answered):**

1. Decide backend: re-use the existing `toolkit.members` mailout system (which already holds mailing lists), or integrate with an external list manager.
2. Create a `WorkingGroup` model (name, description, list address or slug, display order, active flag).
3. Create subscribe/unsubscribe view — probably under `/toolkit/working-groups/` — with a simple form. Anonymous access is fine (mirrors the live behaviour).
4. Wire up to the chosen backend to actually manage subscriptions.
5. Seed the working group list from the live site's current groups.
6. If member data needs migrating from the old backend: write a one-off management command.

**Why this is XL:** The biggest unknowns are the backend integration and data migration. The Django/template work itself is probably 🔵 S once those are settled; the coordination and migration work could be 🟠 L on its own.

**Blocker:** Needs a conversation with the current S&S developers / sysadmin before implementation can be scoped properly.

---

### 9.68 — Collectives public directory 🔵 S (4–8h)

#### 9.68.1 — Public copy field and /collectives/ page 🔵 S (4–8h)

**Context:** The `Collective` model (`toolkit/labs/models.py`) holds rich internal content about each working group: what they do, what they're proud of, how to get involved, and a contact address. All of this is currently visible only to logged-in toolkit users at `/labs/collectives/`. There is no public-facing page.

Prospective volunteers — people who have heard about S+S but haven't yet signed up — often don't realise the breadth of what goes on: the Community Kitchen, Print Room, Library, Film Archive, and others are invisible until you're already on the inside. A lightweight public page would help people self-sort into the right collective before they arrive, and reduce the load on induction nights.

**What to build:**

Two new fields on `Collective`:

- `public_copy` — `TextField(blank=True, default="")`. A short blurb (target: 100–300 chars) written for a public audience, distinct from the internal `about` field. Blank by default; leaving it blank means the collective opts out even if `listed_publicly=True`.
- `listed_publicly` — `BooleanField(default=False)`. Opt-in flag. Collectives are hidden from the public page unless both `listed_publicly=True` and `public_copy` is non-empty.

Both fields should be exposed in the collective edit form in the toolkit labs UI.

A new Django view (no `login_required`) at `/collectives/` that renders a list of all collectives where `listed_publicly=True` and `public_copy` is non-empty, ordered by `display_order`. For each collective, show:

- Name (as a heading)
- `public_copy` text
- `get_involved` text (already exists; copy written for internal users but usually usable publicly — no transformation needed)
- Contact email/link if `contact` is non-empty

**URL routing:**

Register in `urls_flat.py` (S+S root URL conf) and `urls.py` (Cube root URL conf) under `/collectives/`. No login required. Add an `IndexLink` or direct template link from the S+S homepage if appropriate.

**Template:**

`star_and_shadow_templates/collectives_public.html` (or in the labs template dir). Should not use the toolkit base layout — use the public site base (`base.html` or equivalent) so it looks like part of the public website, not the staff toolkit.

**Toolkit edit form:**

The existing collective edit view and template should gain the two new fields. Keep `public_copy` near `about` in the form. Show a short note: "Leave blank to exclude from the public directory." `listed_publicly` can be a checkbox.

**Migration:** straightforward `ALTER TABLE ADD COLUMN` for both fields — no data migration needed.

**Out of scope:** images per collective, translations, search/filter on the public page, volunteer sign-up flow from the page. Keep it static and readable.

**Related:** 9.87 (simplelists sync) surfaces collectives differently (mailing list subscription). This ticket is presentation-only, no list sync needed.

---

*Completed tasks: [ARCHIVE.md](ARCHIVE.md)*

---

### 9.74 — Permission model redesign investigation 🟡 M (design first)

**Context:** The current permission tiers (read, write, superuser) are a Cube Microplex inheritance and don't fully fit S+S. The immediate trigger is realising that `toolkit.write` grants access to volunteer and member personal data, which may be more than programmers should have. Current state (as of 2026-04-12):

| Tier | Current access |
|------|---------------|
| Unauthenticated | Public programme only |
| Volunteer | Rota edit (`change_rotaentry`); no programme write; now can edit own profile |
| Read-only (`toolkit.read`) | Read most views; no write |
| Programmer (`toolkit.write`) | Read + write all data including volunteer/member records |
| Panopticon (`is_superuser`) | Everything + Django admin |

**Proposed redesign (draft, for collective ratification):**

| Tier | Access |
|------|--------|
| Unauthenticated | Public programme |
| Volunteer | Own rota slots; own profile edit |
| Programmer | Programme data (events, showings, templates, roles); NOT volunteer/member PII |
| Panopticon | Everything including volunteer/member data |

**Questions to answer:**
1. Should programmers be able to *view* the volunteer list and member data, or only their own contact info?
2. Should there be a separate "volunteer admin" role (currently only Panopticon)? Probably yes — many cinemas have a volunteer coordinator who isn't a sysadmin.
3. What does "read" permission mean in the proposed model? Is it still useful, or does it collapse into other tiers?
4. Does 9.49 (Panopticon-only roles, templates) need revisiting in light of this? (Currently: roles page is superuser-only.)

**Related:** 9.49 (programmer/panopticon split for roles/templates), 9.25 (tap to sign up), 9.36 (vacancies)

**Implementation notes when the design is settled:**
- The `toolkit.write` permission is used in many `@permission_required("toolkit.write")` decorators and template `{% if perms.toolkit.write %}` guards. A redesign will touch a significant portion of the codebase.
- Consider whether to use Django's group system (new groups: "Volunteer Coordinator", etc.) or add a new `toolkit.volunteer_admin` permission.
- New tests for each tier boundary will be essential.

---

### 9.78 — Donation specifier: what we do and don't need 🔵 S (6–12h)

**Context:** S+S is vulnerable to well-meaning donations of items it doesn't need. Without a clear, up-to-date signal of what's actually wanted, the default is either constant vigilance from a handful of volunteers or a slow accumulation of unwanted stuff that has to be disposed of. A structured, public-facing page that gives donors an at-a-glance status per item category would reduce friction on both sides: volunteers don't have to field every enquiry, and donors know before they load up the car.

**Goals:**
- Public page at a stable URL (linkable from social media, the website, physical signage)
- Each item has a clear status: not needed / check first / actively wanted
- Status drives visual design (traffic-light colour coding) — not just a text label
- Notes field per item for nuance (e.g. "We have 3, could use 5 more if in good condition")
- Manageable by toolkit write-permission users without touching code or Wagtail

**Data model:** New `DonationItem` model in a new `toolkit.operations` app (or added to `toolkit.index`):

| Field | Type | Notes |
|---|---|---|
| `name` | CharField(128) | e.g. "Bar stools", "Coffee machine" |
| `category` | CharField(64, blank) | Optional grouping: Furniture, Electronics, Kitchen, etc. |
| `status` | CharField choices | `not_needed` / `check_first` / `wanted` |
| `notes` | TextField(blank) | Nuance, quantity, condition requirements |
| `contact` | CharField(128, blank) | Override contact for this item; falls back to a site-wide setting |
| `display_order` | IntegerField(default=0) | Manual sort within category |
| `active` | BooleanField(default=True) | Hide seasonal or paused items without deleting |

**Views:**
- **Public `/donate/` or `/donations/`** — No login required. Groups items by category if set. Each item rendered as a card with a coloured status badge (🟢 Wanted / 🟡 Check first / 🔴 Not needed). Contact route shown for `check_first` items. Page-level intro text pulled from a site setting or hardcoded. Mobile-first card grid.
- **Toolkit admin CRUD** — Standard Django admin or a lightweight toolkit-style list + edit form. Write-permission users can add/edit/reorder items and toggle active.

**Design notes:**
- Status badge should be visually dominant — the whole point is at-a-glance readability.
- Notes should be optional and collapsible/small on mobile to keep the overview clean.
- A page-level "last reviewed" date (editable from admin) gives donors confidence the page is current.
- Consider a short default intro: "Before donating, please check what we actually need."

**Sizing:**

| Component | Est. |
|---|---|
| `DonationItem` model + migration | 1h |
| Django admin registration | 30m |
| Public view + template (card grid, colour coding) | 3–4h |
| URL + site nav link | 30m |
| Tests | 1–2h |
| **Total** | **~6–8h** |

**Minimum viable increment:** model + admin + barebones list view (~3h). Design polish is a follow-up.

---

### 9.79 — Tool library: community lending catalogue 🔵 S (8–16h)

**Context:** S+S has tools used collectively at the venue (not for lending) and tools that individual volunteers would be happy to share with other volunteers for personal projects. At the moment there is no way to know what's available, who to ask, or whether a tool is currently out on loan. A simple catalogue with availability status would reduce the "do you know if anyone has a..." messages and make the collective's shared resources actually discoverable.

**Scope:** MVP is a catalogue with a contact-to-borrow model — no checkout tracking system. Phase 2 can add a `ToolLoan` model if the catalogue proves useful enough to justify it.

**Data model:** `LibraryTool` model:

| Field | Type | Notes |
|---|---|---|
| `name` | CharField(128) | e.g. "DeWalt cordless drill", "Stand mixer" |
| `description` | TextField(blank) | What it is, what jobs it's useful for |
| `category` | CharField choices | Power tools / Hand tools / Kitchen / AV & tech / Garden / Other |
| `condition` | CharField choices | New / Good / Fair / Needs attention |
| `owner_type` | CharField choices | `collective` (S+S property) / `volunteer` (personal loan) |
| `owner_volunteer` | FK(Volunteer, null, SET_NULL) | Populated when owner_type=volunteer |
| `location_notes` | CharField(256, blank) | e.g. "Ask at the bar", "Green cupboard near stage" |
| `status` | CharField choices | `available` / `on_loan` / `unavailable` |
| `notes` | TextField(blank) | Quirks, usage notes — e.g. "Battery needs overnight charge" |
| `image` | ImageField(null) | Optional photo |
| `active` | BooleanField(default=True) | Soft-delete |

**Views:**
- **Toolkit tool list** (login required) — Filterable by category and status. Each tool shows name, category, condition, status badge, location notes, and how to borrow (contact the owner volunteer if volunteer-owned, otherwise a shared enquiries route).
- **Toolkit tool detail** — Full description, notes, image if present.
- **CRUD** — Write-permission users can add, edit, retire tools. Volunteer-owned tools: the owner volunteer gets a link from their profile to their lending tools.

**Phase 2 — `ToolLoan` model:**
- `tool` FK, `borrowed_by` FK(Volunteer), `borrowed_on`, `due_back`, `returned_on`(null), `notes`
- Overdue highlighting on the list view
- Email reminder to borrower when approaching due date

**Design notes:**
- Volunteer-owned tools should not show the owner's personal contact details publicly — route enquiries through the toolkit messaging or a shared inbox.
- The `owner_volunteer` field should only be visible to logged-in users (not on any public-facing view).
- Condition and status should be self-service updatable by write-perm users, not just admins.

**Sizing (MVP catalogue only):**

| Component | Est. |
|---|---|
| `LibraryTool` model + migration | 1h |
| Django admin registration | 30m |
| Toolkit list view + template (filterable cards) | 4–6h |
| Detail view | 1–2h |
| CRUD form (add/edit) | 2–3h |
| Tests | 1–2h |
| **Total** | **~9–14h** |

---

### 9.80 — Non-rota jobs and maintenance schedule 🟡 M (20–35h)

**Context:** S+S currently tracks recurring maintenance obligations, contractor visits, compliance renewals, and venue upkeep tasks in a spreadsheet (`Dates for Renewals and Maintenance RH.xlsx`, in the Nextcloud). The spreadsheet has evolved over several years and contains around 40 recurring tasks, and already uses conditional formatting for colour-coded due-date highlighting. It does its job, but has real limitations: it requires Excel or Libreoffice to edit, doesn't reflow for mobile, is invisible unless you know where to find it, and has nowhere to store the embedded knowledge a volunteer would need to actually do a task — what skills are required, whether it needs a keyholder, how long it takes.

The key improvement over the spreadsheet is not the colour coding (it already does that) but **progressive disclosure**: a compact overview table for anyone who wants to know what's coming due, with expandable task details for anyone who might volunteer to take one on.

**Goals:**
- Replace the spreadsheet as the canonical source of truth for maintenance scheduling
- Any logged-in volunteer can see what's coming due at a glance
- Expanding a task reveals the full spec: skills, keyholder requirement, time commitment, contractor details, linked documentation
- Write-permission users can add records and mark tasks complete
- Mobile-friendly: the collapsed view is usable on a phone; expanded detail is readable without horizontal scrolling
- **Make background work visible to volunteers who only do shifts.** S+S has a cultural gap: people who do shifts (which can itself be a lot of work) often have no visibility into the volume of behind-the-scenes maintenance, compliance, and admin work that keeps the building running. A schedule that's only ever opened by the few people who already know it exists doesn't close that gap — see the **dashboard card** requirement below, and [9.148](#9148--jobs-board-skill-labelling-and-dashboard-visibility-s-1015h) for the matching change to the existing ad-hoc jobs board.

**Dashboard integration:** add an "Upcoming maintenance" card to the volunteer dashboard (alongside the cards from [9.94](#994--dashboard-widget-toggles-localstorage-xs-23h) / [9.126](#9126--dashboard-preferences-to-db--favourite-links-panel--shipped-2026-06-16)) showing the next 3–5 tasks by `next_due`, colour-coded, with a link through to the full schedule. This is the main fix for the visibility problem — most volunteers will never navigate to a dedicated maintenance page, but will see the dashboard on every login.

**Data model:** Two new models (new `toolkit.operations` app, or `toolkit.diary` if preferred):

`MaintenanceTask`:

| Field | Type | Notes |
|---|---|---|
| `name` | CharField(128) | e.g. "Fire alarm annual service" |
| `category` | CharField choices | Security & Fire / HVAC / Compliance & Legal / Utilities / Property / Digital & AV / Other |
| `frequency` | CharField choices | `monthly` / `quarterly` / `biannual` / `annual` / `three_yearly` / `bespoke` |
| `frequency_notes` | CharField(128, blank) | For bespoke or unusual patterns |
| `contractor` | CharField(128, blank) | Name of service provider if external; blank for volunteer-delivered tasks |
| `keyholder_required` | BooleanField(default=False) | Whether doing this task requires keyholder status |
| `skills_required` | TextField(blank) | Free text: what you need to know or be trained in |
| `time_commitment` | CharField(128, blank) | e.g. "~2 hours", "Half a day including travel" |
| `nextcloud_link` | URLField(blank) | Link to related documents, previous reports, contracts |
| `notes` | TextField(blank) | Context, caveats, embedded knowledge currently buried in spreadsheet cells |
| `active` | BooleanField(default=True) | Retire tasks without losing history |
| `committed_to` | FK(Volunteer, null, SET_NULL) | Who has said they'll do the next occurrence, if anyone. See trust/commitment note below |
| `committed_on` | DateField(null) | When the commitment was made — lets a stale commitment (e.g. 6 months old, nothing done) surface as a problem rather than silently blocking the task from view |

`MaintenanceRecord`:

| Field | Type | Notes |
|---|---|---|
| `task` | FK(MaintenanceTask, CASCADE) | |
| `completed_date` | DateField | |
| `completed_by` | FK(Volunteer, null, SET_NULL) | |
| `completed_by_name` | CharField(128, blank) | For contractor completions or cases where no toolkit account exists |
| `notes` | TextField(blank) | Issues found, follow-up required, anything the next person should know |
| `next_due_override` | DateField(null) | Manual override of calculated next-due date |

Calculated `next_due` property: most recent `MaintenanceRecord` + frequency period, or `next_due_override` if set.

**Views:**
- **Main schedule view** (login required) — Compact table or card list sorted by `next_due`, colour-coded (overdue / due within 4 weeks / ok). Collapsed view shows: task name, category, last done, next due. Each row is expandable (e.g. `<details>`) to reveal: skills required, keyholder flag, time commitment, contractor, notes, nextcloud link, and full completion history. "Mark done" button in the expanded panel opens a short inline form (date, who, notes). Grouped by category as an option.
- **Add/edit task** — Write-permission users only. Full field set.
- **Mark done** — Write-permission users only; quick form with pre-filled today's date.

**Import:** A one-off script to import the current spreadsheet is worth doing at launch. Around 40 tasks; manual entry is viable but tedious. The new fields (`skills_required`, `keyholder_required`, `time_commitment`) would need to be filled in manually regardless — they don't exist in the spreadsheet.

**Design notes:**
- The `<details>`/`<summary>` expand pattern works well here: the summary row is the at-a-glance view; the detail panel is the full task spec. No JavaScript needed; degrades gracefully.
- Keyholder flag should render as a visible badge (🔑) in the collapsed view — important for volunteers scanning for tasks they can take on.
- `completed_by_name` text field matters: many tasks are done by contractors who don't have toolkit accounts.
- Phase 2: email/notification when tasks come within N weeks of due date. Phase 2: assign a task owner per upcoming period (mirroring the spreadsheet's task owner columns).
- **Commitment vs trust.** A standing problem at S+S: someone picks up a task by saying "I'll do it", which discourages anyone else from doing it, but doesn't always result in it actually getting done. `committed_to`/`committed_on` makes that claim visible (a "claimed by Alex, 3 weeks ago" badge) rather than gating the task on it — anyone can still mark it done regardless of who's committed. If `committed_on` is old relative to `frequency` and the task still isn't done, the schedule view should surface that as its own "stale commitment" flag, distinct from plain overdue, so it's visible without anyone having to publicly call it out. This mirrors `claimed_by` on the existing `Job` model in `toolkit/labs/models.py` (see [9.148](#9148--jobs-board-skill-labelling-and-dashboard-visibility-s-1015h)) — same idea, applied to recurring tasks rather than one-off jobs.

**Sizing:**

| Component | Est. |
|---|---|
| `MaintenanceTask` + `MaintenanceRecord` models + migrations (incl. `committed_to`/`committed_on`) | 2.5h |
| Django admin registration | 1h |
| Main schedule view + template (collapsed rows, expand on click, colour coding, stale-commitment flag) | 7–9h |
| Add/edit task form + "commit to this" action | 4h |
| "Mark done" inline form | 2–3h |
| Dashboard "Upcoming maintenance" card | 2–3h |
| Tests | 3–4h |
| Optional: spreadsheet import script | 3–4h |
| **Total** | **~21–26h** (without import script) |

**Minimum viable increment:** models + admin registration + read-only schedule view (~8h). "Mark done" action is the next step; full CRUD follows.

---

### 9.148 — Jobs board: skill labelling and dashboard visibility 🔵 S (10–15h)

**Context:** The ad-hoc jobs board already exists (`toolkit/labs/models.py` `Job`, `toolkit/labs/views/jobs.py`, `/labs/jobs/`) — title, area, description, `plan_status` (progress notes), `safety_risk`, `skill_needed` flag, `keyholder_required`, `urgency`, `location_type`, `posted_by`/`reporter_name`, `claimed_by`, `resolved`/`resolved_at`. Claim/unclaim/resolve actions are all built. This ticket is **not** a new jobs feature — it's two gaps against what's already shipped, both aimed at the same cultural problem described in [9.80](#980--non-rota-jobs-and-maintenance-schedule-m-2035h): volunteers who only do shifts often don't know how much background work exists, and there's a recurring trust friction around claimed-but-stalled jobs.

**Gap 1 — `skill_needed` is a flag, not a description.** The jobs list renders it as a 🔧 icon (`jobs.html:126`) meaning "needs a skill or trade", but doesn't say *which* one. A volunteer scanning the board for something they can personally help with has to open every flagged job to find out if it's electrical, IT, woodwork, etc. Add a `skill_required` `CharField(blank=True)` free-text field (e.g. "Electrical", "Sound desk", "Carpentry") shown directly in the list view, alongside or instead of the icon. Keep it free text rather than a choices field or lookup table — a fixed list will always lag behind the actual range of jobs that come up, and free text is enough to scan.

**Gap 2 — no dashboard presence.** The jobs board has no card on the volunteer dashboard (`toolkit/index/views.py` `ToolkitIndexView.get_context_data` — compare the existing `shopping_needs` and `recent_bulletins` cards, which follow the same pattern: query a short list, add to context only if non-empty, template renders a card). Most volunteers will never navigate to `/labs/jobs/` unprompted; the dashboard is the one place that's seen on every login, so it's the actual fix for the visibility problem the user described, not a nice-to-have.

Add an "Open jobs" card: open + claimed (not yet resolved) jobs, ordered by urgency then `posted_at`, capped at ~8. Show title, `skill_required` (if set), urgency badge, and claimed-by (or "unclaimed") — same minimal-but-legible treatment as `jobs.html`'s table, condensed for a card. Link through to the full `/labs/jobs/` board.

**Out of scope for this ticket:** anything resembling the recurring maintenance schedule in 9.80 — that's a genuinely separate model (scheduled, frequency-driven, contractor-aware) and shouldn't be bolted onto `Job`, which is deliberately a flat one-off list. If a `Job` turns out to be recurring in practice, the right move is to promote it to a `MaintenanceTask`, not to grow `Job` extra scheduling fields.

**Sizing:**

| Component | Est. |
|---|---|
| `skill_required` field + migration | 1h |
| Update job list/form templates to show/edit it | 2h |
| Dashboard "Open jobs" card (query + template) | 4–6h |
| Tests | 3–4h |
| **Total** | **~10–13h** |

---

### 9.88 — Shared shopping list (consumables) 🟡 M (20–35h)

A lightweight shared list for flagging when consumables run out and coordinating who will restock them. Lives under the existing Labs section (`/volunteers/labs/`), accessible to any logged-in volunteer.

---

#### Problem

When something runs out at the venue (hand soap, bin bags, dishwasher tablets), the current process is word of mouth or a message on the volunteers list. There is no central record of what is needed, who said they'd get it, or when it will arrive. Things fall through the gaps between busy weeks.

---

#### Scope

This spec covers venue consumables only. Bar stock ordering is intentionally excluded: the existing bar ordering process is working and we don't have enough knowledge of it to avoid breaking something. A separate "last item used" flag for bar stock could be considered later, but the ordering integration would need input from whoever currently runs it.

---

#### Core concepts

**Item** — a consumable the venue regularly stocks. Has a name, optional notes, and optional supplier info (see below). Items are managed by Panopticon in the Django admin; volunteers cannot create or delete them.

**NeedFlag** — a record that a particular item has run out (or is low). Created by any volunteer with a single tap. Has: `item`, `flagged_by` (FK to `Volunteer`), `flagged_at` (datetime), `notes` (optional short free text, e.g. "last one used Thursday"), `resolved_at` (nullable datetime), `resolved_by` (nullable FK to `Volunteer`).

**ProcurementPledge** — a volunteer's commitment to get the flagged item. One pledge per flag (first-come-first-served, or the most recent pledge wins — see design questions). Has: `need_flag` (FK to `NeedFlag`), `pledged_by` (FK to `Volunteer`), `pledged_at` (datetime), `eta` (optional date or free text, e.g. "Friday cleaning club" or "by next Saturday"), `fulfilled_at` (nullable datetime).

When a pledge is marked fulfilled, the parent `NeedFlag` is auto-resolved if not already.

---

#### Item catalogue

Pre-seeded list of common consumables, plus a mechanism for Panopticon to add more via admin.

Initial catalogue:

- Hand soap
- Bin bags
- Washing detergent
- Dishwasher detergent
- Dishwasher rinse aid
- Washing up sponges
- Steel scrubbers
- Cling film
- Steriliser tablets
- Pens
- Lamination sheets (A4)
- Reams of paper (A4)
- Reams of paper (A3)
- Microfibre cloths

Each item has a `category` field (free-text or choice: Cleaning / Stationery / Kitchen) for display grouping.

---

#### Supplier info

Each item can have zero or more `SupplierRecord` entries (a separate model, edited in the Django admin inline). Fields:

- `supplier_name` — e.g. "Suma", "Bookers", "Nisbets", "Amazon"
- `product_code` — optional, e.g. Suma SKU
- `product_url` — optional link to the product page
- `unit_description` — e.g. "6-pack", "25 tablets", "5L"
- `approx_unit_price` — optional decimal
- `ordering_notes` — free text for logistics that don't fit elsewhere (see examples below)
- `account_holder` — optional FK to `Volunteer` (who holds the login for this supplier account)
- `account_notes` — short free text for anything else about the account

Example ordering notes for Suma: "Order arrives next working day. Can be scheduled for Friday delivery to coincide with cleaning club. Bulk orders only — check if anything else is needed before placing."

Example for Nisbets: "Next-working-day delivery. Login held by [volunteer]. Can deliver to a volunteer's home address for non-bulky items if needed."

The `account_holder` field is informational only — it surfaces who to ask for the login, without storing credentials anywhere.

Supplier info is Panopticon-only to edit, and is shown read-only to volunteers on the item detail view.

---

#### Views

**`/volunteers/labs/shopping/`** — the main list view. Two sections:

1. **Needs attention** — items with an unresolved `NeedFlag`, sorted by `flagged_at` descending. Each row shows: item name, who flagged it, when, and whether there is a current pledge (and by whom, and the ETA). A volunteer can click "I'll get it" to create a pledge.
2. **Recently resolved** — flags resolved in the last 30 days, collapsed by default. Shows item, who got it, when resolved.

A button on each item row opens the item detail view.

**`/volunteers/labs/shopping/<item_id>/`** — item detail. Shows:

- Current need flag status (or "none flagged")
- Supplier info (read-only)
- History: previous flags and how they were resolved

**`/volunteers/labs/shopping/flag/<item_id>/`** — POST endpoint. Creates a `NeedFlag` for the item. If there is already an open flag for that item, either silently no-ops or adds a +1 acknowledgement (see design questions). Redirects back to the list.

**`/volunteers/labs/shopping/pledge/<flag_id>/`** — POST endpoint. Creates or updates a `ProcurementPledge`. Redirects back to the list.

**`/volunteers/labs/shopping/resolve/<flag_id>/`** — POST endpoint. Marks a flag as resolved (and its pledge as fulfilled if one exists). Any volunteer can resolve; does not need to be the pledger.

---

#### Design questions to resolve before building

1. **Duplicate flags:** if an item already has an open flag, should a second volunteer's "flag it" tap no-op silently, show a "someone already flagged this" message, or add a separate acknowledgement count? The simplest path is a `unique_together` constraint on `(item, resolved_at=None)` so only one open flag per item can exist at a time, and the UI shows "already flagged — do you want to pledge to get it?" instead.

2. **Pledge ownership:** should only one pledge be active per flag (first-come-first-served), or can multiple volunteers each say they'll get it? Multiple is messier to resolve but more resilient if one person drops out. Proposed default: one active pledge, with the ability for the pledger to cancel it (returning it to "needs a pledger").

3. **ETA field:** free text is flexible but hard to sort. A date picker with an optional "delivery window" note (like "Friday cleaning club") may be more useful for planning. Could be an optional date + optional notes.

4. **Notifications:** no push notifications are planned for this feature. The assumption is volunteers check the list occasionally, or it's mentioned on the mailing list. Revisit if the list goes stale.

5. **Bar stock:** excluded for now. If bar volunteers later want a "last item used" flag, the `NeedFlag` model is directly reusable — the only question is whether bar ordering should trigger auto-alerts or touch an external system.

6. **Supplier account credentials:** explicitly out of scope. The `account_holder` field points to a person to ask; actual credentials are never stored in the toolkit.

---

#### Permissions

| Action | Who |
|---|---|
| View the shopping list | Any logged-in volunteer (`diary.view_rotaentry` or just `is_authenticated` + volunteer record) |
| Flag an item as needed | Any logged-in volunteer |
| Pledge to get an item | Any logged-in volunteer |
| Mark a flag as resolved | Any logged-in volunteer |
| Edit items / supplier records | Panopticon only (Django admin) |
| View supplier info (read-only) | Any logged-in volunteer |

---

#### Data model sketch

```
ConsumableItem
  name           CharField(100)
  category       CharField (choices: Cleaning / Stationery / Kitchen / Other)
  notes          TextField (blank)
  active         BooleanField (default True; soft-delete inactive items)

SupplierRecord
  item           FK → ConsumableItem
  supplier_name  CharField(100)
  product_code   CharField(100, blank)
  product_url    URLField(blank)
  unit_desc      CharField(200, blank)
  approx_price   DecimalField(null)
  ordering_notes TextField(blank)
  account_holder FK → Volunteer (null, blank)
  account_notes  TextField(blank)

NeedFlag
  item           FK → ConsumableItem
  flagged_by     FK → Volunteer
  flagged_at     DateTimeField(auto_now_add)
  notes          CharField(300, blank)
  resolved_at    DateTimeField(null, blank)
  resolved_by    FK → Volunteer (null, blank, related_name='resolved_flags')

ProcurementPledge
  need_flag      OneToOneField → NeedFlag  (one active pledge per flag)
  pledged_by     FK → Volunteer
  pledged_at     DateTimeField(auto_now_add)
  eta_date       DateField(null, blank)
  eta_notes      CharField(200, blank)
  fulfilled_at   DateTimeField(null, blank)
```

---

#### Sizing

| Component | Est. |
|---|---|
| Models + migrations | 2h |
| Django admin (items, supplier records inline) | 2h |
| List view + item detail view | 4h |
| Flag / pledge / resolve POST endpoints | 3h |
| Templates (list, detail, forms) | 4h |
| Seed data (initial item catalogue) | 1h |
| Tests (model constraints, view permissions, flag/pledge flow) | 5h |
| **Total** | **~21h** (after design questions resolved) |

**Blocked by:** design question 1 (duplicate flags), design question 2 (pledge ownership). Resolve those before writing any model code.

---

### 9.90 — Access transparency: visible list of privileged users with rights explanation 🔵 S (8–14h)

The toolkit has two elevated access tiers above ordinary volunteers: **Programmer** and **Panopticon**. The collective values non-hierarchy, which creates a tension: some members hold privileges that others don't -- and those members should be clearly identified and accountable, not invisible. This feature surfaces that information to all logged-in users and builds in a lightweight accountability mechanism for Panopticon access specifically.

This spec reflects Jonny's individual strong opinion; implementation should be flagged to the wider collective before deploying to production as it touches governance norms.

---

#### Access levels page

**URL:** `/toolkit/access/` — login required (any tier).

The page has two sections:

**1. What each access level can do**

A plain-language table or set of cards explaining the three tiers:

| Tier | Who | What they can do |
|---|---|---|
| Volunteer | All logged-in volunteers | View programme and rota, sign up for shifts, edit own profile, view the volunteer directory |
| Programmer | Members granted programming access | Everything volunteers can do, plus: create and edit events and showings, manage rota entries for any volunteer, view the full volunteer list, use event templates |
| Panopticon | Members granted full access | Everything above, plus: create and manage other users, view and edit all volunteer/member PII (names, emails, phone numbers, access riders), perform GDPR anonymisation, grant or revoke access tiers, manage site configuration |

The descriptions should be written in plain language -- this page should be usable as part of a volunteer privacy notice (data rights, who can see what). The Panopticon row in particular should be accurate and honest about PII access.

**2. Current privileged users**

Two sub-sections, each listing the relevant volunteers:

*Panopticon users*: name (linked to volunteer profile for superusers, or unlinked otherwise), reason for access, date granted, date of last review (or "Not yet reviewed" if null). Ordered by date granted ascending (longest-serving first).

*Programmer users*: name, date added to Programmers group (if recorded; "Unknown" if pre-existing). Ordered alphabetically.

Only lists active users (`is_active=True`, `volunteer.status='active'`). Does not list the system admin / service accounts if any.

---

#### Panopticon grant record

A new `PanopticonGrant` model captures the audit trail when Panopticon is granted:

```python
class PanopticonGrant(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="panopticon_grant")
    reason = models.TextField(help_text="Why does this person have Panopticon access?")
    granted_at = models.DateField(auto_now_add=True)
    granted_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="+")
    last_reviewed_at = models.DateField(null=True, blank=True)
    reviewed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
```

**When Panopticon is granted** (i.e. `is_superuser` ticked in `UserForm` and was previously False): `UserForm.save()` creates a `PanopticonGrant` for the user. The reason is required -- `UserForm` gains a `panopticon_reason` text field that is shown conditionally (JS: visible when "Panopticon access" is checked, hidden otherwise). If `is_superuser` is being set to True and no reason is given, the form is invalid.

**When Panopticon is revoked** (i.e. `is_superuser` unchecked): `PanopticonGrant` is deleted.

**Pre-existing Panopticon users** (those who had `is_superuser=True` before this feature was deployed): their `PanopticonGrant` will not exist. The access list page handles this gracefully by showing "Reason not recorded" and "Date unknown" for those users. A one-time management command (`backfill_panopticon_grants`) can be run post-deploy to create stub grants for them with an admin-supplied reason.

**Annual review:** The access list page highlights (amber row or badge) any Panopticon user whose `last_reviewed_at` is null or more than 365 days ago. A "Mark as reviewed" button (Panopticon-only) updates `last_reviewed_at = today` and `reviewed_by = request.user`. This is the minimal mechanism -- no email, no expiry, no automatic revocation. The social pressure of a publicly visible "not reviewed" flag is the accountability mechanism.

---

#### Programmer grant record

Programmer status is currently tracked only via group membership (`User.groups`), with no date or reason. This feature adds a lightweight record for new grants:

A `ProgrammerGrant` model (similar to above but without `reason` -- reasons for programmer access are less sensitive and the collective convention is less formal):

```python
class ProgrammerGrant(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="programmer_grant")
    granted_at = models.DateField(auto_now_add=True)
    granted_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="+")
```

Created when the "Programmer status" checkbox is first ticked. Deleted when unchecked. Pre-existing programmers shown with "Date unknown".

---

#### Design questions to resolve before implementation

1. **Should the page be public (no login) or internal (login required)?** The spec says login required. A case could be made for public access (maximum transparency to community members who aren't toolkit users), but this would expose the names of people who may not want to be findable via Google. Login-required is the safer default; revisit if the collective prefers full transparency.

2. **Should the reason field be visible to all logged-in users, or only to Panopticons?** The spec shows it to all. The reason for access is not sensitive and transparency is the point. Override this only if a specific reason turns out to contain personal information (e.g. "replacing [person] who left").

3. **Should Programmer access also require a reason?** The spec omits this. Programmer access touches programme data only, not PII. If the collective wants parity, add a `reason` field to `ProgrammerGrant`.

4. **What happens to `PanopticonGrant` if the volunteer record is anonymised (GDPR)?** The `PanopticonGrant.user` FK is `CASCADE` -- if the `User` is deleted, the grant goes with it. The `granted_by` and `reviewed_by` FKs are `SET_NULL`. This is correct behaviour: a deactivated/anonymised account should not remain on the access list.

---

#### Sizing

| Component | Est. |
|---|---|
| `PanopticonGrant` + `ProgrammerGrant` models + migration | 1h |
| `UserForm` changes (conditional reason field, validation) | 1.5h |
| Access levels page (view + template -- rights table + user lists) | 3–4h |
| Annual review "Mark as reviewed" button | 1h |
| Tests | 2h |
| **Total** | **~8–10h** |

**Minimum viable increment:** Access levels page (rights explanation only, no grant model) + simple list of current Panopticon/Programmer users by name (~3h). The grant model and review mechanism can follow in a second pass.

**Governance note:** Deploy the access list page in dev first and share with the collective for feedback on the rights descriptions before going live. The plain-language summary of what Panopticon can do will be the first time it's been written down anywhere, and it should be accurate.

---

### 9.94 — Dashboard widget toggles (localStorage) 🟢 XS (2–3h)

Lets each user show or hide individual dashboard widgets. Preferences stored in `localStorage` — same pattern as the rota filter panel — so no model change or migration is needed. Preferences are per-browser; cross-device persistence is explicitly out of scope for this increment.

#### Which widgets are toggleable

Only widgets the current user is eligible to see. The toggle UI should not reveal the existence of widgets the user can't access. Eligibility is determined server-side (the view already conditionally includes context variables); the toggle JS only operates on cards that are actually present in the DOM.

Proposed widget keys (used as `localStorage` keys):

| Key | Widget | Shown to |
|---|---|---|
| `dash_upcoming_shifts` | Your upcoming shifts | Volunteers with accounts |
| `dash_starred_events` | Your starred events | Volunteers with accounts |
| `dash_new_showings` | New since your last login | Programmer+ |
| `dash_rota_gaps` | Gaps in the rota | All |
| `dash_unconfirmed` | Not yet confirmed | Programmer+ |
| `dash_training` | Upcoming inductions & training | All |

#### Implementation

A small "Customise" toggle button or link in the dashboard header area opens a panel (or inline checkboxes) listing the visible widgets. Checking/unchecking hides/shows the corresponding card immediately and writes to `localStorage`. On page load, a short JS block reads preferences and hides cards accordingly before paint (to avoid flash of hidden content).

```javascript
(function() {
    var KEYS = ['dash_upcoming_shifts', 'dash_starred_events', /* ... */];
    KEYS.forEach(function(key) {
        if (localStorage.getItem(key) === 'hidden') {
            var el = document.getElementById(key);
            if (el) el.style.display = 'none';
        }
    });
})();
```

Each card's wrapper `<div>` gets an `id` matching its key (e.g. `id="dash_rota_gaps"`). The customise panel is a set of checkboxes that toggle `style.display` and write to `localStorage` on `change`.

#### What this does not do

- No server-side persistence. A volunteer using a different browser or device sees the default (all widgets visible).
- No admin override of defaults. If the collective later wants to set organisation-wide defaults (e.g. hide the gaps widget on a fully staffed week), that's a separate server-side feature.
- No drag-to-reorder. Order is fixed in the template.

#### Sizing

| Component | Est. |
|---|---|
| Card `id` attributes in template | 0.25h |
| Page-load hide script | 0.5h |
| Customise panel UI + toggle JS | 1h |
| Tests (JS is minimal; test the rendered `id` attributes) | 0.5h |
| **Total** | **~2–2.5h** |

---

### 9.101 — Lost & found log 🔵 S (8–14h)

**Context.** The Green Room accumulates unclaimed items with no record of when they arrived, who found them, or when they can be disposed of. Coordinators have no way to answer "was a blue jacket handed in last Friday?" without physically searching the pile. Disposal is ad-hoc and undocumented.

**Goal.** A lightweight, mobile-friendly logging tool that gives every found item a numbered identity and a clear lifecycle: unclaimed → claimed or disposed.

**Core workflow.**

```
Volunteer finds item
  → opens toolkit on phone, logs it in ~30 seconds
  → sticks a sticky with the item number on it (hand-written or printed label)
  → puts it in the designated spot

Owner enquires → panopticon searches list, marks as claimed
After X days  → system flags item → panopticon marks disposed
```

**Data model — `FoundItem`.**

| Field | Type | Notes |
|---|---|---|
| `short_id` | auto sequential | Displayed as "L-042". Printed/written on the physical label |
| `description` | CharField (200) | What it is. Required, kept brief |
| `location_found` | CharField (100) | "Bar", "Cinema", "Toilets" — free text |
| `found_on` | DateField | Defaults to today |
| `logged_by` | CharField (100) | Free-text name — avoids login friction for non-system volunteers |
| `photo` | ImageField | Optional. Helps owners identify items |
| `status` | choices | `unclaimed` / `claimed` / `disposed` |
| `claimed_by` | CharField | Optional note when claimed |
| `claimed_on` | DateField | Set on claim action |
| `disposed_on` | DateField | Set on disposal action |
| `disposal_method` | choices | `binned` / `donated` / `returned` / `other` |
| `notes` | TextField | Anything else |

`retain_days` lives in `SiteConfiguration` (default: 60). Items past this threshold are flagged in the list view.

**Views.**

| View | Access | Notes |
|---|---|---|
| Log new item | Any logged-in user | Mobile-optimised. Minimal required fields: description + location. Auto-sets date. Shows resulting ID on success so volunteer can write it on the label |
| Item list | Panopticon | All unclaimed items. Items past `retain_days` flagged amber. Tabs: unclaimed / claimed / disposed |
| Item detail | Panopticon | Full record + claim / dispose action buttons |
| Printable label | Panopticon | Big `L-042` + date + description, print-optimised |

**Design decisions.**

- **No QR codes in MVP.** They add a library dependency and printing complexity. A hand-written number on a sticker is sufficient; the list view is the lookup interface.
- **Login required for logging.** Reduces garbage entries. The `logged_by` CharField means volunteers who aren't in the auth system can still be recorded by name — a logged-in volunteer fills it in on their behalf.
- **Disposal is manual, not automatic.** The system flags overdue items; a panopticon confirms and records the method. Preserves the audit trail.
- **Photo is optional** but the field should be in the model from day one; retrofitting it later means a migration and template rewrite.

**Not in MVP.**
- Public-facing "I lost something" search page
- Email alerts when items are flagged for disposal
- Bulk disposal action
- QR code label generation
- Integration with floorplan / Green Room booking

**Lives in:** `toolkit/labs/` — new model, views, and templates alongside existing Labs features.

**Size estimate:** 🔵 S if photo is deferred, 🟡 M if photo upload is included in MVP.

**Size estimate:** 🟡 M — ~22–34h across all three phases; MVP (phase 1) alone is 🔵 S (~8–12h). Requires 8.1 (rota↔volunteer FK, done) for the gate to know who is signing up.

---

### 9.126 — Dashboard preferences to DB + favourite links panel ✅ SHIPPED 2026-06-16

**Problem.** Dashboard card visibility and order were stored in localStorage, which is lost when clearing browser data and not shared across devices. The diary `daysahead` preference was stored in the session, which expired at browser close.

**Shipped:**
- `dashboard_hidden_cards`, `dashboard_card_order` (JSONField), `diary_days_ahead` (IntegerField), `favourite_link_keys` (JSONField) on `Volunteer` — migration `members/0027`.
- `/toolkit/dashboard/prefs/` AJAX endpoint: saves visibility + order for volunteers; localStorage used as local cache and fallback for non-volunteers.
- Server renders initial hidden state so no flash of wrong content on first paint.
- `diary_days_ahead` persisted via updated `edit_prefs.py` (volunteer kwarg).
- "Quick links" dashboard card showing pinned links; `/toolkit/favourites/` manage page with 19-item access-level-filtered catalogue, max 8 pinned.

---

### 9.127 — Collective sample role field ✅ SHIPPED 2026-06-16

**Problem.** The public collectives directory gives a general pitch but doesn't help potential members understand what day-to-day involvement actually looks like.

**Shipped:** `sample_role` TextField on `Collective` (migration `labs/0023`). Shown on internal card as "Example of what you might do" and on the public directory as "Example role:". Exposed in the collective edit form.

---

### 9.128 — Collective defined roles (CollectiveRole model) 🔵 S

**What.** Structured roles within a collective: title, description, time commitment, "getting started" text, up to 2 links, open-to-new-volunteers flag, display order. Managed inline in the collective edit form (same formset pattern as `CollectiveLink`). Shown in collapsible section on the internal collectives view and on the public directory.

**Why.** Structured roles reduce the friction of "I want to help but I don't know what I'd actually do." A potential member can read "Head Cook: plan one meal per month, ~3hrs. First step: come to the next Community Kitchen evening." and immediately know whether it's for them.

**Discussion needed.** The original spec discussion surfaced an interesting idea: listing which roles within a collective are currently well-filled vs. which need more people. This could be a `needs_volunteers` BooleanField on `CollectiveRole`, surfaced as a visual indicator on the collective card. Worth ratifying before implementation.

**Models.**
```python
class CollectiveRole(Model):
    collective = ForeignKey(Collective, related_name="defined_roles", on_delete=CASCADE)
    title = CharField(max_length=128)
    description = TextField(blank=True)
    time_commitment = CharField(max_length=128, blank=True)
    getting_started = TextField(blank=True)
    needs_volunteers = BooleanField(default=False)
    open_to_new_volunteers = BooleanField(default=True)
    display_order = IntegerField(default=0)

class CollectiveRoleLink(Model):
    role = ForeignKey(CollectiveRole, related_name="links", on_delete=CASCADE)
    label = CharField(max_length=80)
    url = URLField(max_length=500)
    order = IntegerField(default=0)
    # Max 2 per role enforced by formset
```

**Files.** `labs/models.py`, `labs/forms.py`, `labs/views.py` (collective_edit), `labs/admin.py`, templates (collective_edit, collectives, collectives_public). Migration required.

**Size estimate:** 🔵 S (5–8h)

---

### 9.129 — Support wiki and user feedback (deferred, evaluation only)

**Support wiki.** Recommendation: avoid. The toolkit's user base is ~500 active volunteers accessible through direct channels (bulletin board, Signal). A wiki would rot. If specific UI patterns consistently generate questions, add 3–5 Wagtail FAQ pages under `/help/` — no custom model needed.

**User feedback tool.** The user base is large enough (~500 active volunteers) that a structured feedback tool has merit for prototype testing. Third-party option: **Marker.io** — screenshot + annotation widget, GitHub Issues integration, free tier suitable for a dev/staging site. Could be added to the staging deployment only. If we want in-house: a `PrototypeFeedback` model (volunteer, page URL, rating 1–5, comment, submitted_at) with a floating "Give feedback" button gated behind a `FEEDBACK_ENABLED` setting (~3–4h). Both options deferred until there's a specific prototype to test.

---

### ~~9.146~~ — ~~Shopping list: buyer-oriented view + first-class suppliers~~ ✅ 2026-06-26

Extends the shared shopping list (9.88). The existing list is built around *adding* needs quickly. This adds a parallel **buyer-oriented view** for the person about to place an order (e.g. a Suma delivery or a Bookers run), answering: what does everyone need that I can get from *this* supplier, what's already being handled, and what can I skip? Additive — the existing quick-add list (`labs/shopping.html`) is untouched.

**Governing principle — progressive enrichment, never gate fast entry.** The real process is barely a system: people email sporadically, requests cross collectives (bar *and* cafe both order from Bookers), thoroughness varies. The dominant failure mode is friction killing capture. So the design follows a three-stage lifecycle, and every stage must work even if the later ones never happen:

1. **Fast, poor data** — anyone flags "we need X" in seconds; no supplier, category, or anything required (the existing quick-add; must not regress).
2. **Enrichment by people who know** — a *different*, knowledgeable volunteer later attaches supplier(s), delivery/pickup, category. Separate, optional act.
3. **Encoded for future orders** — that metadata persists on `Supplier` / `SupplierRecord` so the next order is informed automatically.

Hard constraints: **no new required field** (supplier on items and on pledges is always nullable — "I'll sort this" is a valid pledge); the un-enriched pile is **first-classed** as a "needs sorting" bucket with low-friction inline enrichment, not buried as admin; grouping is **by supplier**, deliberately cutting across category/collective.

**The four buyer facts:** (a) all needed items for a given supplier; (b) whether an item is already in someone's basket/order (and whether for *this* supplier — "in this order" — or another — "being got from X", so the buyer skips it); (c) "also at X, Y" for items stocked by multiple suppliers; (d) delivery (booked, confirmed on order) vs in-person pickup (availability not guaranteed) — a property of the supplier.

**Edge case — out of stock.** A supplier accepts an order then says an item is out of stock: mark that pledge out-of-stock, record *which* supplier failed, and leave the `NeedFlag` open so the item resurfaces under alternative suppliers' buyer views. Nobody retries the dead end.

**Data model.** New first-class `Supplier` (name, `fulfilment_type` delivery/pickup/either, ordering URL/notes, account holder, active). `SupplierRecord` gains a nullable FK to `Supplier`; a reversible data migration folds existing `supplier_name` strings into `Supplier` rows. `ProcurementPledge` gains nullable `intended_supplier` FK and a `status` (pledged → ordered → out-of-stock → fulfilled); `fulfilled_at` stays the authoritative "arrived" timestamp so existing flows keep working.

**Views/URLs** (name prefix `labs-shopping-*`): `shopping_buy` (supplier picker + prominent "needs sorting (N)" entry), `shopping_buy_supplier` (the per-supplier shop sheet), `shopping_buy_unsorted` (enrichment workbench — attach supplier inline, `get_or_create` on new names), `shopping_item_enrich` (POST), `shopping_out_of_stock` (POST). Reuses existing pledge/resolve handlers.

**Integration.** Nav entries beside the existing Shopping links in `base_admin.html`; register `Supplier` in `labs/admin.py`; seed a couple of suppliers (one delivery, one pickup) and link existing records. Optional stretch: dashboard widget for "out of stock, needs re-sourcing".

**Note on the `__init__` caching trap.** Any query touching `Volunteer`/`Member` for these views must use `.values()` / `select_related`, never `.only()` (infinite recursion — see known-issues + CLAUDE.md).

**Files.** `labs/models.py`, `labs/views.py`, `labs/urls.py`, `labs/admin.py`, new `labs/templates/labs/shopping_buy*.html`, migration + data migration, `base_admin.html`, seed data, `labs/tests/test_shopping.py`. Update `docs/SPEC.md` §4/§8.

**Size estimate:** 🟠 L (40–80h). Full design rationale: approved plan at `~/.claude/plans/i-d-like-to-spec-sparkling-salamander.md`.

---

