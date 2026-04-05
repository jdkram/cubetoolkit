# Programming Pipeline — Implementation Plan

## Goal

Transform the toolkit from a scheduling tool into a planning tool. Events move through a formal status workflow that maps to how Monday programming meetings actually work.

## Status model

Replace `Showing.confirmed` + `Showing.cancelled` booleans with a single `status` CharField on **`Event`** (not Showing — an event's pipeline status is about the event as a whole, not individual showings).

```
idea → proposed → queued → confirmed
                         → denied
                         → cancelled  (post-confirmation)
```

| Status | Meaning |
|--------|---------|
| `idea` | Seed thought, no commitment. "A Friday in summer", rough concept. Not yet ready for a meeting. |
| `proposed` | Formally submitted — programmer is asking for a slot. Has enough detail for a meeting discussion. |
| `queued` | Accepted into the next meeting agenda. Will be discussed. |
| `confirmed` | Approved at a meeting. Event goes live. |
| `denied` | Rejected at meeting. Requires a `status_notes` reason. |
| `cancelled` | Was confirmed, then cancelled. Distinct from denied. |

**On conditional approval:** The status field stays simple. Conditional approval ("OK if you clear it with the café") is handled by the free-text `status_notes` field — set status to `queued` or `proposed` with a note. No extra enum values needed.

## New fields on Event

- `status` — CharField with choices above, default `idea`
- `proposed_dates` — TextField, nullable. Free text for fuzzy dates ("a Friday in summer", "late June"). Visible only when no Showing exists yet.
- `status_notes` — TextField, nullable. Reason for denial, conditional note from a meeting, etc.
- `status_changed_at` — DateTimeField, auto-updated on status change
- `status_changed_by` — ForeignKey to User, nullable

## Migration strategy

Existing data: map `confirmed=True` → `confirmed`, `cancelled=True` → `cancelled`, else → `confirmed` (since existing showings that are neither cancelled nor explicitly unconfirmed were previously treated as confirmed in the public programme). Add a migration that reads the old Showing booleans and sets the new Event.status.

Keep `Showing.confirmed` and `Showing.cancelled` **for now** as a transition — we'll deprecate them in a follow-up once the pipeline is live.

## MVP views

### 1. Programming queue `/diary/edit/queue/`
- Lists all events with status `proposed` or `queued`, ordered by `updated_at`
- Shows: event name, programmer, proposed dates (or first Showing date), estimated cost vs threshold, status_notes
- Finance referral flag (⚠️) when event costs exceed `FINANCE_REFERRAL_THRESHOLD_STANDARD` (500) or `FINANCE_REFERRAL_THRESHOLD_MUSIC` (750)
- Actions per event: **Approve** (→ confirmed), **Deny** (→ denied, requires note), **Queue for next meeting** (proposed → queued)
- Accessible to Programmers and above

### 2. Event Hub additions
- Status badge prominently on the hub
- Status history (status_notes + who changed it + when)
- "Submit for meeting" button (idea → proposed) with guidance reminder
- "Move to next meeting" (proposed → queued)
- Approve/Deny actions (Panopticon only, or Programmer for their own)

### 3. Diary/Calendar integration
- `idea` events: shown only to Programmers+, muted grey, dashed border
- `proposed`/`queued` events: shown to Programmers+, normal colour but with ⏳ indicator
- `confirmed` events: current behaviour
- `denied` events: hidden from all views (archive only)
- Public programme: only `confirmed` events (no change to current filter logic)

## Not in MVP

- Auto-populate programmer rota slot on approval (9.2 follow-up)
- Rota deadline warning (9.2 follow-up)
- Etiquette guide reminder on first event creation
- Finance referral hard-gate (guidance only, as per spec)
- Shift count display / volunteer history gate

## File changes

| File | Change |
|------|--------|
| `toolkit/diary/models.py` | Add `status`, `proposed_dates`, `status_notes`, `status_changed_at`, `status_changed_by` to Event |
| `toolkit/diary/migrations/` | New migration for new fields + data migration |
| `toolkit/diary/edit_views.py` | Queue view, approve/deny actions, status update endpoint |
| `toolkit/diary/urls.py` | `/diary/edit/queue/` route |
| `toolkit/diary/templates/edit_event_queue.html` | New queue template |
| `toolkit/diary/templates/edit_event_details_view.html` | Status section on Event Hub |
| `toolkit/diary/templates/edit_event_index.html` | Status indicators on list view |
| `toolkit/diary/templates/edit_event_calendar_index.html` | Status CSS classes |
| `toolkit/diary/static/diary/js/calendar_index.js` | Status-based event styling |
| `toolkit/diary/views.py` | Public programme filter (already filters confirmed — verify) |
| `docs/TASKS.md` | Nothing (spec is there) |
| `CURRENT_WORK.md` | Mark 9.2 as in-progress |
| `docs/SPEC.md` | Data model section 8 |
