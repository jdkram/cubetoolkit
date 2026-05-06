# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
from django import forms
from crispy_forms.helper import FormHelper
from .models import DonationItem, Job


class JobForm(forms.ModelForm):
    class Meta:
        model = Job
        fields = (
            "title",
            "area",
            "description",
            "plan_status",
            "safety_risk",
            "skill_needed",
            "keyholder_required",
            "urgency",
            "location_type",
            "reporter_name",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "plan_status": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False


class DonationItemForm(forms.ModelForm):
    class Meta:
        model = DonationItem
        fields = ("name", "category", "status", "active", "display_order", "notes", "internal_notes", "contact")
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
            "internal_notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
