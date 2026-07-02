# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
import datetime

from crispy_forms.helper import FormHelper
from django import forms

from .models import MaintenanceRecord, MaintenanceTask


class MaintenanceTaskForm(forms.ModelForm):
    class Meta:
        model = MaintenanceTask
        fields = (
            "name",
            "category",
            "frequency",
            "frequency_notes",
            "contractor",
            "keyholder_required",
            "skills_required",
            "time_commitment",
            "nextcloud_link",
            "notes",
            "active",
        )
        widgets = {
            "skills_required": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False


class MaintenanceRecordForm(forms.ModelForm):
    class Meta:
        model = MaintenanceRecord
        fields = (
            "completed_date",
            "completed_by_name",
            "notes",
            "next_due_override",
        )
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("initial", {})
        kwargs["initial"].setdefault("completed_date", datetime.date.today())
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
