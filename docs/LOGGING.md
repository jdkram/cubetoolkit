---
human-contributors: ["Jonny Kram"]
ai-contributors: ["Claude"]
status: "#ai-written"
---

# Logging

What the toolkit writes to its logs, where to find them, and what you can and can't expect to see there. Covers the changes shipped 2026-07-14 (specs 9.154, 9.155, 9.157, 9.158 — see [tasks/infrastructure.md](tasks/infrastructure.md)).

## Where logs live

All application logging goes to stderr, which Docker captures per container. There is no log file inside the container (the Docker settings files remove the file handler). To read logs:

```bash
docker compose logs toolkit          # web app
docker compose logs mailer           # mailout daemon
docker compose logs scheduler        # daily maintenance jobs
docker compose logs -f --tail 100 toolkit   # follow live
```

Every service is capped at 3 files × 10MB of JSON logs (set per service in the compose files), so a container holds roughly the most recent 30MB of output. Older lines are gone; anything that must survive belongs in the database (see "Gaps" below).

## Log format and levels

Lines look like:

```
[14/Jul/2026 19:46:09] INFO [toolkit.email:69] EMAIL SENT to=[someone@example.com] subject='Welcome' backend=django.core.mail.backends.console.EmailBackend
```

That is timestamp, level, logger name and line number, message.

- Everything under the `toolkit.*` logger hierarchy is emitted at DEBUG and above, in every environment.
- The root logger (framework noise, third-party libraries) is DEBUG in dev and WARNING in production, so a stray `logging.info(...)` call would vanish in production. Always log via a module logger (`logger = logging.getLogger(__name__)`); this exact mistake silently discarded showing-deletion logs until 2026-07-14 (Bug AQ).

## Email logging

Every email the toolkit attempts to send, from any code path (mailouts, password resets, digests, notifications), passes through a logging wrapper (`toolkit/util/email_backend.py`) and produces exactly one line under the `toolkit.email` logger:

| Line | Level | Meaning |
|---|---|---|
| `EMAIL SENT to=[...] subject=... backend=...` | INFO | The configured backend accepted the message |
| `EMAIL FAILED to=[...] subject=... error=...` | ERROR | The backend raised; the error text is included |
| `EMAIL NOT SENT to=[...] (backend reported 0 sent)` | ERROR | The backend declined without raising |

Two things to understand about these lines:

- **"Sent" means handed to the backend.** With the console backend (dev and, currently, production) nothing is actually delivered — the full message is printed to the container log just below the `EMAIL SENT` line. Only with a real SMTP backend does SENT mean "accepted by the mail server", and even then delivery to the inbox is not guaranteed.
- **Bodies are never in the log line.** Recipients, subject, and backend only. This is deliberate: bodies contain personal content and live password-set links. The console backend does print full bodies as its normal output, so treat log access as privileged.

The real backend is set by `TOOLKIT_WRAPPED_EMAIL_BACKEND` in the settings file; `EMAIL_BACKEND` always points at the wrapper.

### What users see when email fails

Notification emails no longer fail silently or crash the page. If an email fails during a volunteer save, suspension, or last-gasp send, the operation still completes and the page shows a warning ("Saved, but the notification email failed to send..."), while the ERROR line above lands in the log. Bulk last-gasp sends continue past individual failures and report a failure count; failed recipients keep no cooldown, so they can be retried.

### Mailouts

The mailout pipeline logs its job lifecycle under `toolkit.mailer.*`, and each recipient send produces a `toolkit.email` line in the `mailer` container's log. The authoritative record of a mailout is the `MailoutJob` row itself (state, progress, send count), visible in the mailout UI — use that, not the logs, to answer "did the mailout run?".

## Scheduler

The `scheduler` container prints one line per job run:

```
[2026-07-14 03:00] [auto_dormancy] starting
[2026-07-14 03:00] [auto_dormancy] done
```

A failed job logs `FAILED (exit N)` and the loop carries on. The schedule itself is printed at container start. The scheduler also purges the file-based email archive (`/log/emails`, where configured) of files older than 60 days.

## What is NOT in the logs

- **Deletions, reliably.** Showing deletions now log correctly (INFO, with showing and event ids), but there is no attribution of *who* deleted, and the line dies with the container log rotation. A durable deletion audit trail is spec'd as 9.159.
- **A queryable email history.** The `toolkit.email` lines rotate away like everything else. A `SentEmailLog` database table with a Panopticon page is spec'd as 9.156.
- **Email bodies** (see above), except as console-backend output.
- **Admin error emails.** The old `mail_admins` handler was dead config (no logger attached, empty `ADMINS`) and was removed; revisit once a real SMTP relay exists.

## Security note

Sent emails include password-set links that stay live for up to 7 days (`PASSWORD_RESET_TIMEOUT`) unless used. The log lines never contain them, but console-backend output and the file archive do. Anyone with `docker logs` or archive access effectively holds every unexpired reset link, so server access is the security boundary — do not widen access to logs or the archive (e.g. over HTTP) without stripping bodies. Fuller analysis in [tasks/infrastructure.md](tasks/infrastructure.md), spec 9.155.
