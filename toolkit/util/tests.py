# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
"""Tests for the LoggingEmailBackend wrapper (9.154)."""
from django.core import mail
from django.core.mail import send_mail
from django.core.mail.backends.base import BaseEmailBackend
from django.test import SimpleTestCase, override_settings


class FailingBackend(BaseEmailBackend):
    """Raises on every send. Referenced by dotted path in override_settings."""

    def send_messages(self, email_messages):
        raise ConnectionRefusedError("SMTP server said no")


class ZeroSendBackend(BaseEmailBackend):
    """Reports nothing sent without raising, as smtp does for refused recipients."""

    def send_messages(self, email_messages):
        return 0


WRAPPER = "toolkit.util.email_backend.LoggingEmailBackend"
LOCMEM = "django.core.mail.backends.locmem.EmailBackend"


@override_settings(EMAIL_BACKEND=WRAPPER)
class LoggingEmailBackendTests(SimpleTestCase):
    @override_settings(TOOLKIT_WRAPPED_EMAIL_BACKEND=LOCMEM)
    def test_success_delegates_to_inner_backend_and_logs(self):
        with self.assertLogs("toolkit.email", "INFO") as logs:
            sent = send_mail(
                "Test subject", "body", "from@example.com", ["to@example.com"]
            )
        self.assertEqual(sent, 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Test subject")
        self.assertEqual(len(logs.output), 1)
        self.assertIn("EMAIL SENT", logs.output[0])
        self.assertIn("to@example.com", logs.output[0])
        self.assertIn("Test subject", logs.output[0])
        self.assertIn(LOCMEM, logs.output[0])

    @override_settings(TOOLKIT_WRAPPED_EMAIL_BACKEND=LOCMEM)
    def test_one_log_line_per_message(self):
        messages = [
            mail.EmailMessage("Subject one", "body", "from@example.com", ["a@example.com"]),
            mail.EmailMessage("Subject two", "body", "from@example.com", ["b@example.com"]),
        ]
        with self.assertLogs("toolkit.email", "INFO") as logs:
            sent = mail.get_connection().send_messages(messages)
        self.assertEqual(sent, 2)
        self.assertEqual(len(logs.output), 2)
        self.assertIn("a@example.com", logs.output[0])
        self.assertIn("b@example.com", logs.output[1])

    @override_settings(
        TOOLKIT_WRAPPED_EMAIL_BACKEND="toolkit.util.tests.FailingBackend"
    )
    def test_failure_logs_error_and_reraises(self):
        with self.assertLogs("toolkit.email", "ERROR") as logs:
            with self.assertRaises(ConnectionRefusedError):
                send_mail(
                    "Doomed", "body", "from@example.com", ["to@example.com"]
                )
        self.assertIn("EMAIL FAILED", logs.output[0])
        self.assertIn("to@example.com", logs.output[0])
        self.assertIn("SMTP server said no", logs.output[0])

    @override_settings(
        TOOLKIT_WRAPPED_EMAIL_BACKEND="toolkit.util.tests.FailingBackend"
    )
    def test_failure_with_fail_silently_logs_error_and_swallows(self):
        with self.assertLogs("toolkit.email", "ERROR") as logs:
            sent = send_mail(
                "Doomed",
                "body",
                "from@example.com",
                ["to@example.com"],
                fail_silently=True,
            )
        self.assertEqual(sent, 0)
        self.assertIn("EMAIL FAILED", logs.output[0])

    @override_settings(
        TOOLKIT_WRAPPED_EMAIL_BACKEND="toolkit.util.tests.ZeroSendBackend"
    )
    def test_zero_sent_without_exception_logs_error(self):
        with self.assertLogs("toolkit.email", "ERROR") as logs:
            sent = send_mail(
                "Refused", "body", "from@example.com", ["to@example.com"]
            )
        self.assertEqual(sent, 0)
        self.assertIn("EMAIL NOT SENT", logs.output[0])
