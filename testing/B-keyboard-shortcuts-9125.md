# Keyboard shortcuts + power-user UI (9.125) — unreleased

---

## g-key global navigation (admin)

- [ ] On any admin page, press `g` — nav badges (yellow, monospace letter) appear next to navbar links. Font is readable.
  RESULT:

- [ ] Press a badged letter (e.g. `d` for Diary) — navigates correctly. Pressing an unregistered letter exits nav mode without navigating.
  RESULT:

- [ ] `g → n` (Noticeboard or another submenu) — Bootstrap dropdown opens, sub-items get badges. Press a sub-item letter to navigate; press a non-letter to close without navigating.
  RESULT:

- [ ] Pressing `g` twice exits nav mode without navigating.
  RESULT:

- [ ] Pressing `Esc` in nav mode or sub-nav mode exits cleanly; no stuck badges.
  RESULT:

---

## ? help modal (admin)

- [ ] On the diary list — press `?`. Modal opens titled "Keyboard shortcuts". GLOBAL NAVIGATION section shows `g`, `g → letter`, `Esc`. DIARY section shows `/`, `n`, `{ / }`, `F`.
  RESULT:

- [ ] On the event hub — `?` opens modal with EVENT HUB section (`e`, `b`, `r`, `j/k`, `Enter`).
  RESULT:

- [ ] On the volunteer list — `?` opens modal with VOLUNTEER LIST section.
  RESULT:

- [ ] On the programming queue — `?` shows PROGRAMMING QUEUE section.
  RESULT:

- [ ] On the calendar — `?` shows CALENDAR section (`{ / }`, `t`, `n`, `/`).
  RESULT:

- [ ] On the new event form — `?` shows NEW EVENT section (`Ctrl+Enter`, `Esc`).
  RESULT:

- [ ] Key labels inside the modal are visible (dark text on light-grey background). No blank boxes.
  RESULT:

- [ ] Modal closes with `Esc`. Modal closes with the × button. Clicking the backdrop closes it.
  RESULT:

- [ ] On the rota edit page — `?` opens the rota's own elaborate modal (not the global one).
  RESULT:

---

## ? help modal (public)

- [ ] On `http://localhost:8000/` (public homepage), press `?` — a help modal appears showing NAVIGATION and HELP sections. Key labels visible.
  RESULT:

- [ ] Modal closes with `Esc` and with the × button.
  RESULT:

---

## Command palette (Ctrl+K / Ctrl+/)

- [ ] On any admin page, press `Ctrl+K` — command palette opens with a search input and all commands listed.
  RESULT:

- [ ] Press `Ctrl+/` — same palette opens (alternative trigger with no browser conflict).
  RESULT:

- [ ] Type a partial name (e.g. "rot") — results filter to matching commands. Arrow keys move selection. Enter navigates.
  RESULT:

- [ ] Multi-token search: type "new eve" — "New event" result appears.
  RESULT:

- [ ] `Esc`, `Tab`, or clicking the backdrop closes the palette without navigating.
  RESULT:

- [ ] Results are grouped by category (Navigate, Website, Community, Meta, People, Actions). Permission-gated commands absent for lower-tier users (log in as `programmer` and check People commands are not shown).
  RESULT:

- [ ] The `⌘K` navbar button opens the palette on click.
  RESULT:

---

## Page-level shortcuts

- [x] Diary list: `/` focuses the filter input. `n` navigates to new event. `{`/`}` scroll to previous/next month. `F` toggles full width. `Esc` (while filter is focused) clears filter and blurs.
  RESULT: good. Is there any way we can make the scroll to the month leave the month name visible at the top of the page? is it is we scroll to the row that's the 1st of that month, but that omits the key information the user needs.
  Can we please add `j` / `k` to navigate through all events, limiting to those which are visible within the filter? they should highlight them the way tabbing through links on a page does generally, letting them press enter to open the details

- [x] Diary list: filter input does NOT have autofocus on page load (keyboard shortcuts work immediately without clicking away).
  RESULT: good

- [x] Volunteer list: `j`/`k` navigate cards (blue outline appears). `o`/`Enter` opens selected card. `/` focuses filter. `n` navigates to add volunteer.
  RESULT: fail - j and k don't do anything I can see. No keyboard shortcuts are working specifically at `http://localhost:8000/volunteers/view/summary/` - but the general ones (`g` and `?`) work ok

- [x] Calendar: `{`/`}` go to previous/next period. `t` jumps to today. `n` navigates to new event. `/` focuses the name search input.
  RESULT: good. Can we add something easier than curly braces? look at the other shortcuts and see if there's something more ergonomic we can add that's inkeeping with the design on other pages (would `j`/`k` work well here? though if we ever added "page through events in the calendar we'd want to assign those to that... hmm)

- [x] New event form: `Ctrl+Enter` submits the form. `Esc` (when not in an input) navigates to cancel URL.
  RESULT: good

- [x] All page-level shortcuts are inert when the cursor is inside a text input or textarea.
  RESULT: good

**Feedback:** Change calendar navigation from `{`/`}` to `[`/`]` (no shift key) or `j`/`k`. Add shortcuts for the calendar view modes: month, week, 3 days, week (rooms), month (rooms).

---

## Filter state persistence

- [x] Type a filter on the diary list, navigate away, return — filter text is restored (sessionStorage).
  RESULT: good (but is this desired behaviour? I feel like users would actually expect the filter to be cleared)

- [x] Clear the filter with `Esc` on the diary list, navigate away, return — filter is empty (clear was persisted).
  RESULT: good

- [x] Type a filter on the volunteer list, navigate away, return — filter text is restored.
  RESULT: bad - there is no filter

**Nerd request:** Support regex in search boxes across the site.
