# Calendar View Fixes — Implementation Plan

## Overview

Fix two critical issues with the calendar edit view at `/diary/edit/calendar/`:

1. **Bug M — Overlapping Events**: Simultaneous events overwrite each other on busy days
2. **Mobile Failures**: Calendar view fails entirely on mobile devices

---

## Issue 1: Overlapping Events (Bug M)

### Current Behaviour

On days with 6+ events scheduled at the same time, FullCalendar 3 renders later events on top of earlier ones rather than shrinking and tiling them side-by-side. The result is that some events become completely hidden and unreachable from the calendar view.

### Root Cause Analysis

1. The [`Showing.end_time`](toolkit/diary/models.py:617) property returns `self.start` when `event.duration` is `None`
2. Events without duration have identical start and end timestamps
3. FullCalendar's column-based layout is not triggered when events share the same time
4. The [`edit_diary_data`](toolkit/diary/edit_views.py:213) endpoint already returns `end` timestamps (line 280), but they're identical to `start` for events without duration

### Implementation Approach

#### Option 1: Add Default Duration (Recommended)

**File:** [`toolkit/diary/models.py`](toolkit/diary/models.py:617)

Modify the `end_time` property to apply a default duration when `event.duration` is `None`:

```python
@property
def end_time(self):
    # Used by templates and calendar JSON
    duration = self.event.duration
    if duration is None:
        # Apply default 2-hour duration for events without explicit duration
        # This ensures FullCalendar can detect overlaps and tile events properly
        return self.start + datetime.timedelta(hours=2)
    return self.start + datetime.timedelta(
        hours=duration.hour, minutes=duration.minute
    )
```

**Pros:**
- Simple one-line change
- Fixes the overlapping issue immediately
- No changes needed to FullCalendar configuration
- Events become clickable on busy days

**Cons:**
- Default duration may not match actual event length
- Events without duration will appear longer than they are

**Mitigation:**
- Add a comment explaining the default duration
- Consider adding a setting for default duration (e.g., `CALENDAR_DEFAULT_DURATION_HOURS`)

#### Option 2: FullCalendar Configuration Changes

**File:** [`toolkit/diary/static/diary/js/calendar_index.js`](toolkit/diary/static/diary/js/calendar_index.js:115)

Add FullCalendar options to improve overlap handling:

```javascript
var calendar_options = {
    // ... existing options ...
    slotEventOverlap: false,  // Force events into separate columns
    slotLabelInterval: '00:30:00',  // Show 30-minute slot labels
    minTime: '00:00:00',
    maxTime: '23:59:59',
    slotDuration: '00:15:00',  // 15-minute slots
    // ... rest of options ...
};
```

**Pros:**
- More granular control over calendar layout
- Doesn't change data model

**Cons:**
- More complex configuration
- May not fully solve the issue without proper end times
- Events with identical start/end will still overlap

**Recommendation:** Implement Option 1 first (default duration), then add Option 2 configuration if needed.

---

## Issue 2: Mobile Failures

### Current Behaviour

The calendar view "fails entirely on mobile devices." The exact failure mode needs investigation, but likely causes include:

1. FullCalendar 3.x has limited mobile support
2. Calendar container doesn't resize properly on mobile
3. Navbar interferes with calendar rendering
4. Touch events not properly handled

### Root Cause Analysis

Current mobile CSS in [`edit_event_calendar_index.html`](toolkit/diary/templates/edit_event_calendar_index.html:107):

```css
@media (max-width: 800px) {
    #controls {
        flex: 1 1 100%;
        order: -1;
        position: static;
        max-height: none;
    }
}
```

This only stacks the controls above the calendar but doesn't address:
- Calendar container width/height on mobile
- FullCalendar responsive behavior
- Touch event handling

### Implementation Approach

#### Step 1: Add Mobile-Specific CSS

**File:** [`toolkit/diary/templates/edit_event_calendar_index.html`](toolkit/diary/templates/edit_event_calendar_index.html:13)

Add comprehensive mobile CSS:

```css
/* Mobile: calendar container fixes */
@media (max-width: 768px) {
    #calendar-container {
        flex: 1 1 100%;
        min-width: 0;
        overflow-x: auto;
    }

    #calendar {
        min-width: 100%;
        width: 100%;
    }

    /* Reduce padding on mobile */
    body {
        padding: 4rem 0.5rem 1rem 0.5rem !important;
    }

    /* Make calendar touch-friendly */
    .fc-event {
        min-height: 30px;  /* Larger touch targets */
    }

    /* Hide resource area on mobile to save space */
    .fc-resource-area {
        display: none;
    }

    /* Use month view by default on mobile */
    .fc-agendaWeek-view,
    .fc-agendaThreeDay-view,
    .fc-timelineMonth-view {
        display: none;
    }
}

/* Extra small screens */
@media (max-width: 480px) {
    #calendar .fc-toolbar {
        flex-direction: column;
    }

    #calendar .fc-center {
        margin: 0.5rem 0;
    }

    #calendar .fc-right {
        margin-top: 0.5rem;
    }
}
```

