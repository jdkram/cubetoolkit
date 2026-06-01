# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
from django import forms
from django.forms import inlineformset_factory
from django.utils.html import mark_safe
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, HTML
from toolkit.diary.form_widgets import HtmlTextarea
from .models import Bulletin, Collective, CollectiveLink, DonationItem, ExchangeItem, FoundItem, Job, COLLECTIVE_PALETTE


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
        fields = ("colour", "volunteer_count", "about", "roles", "organising", "proud_of", "get_involved", "contact", "listed_publicly", "public_copy")
        widgets = {
            "colour": ColourPickerWidget(),
            "about": forms.Textarea(attrs={"rows": 5}),
            "roles": forms.Textarea(attrs={"rows": 5}),
            "organising": forms.Textarea(attrs={"rows": 4}),
            "proud_of": forms.Textarea(attrs={"rows": 4}),
            "get_involved": forms.Textarea(attrs={"rows": 5}),
            "public_copy": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            "colour", "volunteer_count", "about", "roles", "organising", "proud_of", "get_involved", "contact",
            HTML(
                '<hr style="margin: 1.5rem 0 1rem;">'
                '<h2 style="font-size: 1rem; font-weight: 600; margin-bottom: 0.25rem;">Public directory</h2>'
                '<p class="text-muted" style="font-size: 0.85rem; margin-bottom: 1rem;">'
                'Controls whether this collective appears on the public <code>/labs/collectives/public/</code> page. '
                'Both the checkbox and a non-empty public description are required to be listed.</p>'
            ),
            "listed_publicly",
            "public_copy",
        )


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


BULLETIN_BODY_MAX = 2000

# Characters to strip from bulletin text on save:
# - C0/C1 controls (except \n and \t)
# - Bidi-override / direction marks (used for homoglyph-style URL spoofing)
# - Zero-width spaces / joiners and the byte-order mark
_BULLETIN_STRIP_CHARS = (
    set(range(0x00, 0x09)) | {0x0B} | set(range(0x0E, 0x20))  # C0 minus \t\n
    | set(range(0x7F, 0xA0))                                  # DEL + C1
    | {0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0xFEFF}        # ZW marks + LRM/RLM + BOM
    | set(range(0x202A, 0x202F))                              # LRE/RLE/PDF/LRO/RLO
    | set(range(0x2066, 0x206A))                              # LRI/RLI/FSI/PDI
)


def _scrub_bulletin_text(value: str) -> str:
    return "".join(c for c in value if ord(c) not in _BULLETIN_STRIP_CHARS)


class BulletinForm(forms.ModelForm):
    class Meta:
        model = Bulletin
        fields = ("title", "body")
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "maxlength": 200}),
            "body": forms.Textarea(attrs={
                "rows": 4, "class": "form-control", "maxlength": BULLETIN_BODY_MAX,
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.fields["body"].help_text = (
            f"Plain text. Max {BULLETIN_BODY_MAX} characters. URLs stay as plain "
            "text — readers must copy-paste to follow them."
        )

    def clean_title(self):
        return _scrub_bulletin_text(self.cleaned_data["title"]).strip()

    def clean_body(self):
        body = _scrub_bulletin_text(self.cleaned_data["body"]).strip()
        if len(body) > BULLETIN_BODY_MAX:
            raise forms.ValidationError(
                f"Body is too long ({len(body)} chars; max {BULLETIN_BODY_MAX})."
            )
        return body


class BulletinExpiryForm(forms.ModelForm):
    class Meta:
        model = Bulletin
        fields = ("expires_at",)
        widgets = {
            "expires_at": forms.DateTimeInput(
                attrs={"type": "datetime-local", "class": "form-control"}
            ),
        }


class DonationItemForm(forms.ModelForm):
    class Meta:
        model = DonationItem
        fields = ("name", "category", "status", "active", "display_order", "notes", "internal_notes", "contact")
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
            "internal_notes": forms.Textarea(attrs={"rows": 3}),
        }


class DonationsIntroForm(forms.Form):
    intro = forms.CharField(
        required=False,
        widget=HtmlTextarea(attrs={"id": "id_intro"}),
        label="Page introduction",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False


class FoundItemLogForm(forms.ModelForm):
    class Meta:
        model = FoundItem
        fields = ("report_type", "description", "location_found", "found_on", "logged_by", "reporter_contact", "photo", "notes")
        widgets = {
            "report_type": forms.RadioSelect(attrs={"class": "laf-type-radio"}),
            "description": forms.TextInput(attrs={"class": "form-control", "autocomplete": "off"}),
            "location_found": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Bar, Cinema, Toilets"}),
            "found_on": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "logged_by": forms.TextInput(attrs={"class": "form-control"}),
            "reporter_contact": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Name, phone number, email — whatever they're comfortable leaving"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["photo"].required = False
        self.fields["notes"].required = False
        self.fields["reporter_contact"].required = False
        self.fields["reporter_contact"].label = "Reporter's contact details (private)"
        self.helper = FormHelper()
        self.helper.form_tag = False


class FoundItemClaimForm(forms.Form):
    claimed_by = forms.CharField(
        max_length=200,
        label="Claimed by",
        help_text="Name or contact details of the person collecting the item.",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )


class FoundItemDisposeForm(forms.Form):
    disposal_method = forms.ChoiceField(
        choices=FoundItem.DISPOSAL_CHOICES,
        label="Disposal method",
        widget=forms.Select(attrs={"class": "form-select"}),
    )


class ExchangeItemForm(forms.ModelForm):
    class Meta:
        model = ExchangeItem
        fields = (
            "listing_type",
            "name",
            "description",
            "category",
            "condition",
            "quantity",
            "available_until",
            "owner_type",
            "owner_volunteer",
            "location_notes",
            "status",
            "notes",
            "image",
        )
        widgets = {
            "listing_type": forms.RadioSelect(attrs={"class": "form-check-input"}),
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "condition": forms.Select(attrs={"class": "form-select"}),
            "quantity": forms.TextInput(attrs={"class": "form-control"}),
            "available_until": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "owner_type": forms.Select(attrs={"class": "form-select"}),
            "owner_volunteer": forms.Select(attrs={"class": "form-select"}),
            "location_notes": forms.TextInput(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        from toolkit.members.models import Volunteer
        self.fields["owner_volunteer"].queryset = (
            Volunteer.objects.active().select_related("member").order_by("member__name")
        )
        self.fields["owner_volunteer"].label_from_instance = lambda v: v.member.name
        self.fields["owner_volunteer"].required = False
