---
# Plan: Seed data and test improvements from live site data

**Source:** `~/code/sns-live-toolkit/sns_production.db` — SQLite dump of the Star and Shadow production database, examined 2026-03-26.

---

## What the live data tells us

### Scale
- **2,357 members**, all with emails, all with `membership_expires` set
- **2,102 expired** memberships (of 2,357 total) — this is the normal state
- **1,901 volunteers** (1,888 active, 13 inactive)
- **9,314 events**, **11,113 showings**, **39,091 rota entries**
- **56 event templates**, **109 roles**, **9 rooms**

### Distribution patterns that matter for testing
- Most events have 1 showing (7,304), but recurring events have many: "CAFE OPEN 12NOON-4PM EVERY SUNDAY" has 62, "FRIDAY CLEANING CLUB & BRUNCH SOCIAL" has 60
- 890 showings have **no room assigned** (room_id IS NULL)
- 2,012 events have **null or zero duration** (00:00:00)
- `RotaEntry.required` is always `True` in production — no optional slots observed
- `RotaEntry.name` is used for real volunteer names as free text (not a FK to Volunteer)
- Rota size varies enormously: 1–20+ entries per showing
- Member numbers are plain incrementing integers starting at 18, not prefixed strings

### Pricing is a mess (confirm 9.54 is real)
Production pricing strings include: `FREE`, `Free`, `free`, `£7/5`, `£7/£5`, `£7/£5/£3/£0`, `n/a`, `NA`, `No Pounds`, `£0`, `£5`, `£6/5`, `£6/£5`, `£7/£5/£3/FREE`. Case-insensitive match or normalisation is needed anywhere pricing is displayed or parsed.

### Terms are also messy
- 4,610 events have null terms
- 210 have empty string
- 60 use a "Contacts-\nCompany-\nAddress-\nEmail-\nPh No-\nHire Fee..." template (the live outside hire format)
- 4,434 have other free text

### EventTemplate set (production had 56, seed has ~10)
Key templates missing from seed: `Film (35mm)`, `Film (16mm)`, `Film (Stream)`, `Gig`, `Workshop`, `Talk`, `Conference`, `Cleaning Session`, `Café`, `Bar Training`, `Cafe Training`, `Volunteer Induction`, `Exhibition`, `Radio`, `Cabaret`. Several templates have **no roles at all** — the UI should handle this gracefully.

### Volunteer roles distribution
- Most volunteers: 1–3 roles (306/152/59)
- Some extremes: one volunteer with 45 roles, one with 20
- Top volunteer-profile roles: Front of House - Keyholder Assistant (204 vols), Cafe Level 1 (197), Usher - Fire Trained (180), Bar (156), Programmer (138), Fire safety warden (132)

---

## Seed data improvements

### 1. Recurring event (multi-showing)
**Priority: high.** The biggest gap. Add one recurring event — "Sunday Café" or "Friday Cleaning Club" — with 8–12 showings spread over future Sundays/Fridays, all same event entity. This exercises: diary list view (many rows for one event), clone-to-dates (9.21) when built, calendar rendering, rota inheritance.

### 2. Showing with no room
**Priority: high.** Add at least one showing with `room=None`. Exercises all views and templates that display room — calendar, diary list, rota. Several templates could crash or render "(None)" without a guard.

### 3. Event with null/zero duration
**Priority: medium.** Add one event with `duration=None`. The rota already has a guard (`if event.duration`), but the break-even calculator and calendar end-time display may not.

### 4. Members: realistic mix of expiry/GDPR/mailout states
Current seed likely creates all members with the same state. Should cover:
- Active member, current membership, gdpr_opt_in set, mailout=True ← the common case (85%)
- Expired member (membership_expires in past) ← 89% of live members are expired!
- Member with mailout=False (opted out)
- Member with mailout_failed=True (bounced email address)
- Member without gdpr_opt_in (null) — the pre-GDPR cohort
- Member with no membership_expires set (null) — pre-expiry-tracking cohort

