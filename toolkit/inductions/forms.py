# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
import json

from django import forms
from django.utils import timezone
from django.utils.safestring import mark_safe

from .models import InductionRequest, InductionSession, InductionsSettings


class SignupForm(forms.Form):
    """Public sign-up form for an induction session."""

    first_name = forms.CharField(max_length=100, label="First name")
    last_name = forms.CharField(max_length=100, label="Last name")
    email = forms.EmailField(label="Email address")
    phone = forms.CharField(max_length=64, required=False, label="Phone number")
    address = forms.CharField(max_length=128, required=False, label="Address")
    postcode = forms.CharField(max_length=16, required=False, label="Postcode")

    def get_name(self):
        return f"{self.cleaned_data['first_name']} {self.cleaned_data['last_name']}"

    def __init__(self, *args, session=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = session

        # GDPR consent — build label with optional privacy policy link
        cfg = InductionsSettings.load()
        purge_days = cfg.induction_purge_days
        if cfg.privacy_policy_url:
            policy_link = mark_safe(
                f' <a href="{cfg.privacy_policy_url}" target="_blank" rel="noopener">Privacy policy</a>.'
            )
        else:
            policy_link = mark_safe("")
        self.fields["age_confirm"] = forms.BooleanField(
            required=True,
            label="I confirm that I am 18 years of age or over.",
        )
        self.fields["consent"] = forms.BooleanField(
            required=True,
            label=mark_safe(
                f"I consent to my name, email address, and any contact details I provide being stored "
                f"to process my induction sign-up. "
                f"If I attend and become a volunteer, they'll be kept as part of my volunteer record. "
                f"If I don't attend, they'll be deleted within {purge_days} days.{policy_link}"
            ),
        )

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
    age_confirm = forms.BooleanField(
        required=True,
        label="I confirm that I am 18 years of age or over.",
    )


class InductionSessionForm(forms.ModelForm):
    """Panopticon form for creating/editing an induction session."""

    class Meta:
        model = InductionSession
        fields = [
            "title", "session_type", "date", "location",
            "max_signups", "status", "purge_after",
        ]
        widgets = {
            "date": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "purge_after": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["date"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["purge_after"].input_formats = ["%Y-%m-%dT%H:%M"]
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
            "default_max_signups",
            "privacy_policy_url",
            "organiser_notification_email",
            "notify_on_each_signup",
            "welcome_pack_url",
            "welcome_pack_label",
            "access_needs_enabled",
            "access_needs_intro_text",
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
            "access_needs_intro_text": forms.Textarea(attrs={"rows": 5, "class": "form-control"}),
            "confirmation_email_body": forms.Textarea(attrs={"rows": 8, "class": "form-control"}),
            "reminder_email_body": forms.Textarea(attrs={"rows": 8, "class": "form-control"}),
            "welcome_email_body": forms.Textarea(attrs={"rows": 10, "class": "form-control"}),
            "access_needs_ack_body": forms.Textarea(attrs={"rows": 8, "class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif "class" not in widget.attrs:
                widget.attrs["class"] = "form-control"


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
