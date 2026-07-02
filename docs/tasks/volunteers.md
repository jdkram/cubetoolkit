# S&S Toolkit — Volunteer Management

Feature specs for volunteer records, inductions, training, qualifications, accounts, GDPR, and pool management.

**For work status:** [CURRENT_WORK.md](../../CURRENT_WORK.md)

---

### 9.2 Volunteer rota — account-linked sign-up

**Current state:** The rota at `/diary/edit/rota/` is already self-service in a
crude sense — any logged-in volunteer can click any slot and type a name. The S&S
branch adds name coercion (it ignores what you type and saves the logged-in user's
own name instead), but this is not yet on master. Either way, the entries are plain
text with no identity link.

**Goal:** Replace free-text rota entries with account-linked sign-ups, so that
the system knows *who* is actually on the rota — enabling automatic reminders,
"my upcoming shifts" views, and drop-out notifications.

Features:
- **Volunteer accounts** — each volunteer has a login (username + password or
  magic link via email)
- **Sign up for rota slots** — volunteers can sign up for open slots on showings,
  with slots linked to their account (not free text)
- **Drop out of a slot** — with notification to the organiser
- **Reserve / standby slots** — volunteers can mark themselves as "reserve" for
  a role, and be notified if the primary person drops out
- **Email reminders** — automatic reminders to volunteers who are signed up,
  sent N days before a showing
- **My schedule view** — a volunteer can see all showings they're signed up for

### 9.4 Volunteer induction workflow

**Goal:** Replace the Google Form → manual entry process with something integrated.

Features:
- **Self-registration form** — public-facing form where prospective volunteers
  can submit their details (replaces Google Form)
- **Pending volunteer queue** — admins see a queue of submitted applications
- **Induction session attendance tracking** — mark which sessions someone attended
- **One-click activation** — once verified, activate the volunteer with a single
  action that creates their account and notifies them
- **Welcome email** — automatic email sent on activation with login details and
  next steps
- **Induction checklist** — record which induction topics were covered for each
  new volunteer

### 9.5 Volunteer wellbeing dashboard

**Goal:** Give coordinators visibility of volunteer workload and engagement, to
support a healthy and sustainable volunteer community.

Features:
- **Rota commitment overview** — for a given date range, show each volunteer's
  total number of signed-up shifts and roles
- **Role distribution** — see which roles are under-resourced (few qualified
  volunteers) and which are well-covered
- **Engagement trend** — flag volunteers who have not signed up for any shifts in
  the last N weeks (potential disengagement)
- **Upcoming capacity alert** — compare the number of rota slots required for
  confirmed events in the next month against the recent monthly average of
  volunteer hours. Alert if the ratio is unusually high.
- **Training lapse alerts** — list volunteers whose training records have expired
  or are due to expire within 30 days

### 9.6 Communication improvements

**Goal:** Reduce manual steps in keeping volunteers informed.

Features:
- **Email volunteers on a showing** — send a message to all volunteers signed up
  for a specific showing (requires volunteer accounts + rota linked to accounts)
- **Email volunteers by role** — send a message to all active volunteers qualified
  in a specific role
- **Rota vacancy alert** — automatic email to a volunteer mailing list when a
  showing has unfilled key roles within N days
- **Direct sync with mailing list** — rather than emailing admins to manually
  update Simplelists, the system manages list membership directly via an API
  (if Simplelists exposes one, or migrate to a different list manager)

### 9.12 "Dormant" volunteer status 🟢 XS (2–4h) — ✅ DONE 2026-05-29

> **Shipped.** `Volunteer.status` now has four values (active / dormant / retired / suspended). Dormant is soft and reversible (no login/rota restriction), can be set by hand or auto-applied by the `auto_dormancy` command on login inactivity, and a returning dormant volunteer gets a one-click "I'm back" welcome-back card on the dashboard. See SPEC §"Volunteer status, login access and suspension". Original design note below.

The current volunteer status model is binary: `active` or `retired`. In
practice, the volunteer community is more fluid than this. People go
travelling, take breaks for health or life reasons, or drift away and
return. Formal "retirement" implies a finality that doesn't reflect how
S&S actually works — and the flat, non-hierarchical structure means there
are no formal membership rules that require strict status tracking.

A **dormant** status would sit between active and retired:

| Status | Meaning | Effect |
|---|---|---|
| **Active** | Volunteer is engaged, available, receives comms | Appears in rota, on mailing lists, in standard reports |
| **Dormant** | On a break; intends to return | Hidden from default rota and reports; not emailed; preserved in the system |
| **Retired** | Has left the organisation | Marked inactive; removal from mailing lists triggered |

Dormant is soft and self-directed — a volunteer can flag themselves as
dormant, or a coordinator can do so after a period of inactivity. There is
no expiry on dormancy; the volunteer can reactivate whenever they return.

This avoids the awkward situation of retiring someone who is just taking a
break, and avoids cluttering the rota with inactive names.

**Data model change:** add a third option to the `active` field (or add a
separate `status` field with values `active`, `dormant`, `retired`).

### 9.13 GDPR compliance and data purging 🟠 L (40–80h)

