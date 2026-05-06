# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
from django import forms
from crispy_forms.helper import FormHelper
from .models import Job


class JobForm(forms.ModelForm):
    class Meta:
        model = Job
        fields = ("title", "description", "location", "skills", "keyholder_required", "urgency")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "skills": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