#### Step 2: Add Mobile View Detection

**File:** [`toolkit/diary/static/diary/js/calendar_index.js`](toolkit/diary/static/diary/js/calendar_index.js:111)

Add mobile detection and default view switching:

```javascript
function init_calendar() {
    var calendar = $('#calendar');
    currentDate = $.fullCalendar.moment(defaultDate);

    // Detect mobile and set default view
    var isMobile = window.innerWidth <= 768;
    var mobileDefaultView = isMobile ? 'month' : defaultView;

    var calendar_options = {
        header: {
            left: 'prev,next today',
            center: 'title',
            right:
                (resources_enabled && !isMobile ?
                    'agendaThreeDay,agendaWeek,month,timelineMonth'
                    : (resources_enabled ? 'month,timelineMonth' : 'month'))
        },
        // ... existing options ...
        defaultView: mobileDefaultView,
        // ... rest of options ...
    };
    // ... rest of function ...
}
```

#### Step 3: Add Window Resize Handler

**File:** [`toolkit/diary/static/diary/js/calendar_index.js`](toolkit/diary/static/diary/js/calendar_index.js:188)

Add resize handler to re-render calendar on orientation change:

```javascript
$(document).ready(function() {
    init_calendar();

    // Re-render calendar on resize to handle orientation changes
    var resizeTimer;
    $(window).on('resize', function() {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(function() {
            $('#calendar').fullCalendar('render');
        }, 250);  // Debounce to avoid excessive re-renders
    });
});
```

#### Step 4: Add Touch Event Support

**File:** [`toolkit/diary/static/diary/js/calendar_index.js`](toolkit/diary/static/diary/js/calendar_index.js:115)

Add FullCalendar options for better touch support:

```javascript
var calendar_options = {
    // ... existing options ...
    longPressDelay: 500,  // Distinguish tap from long press
    eventLongPressDelay: 500,
    selectLongPressDelay: 500,
    // ... rest of options ...
};
```

---

## Implementation Order

1. **Fix overlapping events (Bug M)** — Priority 1
   - Modify `Showing.end_time` property to add default duration
   - Test on busy days in seed data

2. **Add mobile CSS** — Priority 2
   - Add mobile-specific styles to `edit_event_calendar_index.html`
   - Test on actual mobile devices or browser dev tools

3. **Add mobile view detection** — Priority 3
   - Modify `calendar_index.js` to detect mobile and switch to month view
   - Test view switching on resize

4. **Add resize handler** — Priority 4
   - Add window resize listener with debouncing
   - Test orientation changes

5. **Add touch event support** — Priority 5
   - Add FullCalendar touch options
   - Test tap vs long press behavior

---

## Testing Plan

### Overlapping Events

1. Navigate to `/diary/edit/calendar/`
2. Find a busy day (seed data has busy days at +35, +70, +105 days from today)
3. Verify all events are visible and clickable
4. Verify events are tiled side-by-side, not overlapping
5. Verify clicking any event navigates to the Event Hub

### Mobile

1. Use browser dev tools to simulate mobile viewport (375x667, iPhone SE)
2. Verify calendar renders without errors
3. Verify month view is default on mobile
4. Verify events are clickable with touch
5. Test orientation change (portrait ↔ landscape)
6. Verify calendar re-renders correctly after orientation change
7. Test on actual mobile device if possible

---

## Files to Modify

1. [`toolkit/diary/models.py`](toolkit/diary/models.py:617) — `Showing.end_time` property
2. [`toolkit/diary/templates/edit_event_calendar_index.html`](toolkit/diary/templates/edit_event_calendar_index.html:13) — Mobile CSS
3. [`toolkit/diary/static/diary/js/calendar_index.js`](toolkit/diary/static/diary/js/calendar_index.js:111) — Mobile detection and resize handler

---

## Related Issues

- **Bug J** — Calendar broken by jQuery 3.5 htmlPrefilter (already fixed)
- **9.41** — Clickable legend room filter (future enhancement)
- **FullCalendar 3 → 6 upgrade** — Long-term solution (🔴 XL effort)

---

## Notes

- FullCalendar 3.x is from 2017 and has limited mobile support
- A full upgrade to FullCalendar 6.x would provide better mobile support but is a large effort (🔴 XL)
- The fixes in this plan are pragmatic workarounds for the current FullCalendar 3.x version
- Consider FullCalendar 6.x upgrade as a future Phase 2 or Phase 3 task
