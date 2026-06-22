# Star and Shadow Toolkit — Tasks Index

**Purpose:** Design rationale, system limitations, and feature specifications.

This file is the index. Full specs live in [`docs/tasks/`](tasks/) split by domain. Links to `docs/TASKS.md` continue to work; follow the table below to find a specific section.

**For work status and priorities:** [CURRENT_WORK.md](../CURRENT_WORK.md)

**Rule:** specs and rationale only — no ❌/✅ status markers. Status lives in CURRENT_WORK.md.

**Size key:** 🟢 XS (1–4h) · 🔵 S (4–16h) · 🟡 M (16–40h) · 🟠 L (40–80h) · 🔴 XL (80–160h) · ⛔ XXL (160h+)

---

## Domain files

| File | Contents |
|------|----------|
| [tasks/known-issues.md](tasks/known-issues.md) | Active bugs and section 8 current system limitations (8.1–8.16) |
| [tasks/events-and-rota.md](tasks/events-and-rota.md) | Programming pipeline, event creation, rota, room bookings, diary — sections 9.2 (events), 9.3, 9.7, 9.9–9.11, 9.14–9.15, 9.18, 9.21–9.23, 9.25–9.26, 9.29–9.36, 9.38–9.41, 9.43–9.44, 9.47–9.48, 9.52–9.55, 9.60–9.61, 9.66, 9.69, 9.71–9.73, 9.75–9.76, 9.91–9.92, 9.95, 9.108–9.116, 9.118–9.119, 9.122, 9.124–9.125 |
| [tasks/volunteers.md](tasks/volunteers.md) | Volunteer records, inductions, training, GDPR, accounts, pool management — sections 9.2 (rota/accounts), 9.4–9.6, 9.12–9.13, 9.24, 9.45, 9.50, 9.56, 9.86–9.87, 9.89, 9.93, 9.96, 9.99–9.100, 9.120–9.121, 9.123, 9.142 |
| [tasks/public-site.md](tasks/public-site.md) | Public programme, archive images, feeds, filter UI — sections 9.27–9.28, 9.37, 9.57–9.59, 9.62, 9.102–9.107, 9.130 |
| [tasks/operations.md](tasks/operations.md) | Community tools, donations, bulletins, lost & found, permission model, dashboard prefs, favourites, collectives — sections 9.49, 9.51, 9.68, 9.74, 9.78–9.80, 9.88, 9.90, 9.94, 9.101, 9.126–9.129 |
| [tasks/infrastructure.md](tasks/infrastructure.md) | Accessibility, test coverage, backup, Bootstrap migration — sections 9.16–9.17, 9.19–9.20, 9.42, 9.46, 9.70, 9.117 |

---

## Adding a new feature spec

Add it to the appropriate domain file above. Use the next available `9.X` number. Include a sizing label. Add a row to [CURRENT_WORK.md](../CURRENT_WORK.md) to track status.