### 5. More event templates
Add to TEMPLATES constant (or equivalent) in seed:
- `Film (35mm)` — with roles: Keyholder, Projectionist - 35mm, Box Office, Bar Staff, Usher
- `Gig` — Keyholder, Sound Technician level 3, Bar Staff × 2, Box Office, Usher
- `Workshop` — Keyholder, Facilitator, Extra Hands × 2
- `Talk` — Keyholder, Facilitator, Box Office
- `Cleaning Session` — Keyholder, Cleaner × 4, Extra Hands × 2
- `Café` — Keyholder, Cafe (Level 1) × 2, Cafe Shadowing
- `Empty template` — **no roles at all**, to exercise the empty-template code path

### 6. Outside hire terms template
Add an outside hire event whose `terms` field uses the live production format:
```
Contacts-
Company-
Address-
Email-
Ph No-
Hire Fee (inclusive of VAT, if applicable)-
```
This exercises the terms display in Event Hub and any future structured terms parsing (9.54).

### 7. Inactive volunteer
Add at least one `Volunteer` with `active=False`. The volunteer list view, rota assignment, and any "active volunteers only" filters should handle this.

### 8. Event without copy (no description)
Add one event where `copy` is None/blank and `copy_summary` is also blank. Several views fall back gracefully, but this should be covered in seed so it's obvious in the dev UI.

### 9. Rota entry with name filled in
The `RotaEntry.name` field is used in production to record who filled a slot (free-text, not a FK). Seed should include at least one showing where some rota slots have `name` populated (simulating a partially-filled rota).

---

## New / missing tests

### Diary models

**A. `Event` with null duration**
```python
# test_models.py
def test_event_with_null_duration_does_not_crash_end_time():
    event = Event.objects.create(name="No Duration", duration=None, ...)
    showing = Showing.objects.create(event=event, start=datetime(...))
    # Assert that accessing showing.end (or however end time is computed) returns None, not crash
```

**B. `Showing.room` is None**
```python
def test_showing_without_room_is_valid():
    showing = Showing(event=event, room=None, start=datetime(...))
    showing.full_clean()  # should not raise
```

### Diary views

**C. Diary list view with multi-showing event**
`test_edit_views.py` — create one event with 5+ showings and assert the list view renders all rows. Exercises the `rooms` / blank-day logic that had a None sentinel bug (9.42).

**D. Calendar view with no-room showing**
Create a showing with `room=None`, GET the calendar JSON or HTML, assert no 500 and the showing appears (or is gracefully skipped).

**E. Public programme with null-duration event**
GET `/programme/` with an event that has no duration — assert no 500, no end-time shown.

**F. Rota view with no-room showing**
GET the rota for a date that has a showing with `room=None` — assert the page renders.

### Members

**G. Expired member queryset**
```python
def test_expired_members_queryset():
    # Create member with membership_expires = yesterday
    m = Member.objects.create(..., membership_expires=date.today() - timedelta(days=1))
    assert m in Member.objects.expired()
    assert m not in Member.objects.active_members()
```

**H. Mailout queryset excludes mailout_failed**
```python
def test_mailout_queryset_excludes_failed():
    m = Member.objects.create(..., mailout=True, mailout_failed=True)
    assert m not in Member.objects.mailout_recipients()
```

**I. GDPR opt-in state**
```python
def test_gdpr_opt_in_null_member_valid():
    m = Member(name="Pre-GDPR", email="old@example.com", gdpr_opt_in=None)
    m.full_clean()  # should not raise
```

**J. `Member.number` generation from pk**
Confirm the member number equals `str(pk)` after first save, not a prefixed string.

### EventTemplate edge cases

**K. Template with no roles**
Create an `EventTemplate` with no `EventTemplateRole` entries. Call `Event.__init__` with that template. Assert it creates an event with an empty rota (no crash, no phantom roles).

**L. Template with role count > 1**
Verify that `EventTemplateRole.count` (if it exists in the new schema) correctly creates N rota entries when applied to a new event.

### Pricing edge cases

**M. Break-even calculator with unusual pricing strings**
If any Python code parses the `pricing` field (break-even is JS-only currently, but future 9.54 work will parse), add tests covering: `FREE`, `free`, `£7/5`, `£7/£5`, `n/a`, empty string.

### Mailout / copy sanitisation