The Star and Shadow holds personal data on ~1,500 registered volunteers.
Under UK GDPR (the UK's post-Brexit equivalent of EU GDPR), individuals have
the right to:

- **Access** their data (Subject Access Request — SAR)
- **Erasure** ("right to be forgotten")
- **Rectification** (correct inaccurate data)
- **Portability** (data in a machine-readable format)

S&S does not currently have a designated Data Protection Officer, which is
a compliance gap for an organisation holding this volume of personal data.
The toolkit should provide tools that make compliance manageable even without
a dedicated DPO.

#### What data is held

The toolkit holds:

| Category | Location | Sensitivity |
|---|---|---|
| Name, email, phone, address | `Member` record | High |
| Personal pronouns, notes | `Member` record | Medium-High |
| Volunteer notes (admin-written) | `Volunteer.notes` | High (may contain sensitive observations) |
| Portrait photo | `Volunteer.portrait` | High |
| Training records | `TrainingRecord` | Medium |
| Rota history (free text name in `RotaEntry.name`) | All historical showings | Medium |
| GDPR consent timestamp | `Member.gdpr_opt_in` | Administrative |

#### Data purge workflow

> **Partially shipped (2026-05).** The erasure steps below are implemented as `Volunteer.anonymise()`, reachable per-record via the Anonymise web flow and in bulk via the `purge_stale_volunteers` command (dry-run by default; `--apply` + typed confirmation to mutate). The panopticon pool-health dashboard (`/volunteers/view/pool-health/`) flags volunteers past the `volunteer_purge_days` retention window. Step 4 (mailing-list removal) is still manual. The broader SAR/portability/DPO items remain open.

When a volunteer requests erasure, or when data is cleaned up on retirement:

1. **Anonymise rota entries** — replace `RotaEntry.name` with an
   anonymised placeholder (e.g. "[Volunteer removed]") across all past
   showings. This preserves the rota record for operational history while
   removing the identifying information.
2. **Delete volunteer record** — `Volunteer`, `TrainingRecord`, portrait photo
3. **Delete or anonymise member record** — `Member` (or replace identifying
   fields with null/empty values while preserving the non-identifying
   structure for data integrity)
4. **Remove from mailing lists** — trigger the manual Simplelists removal
   process, or automate if API is available
5. **Log the erasure** — maintain a minimal audit record: "erasure
   completed for member #N on [date]" — no personal data, just a timestamp
   and an ID (which is now meaningless)

#### Subject Access Request (SAR) workflow

The toolkit should be able to generate a full data export for a named
individual, including:

- Their `Member` and `Volunteer` fields
- Their rota history (all `RotaEntry` records matching their name — noting
  that the current free-text model makes this fuzzy)
- Their training records
- Any admin notes

A management command or Panopticon-accessible view that produces a JSON or
PDF export of all data held for a given member ID is the minimum viable
implementation.

#### Consent and privacy policy

- The GDPR consent timestamp is already stored (`gdpr_opt_in`)
- A public-facing privacy policy page (as a Wagtail CMS page) should exist
  and be linked from the volunteer sign-up form and from the member's own
  profile page
- Any new form that collects personal data should include a consent checkbox
  and record the timestamp

#### Implementation notes

The main technical complexity is the rota history: `RotaEntry.name` is free
text, so there is no guaranteed FK to find all of a person's entries. An
erasure process must do a fuzzy name match across all historical rota entries
— which may miss entries made under a nickname or typo, and may accidentally
catch entries made by a different person with the same name. This is a
fundamental limitation of the free-text rota model. The long-term fix is
linking rota entries to volunteer accounts (8.1), at which point erasure
becomes a clean FK delete. Until then, the process should flag matches for
human review rather than auto-deleting.

**Note on financial records:** The toolkit does not currently store financial
records (ticket revenue, expenses). These are held in TicketSource, EPOSnow,
and the venue's accounting system. GDPR obligations for financial records
differ (statutory retention requirements may apply). This is outside the
toolkit's scope.

### 9.24 Pronouns on hover for rota names 🔵 S (4–8h)

**Context (from programmer interviews, 2026-02):**

Volunteer names appear on the rota view and edit pages. Programmers who don't know all volunteers personally may accidentally misgender someone when referring to them in conversation. Showing pronouns on hover over a name is a low-friction, non-intrusive way to surface this.

**Goal:** When a logged-in user hovers over a volunteer's name on the rota (view or edit), a tooltip shows their preferred pronouns.

**Scope:**

- Add a `pronouns` CharField (max 50, blank=True) to the `Volunteer` model; add to the volunteer edit form and admin
- Migration required
- In rota view/edit templates, render volunteer names with a `title` attribute or a lightweight JS tooltip containing their pronouns (only if `pronouns` is non-empty)
- The tooltip should be keyboard-accessible (focusable element or `aria-label`)
- Update `seed_dev_data` to populate some volunteers with example pronouns

**Note:** Pronouns are inherently personal data. Do not display them on public-facing pages or in any exported data. They should only be visible to logged-in users with rota access.

**Related:** 9.13 (GDPR / data minimisation)

---

### 9.45 — Password management in the volunteer profile ✅ implemented (2026-05-29)

**Status:** Both flows are implemented. See SPEC.md §4.6 for full documentation.

**What was built:**

- **On new volunteer creation:** `_send_password_set_email(request, user, welcome=True)` is called automatically. The volunteer receives a welcome email with a 3-day password-set link. No plaintext password is ever generated or sent.
- **"Send password reset email" button** on the volunteer edit page (Panopticon only): calls `send_volunteer_password_reset()` → `_send_password_set_email(request, user, welcome=False)`. Use this when the welcome email expired or was lost.
- **"Set password" form** on the volunteer edit page (Panopticon only, when `VENUE.show_user_management`): calls `set_volunteer_password()` using Django's `SetPasswordForm`. Use for in-person setup or volunteers without email.

**Design decision taken:** "Send password reset email" is the primary flow (no plaintext exposure, volunteer chooses their own password). Direct set is the fallback. This was the cleaner option identified in the original spec.

**Known remaining gap:** No "Change password" link for the volunteer themselves (they rely on the Panopticon-triggered reset flow). Volunteer self-service password change would be a separate small task.

---

### 9.50 — Volunteer self-service profile edit from nav 🟢 XS (1–3h)

**Problem:** On the live S&S site, volunteers can click their own name in the top nav bar to edit their personal details (name display, email, etc.). This feature existed on the `s+s` branch but was not ported. Currently logged-in volunteers have no quick route to their own profile — they either have to know the URL or ask a Panopticon user.

**How s+s did it** (in `toolkit/index/templates/base_admin.html`):

- Panopticon users: `<a href="{% url "edit-volunteer" user.volunteer.pk %}">{{ user.volunteer.member.name }}</a>` — links to the full volunteer edit form
- Regular volunteers: `<a href="{% url "edit-member" user.volunteer.member.pk %}?k={{ user.volunteer.member.mailout_key }}">{{ user.volunteer.member.name }}</a>` — links to the member contact-details form (name, email, mailout opt-in), using the `mailout_key` for anonymous-style auth without requiring staff access to the member admin

**Proposed approach for sns_2026_overhaul:**
Since volunteers now have proper Django user accounts (`VENUE.show_user_management=True`), the `mailout_key` shortcut is less important — the logged-in user IS authenticated. Options:

1. **Simple:** Link both tiers to `edit-volunteer/<pk>` (the full volunteer edit page, which already restricts fields by permission level).
2. **Tighter:** Link regular volunteers to a new lightweight self-service page that only shows name + email + opt-in fields, omitting roles/training/permission fields that only Panopticon should edit.

Option 1 is simplest and sufficient for now. The volunteer edit form already hides Panopticon-only fields (the `UserForm` section is gated on `show_user_management`).

**Implementation (option 1):**

In `base_admin.html`, before the Log out button, add:

```html
{% if user.volunteer.pk %}
<li class="nav-item">
  <a class="nav-link" href="{% url "edit-volunteer" user.volunteer.pk %}">
    <span class="fa fa-user"></span> {{ user.volunteer.member.name }}
  </a>
</li>
{% endif %}
```

- Guard with `{% if user.volunteer.pk %}` so accounts without a linked volunteer profile (e.g. a bare Django admin account) don't break.
- No backend changes needed.

**Edge cases:**

- User with no linked volunteer: guard handles this (no link shown).
- Panopticon editing their own profile: they already have access to `edit-volunteer`; no difference.
- Gate on `VENUE.show_user_management`: the volunteer edit page already exists on both branches. The nav link is harmless even on the Cube instance.

---

### 9.56 — Volunteer activity tracking: lifecycle `status` and programmer eligibility 🔵 S (6–12h)

#### Context and current state

`Volunteer.status` (active / dormant / retired / suspended) is administered on the profile page — `active` means on the rota and receiving mailouts. (It replaced the old `active` boolean in migration `members/0018`; `is_active` is now a derived property.) Since the 2026-05 pool-management work, the `auto_dormancy` command auto-applies the Active→Dormant transition based on login age (`volunteer_dormancy_days` / `volunteer_never_logged_in_grace_days`); retire/purge remain manual. The live database shows ~13 non-active volunteers, most of which are test accounts or people who registered and never returned. **Note:** dormancy is still driven by *login* activity, not *shift* activity — the shift-based eligibility logic below remains unimplemented.

The `RotaEntry.name` field stores free-text volunteer names, not a FK to `Volunteer`. This means rota activity cannot be automatically correlated with a volunteer record without a matching step.

#### Business logic intent

The collective has discussed a policy under which programmers should only be able to schedule events if they have completed at least **10 shifts in the last 12 months**. This is a fairness and accountability mechanism: programming slots are a limited resource and should go to people who are actively contributing in other ways, and have enough experience to run an event that goes well and doesn't cause too much stress for the volunteers helping with it.

#### What would need to change to implement this

1. **Shift completion tracking:** `RotaEntry.name` is currently the only "filled" signal. A proper implementation would need either:
   - A `completed` BooleanField on `RotaEntry` (set by keyholder or programmer post-event), or
   - A `shifts_completed` counter on `Volunteer` updated via a management command or webhook.

2. **`Volunteer.status` automation:** login-based auto-dormancy now exists (`auto_dormancy` sets Active→Dormant). A *shift-based* refinement — e.g. auto-derive activity from "has completed ≥ 1 shift in the last 3 months" — would require the shift-completion tracking above.

3. **Programmer eligibility gate:** The `add_event` and `add_showing` views would check `request.user.volunteer.is_eligible_to_programme` (a property, not a DB field) before allowing access. The index page would surface this eligibility status with a friendly prompt to build more shifts.

#### Design questions for the collective

- What counts as a shift? (All rota roles, or only certain ones?)
- Who verifies completion? (Keyholder marks it after the event?)
- Is 10-in-12-months a hard gate or a soft warning?
- What happens to existing programmers with incomplete records?

#### Current recommendation

Do not implement until the collective has answered the design questions above. The infrastructure (shift tracking) is a prerequisite for the eligibility check. Track the design discussion in a collective meeting before any code is written.

---

### 9.86 — Volunteer opt-in directory 🔵 S (8–14h)

A page (login required) listing volunteers who have opted in, with granular controls per volunteer on what to share.

**Per-volunteer privacy controls** (new fields on `Volunteer` or a companion model):
- `dir_share_name` choices: full name / first name + initial / not listed
- `dir_share_email` BooleanField (default off)
- `dir_share_phone` BooleanField (default off)
- `dir_share_pronouns` BooleanField (default off) — reuses `Member.personal_pronouns`
- `dir_share_access_rider` BooleanField (default off) — reuses `Member.access_requirements`
- `dir_share_collectives` BooleanField (default off)

**Directory page:** `/toolkit/volunteers/directory/` — table or card list, login required. Searchable by name. Filterable by collective membership. Shows only entries where `dir_share_name != 'none'`.

**Volunteer edit page:** New "Directory" card in the volunteer profile. Volunteer can set their own preferences. Panopticon can set them for any volunteer.

**Design notes:**
- All fields default off — opt-in only, never opt-out.
- `dir_share_name: 'initial'` shows e.g. "Jonny K" — not the full surname.
- Phone number only shown to authenticated users with at least volunteer-level access.
- Email shown as `<a href="mailto:...">` — no harvesting protection needed since this is internal only.

**Sizing:**

| Component | Est. |
|---|---|
| Privacy fields on `Volunteer` + migration | 1h |
| Volunteer edit form additions | 1h |
| Directory view + template | 3–4h |
| Tests | 2h |
| **Total** | **~8–14h** |

**Minimum viable increment:** name + pronouns + collectives only (~5h).

---

### 9.87 — Collectives → simplelists email list sync 🟡 M (design first) — PARKED

**Status (May 2026): parked — requires live site access to implement and test properly. Developer no longer has prod access. Do not attempt without someone who can test against the real simplelists instance and verify the subscribe/unsubscribe forms accept programmatic POSTs.**

When a volunteer joins or leaves a collective, automatically subscribe or unsubscribe them from the corresponding simplelists mailing list.

**Known lists** (from the working-groups form at `/toolkit/working-groups/`):
- `volunteers@lists.starandshadow.org.uk` — volunteer shifts
- `filmprogramming@lists.starandshadow.org.uk` — film programming
- `musiceventprogramming@lists.starandshadow.org.uk` — music event programming
- `programme@lists.starandshadow.org.uk` — programme
- `tech@lists.starandshadow.org.uk` — tech
- `garden@lists.starandshadow.org.uk` — garden
- `access@lists.starandshadow.org.uk` — access
- `radio@lists.starandshadow.org.uk` — radio
- `howtovideos@lists.starandshadow.org.uk` — how to videos
- `artgroup@lists.starandshadow.org.uk` — artgroup
- `knittingclub@lists.starandshadow.org.uk` — knitting club
- `fundraising@lists.starandshadow.org.uk` — fundraising
- `facilitation@lists.starandshadow.org.uk` — facilitation
- `Building@lists.starandshadow.org.uk` — building maintenance
- `CommunityKitchen@lists.starandshadow.org.uk` — community kitchen
- `BuildingWork@lists.starandshadow.org.uk` — S&S building work
- `PrintRoom@lists.starandshadow.org.uk` — print room
- `darkroom@lists.starandshadow.org.uk` — dark room
- `barlicencing@lists.starandshadow.org.uk` — bar licencing
- `chat@lists.starandshadow.org.uk` — chat

**Integration approach:** Simplelists has a REST API at `https://www.simplelists.com/api/2/` (documented at `simplelists.com/api/docs/2/protocol/`). Auth is HTTP Basic with an API key generated from the Simplelists admin panel. Key operations:

- Subscribe: `POST /api/2/membership/` with `{"list": "listname", "email": "...", "digest": false}`
- Unsubscribe: `DELETE /api/2/membership/:id/` (requires knowing the membership ID — fetch it first via `GET /api/2/membership/?list=listname&email=...`)
- The API returns JSON; errors include an `is_error` flag and a message.

**Prerequisite:** Someone with access to the S+S Simplelists admin account must generate an API key and store it in settings (e.g. `SIMPLELISTS_API_KEY`). Without this the feature cannot be built or tested.

**Collective → list mapping:** New `Collective.simplelists_list` optional field (the list name slug, e.g. `filmprogramming`). Mapping is opt-in per collective. Lists without a mapping are unaffected.

**Sync policy:**
- Join collective → subscribe to list
- Leave collective → unsubscribe from list
- Existing manual subscriptions (people who subscribed via the form but aren't in the toolkit collective) are never touched — we can only manage what we create.
- Failure tolerance: failed API call logs a warning but doesn't block the collective join/leave. Collective membership is the source of truth.

**Design questions (resolved):**
- `digest` mode: off by default (matches form default).
- Automatic unsubscribe on leave: yes, this is the chosen policy.
- Subscriber name: `member.name` from the volunteer record.

**Sizing:**

| Component | Est. |
|---|---|
| `Collective.simplelists_list` field + admin | 1h |
| `m2m_changed` signal for collective membership | 2h |
| Simplelists API client helper + error handling | 2h |
| Tests (mock the HTTP calls) | 2h |
| **Total** | **~7h** (after API key is in hand) |

---

### 9.89 — Weekly volunteer digest email 🔵 S (10–16h)

An opt-in weekly email sent to each volunteer with a personalised summary: their upcoming shifts, what's new on the programme, their starred events, and the current shopping list needs. Content mirrors the 9.35.1 dashboard but reformatted for email.

---

#### Why it's different from the existing mailer

The existing mailer (`MailoutJob` / `mailerd.py`) is a broadcast system: one job, one body, sent to all member recipients. The volunteer digest is fundamentally different:

- Recipients are **volunteers**, not members (though most volunteers are members)
- Content is **personalised per recipient** -- each email shows that volunteer's own shifts and starred events
- Delivery is **scheduled weekly by a management command**, not by the UI-driven `MailoutJob` workflow
- Opt-in is per-volunteer, not per-member

For these reasons the digest does not use `MailoutJob` or `mailerd.py`. It is a standalone management command that sends directly via Django's email backend.

---

#### Opt-in mechanism

A `weekly_digest` BooleanField on `Volunteer` (default `False`). Exposed on the volunteer self-edit page (9.50, already implemented) and on the Panopticon volunteer edit page.

No default opt-in. Volunteers choose to receive it.

Email address: `volunteer.member.email`. If a volunteer has no `Member` record with an email, they are skipped silently.

---

#### Digest content

The email content is computed per-recipient. Each section is included only if it has something to show; empty sections are omitted.

**1. Your upcoming shifts (next 7 days)**

Shifts within the next 7 days where `RotaEntry.volunteer == this_volunteer` and `showing.confirmed == True`. Ordered by `showing.start`. If empty, the section is omitted.

**2. New on the programme**

Events with showings added since `volunteer.last_digest_sent_at` (see below), with at least one future showing. Capped at 30 days lookback for first-time recipients (where `last_digest_sent_at` is null). If empty, omitted.

This section is shown to all opted-in volunteers, not just Programmers -- all volunteers benefit from knowing what's new.

**3. Your starred events (next 30 days)**

Events where `VolunteerEventMark.volunteer == this_volunteer` and `mark == 'star'`, with at least one showing in the next 30 days. Ordered by next showing date. If empty, omitted.

**4. Shopping list: items needed** (blocked on 9.88)

All currently unresolved `NeedFlag` records. If nothing is flagged, omitted. Not personalised -- all volunteers see the same list.

---

#### Tracking: `last_digest_sent_at`

A nullable `DateTimeField` on `Volunteer`. Set to `now()` after each successful send. Used to compute the "new on the programme" lookback window.

First-time send: `last_digest_sent_at` is null → lookback window is `now() - 30 days`.

If a volunteer's email bounces or the send raises an exception, `last_digest_sent_at` is not updated (so next week's digest will cover the missed period too).

---

#### Scheduling

A management command: `manage.py send_volunteer_digest`. Intended to run weekly via a systemd timer or cron job on the production server. Not triggered by the UI.

The project has no Celery. Do not introduce it for this feature.

Example systemd timer (to document in `docs/ONBOARDING.md`):

```ini
# /etc/systemd/system/volunteer-digest.timer
[Unit]
Description=Weekly volunteer digest email

[Timer]
OnCalendar=Thu 09:00
Persistent=true

[Install]
WantedBy=timers.target
```

The day and time (Thursday 09:00) are a reasonable default for a weekend-heavy programme. Could be made configurable via `SiteConfiguration` later, but hardcoding is fine for MVP.

---

#### Email format

Plain text for the MVP. The existing mailer supports HTML, but the added complexity of HTML email templating is not worth it for the first version. A plain-text digest is readable in all clients and simpler to maintain.

Structure:

```
Subject: Your Star and Shadow volunteer digest — week of [date]

Hi [name],

Here's your weekly summary.

YOUR UPCOMING SHIFTS (next 7 days)
-----------------------------------
[Event name] — [date] — [role]
[Event name] — [date] — [role]

NEW ON THE PROGRAMME
---------------------
[Event name] — first showing [date]
[Event name] — first showing [date]

YOUR STARRED EVENTS
--------------------
[Event name] — next showing [date]

SHOPPING LIST: ITEMS NEEDED
-----------------------------
[Item name] — flagged by [name] on [date]

---
You're receiving this because you opted in at [toolkit URL].
To stop receiving these emails, visit: [unsubscribe link]
```

---

#### Unsubscribe

The email footer includes a one-click unsubscribe link: `/volunteers/digest/unsubscribe/?token=<token>`. The token is derived from the volunteer's pk + a HMAC using `SECRET_KEY` (same pattern as Django's password reset tokens, using `django.core.signing`). The view sets `volunteer.weekly_digest = False` and confirms with a short "You've been unsubscribed" page. No login required.

