# Induction tracking (9.4) — unreleased

Feature is gated by `InductionsSettings.inductions_enabled`. Base URL is `/inductions/`.

- [x] `inductions_enabled` toggle in InductionsSettings: with it off, inductions links absent from nav; with it on, links appear
  RESULT: Good. One note: "Enable the inductions sign-up workflow. When off, all public induction URLs return 404." please expand this to say "If you're handling Inductions signups through another route (e.g. Google Forms) then you'll want to check this box."

- [x] Panopticon: create a new induction session at `/inductions/manage/new/`; session appears in session list
  FIXED: Template syntax error (unclosed `{% block body %}`) was already corrected in `inductions/manage/session_form.html` — template loads cleanly now.
  RESULT (re-test needed): Page should load at `/inductions/manage/new/` without error.
  ```
  [HISTORICAL ERROR — now fixed]
  TemplateSyntaxError at /inductions/manage/new/

Unclosed tag on line 4: 'block'. Looking for one of: endblock.

Request Method: 	GET
Request URL: 	http://localhost:8000/inductions/manage/new/
Django Version: 	5.2.14
Exception Type: 	TemplateSyntaxError
Exception Value: 	

Unclosed tag on line 4: 'block'. Looking for one of: endblock.

Exception Location: 	/venv/lib/python3.11/site-packages/django/template/base.py, line 591, in unclosed_block_tag
Raised during: 	toolkit.inductions.views.manage_session_new
Python Executable: 	/venv/bin/python3
Python Version: 	3.11.2
Python Path: 	

['/site',
 '/usr/lib/python311.zip',
 '/usr/lib/python3.11',
 '/usr/lib/python3.11/lib-dynload',
 '/venv/lib/python3.11/site-packages']

Server time: 	Mon, 22 Jun 2026 10:37:28 +0100
```

- [ ] Public sign-up URL for the session works; submit the form; signup appears in the session manage view
  RESULT:

- [ ] Check-in page (`/inductions/manage/<slug>/`): AJAX check-in marks attendee as confirmed without page reload
  RESULT:

- [ ] "Create volunteer accounts" from the manage page creates `Member` + `Volunteer` records for checked-in attendees
  RESULT:

- [ ] CSV export (`export.csv`) downloads; columns match Simplelists format (first name, last name, email — no headers)
  RESULT:

- [ ] Access-needs request (`/inductions/access-needs/`) submits; appears in `/inductions/manage/access-needs/` queue
  RESULT:

- [ ] `send_induction_reminders` management command runs without error
  RESULT:

- [ ] `purge_induction_signups` management command runs without error; signups older than configured days are removed
  RESULT:

**Feedback from testing:**
- Marking someone as "no show" can't be undone — make it toggleable.
- Support setting a max number of signups per session, with a global default in SiteSettings.
- Allow inductors to quickly register someone on the spot.
- Sign-up form should link to the GDPR policy and ask for consent to store their info.
- Sign-up form should separate first/last names, and let inductees pick how their name appears on the rota (default: First name + first letter of surname).


http://localhost:8000/volunteers/view/summary/

There are links at the top of this page which aren't comprehensive: qualifications and directory should be there too. Or maybe let's ditch all the links, it's just another place to maintain them outside of the nav.

The Induction Settings page is not visible in the nav bar - please add it, after the main Site Settings page.