**N. Event copy with `&` in title**
The `copy_html` property sanitises via nh3. Test that `&` in event name or copy round-trips correctly through the mailout template without double-encoding.

---

## Potential bugs the live data reveals

### B1. Pricing display inconsistency (confirmed real)
The break-even calculator has a "door price" field. If a programmer copies the pricing string from the event ("£7/£5/£3/FREE"), the calculator will fail to parse it. Task 9.54 (structured cost terms) addresses this, but until then, the calculator's door-price input should be freeform, not a number input.

**Risk:** Currently `type="number"` on the door price input would reject "£7/£5". Check the HTML.

### B2. Showing without room crashes calendar
`edit_event_calendar_index.html` passes rooms to FullCalendar. If a showing has `room=None`, the calendar segment's `resourceId` will be null — FullCalendar may silently drop it or throw a JS error. **The 890 production null-room showings mean this has been hit.**

Test by seeding a null-room showing and loading the calendar.

### B3. Duration 00:00:00 vs NULL
Events exported from the old system may have `duration='00:00:00'` (falsy in Python as timedelta(0)) vs `None`. The guard `if event.duration` already handles this in the rota template, but check:
- `edit_event_calendar_index.html` — end time calculation
- Any future "show end time in programme" feature
- The break-even calculator duration field

### B4. Recurring event in diary list: same-name collision
If an event named "Sunday Café" has 50 showings, the diary edit list will show 50 rows with the name "Sunday Café". This is correct but visually overwhelming. No crash, but a UX issue worth flagging in TASKS.md (9.34 "Showing" terminology is related).

### B5. `RotaEntry.name` → volunteer display
In production, `RotaEntry.name` stores a real human name. In the dev build, rota entries are seeded with `name=""`. The rota view shows this field as the "who has this slot" display. Confirm the template handles empty string correctly (renders "—" or nothing, not an empty `<span>`).

### B6. Member number as integer string
Live member numbers are `"18"`, `"19"`, etc. — plain integers as strings. Code that treats member numbers as strings (search, display) is fine. Code that tries to parse them as ints or prefix them ("M" + number) would break on import. The current `_generate_membership_number` uses `str(pk)` — consistent with live data.

### B7. EventTemplate with no roles (empty template)
If a programmer selects an "empty" template when creating an event, `reset_rota_to_default()` will produce no rota entries. The rota will be blank. This is valid but the UI should not show a "Rota is empty" error state as a bug — it's intentional for certain template types.

### B8. `mailout=True` but `gdpr_opt_in=None`
2,023 members have mailout=True, but some may have gdpr_opt_in=None (pre-GDPR cohort). If any view or export enforces GDPR opt-in as a hard gate for mailout, these members would be silently excluded. Confirm the mailout queryset behaviour matches the intended policy.

---

## Prioritised action list

| # | Item | Size | Notes |
|---|------|------|-------|
| S1 | Add recurring event (8–12 showings) to seed | 🟢 XS | Most impactful gap |
| S2 | Add null-room showing to seed | 🟢 XS | 890 in prod, zero in seed |
| S3 | Add members with varied expiry/GDPR/mailout states | 🟢 XS | 6 member variants |
| S4 | Add inactive volunteer to seed | 🟢 XS | 1 line change |
| S5 | Add 6 missing event templates with roles | 🔵 S | Film 35mm, Gig, Workshop, Talk, Cleaning, Café |
| S6 | Add outside hire terms template event | 🟢 XS | Copy from prod format |
| T1 | Test expired members queryset | 🟢 XS | test_models.py |
| T2 | Test mailout_failed excluded from mailout queryset | 🟢 XS | test_models.py |
| T3 | Test showing with null room renders without crash | 🟢 XS | 3 view tests |
| T4 | Test multi-showing event in diary list | 🟢 XS | test_edit_views.py |
| T5 | Test EventTemplate with no roles | 🟢 XS | test_models.py |
| T6 | Test null-duration event in public programme | 🟢 XS | test_public_views.py |
| B1 | Check break-even door-price input type | 🟢 XS | May already be text |
| B2 | Investigate null-room showing in calendar | 🔵 S | JS + view |

---

*Written 2026-03-26. Based on direct inspection of `sns_production.db`.*