Do not reuse the existing member unsubscribe mechanism -- that controls all mailouts to members; we only want to toggle the digest preference.

---

#### Data model addition

```python
# On Volunteer:
weekly_digest = models.BooleanField(default=False)
last_digest_sent_at = models.DateTimeField(null=True, blank=True)
```

One migration. No new model needed.

---

#### Design questions to resolve before building

1. **Day of send:** Thursday 09:00 proposed. Check with coordinators whether Friday (closer to weekend shifts) is better, or Monday (planning the week ahead).

2. **Digest vs real-time:** would some volunteers prefer immediate notifications (e.g. when a shift they're signed up to is changed)? Real-time is a larger feature; the digest is deliberately weekly and low-frequency. Decide scope clearly before starting.

3. **What counts as "new on the programme":** is it `Showing.created_at >= last_digest` (new dates added to any event), or `Event.created_at >= last_digest` (new events only)? Proposed: `Showing.created_at`, which also catches new dates added to existing events -- more useful for volunteers planning their attendance.

4. **Deduplication:** if a volunteer is also a member and the existing member mailout goes to all members, will they receive two emails from the toolkit in the same week? Yes, potentially. These are different in purpose (digest vs. programme/newsletter), but worth noting. No action required for MVP; could be addressed if volunteers complain.

---

#### Sizing

| Component | Est. |
|---|---|
| `Volunteer.weekly_digest` + `last_digest_sent_at` fields + migration | 1h |
| Opt-in toggle on volunteer self-edit + Panopticon edit pages | 1h |
| Management command: query logic + per-recipient build | 3h |
| Plain-text email template | 2h |
| Unsubscribe view + token generation | 2h |
| Tests (opt-in/out, content generation, unsubscribe, skips for missing email) | 4h |
| Systemd timer docs update | 0.5h |
| **Total** | **~13–14h** |

**Dependencies:** 9.35.1 (dashboard) is a design dependency -- share the query logic. Shopping list section blocked on 9.88. Everything else is independent.

**Prerequisite:** Verify simplelists accepts programmatic POSTs before coding. Test manually with `curl` first.

---

### 9.93 — Dashboard widget: upcoming inductions and training 🟢 XS (2–3h)

A card showing upcoming confirmed showings tagged `induction` or `training-for-volunteers`, visible to all logged-in users. Helps new volunteers find their way in, and reminds experienced ones that training routes exist. Directly addresses the spec's stated value: "low barrier to entry is a core value."

The two relevant tags already exist in the system (`induction`, `training-for-volunteers`). The induction tag is used for monthly volunteer inductions (first Sunday of the month). The training tag covers role-specific training sessions (projection, bar, café, etc.).

#### Query

```python
DAYS_AHEAD = 42  # six weeks — inductions are monthly, so this shows 1–2 ahead

upcoming_training = list(
    Showing.objects.filter(
        confirmed=True,
        start__gte=now,
        start__lte=now + timedelta(days=DAYS_AHEAD),
        event__tags__name__in=["induction", "training-for-volunteers"],
    )
    .select_related("event")
    .order_by("start")
    .distinct()[:8]
)
```

`.distinct()` is needed because a showing with both tags would otherwise appear twice.

#### Permission gate

All logged-in users. This is explicitly about lowering barriers, so there is no reason to restrict it.

#### View changes

Run the query unconditionally for any authenticated user. Add `upcoming_training` to context if non-empty.

#### Template

New card gated on `{% if upcoming_training %}`. Each row: date, event name linked to the public event detail page (not the edit view — this is informational, not an action). A brief role name or tag badge would be useful if the event name doesn't already make the type clear (e.g. "Volunteer Induction" is self-describing; "First Sunday" is not).

```
┌─────────────────────────────────────────────────┐
│ Upcoming inductions & training                  │
├─────────────────────────────────────────────────┤
│ Sun 1 Jun    Volunteer Induction                │
│ Sat 7 Jun    Café Induction                     │
│ Sun 15 Jun   Projection Training (Level 1)      │
│ ...                                             │
└─────────────────────────────────────────────────┘
```

No "view all" link needed — the public programme filtered by tag covers this.

#### Sizing

| Component | Est. |
|---|---|
| View query + context | 0.5h |
| Template card | 0.5h |
| Tests | 1h |
| **Total** | **~2h** |

---

### 9.96 — Volunteer pool management GUI 🔵 S (14–22h total)

**Goal:** Make the volunteer lifecycle management tools accessible to Panopticon users without needing shell/console access. The `auto_dormancy` and `purge_stale_volunteers` management commands currently require SSH access, which is a barrier for day-to-day pool maintenance.

#### Background

The pool health dashboard (`/volunteers/view/pool-health/`) already surfaces two cohorts — dormant volunteers and purge candidates — in a read-only view. This feature adds the management actions that belong alongside that view.

#### Features

**9.96.1 — Run auto-dormancy from the GUI** 🟢 XS (2–3h)

A "Run auto-dormancy" button on the pool health page. On click, shows a dry-run preview (names + last login dates of volunteers who would be marked Dormant) and asks for confirmation before making any changes. On confirm, applies the same logic as the `auto_dormancy` management command and shows a summary of what changed.

Implementation: a new pair of views (`auto-dormancy-preview` GET and `auto-dormancy-apply` POST) that run the same queryset logic currently in the command. The command itself should stay — it is still useful for cron scheduling.

**9.96.2 — Quick "restore to active" from pool health** 🟢 XS (1–2h)

Each dormant volunteer in the pool health table should have a "Restore to active" POST action alongside the existing "edit" link. Applies the same logic as `reactivate_self` but admin-triggered: sets `status = active`, fires `_notify_vols_admin_status_change`, and adds a success message. Returns to the pool health page.

This is distinct from editing the volunteer's full profile — it's a one-click decision, not a form.

**9.96.3 — Retention override flag** 🔵 S (4–6h)

A boolean `retention_exempt` field on `Volunteer` (plus migration). When set, the volunteer is excluded from `purge_candidates()` regardless of their status or last-activity date. An optional `retention_exempt_reason` text field (max 200 chars) lets the operator record why.

**Why a flag, not a new status value:** the existing statuses (`active`, `dormant`, `retired`, `suspended`) describe lifecycle state and each drives concrete system behaviour — rota eligibility, login access, comms inclusion. A retention override is a data governance decision that is orthogonal to lifecycle state: a volunteer can be dormant+retained or retired+retained. Adding a fifth status value would create an enum where two values secretly mean "dormant+exempted" and "retired+exempted", which conflates two independent dimensions onto one field.

The pool health page should show a small "retained" badge alongside the volunteer's name in the purge candidates section, and the edit form should expose the checkbox and reason field (Panopticon only).

**9.96.4 — Last-gasp contact email** 🔵 S (4–6h)

A "Send last-gasp email" action on each purge candidate row. On click, shows a preview of the email (subject and body configurable via `SiteConfiguration`) and sends it to the volunteer's address on confirm. The email asks whether the volunteer is still interested in the venue and optionally mentions sponsorship (e.g. Ko-fi). Records the send as a log entry (timestamp + volunteer PK) so the action cannot be triggered twice for the same volunteer within a configurable cooldown window (default 30 days).

Use case: before anonymising a record, give the person a chance to re-engage or at least say goodbye. Can also double as a soft marketing touchpoint for sponsorship asks.

**9.96.5 — Guard anonymise against active membership** 🟢 XS (1–2h)

The `anonymise_volunteer` view and `purge_stale_volunteers` command currently anonymise the linked `Member` record unconditionally. If the volunteer also holds an active membership (`member.is_member = True` and `member.membership_expires` is in the future), this silently destroys their membership data.

Fix: on the anonymise confirmation page, check for active membership and display a prominent warning if found. Do not block the action (the operator may legitimately want to proceed), but ensure it is a conscious decision. The `purge_stale_volunteers` command should also log a warning for any candidate with an active membership and exclude them from bulk anonymisation by default (opt-in with `--include-members`).

#### Sizing

| Component | Est. |
|---|---|
| Auto-dormancy preview + apply views | 2–3h |
| Quick restore action | 1–2h |
| `retention_exempt` field + migration + queryset update | 1–2h |
| Retention exempt UI (pool health badge + edit form field) | 2–3h |
| Last-gasp email (view + template + log model + cooldown) | 3–5h |
| Active-membership guard (view warning + command flag) | 1–2h |
| Tests | 4–5h |
| **Total** | **~14–15h** |

---

### 9.99 — Volunteer stats page 🟡 M (20–30h)

**Goal:** Give each logged-in volunteer a personal "your history at S+S" page. A place to go down memory lane, see what kinds of shifts they've signed up for, understand their activity over time, and feel recognised for their contribution.

This surfaces data that already exists in the database (rota entries, training records, induction date). It does not require any new data collection — only querying and presenting existing records.

#### Background

The sns-analysis project (`~/code/sns-analysis`) already generates a similar report as a WhatsApp-formatted text block (see `src/export_volunteer_shifts_enhanced_report.py`). That analysis includes: monthly heatmaps, shifts-per-year bars, event-type breakdown with percentage bars, most common roles, role evolution narrative, milestone shifts (10th, 25th, 50th...), and co-volunteer frequency. This spec translates that data into a proper web page, adapting it to what is available directly in the toolkit database (no DuckDB, no external analysis pipeline required).

The analysis script operates on a richer, deduplicated dataset (via a name-disambiguation pipeline). The toolkit version will operate on the raw `RotaEntry` data linked to the logged-in volunteer's `Volunteer` PK — straightforward and fully self-contained.

#### Access model

- Volunteers see only their own stats (authenticated, own record only).
- Panopticon users can view any volunteer's stats page (useful for welfare check-ins, appreciation moments, and one-to-one conversations).
- The page is read-only. No data is modified.

#### Features

**9.99.1 — Core stats: headline numbers** 🟢 XS (2–3h)

At the top of the page, a summary header showing:

- Total shifts completed (count of `RotaEntry` records where `volunteer = self` and the showing's date is in the past).
- First shift date and most recent shift date.
- Duration active at the venue (e.g. "3 years, 4 months").
- Induction date (`volunteer.created_at`).
- Time since induction (e.g. "member of the community for 4 years").

The living-wage estimate from the analysis script (shifts × 3.5h × NMW) is emotionally effective — consider including it as a "your contribution is worth approximately £X at the living wage" note, framed as appreciation rather than compensation. This should probably be togglable via `SiteConfiguration`.

**9.99.2 — Activity heatmap (year × month grid)** 🟡 M (5–7h)

A calendar-style heatmap rendered in HTML/CSS (no JS charting library required — CSS grid with colour-coded cells works well). Each cell is one calendar month; colour intensity encodes shift count (0 = empty, 1–2 = light, 3+ = strong). Years as rows, months as columns.

This is the most visually arresting section of the analysis report. In the web version it can use proper colour rather than ASCII characters.

Accessible fallback: each cell should have a title attribute or aria-label with the count.

**9.99.3 — Shifts per year bar chart** 🟢 XS (2–3h)

A simple horizontal bar chart showing shift count per calendar year. Can be rendered as a CSS-only chart (no JS needed) or a `<table>` with bar cells. Include the raw count alongside each bar.

**9.99.4 — Role breakdown** 🟢 XS (2–3h)

A ranked list of the roles the volunteer has done, with counts and percentages (e.g. "Bar Staff — 34 shifts, 28%"). Show the top 8–10 roles; collapse the rest under a "show more" if there are many.

A secondary section could group roles into the functional buckets from the analysis script (film crew, bar team, café team, tech, building ops) to give a higher-level picture of "what kind of volunteer are you". The bucket mapping is already defined in `export_volunteer_shifts_enhanced_report.py` and can be replicated as a Python dict in the toolkit.

**9.99.5 — Event type breakdown** 🟡 M (3–4h)

Showing → Event has a category field (from the `Event.media_type` or similar). Show what proportion of their shifts were at film screenings, gigs, community events, etc. A horizontal stacked bar or percentage list works well here.

Note: need to verify which field on `Event` / `Showing` encodes the event type and whether it maps cleanly to the 6-category system in the analysis script. May require a translation layer.

**9.99.6 — Role evolution timeline** 🟢 XS (3–4h)

A chronological list of "first time" milestones — when the volunteer first did each distinct role bucket, and when they hit named milestones like "became a keyholder" or "started training new volunteers". Presented as a vertical timeline or a simple dated list.

The narrative format from the analysis script ("▸ 2021-03 first film crew shift") translates well to a `<dl>` or a styled `<ol>`.

**9.99.7 — Milestone shifts** 🟢 XS (1–2h)

Mark the 10th, 25th, 50th, 100th, 150th, 200th shifts with the event title and date. Short section — a simple table. Doubles as a "wow, your 50th shift was at..." moment.

**9.99.8 — Training record** 🟢 XS (2–3h)

List the volunteer's training records from `TrainingRecord`: date, training type (general safety / role-specific), role (if applicable), trainer name. A simple table is fine. Show the most recent general safety training date prominently, since it determines whether they are currently considered trained.

This section may not be relevant for all venues; gate it behind a `SiteConfiguration` flag.

**9.99.9 — Panopticon: view-as for any volunteer** 🟢 XS (1–2h)

Panopticon users should be able to navigate to `/volunteers/<pk>/stats/` to see any volunteer's stats. The volunteer summary page (`/volunteers/view/`) should link to this view for each row. The page header should make clear whose stats are being shown when viewed by a Panopticon user (e.g. "Viewing stats for Alex Birch").

#### URL design

```
/volunteers/stats/               # own stats (requires login, volunteer status)
/volunteers/<pk>/stats/          # any volunteer's stats (requires Panopticon)
```

The own-stats URL redirects to the PK-based URL once the volunteer is identified — avoids duplicating the view logic.

#### Data availability caveat

The toolkit's rota data only goes back to whenever records were entered. The analysis script works on a richer dataset (including archived spreadsheets predating the toolkit). The volunteer stats page should make this caveat visible: "Your stats cover shifts recorded in this system from [earliest date] onwards." The analysis project covers a longer history — that is a separate offline tool for appreciation events.

#### Template and visual design

The page should feel warm and appreciative — this is not a productivity dashboard, it is a "look how much you've given" page. Consider a celebratory header tone. The heatmap is the centrepiece; keep the rest scannable.

Uses the existing base templates. No new JS dependencies.

#### Sizing

| Component | Est. |
|---|---|
| Core stats header (9.99.1) | 2–3h |
| Activity heatmap (9.99.2) | 4–6h |
| Shifts per year bar (9.99.3) | 1–2h |
| Role breakdown (9.99.4) | 2–3h |
| Event type breakdown (9.99.5) | 2–4h |
| Role evolution timeline (9.99.6) | 2–3h |
| Milestone shifts (9.99.7) | 1–2h |
| Training record section (9.99.8) | 1–2h |
| Panopticon view-as (9.99.9) | 1–2h |
| URL routing + access control | 1h |
| Tests | 3–4h |
| **Total** | **~20–32h** |

### 9.100 — Role qualification gates: training-gated rota sign-up with shadow progression 🟡 M (draft — needs ratification)

**Status:** First-draft spec, 2026-05-30. Captures the last outstanding volunteer-feedback request. Needs a design decision on the open questions below and collective buy-in before any build. Closely related to §8.8 (training records too rigid), the shadow-mode spec under 9.x (programmer/shadow roles), and §9.4 (induction workflow — where inductions get recorded in the first place).

**The request (verbatim intent).** Volunteers should not be able to sign up for a skilled role until they have done the relevant induction — e.g. you can't take the **Projectionist** slot unless you've done the **Projection Induction**. Ideally, after the induction a volunteer should **shadow 2–3 times** before going solo, especially for trickier formats (35mm, unusual aspect ratios, multi-projector).

**Why this is hard, and why it has stalled before.** §8.8 already diagnoses the core problem: the existing `TrainingRecord` model tries to force every kind of qualification through one schema (trainer + date + role, expiring after 12 months), so it is never maintained and is therefore used to gate nothing. Real qualifications differ in kind: binary inductions (bar, projection — you've done it or you haven't, no expiry), expiring external certificates (food hygiene L2), tiered internal progression (projectionist levels), and informal "comfortable with this" signals (sound/tech). A gate that blocks sign-up is only as trustworthy as the records behind it — **if the records aren't reliably kept, a hard gate locks out genuinely-qualified people.** That is the central risk and it shapes everything below.

**Core concept — a `Qualification`, decoupled from the expiring training log.**

Introduce a lightweight `Qualification` model representing a thing a volunteer can hold (e.g. "Projection induction", "Bar induction", "Food hygiene L2"). A volunteer *holds* qualifications via a join record. A `Role` can *require* zero or more qualifications. This deliberately sits **alongside** the existing `TrainingRecord` rather than replacing it — `TrainingRecord` can remain the audit log of training *events*; `Qualification` is the durable "is this person cleared for this?" fact that the gate actually reads. (Long-term, §8.8's rewrite could fold the two together, but that is a bigger job and not required for this feature.)

**The gate is a spectrum, set per requirement — not a single hard block.**

| Mode | Behaviour at sign-up | Use for |
|---|---|---|
| **Off** | No check. (Today's behaviour.) | Most roles |
| **Advisory** | Volunteer can still sign up, but sees a notice ("This role normally needs the Projection induction — have you done it?") and the slot is flagged on the rota for a coordinator to eyeball. | Soft signals; roles where records are incomplete; rollout phase |
| **Blocking** | Volunteer without the qualification cannot take the **primary** slot. They may still take a **shadow** slot if one is open (see below). | Genuine hard gates (projection, bar) once records are trusted |

Defaulting new requirements to **Advisory** is the safe path: it surfaces the expectation without locking anyone out while the qualification records are still being populated. A requirement can be promoted to **Blocking** per-role once the collective trusts the data.

**Shadow progression (the "shadow 2–3 times before solo" part).**

This composes with the existing **shadow-mode** spec (solo / shadow-open / shadow-at-discretion). The progression adds one idea: holding the induction unlocks *shadowing*; logging enough shadows unlocks *solo*.

- A volunteer who **has the induction but not enough shadows** may sign up only to the **shadow** slot (when one is open), not the primary slot.
- Each completed shadow is logged (by the primary volunteer, a coordinator, or self-attested — open question). When the volunteer reaches the role's `shadows_required` threshold (e.g. 3), they become eligible for the **primary** slot.
- The threshold lives on the role requirement (`shadows_required`, default 0 = no shadow gate). Setting it to 0 reduces the feature to a plain induction gate.

**Format-specific difficulty ("especially for trickier formats").** The cleanest first cut treats difficulty at the **role** level (one "Projectionist" gate). True per-format gating (digital vs 35mm) likely wants either separate roles ("Projectionist — 35mm") or a per-showing `difficulty`/`format` tag that raises the required shadow count. This is a genuine fork — see open questions. **Recommend deferring format-specificity to a phase 2**; the MVP gate is per-role.

**Where the gate fires.** The sign-up coercion path (§8.3 / 8.1 MVP) is the single choke point. When a non-superuser claims a slot, the server already overrides the submitted text with their own identity; the gate is an additional check at that same point: look up the role's requirements, check the volunteer's held qualifications + shadow count, then allow / warn / block. Superusers (Panopticon) bypass the gate, exactly as they bypass name coercion — a coordinator can always place someone manually. The rota UI should *also* reflect eligibility ahead of the click (e.g. lock/grey the slot for ineligible volunteers, with a tooltip explaining what's needed) so the block is never a surprise.

**Data model sketch.**

```
Qualification:
  name              # "Projection induction"
  kind              # induction | certificate | tier   (informs expiry UI; see §8.8)
  expires_after     # nullable duration; null = never expires (inductions)

VolunteerQualification (join):
  volunteer FK
  qualification FK
  awarded_on, awarded_by, expires_on (nullable), notes

RoleQualificationRequirement:
  role FK
  qualification FK
  gate_mode         # off | advisory | blocking
  shadows_required  # int, default 0

ShadowLog:           # one row per completed shadow shift
  volunteer FK
  role FK            # which role they shadowed
  showing FK         # provenance
  signed_off_by      # who confirmed (nullable if self-attested)
  date
```

A volunteer is **solo-eligible** for a role when, for every blocking requirement on that role, they hold a current qualification *and* their `ShadowLog` count for that role ≥ `shadows_required`.

**Open design questions (need a decision before building):**
1. **Who logs a shadow?** Self-attested (low friction, low trust), confirmed by the primary volunteer on the night (medium), or only by a coordinator (high trust, high friction)? This is the make-or-break culture question, mirroring §8.8's point that gates are only as good as the records.
2. **Advisory vs blocking default, and who can promote to blocking** — Panopticon only, or any programmer per role?
3. **Format-specific difficulty** — separate roles, per-showing difficulty tag, or out of scope for v1?
4. **Expiry surfacing** — inductions never expire; certificates do. Do we want the dashboard lapse-warning (§8.9) in scope here, or keep that separate?
5. **Interaction with bulk/superuser placement** — confirmed that Panopticon bypasses, but should an advisory note still log against superuser placements for later review?

**Suggested phasing.**
- **Phase 1 (MVP, ~8–12h):** `Qualification` + `VolunteerQualification` + `RoleQualificationRequirement` with `off`/`advisory` only (no blocking, no shadows). Admin/UI to award qualifications and attach requirements. Advisory notice on sign-up. This delivers the visible expectation and starts populating records with zero lock-out risk.
- **Phase 2 (~8–12h):** `blocking` mode + `ShadowLog` + shadow-progression gate + rota slot eligibility display.
- **Phase 3 (~6–10h):** format-specific difficulty; expiry dashboard tie-in (§8.9); fold legacy `TrainingRecord` into the new model per §8.8.

**Open edge case: qualification revocation when a volunteer holds a gated rota slot.**

If a Panopticon revokes a qualification from a volunteer who is currently signed up to a role gated on that qualification, the system needs a defined behaviour. Three options:

1. **Silent pass** — revocation only blocks future sign-ups; existing rota entries are left in place. The volunteer can remain in a role they're no longer qualified for until a coordinator notices.
2. **Warn on revoke** — when revoking, check for future rota entries in blocking-gated roles and show a warning panel (with links to the affected showings) but do not auto-clear them. The Panopticon decides whether to remove them manually.
3. **Auto-clear** — revocation triggers automatic removal from affected future rota slots, following the suspension pattern.

**Recommendation: option 2** (warn but don't auto-clear). Auto-clear is appropriate for suspension (an emergency safety action) but too aggressive for a routine qualification update — the Panopticon should decide. The warning ensures nothing is silently left in an inconsistent state.

---

### 9.120 — Volunteer CSV export: full page with field selector + PII notification 🔵 S (6–10h)

**Problem.** The current volunteer export is a one-click download that exports everything or nothing — it makes it trivially easy to export phone numbers and home addresses that are almost never needed and should not be routinely downloaded.

**Proposed design.**

Replace the one-click link with a full `/volunteers/export/` page (Panopticon only) containing:

- **Field-group checkboxes:** Basic (name, email, status, collectives — pre-ticked) / Contact details (phone — opt-in) / Home address (opt-in). Possibly finer-grained.
- **Prominent discouragement notice** above the sensitive field options: "Phone numbers and addresses should only be exported if you have a specific, immediate need. The export will be logged."
- **Audit notification** when address or phone fields are selected: record an `ExportAuditLog` entry (who exported, which fields, timestamp); optionally also email the Panopticon list so other keyholders are aware.
- **Download button** generates the CSV on the fly from selected fields.

The basic field set (name, email, status) should be the default and require no acknowledgement. The sensitive fields require an explicit opt-in tick per export.

**Audit log model:**

```
ExportAuditLog:
  exported_by     FK → User
  exported_at     datetime
  fields_included JSON   # list of field names selected
  recipient_count int    # number of rows in the export
```

Panopticons can view the audit log at `/volunteers/export/audit/`.

**Notification approach** — options to decide:
1. Email to Panopticon mailing list (requires `PANOPTICON_EMAIL` setting)
2. Dashboard notification in the toolkit index (visible to all Panopticons on next login)
3. Both

---

### 9.121 — Qualification report + training/qualification page consolidation 🔵 S (8–14h)

**Context.** After landing 9.100 (role qualification gates), we now have two overlapping data structures (qualifications and training records) and a growing set of volunteer-management tools in the Volunteers dropdown that are in different states of relevance.

**Part 1: Add a qualification report.**

By analogy with `/volunteers/training-report/`, add a qualification report at `/volunteers/qualification-report/` showing:
- Each qualification: how many volunteers hold it, who holds it, when each was granted
- Highlight any with blocking role gates so the reader can see which qualifications are load-bearing
- Link through to each volunteer's profile

**Part 2: Audit the existing training/role reports.**

The training report and role report in the Volunteers dropdown are described internally as "defunct". Review them:
- Training report: does it still show useful data now that qualifications are the gating mechanism? Consider whether it should be updated or retired.
- Role report: what does it currently show? Is it useful?

**Part 3: Consolidate the bulk-record interfaces.**

We have two separate bulk-add UIs that serve similar purposes:
- `/volunteers/add-training-group/` — bulk-add a training record to a group of volunteers
- The new bulk qualification-grant tool (added with 9.100)

Compare the UX of both. Take the best of each. Consider merging them into a single "Bulk record" page with a **type selector** at the top:

> ○ Training record  ○ Qualification grant

With an inline explanation of the difference:
> **Training records** are event-based log entries (e.g. "attended General Safety Training on 12 May"). They expire and are used for audit, not access control.
> **Qualifications** are durable clearances that gate rota sign-ups (e.g. "cleared for Projection"). They don't expire unless a certificate type is set.

This removes a source of confusion for coordinators who are unsure which tool to use.

**Part 4: Qualifications discoverability.**

Qualifications are currently managed inline on the Roles page (`/diary/edit/roles/`), with no dedicated nav link. Coordinators looking for "qualifications" have no obvious place to go. As part of this consolidation, consider adding a top-level "Qualifications" link in the People/Volunteers nav section, pointing to either the qualification report (Part 1) or a combined qualifications management page that surfaces both the list of qualification types and the bulk-grant tool.

---

### 9.123 — Suspended volunteer: status UX overhaul 🔵 S (4–8h after design decision)

**Problem.** The Suspended status is currently one radio button option alongside Active / Dormant / Retired in the volunteer edit profile. It is not visually distinct, yet it is qualitatively different: it immediately blocks login and clears future rota entries. This severity is not communicated in the UI.

Additionally, the help text above the status section currently reads:

> "This controls what a volunteer can do. Each option below says exactly what changes. Only Suspended stops someone logging in — the others just take them off the rota and mailing list."

This is inaccurate — the options do not in fact say exactly what each one does, and the summary is incomplete (e.g. Dormant and Retired have different implications for things like the digest email and pool-health dashboard).

**Proposed design options — needs decision before implementation:**

**Option A — Red/bold in existing widget:**  
Keep the four-option radio group. Style the Suspended option with a red text label, a ⚠ prefix, and a one-line consequence note ("Immediately blocks login and removes from future rota"). Cheapest; least disruptive to the existing form layout.

**Option B — Split status box + separate suspend section:**  
Split the status widget into two sections on the form:
- Top: "Volunteer status" — Active / Dormant / Retired (normal lifecycle states with plain-English descriptions of each)
- Bottom: "Suspension" — a separate card or callout with a red/amber border, containing a single "Suspend this volunteer" toggle with a clear warning and confirmation step. Reinstatement via the same card.

This makes Suspended a qualitatively separate category rather than one of four peer options.

**Option C — Status-only radios + dedicated suspend button (like anonymise):**  
Active / Dormant / Retired remain as a radio group. Suspend is a standalone action button in the danger zone (like "Anonymise this volunteer"), requiring a confirmation dialog that lists the consequences and asks the Panopticon to type something to confirm. Makes the exceptional nature of suspension fully explicit.

**Also fix the help text** regardless of which option is chosen: replace the misleading promise ("each option below says exactly what changes") with accurate per-option descriptions:

| Status | What it means |
|---|---|
| Active | On the rota, receives the digest email, appears in the directory |
| Dormant | Removed from active rota and digest; retained for re-induction tracking |
| Retired | Permanently left; no rota, no digest, not surfaced in pool health |
| Suspended | Login blocked immediately; future rota entries cleared; digest paused |

**Recommendation:** Option B. It keeps the form cohesive while making the severity clear. Option C (dedicated button) is the cleanest architecturally but adds another confirmation flow; reserve for a future pass if Option B still feels unclear in practice.

---

### 9.137 — Bulk training: replace Chosen multi-select with checkbox table + name search 🔵 S (6–10h)

**Problem.** The training mode of `/volunteers/bulk-record/` uses a `ChosenSelectMultiple` widget (shift-click multi-select). On large volunteer pools (1000+) this is fragile: accidentally releasing Shift loses the whole selection, and there's no way to select non-contiguous groups without repeated shift-clicks.

**Goal.** Replace the Chosen widget with a checkbox table matching the qualification section: each volunteer is a row with a checkbox, a name link, and relevant info columns. Add a JS name-search filter above the table so programmers can find volunteers without scrolling.

**Approach.**

1. Remove `volunteers` from `GroupTrainingForm`. Instead, pass `volunteers_qs` to the template context (all active volunteers, ordered by name).
2. In the template, render a table with checkboxes (`name="volunteer_ids"`, `value="{{ member.pk }}"`) — same pattern as the qualification table.
3. Add a `<input type="search">` above the table; JS filters rows by name substring in real time.
4. In `_bulk_record_training`, read `request.POST.getlist("volunteer_ids")` instead of `form.cleaned_data["volunteers"]`. Validate that all PKs are active members before saving.
5. Add a select-all / select-none control row (same as qualification section).

**Out of scope:** pagination (filter-as-you-type makes this unnecessary for up to a few thousand names).

**Related:** 9.121 (bulk-record UX), 9.138 (training + qual combo)

---

### 9.138 — Bulk training: optional simultaneous qualification grant 🔵 S (4–8h)

**Problem.** Running a training session often means both recording the training event AND awarding the corresponding qualification. Currently these are two separate bulk-record operations.

**Goal.** Add an optional "Also grant qualification" dropdown to the training form. When a qualification is selected, the same volunteers who receive the training record also receive that qualification in a single submission.

**Approach.**

1. Add an optional `ModelChoiceField` for `Qualification` to `GroupTrainingForm` (or pass queryset in context if moving to a formless approach as in 9.137).
2. In `_bulk_record_training`, after saving training records, if a qualification was chosen, bulk-award it (create `VolunteerQualification` for each volunteer who doesn't already hold it).
3. Success message covers both actions.

**Decision to make at implementation time:** whether to implement this before or after 9.137 (checkbox table). If after, the volunteer IDs will come from the checkbox list; if before, they still come from `GroupTrainingForm.volunteers`. Implement after 9.137 for consistency.

**Related:** 9.137 (checkbox table), 9.121 (bulk-record)

---

### 9.139 — Volunteer export: filter by upcoming shift or specific event 🔵 S (4–8h) — ✅ DONE 2026-07-01

**Problem.** The current volunteer export gives every volunteer in the database. There is no way to quickly get a list of people signed up to a specific upcoming event — which is needed when something changes and you need to contact all attendees.

**Proposed design.**

Add a filter section to the existing `/volunteers/export/` page (9.120), above the field-group checkboxes:

- **"All volunteers"** (default, current behaviour)
- **"Volunteers with any upcoming shift"** — filter to volunteers who have at least one RotaEntry for a Showing on or after today
- **"Volunteers signed up to specific events"** — a checklist of upcoming confirmed events (next 60–90 days), selectable by the user; export includes volunteers with a RotaEntry on any of the selected events

The filter selection should be passed as POST params and applied in the view before generating the CSV. The audit log entry (ExportAuditLog) should record which filter was used (e.g. `filter_type` field: `"all"` / `"upcoming"` / `"events"`, plus `filter_event_ids` as JSON for the specific-events case).

**Implementation notes.**

- RotaEntry → Showing → Event chain: `RotaEntry.objects.filter(showing__start__gte=timezone.now(), showing__event__in=selected_events).values_list("volunteer_id", flat=True).distinct()`
- For the "any upcoming shift" filter, omit the `event__in` clause.
- Upcoming events checklist: query confirmed Events with at least one Showing in the future; group by Event for display (not individual Showings).
- The checklist could get long for busy venues — consider a date-range limiter (default: next 60 days) with a "show more" option.

**Audit log changes.**

Extend `ExportAuditLog` (migration required):
- `filter_type` — CharField, choices: `all` / `upcoming` / `events`
- `filter_event_ids` — JSONField (null/blank for `all` and `upcoming`)

Display the filter type and event names in the audit log table.

**Related:** 9.120 (volunteer CSV export)

---

### 9.140 — Sensitive-ops audit log: suspension, anonymisation, account deletion 🟡 M (8–16h)

**Problem.** Suspensions, GDPR anonymisations, and account deletions are high-stakes irreversible actions. Currently they are logged to the server log but there is no in-app audit trail visible to other panopticons. Organisers have no way to see who took these actions, when, or why, without SSH access to the server.

**Goal.** A panopticon-only audit trail page listing every suspension, reinstatement, GDPR anonymisation, and account deletion: who triggered it, on which volunteer, when, and (for suspensions) the reason.

**Approach.**

1. Add a `SensitiveOpsAuditLog` model:
   - `action` — CharField, choices: `suspend` / `reinstate` / `anonymise` / `delete`
   - `performed_by` — ForeignKey to User (null on anonymisation/deletion if actor is also deleted — use `SET_NULL`)
   - `target_volunteer_id` — IntegerField (not FK — the volunteer may no longer exist)
   - `target_name` — CharField, snapshot of name at time of action
   - `performed_at` — DateTimeField (auto_now_add)
   - `reason` — TextField (blank) — suspension reason; free text for other actions if supplied
   - `notes` — TextField (blank) — internal notes field for future use

2. Record an entry at every trigger point:
   - `toggle_volunteer_suspension` (suspend and reinstate)
   - `anonymise_volunteer`
   - The `panopticon_required` bulk-anonymise path
   - User deletion if/when implemented

3. Add a panopticon-only view at `/volunteers/sensitive-ops-log/` showing a reverse-chronological table: date, actor, action, target, reason.

4. Link from the volunteer summary page and/or the existing export audit log page.

**Out of scope:** email notification when a sensitive action is taken (9.X).

**Related:** 9.123 (suspension UX), 9.120 (export audit log)

---

### 9.150 — Induction session: attendee cap + signup removal 🔵 S (6–10h)

**Partial implementation: ✅ 2026-06-23** — cap display in session detail header and × remove button on pending signups shipped as part of the inductions feedback pass (9.4 / B-induction-tracking-94.md). The `max_signups` field and `effective_capacity()` helper already existed from 9.4. Remaining: over-cap warning banner when total > cap, public signup page "session full" behaviour. These are still to do.

**Problem.** Group induction sessions have a natural physical cap (cinema only fits so many people), but there is no way to enforce or communicate it in the system. Inductors also have no way to remove a pending signup when someone emails to say they can't make it.

**Goal.**

1. A per-session attendee cap, with a site-wide default as a starting point.
2. Inductors can set a session cap higher than the site default if they have the space.
3. The public signup page closes (or shows a "full" message) once the cap is reached.
4. If the cap is lowered after signups exist, nobody is removed — but inductors can see who is over the cap and can remove pending signups manually.
5. A "Remove" button on each pending signup on the session detail page, so inductors can act on "sorry I can't make it" emails.

**Data model changes.**

- `InductionsSettings.default_max_attendees` — `PositiveIntegerField(null=True, blank=True)`. Null = no cap by default.
- `InductionSession.max_attendees` — `PositiveIntegerField(null=True, blank=True)`. Null = inherit site default. Session value takes precedence over the default regardless of size.

A helper property on `InductionSession`:

```python
@property
def effective_cap(self):
    if self.max_attendees is not None:
        return self.max_attendees
    return InductionsSettings.load().default_max_attendees  # may be None
```

**Public signup page behaviour.**

- Before rendering the form, compute `session.total_count` and compare against `session.effective_cap`.
- If `effective_cap` is not None and `total_count >= effective_cap`: hide the form; show a message such as "This session is currently full. Check back in case spaces open up, or [request a 1:1 induction] if you have access requirements."
- Cap check must also run at form submission (race condition: two people can submit simultaneously when one slot remains). Return a 409 or re-render with a "full" error if the session is now at capacity.

**Session detail page (manage view).**

- Show cap and current count prominently: e.g. "14 signed up — cap: 20".
- If `total_count > effective_cap`: show a warning banner: "This session has N signups, which is M over the cap. The last M to sign up are shown highlighted below. You can remove pending signups using the × button."
- Sort the signup table by `signed_up_at` ascending so the queue order is visible. (The table already has a "Signed up" column.)
- Add a remove button (×) to each pending signup row. Only pending signups can be removed — checked-in and no-show rows keep the existing controls.

**Session create/edit form.**

- Add an "Attendee cap" field (optional integer). Help text: "Leave blank to use the site default (currently N), or 0 to disable the cap for this session."
- Validate: must be ≥ 1 if set, or blank.

**InductionsSettings admin.**

- Add `default_max_attendees` to the settings form and admin.

**Remove signup endpoint.**

```
POST /inductions/manage/<slug>/signups/<signup_id>/remove/
```

- Requires programmer permission.
- Only removes signups with `status = pending`. Returns 400 for any other status.
- Returns JSON `{"ok": true, "signup_id": N}` on success; updates live count in the JS.
- No email is sent to the removed person (out of scope — they'll have contacted the inductors directly).

**Implementation order.**

1. Migration: add `default_max_attendees` to `InductionsSettings` and `max_attendees` to `InductionSession`.
2. Update settings form/admin to expose `default_max_attendees`.
3. Update session create/edit form to expose `max_attendees`.
4. Add `effective_cap` property and cap check to public signup view.
5. Update session detail template and JS: cap display, over-cap warning, remove button.
6. Add remove endpoint and wire up JS.

**Decisions deferred to implementation.**

- Whether the "full" message on the public page should be "session full" (blunt, accurate) or "sign-ups temporarily closed" (softer). The former is recommended — it helps people understand why and self-route to the 1:1 pathway.
- Whether to notify the inductor when a removal happens (probably not necessary given they initiated it via email).

**Session type and capacity — needs speccing.**

Currently `InductionSession.session_type` has three values (Regular, Small group, 1:1) but capacity works the same way for all of them: session-level `max_signups` overrides site `default_max_signups`, or no cap if both are blank. The "1:1" type is nominal — a 1:1 session can still have any number of sign-ups (e.g. a small group of 5 with access needs). This is probably fine for now, but the session type field is currently doing very little. Before adding more logic that branches on `session_type`, decide:

- Should `session_type` drive different defaults (e.g. Regular inherits site default, Small group defaults to 8, 1:1 defaults to 1)?
- Should `session_type` affect what's shown on the public listing or the sign-up form?
- Should the 1:1 pathway (`InductionRequest` queue) eventually link to a `session_type=ONE_TO_ONE` session, or stay as a separate model?

Spec this before implementing any capacity logic that special-cases session type.

**Related:** 9.4 (volunteer induction workflow), 9.99 (volunteer stats)

---

### 9.143 — Login with email or username 🔵 S (3–5h)

**Problem.** The toolkit currently only accepts username at the login prompt. New volunteers receive their username in the welcome email, but if they lose that email or forget their username, they can't log in and can't use "Reset password" either (which requires username — Django's default — wait, actually Django's default `PasswordResetView` accepts *email* to find the account, but the login form requires username). This creates a dead end: someone who doesn't know their username and has lost the welcome email can't log in or reset their password independently.

**Goal.** Allow volunteers to log in using either their username or their email address.

**Implementation.**

1. Create `toolkit/toolkit_auth/backends.py` with an `EmailOrUsernameBackend`:

```python
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User

class EmailOrUsernameBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        # Try username first (exact, case-sensitive — matches Django default)
        user = super().authenticate(request, username=username, password=password, **kwargs)
        if user:
            return user
        # Fall back to email lookup (case-insensitive)
        try:
            user = User.objects.get(email__iexact=username)
        except (User.DoesNotExist, User.MultipleObjectsReturned):
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
```

2. Add to `settings_common.py`:
```python
AUTHENTICATION_BACKENDS = [
    "toolkit.toolkit_auth.backends.EmailOrUsernameBackend",
]
```

3. Update the login template label from "Username:" to "Username or email:". The field itself doesn't change — Django's `AuthenticationForm` calls the field `username` internally regardless; only the label needs updating. Either subclass `AuthenticationForm` or update the template to override the label.

**Edge cases.**
- `MultipleObjectsReturned`: if two accounts share an email, fall back gracefully (return `None`, let the user try their username). Warn admins in the Django admin if duplicate emails exist.
- Case sensitivity: usernames remain case-sensitive (Django default); email lookup is `iexact`.
- No new dependencies needed.

**Scope.**
- Does not change the password reset flow (already uses email).
- Does not add OAuth / social login.
- Does not enforce email uniqueness on existing accounts (that's a separate, potentially breaking migration).

**Related:** 9.46 (login page styling)

---

### 9.144 — Configurable signup form fields via Inductions Settings 🔵 S (4–8h)

**Problem.** The induction signup form now collects last name, phone number, address, and postcode. These fields are hardcoded as always-shown with fixed required/optional status. Different sessions or future induction contexts may need to collect different combinations — e.g. a 1:1 session might only need name and email; a session with an access-needs focus might want phone but not address. There is currently no way to tune this without editing code.

**Feature.** Add a "Sign-up form fields" section to Inductions Settings. Each configurable field has three states: **Hidden** (not shown, not collected), **Optional** (shown, not required), **Required** (shown, must be filled). Changes take effect immediately for all subsequent sign-ups.

---

**Fixed fields (non-configurable — always present):**

| Field | Reason |
|---|---|
| First name | Minimum identifier; required for account creation |
| Email address | Required for account creation and all email comms |
| GDPR consent checkbox | Required by law |

These are never hidden and are always required. Trying to make them configurable would break account creation.

---

**Configurable fields:**

| Field | Default state | Notes |
|---|---|---|
| Last name | Required | Some people go by one name; hidden removes it from `get_name()` output |
| Phone number | Optional | Stored on `InductionSignup` and copied to `Member.phone` on account creation |
| Address | Optional | Stored on `InductionSignup` and copied to `Member.address` |
| Postcode | Optional | Independent of address — you might want postcode for area data without collecting street address |

Custom questions (configured per-session via `InductionSession.custom_questions`) are out of scope — they have their own required flag already.

---

**Data model — `InductionsSettings`:**

Add a shared constant and four new fields:

```python
FIELD_HIDDEN = "hidden"
FIELD_OPTIONAL = "optional"
FIELD_REQUIRED = "required"
FIELD_VISIBILITY_CHOICES = [
    (FIELD_HIDDEN, "Hidden"),
    (FIELD_OPTIONAL, "Optional"),
    (FIELD_REQUIRED, "Required"),
]

last_name_field = models.CharField(
    max_length=10, choices=FIELD_VISIBILITY_CHOICES, default=FIELD_REQUIRED,
    help_text="Whether the Last name field is shown on the public sign-up form.",
)
phone_field = models.CharField(
    max_length=10, choices=FIELD_VISIBILITY_CHOICES, default=FIELD_OPTIONAL,
    help_text="Whether the Phone number field is shown.",
)
address_field = models.CharField(
    max_length=10, choices=FIELD_VISIBILITY_CHOICES, default=FIELD_OPTIONAL,
    help_text="Whether the Address field is shown.",
)
postcode_field = models.CharField(
    max_length=10, choices=FIELD_VISIBILITY_CHOICES, default=FIELD_OPTIONAL,
    help_text="Whether the Postcode field is shown.",
)
```

Migration: four `AddField` operations, all with `default` set, so no data backfill needed.

---

**`SignupForm` changes:**

In `__init__`, after the field declarations, load settings and adjust:

```python
cfg = InductionsSettings.load()
for field_name, visibility in [
    ("last_name", cfg.last_name_field),
    ("phone",     cfg.phone_field),
    ("address",   cfg.address_field),
    ("postcode",  cfg.postcode_field),
]:
    if visibility == InductionsSettings.FIELD_HIDDEN:
        del self.fields[field_name]
    elif visibility == InductionsSettings.FIELD_REQUIRED:
        self.fields[field_name].required = True
    # FIELD_OPTIONAL: already default for phone/address/postcode;
    # for last_name (default=required), set required=False
    elif visibility == InductionsSettings.FIELD_OPTIONAL:
        self.fields[field_name].required = False
```

Also update `get_name()` to handle missing last name:

```python
def get_name(self):
    first = self.cleaned_data.get("first_name", "").strip()
    last = self.cleaned_data.get("last_name", "").strip()
    return f"{first} {last}".strip()
```

---

**`signup.html` changes:**

Each configurable field block already wraps in a `<div class="signup-field">`. Wrap in `{% if form.field_name %}` — Django templates return an empty string (falsy) when a field doesn't exist in the form, so this works without extra context:

```django
{% if form.phone %}
<div class="signup-field">
  <label for="{{ form.phone.id_for_label }}">
    Phone number{% if form.phone.field.required %} <span aria-hidden="true">*</span>{% endif %}
  </label>
  {{ form.phone }}
  ...
</div>
{% endif %}
```

Apply the same pattern to `last_name`, `address`, and `postcode`.

The address/postcode two-column row needs extra care: if one is hidden and the other isn't, the row should collapse to single-column. Handle with nested `{% if %}` blocks:

```django
{% if form.address or form.postcode %}
<div class="{% if form.address and form.postcode %}signup-row{% endif %}">
  {% if form.address %}...<div class="signup-field">address</div>...{% endif %}
  {% if form.postcode %}...<div class="signup-field narrow">postcode</div>...{% endif %}
</div>
{% endif %}
```

---

**Walk-in form (`session_detail.html`) changes:**

The walk-in form on the manage page is admin-only, so visibility matters less — inductors won't be confused by seeing a phone field that the public form hides. Two options:

- **Option A (simple):** Walk-in form always shows all fields regardless of settings. Accept the minor inconsistency.
- **Option B (consistent):** Pass `inductions_cfg` to the `manage_session_detail` template context; use `{% if inductions_cfg.phone_field != "hidden" %}` in the walk-in HTML.

Recommend **Option B** — it's a one-line view change and a few template conditionals, and it avoids inductors collecting data that the collective has decided not to collect. Also update `manage_add_walkin` to skip validation for hidden fields.

---

**Settings UI (`manage/settings.html`):**

Add a "Sign-up form fields" section. Use a small table with radio buttons — three columns (Hidden / Optional / Required) and one row per configurable field:

```
Sign-up form fields
┌──────────────┬────────┬──────────┬──────────┐
│ Field        │ Hidden │ Optional │ Required │
├──────────────┼────────┼──────────┼──────────┤
│ Last name    │   ○    │    ○     │    ●     │
│ Phone number │   ○    │    ●     │    ○     │
│ Address      │   ○    │    ●     │    ○     │
│ Postcode     │   ○    │    ●     │    ○     │
└──────────────┴────────┴──────────┴──────────┘
```

These are ModelForm fields — use `RadioSelect` widgets in `InductionsSettingsForm.Meta.widgets`.

---

**Edge cases:**

- Last name hidden → `get_name()` returns just first name. Account username derived from first name only (already handled by the `parts[-1]` logic, which returns `''` for a single-word name).
- Address hidden but postcode shown (or vice versa) → independent, fine.
- All contact fields hidden → form just asks first name, last name (if shown), email, consent. Minimal collection, which is a valid configuration.
- Settings cache → `InductionsSettings.save()` already invalidates `_CACHE_KEY`; changes propagate to the form on the next request.

**Out of scope:** Per-session field configuration (site-wide setting only). Custom questions are already per-session via `InductionSession.custom_questions`.

**Related:** 9.4 (induction workflow), 9.150 (session capacity)

---

### 9.145 — Induction public pages: information quality pass 🟢 XS (2–4h)

**Background.** The old S&S induction info page (a static Google Doc / website page) told prospective volunteers several things the new signup flow doesn't communicate: how long the session is, that there's a building tour, that they need to be 18+, and who to contact. The 18+ requirement is now enforced via a checkbox on both signup forms (shipped 2026-06-25). The remaining items are small, independent improvements.

---

**a) Per-session notes field shown on the signup page**

Add `notes = models.TextField(blank=True)` to `InductionSession`. Show it on the public signup page, between the date/location line and the form, if non-empty. No special rendering — plain paragraph(s).

Inductors can use this for anything session-specific: "This session runs for about 90 minutes and includes a short building tour." Or capacity warnings, parking notes, etc. Keep it freeform — don't try to structure duration/tour as separate fields.

- Migration: one `AddField`.
- `InductionSessionForm`: add `notes` to `Meta.fields` with a `Textarea` widget.
- `signup.html`: `{% if session.notes %}<div class="signup-intro">{{ session.notes|linebreaksbr }}</div>{% endif %}` after the date/location line.

**b) Public contact email on signup and thanks pages**

Add `public_contact_email = models.EmailField(blank=True)` to `InductionsSettings`. Distinct from `organiser_notification_email` (which is internal, for new-signup alerts) — this one is shown to the public.

When set, show it at the foot of:
- The signup page (below the form, above the 1:1 link): "Questions? Email [inductions@starandshadow.org.uk](mailto:...)"
- The signup thanks page: same line, so people know who to contact if they need to cancel.
- The access-needs thanks page: same.

If blank, show nothing. No default — forces an explicit decision.

- Migration: one `AddField`.
- `InductionsSettingsForm`: add field (renders as `<input type="email">`).
- Pass `public_contact_email` (or the full `cfg`) in the context for `signup`, `signup_thanks`, `access_needs_thanks` views — all already have `session` or `cfg` available.

**c) "Session full" page already links to other sessions** — no action needed. `signup_full.html` already has "View other upcoming induction sessions" → `/inductions/`. Confirmed present, nothing to do.

---

**Out of scope here:** Facebook/programme links (external, S&S-specific, better handled via the `notes` field in (a) than hardcoded). Session duration as a structured model field (overkill — freeform notes covers it).

**Related:** 9.4 (induction workflow), 9.144 (configurable form fields)

---

### 9.151 — Volunteer consent renewal + privacy-policy-change notification 🔵 S (8–14h) — ✅ DONE 2026-07-01

**Background.** Volunteers consent to data processing once, at induction sign-up (a required checkbox, stamped as `Member.gdpr_opt_in`). That timestamp was never revisited — no mechanism asked volunteers to reconfirm consent periodically, and no mechanism told them when the privacy policy itself changed.

**Design decisions (agreed before build):**

- Scope is volunteers only, not plain mailout `Member`s — the richer personal data (address, phone, rota history, access needs) is the concern here, and mailout already has its own opt-out mechanism.
- Renewal requires **logging in**, not a one-click emailed token link — proves the account is still in active use, which is itself a useful signal alongside the existing login-recency dormancy logic.
- A volunteer who doesn't renew is **flagged for manual review only** — no automatic status change, no automatic anonymisation. This deliberately mirrors the existing lifecycle philosophy in `auto_dormancy.py` (soft/reversible/cron) and `purge_stale_volunteers.py` (manual/reported/confirmed): a *third*, independent clock (consent) is not merged into `Volunteer.status`, which already tracks login-activity-driven state.
- Privacy policy changes are a **manual admin action** (a version-bump button), not automatic diffing — the policy is just an external URL (`InductionsSettings.privacy_policy_url`); the toolkit has no visibility into its content.
- Policy-change notifications are an **immediate email**, not just a login banner — a compliance-relevant event shouldn't wait for a volunteer's next login, which for a dormant account could be months away.

**What shipped:**

- `InductionsSettings`: `privacy_policy_version`, `privacy_policy_updated_at` (stays with `privacy_policy_url`, which it versions).
- `SiteConfiguration`: `consent_renewal_days` (0 disables), `consent_renewal_grace_days` — grouped under "Membership & volunteers" alongside `volunteer_dormancy_days`/`volunteer_purge_days`, the closest sibling settings, rather than in `InductionsSettings` (which is scoped to the induction/sign-up workflow, not ongoing pool management).
- `Volunteer`: `consent_policy_version`, `consent_reminder_sent_at`, computed `consent_overdue` property (excludes `retention_exempt` volunteers, same as `purge_candidates()`).
- `send_consent_renewal_reminders` management command — cron-run alongside `auto_dormancy`, emails active volunteers whose consent has gone stale once the grace period has passed.
- `send_policy_change_notification` command + `notify_policy_change()` helper (`toolkit/inductions/emails.py`) — emails everyone behind the current policy version; invoked directly (function call, not `call_command`) by the "Mark privacy policy as updated" admin action in Inductions settings, so the admin gets an immediate sent/skipped count.
- `renew_consent_self` self-service view (`toolkit/members/views/volunteer_self_service.py`), modelled on the existing `reactivate_self` "welcome back" pattern — a dashboard card appears when `consent_overdue`, with a form POST to reconfirm.
- Volunteer list gains a red "Consent overdue" badge — the reviewer surface, no separate report command needed since the list is already the working view for pool management.

**Known gap surfaced by this work (not fixed, out of scope):** the reminder/notification emails build their login link from `settings.VENUE.get("siteurl", "")`. No settings file for this venue actually defines `siteurl`, so the link resolves relative rather than absolute — the same latent issue already present in `send_volunteer_digest.py`'s `toolkit_url`. Needs a one-line fix to `settings_starandshadow.py` (or wherever `VENUE` is defined per-environment) before either of these email flows can be relied on in production.

**Related:** 9.4 (induction workflow, where consent is first captured)
