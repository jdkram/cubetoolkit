# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
"""
Logging wrapper around the real email backend (spec 9.154).

EMAIL_BACKEND points at LoggingEmailBackend; TOOLKIT_WRAPPED_EMAIL_BACKEND
carries the backend that actually delivers (console, filebased, smtp, ...).
Because it sits at the backend layer it sees every send in the codebase --
mailouts, password resets, digests, one-off notifications -- with no
call-site changes, and logs one line per message to the ``toolkit.email``
logger: success at INFO, failure at ERROR.

This is also the intended hook point for the SentEmailLog DB rows (9.156):
add the write alongside the log calls in send_messages, nothing else needs
restructuring.
"""
import logging

from django.conf import settings
from django.core.mail import get_connection
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger("toolkit.email")


class LoggingEmailBackend(BaseEmailBackend):
    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently)
        self.inner_backend_path = getattr(
            settings,
            "TOOLKIT_WRAPPED_EMAIL_BACKEND",
            "django.core.mail.backends.console.EmailBackend",
        )
        # The inner backend gets fail_silently=False so failures reach us as
        # exceptions; we log them, then honour our own fail_silently.
        self.inner = get_connection(
            backend=self.inner_backend_path, fail_silently=False, **kwargs
        )

    def open(self):
        return self.inner.open()

    def close(self):
        return self.inner.close()

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        sent_count = 0
        for message in email_messages:
            recipients = ", ".join(message.recipients())
            try:
                # One message per call so a failure is attributable to a
                # single message. The inner connection is reused if the
                # caller opened it (bulk sends open it explicitly).
                sent = self.inner.send_messages([message]) or 0
            except Exception as exc:
                logger.error(
                    "EMAIL FAILED to=[%s] subject=%r backend=%s error=%s",
                    recipients,
                    message.subject,
                    self.inner_backend_path,
                    exc,
                )
                if not self.fail_silently:
                    raise
                continue
            if sent:
                sent_count += sent
                logger.info(
                    "EMAIL SENT to=[%s] subject=%r backend=%s",
                    recipients,
                    message.subject,
                    self.inner_backend_path,
                )
            else:
                # Backends signal a swallowed per-message problem by
                # returning 0 without raising.
                logger.error(
                    "EMAIL NOT SENT to=[%s] subject=%r backend=%s "
                    "(backend reported 0 sent)",
                    recipients,
                    message.subject,
                    self.inner_backend_path,
                )
        return sent_count
