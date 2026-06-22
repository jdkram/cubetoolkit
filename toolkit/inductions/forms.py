# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
import json

from django import forms
from django.utils import timezone

from .models import InductionRequest, InductionSession, InductionsSettings


class SignupForm(forms.Form):
    """Public sign-up form for an induction session."""

    name = forms.CharField(max_length=200, label="Your name")
    email = forms.EmailField(label="Email address")

    def __init__(self, *args, session=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = session
        if session:
            for q in session.custom_questions:
                label = q.get("label", "")
                required = q.get("required", False)
                field_name = f"q_{_question_key(label)}"
                qtype = q.get("type", "text")
                if qtype == "checkbox":
                    self.fields[field_name] = forms.BooleanField(
                        label=label, required=required,
                    )
                elif qtype == "select":
                    options = q.get("options", [])
                    choices = [("", "— please select —")] + [(o, o) for o in options]
                    self.fields[field_name] = forms.ChoiceField(
                        label=label, choices=choices, required=required,
                    )
                else:
                    self.fields[field_name] = forms.CharField(
                        label=label, required=required, max_length=500,
                    )

    def get_custom_responses(self):
        """Return {question label: answer} dict for saving to InductionSignup."""
        responses = {}
        if not self.session:
            return responses
        for q in self.session.custom_questions:
            label = q.get("label", "")
            field_name = f"q_{_question_key(label)}"
            responses[label] = self.cleaned_data.get(field_name, "")
        return responses


class AccessNeedsForm(forms.Form):
    """Public form for the 1:1 access-needs induction request queue."""

    name = forms.CharField(max_length=200, label="Your name")
    email = forms.EmailField(label="Email address")
    access_needs = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4}),
        label="Access needs or requirements",
        help_text=(
            "Tell us what would help make your induction work well for you — "
            "e.g. BSL interpretation, quiet environment, step-free access, "
            "extra time, a particular format."
        ),
    )
    rough_availability = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Rough availability",
        help_text="When would generally suit you? e.g. weekday evenings, weekend afternoons.",
        required=False,
    )


class InductionSessionForm(forms.ModelForm):
    """Panopticon form for creating/editing an induction session."""

    class Meta:
        model = InductionSession
        fields = [
            "title", "session_type", "date", "location",
            "linked_event", "status", "purge_after",
        ]
        widgets = {
            "date": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "purge_after": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["date"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["purge_after"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["linked_event"].required = False
        self.fields["location"].required = False

        # Pre-fill purge_after default for new sessions
        if not self.instance.pk:
            cfg = InductionsSettings.load()
            self.fields["purge_after"].initial = (
                timezone.now() + timezone.timedelta(days=cfg.induction_purge_days + 7)
            )


class InductionsSettingsForm(forms.ModelForm):
    class Meta:
        model = InductionsSettings
        fields = [
            "inductions_enabled",
            "induction_purge_days",
            "organiser_notification_email",
            "welcome_pack_url",
            "welcome_pack_label",
            "confirmation_email_subject",
            "confirmation_email_body",
            "reminder_email_subject",
            "reminder_email_body",
            "welcome_email_subject",
            "welcome_email_body",
            "access_needs_ack_subject",
            "access_needs_ack_body",
        ]
        widgets = {
            "confirmation_email_body": forms.Textarea(attrs={"rows": 8}),
            "reminder_email_body": forms.Textarea(attrs={"rows": 8}),
            "welcome_email_body": forms.Textarea(attrs={"rows": 10}),
            "access_needs_ack_body": forms.Textarea(attrs={"rows": 8}),
        }


class InductionRequestAdminForm(forms.ModelForm):
    """Panopticon form for updating an access needs request."""

    class Meta:
        model = InductionRequest
        fields = ["status", "linked_session", "notes", "contacted_at", "purge_after"]
        widgets = {
            "contacted_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "purge_after": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["contacted_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["purge_after"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["linked_session"].required = False
        self.fields["contacted_at"].required = False


def _question_key(label: str) -> str:
    """Stable field name for a custom question label."""
    import re
    return re.sub(r"[^a-z0-9]+", "_", label.lower())[:50]
