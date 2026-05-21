# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
from django import forms
from django.forms import inlineformset_factory
from django.utils.html import mark_safe
from crispy_forms.helper import FormHelper
from .models import Collective, CollectiveLink, DonationItem, Job, COLLECTIVE_PALETTE


class ColourPickerWidget(forms.TextInput):
    """
    Renders palette swatches + a native colour picker + a hex text input.
    Clicking a swatch or using the picker updates all three and the hidden
    field that the form actually submits.
    """

    def render(self, name, value, attrs=None, renderer=None):
        if not value:
            value = "#343a40"

        widget_id = f"cpw-{name}"

        swatches_html = ""
        for hex_val, label in COLLECTIVE_PALETTE:
            swatches_html += (
                f'<button type="button" class="cpw-swatch" '
                f'style="background:{hex_val};" '
                f'data-colour="{hex_val}" '
                f'title="{label}" '
                f'aria-label="{label}"></button>'
            )

        return mark_safe(f"""
<style>
.cpw-wrap {{ margin-bottom: 0.5rem; }}
.cpw-swatches {{ display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 0.6rem; }}
.cpw-swatch {{
  width: 28px; height: 28px; border-radius: 4px;
  border: 2px solid transparent; cursor: pointer; padding: 0;
  transition: transform 0.1s, border-color 0.1s;
}}
.cpw-swatch:hover {{ transform: scale(1.15); }}
.cpw-swatch.active {{ border-color: #fff; outline: 2px solid #000; transform: scale(1.15); }}
.cpw-controls {{ display: flex; align-items: center; gap: 0.5rem; margin-top: 0.25rem; }}
.cpw-picker {{
  width: 40px; height: 36px; padding: 2px;
  border-radius: 4px; border: 1px solid #ced4da; cursor: pointer;
}}
</style>
<div class="cpw-wrap" id="{widget_id}">
  <div class="cpw-swatches" aria-label="Suggested colours">{swatches_html}</div>
  <div class="cpw-controls">
    <input type="color" class="cpw-picker" value="{value}" aria-label="Pick any colour">
    <input type="text" class="cpw-hex form-control form-control-sm"
           value="{value}" maxlength="7" style="width:6rem;" aria-label="Hex colour code">
    <input type="hidden" name="{name}" value="{value}" class="cpw-hidden">
  </div>
</div>
<script>
(function() {{
  var cpw      = document.getElementById('{widget_id}');
  var picker   = cpw.querySelector('.cpw-picker');
  var hexBox   = cpw.querySelector('.cpw-hex');
  var hidden   = cpw.querySelector('.cpw-hidden');
  var swatches = cpw.querySelectorAll('.cpw-swatch');

  function setColour(hex) {{
    hex = hex.trim().toLowerCase();
    if (!/^#[0-9a-f]{{6}}$/.test(hex)) return;
    picker.value = hex;
    hexBox.value = hex;
    hidden.value = hex;
    swatches.forEach(function(s) {{
      s.classList.toggle('active', s.dataset.colour === hex);
    }});
  }}

  setColour('{value}');

  swatches.forEach(function(s) {{
    s.addEventListener('click', function() {{ setColour(s.dataset.colour); }});
  }});
  picker.addEventListener('input', function() {{ setColour(picker.value); }});
  hexBox.addEventListener('input', function() {{ setColour(hexBox.value); }});
}})();
</script>
""")


class CollectiveForm(forms.ModelForm):
    class Meta:
        model = Collective
        fields = ("colour", "volunteer_count", "about", "roles", "organising", "proud_of", "get_involved", "contact")
        widgets = {
            "colour": ColourPickerWidget(),
            "about": forms.Textarea(attrs={"rows": 5}),
            "roles": forms.Textarea(attrs={"rows": 5}),
            "organising": forms.Textarea(attrs={"rows": 4}),
            "proud_of": forms.Textarea(attrs={"rows": 4}),
            "get_involved": forms.Textarea(attrs={"rows": 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False


CollectiveLinkFormSet = inlineformset_factory(
    Collective,
    CollectiveLink,
    fields=("label", "url"),
    extra=3,
    max_num=3,
    can_delete=True,
    widgets={
        "label": forms.TextInput(attrs={
            "placeholder": "e.g. WhatsApp group",
            "class": "form-control form-control-sm",
        }),
        "url": forms.URLInput(attrs={
            "placeholder": "https://...",
            "class": "form-control form-control-sm",
        }),
    },
)


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
