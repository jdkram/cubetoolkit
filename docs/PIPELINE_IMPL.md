---
human-contributors: ["Jonny Kram"]
ai-contributors: ["Claude Sonnet 4.6"]
status: "#ai-input"
---

# Programming Pipeline — Implementation Plan

Feature spec: [TASKS.md §9.2](TASKS.md#92-event-programming-pipeline)

---

## Status model

Add a `status` CharField to **`Event`** (not Showing — pipeline status is about the event as a whole).

```
idea → proposed → queued → confirmed
                          → rejected   (at meeting)
                          → cancelled  (post-confirmation)
```

| Value | Meaning |
|-------|---------|
| `idea` | Seed thought, no commitment. Not yet ready for a meeting. |
| `proposed` | Formally submitted for a meeting discussion. |
| `queued` | Accepted onto the next meeting agenda. |
| `confirmed` | Approved. Event goes live on the public programme. |
| `rejected` | Turned down at meeting. Requires a `status_notes` reason. |
| `cancelled` | Was confirmed, then cancelled. Distinct from rejected. |

Conditional approval ("OK if you clear it with the café") uses `status_notes` on `queued` or `proposed` — no extra enum value needed.

---

## New fields on Event

| Field | Type | Notes |
|-------|------|-------|
| `status` | `CharField(choices=..., default='idea')` | See above |
| `proposed_dates` | `TextField(null=True, blank=True)` | Free text fuzzy dates ("a Friday in summer"). Only shown when no Showing exists yet. |
| `status_notes` | `TextField(null=True, blank=True)` | Rejection reason, conditional note from meeting, etc. |
| `status_changed_at` | `DateTimeField(null=True)` | Auto-updated on status change |
| `status_changed_by` | `ForeignKey(User, null=True)` | Who last changed status |

---

## Migration strategy

- Map existing data: `confirmed=True` → `confirmed`, `cancelled=True` → `cancelled`, anything else → `confirmed` (unconfirmed showings that were visible were treated as confirmed in practice).
- Write a data migration that reads old `Showing.confirmed` / `Showing.cancelled` booleans and sets `Event.status`.
- Keep `Showing.confirmed` and `Showing.cancelled` for now as a transition — deprecate in a follow-up once the pipeline is live and tested.

---

## Views to build

### 1. Programming queue `/diary/edit/queue/`

- Lists events with status `proposed` or `queued`, ordered by `updated_at`
- Columns: event name, programmer, proposed dates (or first Showing date), estimated cost vs threshold, `status_notes`
- Finance referral flag (⚠️) when estimated costs exceed `FINANCE_REFERRAL_THRESHOLD_STANDARD` (500) or `FINANCE_REFERRAL_THRESHOLD_MUSIC` (750)
- Per-event actions: **Approve** (→ confirmed), **Reject** (→ rejected, requires note), **Queue for next meeting** (proposed → queued)
- Permission: Programmer and above

### 2. Event Hub additions

- Status badge prominently displayed
- Status history: `status_notes` + who changed it + when
- "Submit for meeting" button (idea → proposed) with etiquette guide reminder
- "Move to next meeting" action (proposed → queued)
- Approve/Reject actions (Panopticon only, or Programmer for their own events)
- Rota deadline warning: if a confirmed showing is < 7 days away with no rota entries

### 3. Diary/Calendar integration

| Status | Diary list | Calendar | Public programme |
|--------|-----------|----------|-----------------|
| `idea` | Programmers+ only, muted | Programmers+ only, grey/dashed | Hidden |
| `proposed` / `queued` | Programmers+ only, ⏳ badge | Programmers+ only, normal colour + ⏳ | Hidden |
| `confirmed` | All users, current behaviour | All users, current behaviour | Shown |
| `rejected` | Hidden from all views (archive only) | Hidden | Hidden |
| `cancelled` | Current cancelled styling | Current cancelled styling | Hidden |

---

## Settings variables

```python
FINANCE_REFERRAL_THRESHOLD_STANDARD = 500   # £
FINANCE_REFERRAL_THRESHOLD_MUSIC = 750       # £
PROGRAMMING_ETIQUETTE_URL = ""               # URL to NextCloud doc
```

---

## File changes

| File | Change |
|------|--------|
| `toolkit/diary/models.py` | Add `status`, `proposed_dates`, `status_notes`, `status_changed_at`, `status_changed_by` to Event |
| `toolkit/diary/migrations/` | Schema migration + data migration (read old Showing booleans) |
| `toolkit/diary/edit_views.py` | Queue view, approve/reject/queue actions, status update endpoint |
| `toolkit/diary/urls.py` | `/diary/edit/queue/` route |
| `toolkit/diary/templates/edit_event_queue.html` | New queue template |
| `toolkit/diary/templates/view_event_privatedetails.html` | Status section on Event Hub |
| `toolkit/diary/templates/edit_event_index.html` | Status indicators on diary list |
| `toolkit/diary/templates/edit_event_calendar_index.html` | Status CSS classes |
| `toolkit/diary/static/diary/js/calendar_index.js` | Status-based event styling |
| `toolkit/diary/views.py` | Verify public programme already filters on `confirmed` |
| `toolkit/settings_common.py` | Add `FINANCE_REFERRAL_THRESHOLD_*` and `PROGRAMMING_ETIQUETTE_URL` |
| `docs/SPEC.md` | Update data model section 8 |
| `CURRENT_WORK.md` | Mark 9.2 as in-progress when work starts |

---

## Not in MVP

- Auto-populate Programmer rota slot on approval (spec in TASKS.md 9.2 — defer to follow-up)
- Rota deadline warning (defer to follow-up)
- Etiquette guide pre-requisite reminder (one-time notice on first event creation)
- Finance referral hard-gate (guidance only per spec)
- Shift count display / volunteer history gate
- Programming criteria fields (structured cost/revenue capture for the break-even calculator)
