import datetime
import calendar

from django import forms
from django.forms import inlineformset_factory
import django.db.models
from django.conf import settings
from django.utils import timezone
from crispy_forms.helper import FormHelper
from crispy_forms.layout import HTML, Div, Field, Fieldset, Layout

# Custom form widgets:
from toolkit.diary.form_widgets import (
    AgeRatingChoicesWidget,
    HtmlTextarea,
    JQueryDateTimePicker,
    MultiDatePickerWidget,
    ChosenSelectMultiple,
    TagPillSelect,
)

import toolkit.diary.models
from toolkit.diary.models import EventTag, SiteConfiguration, get_site_config
from collections import OrderedDict

from toolkit.diary.validators import validate_in_future


class RoleForm(forms.ModelForm):
    class Meta:
        model = toolkit.diary.models.Role
        fields = (
            "name",
            "standard",
            "description",
            "stats_label",
            "beginner_friendly",
            "wheelchair_accessible",
            "keyholder_only",
            "required_qualification",
            "qualification_gate",
        )


class EventTemplateForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # This form is rendered by hand (not via crispy) so it doesn't pick
        # up Bootstrap classes automatically - add them here, matching the
        # pattern in SiteConfigurationForm.
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, TagPillSelect):
                pass  # manages its own markup
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                existing = widget.attrs.get("class", "")
                if "form-select" not in existing:
                    widget.attrs["class"] = (
                        existing + " form-select"
                    ).strip()
            else:
                existing = widget.attrs.get("class", "")
                if "form-control" not in existing:
                    widget.attrs["class"] = (
                        existing + " form-control"
                    ).strip()

    class Meta:
        model = toolkit.diary.models.EventTemplate
        # roles is handled by a separate inline formset (EventTemplateRoleFormSet)
        fields = (
            "name",
            "tags",
            "pricing",
            "film_information",
            "copy_summary",
            "copy",
            "cost_type",
            "cost_distributor",
            "cost_flat_fee_gbp",
            "cost_fee_includes_vat",
            "cost_percentage_split",
            "cost_minimum_guarantee_gbp",
            "cost_total_gbp",
            "terms",
            "rota_notes",
            "private",
            "outside_hire",
        )
        widgets = {
            "tags": TagPillSelect(),
            "copy": forms.Textarea(attrs={"wrap": "soft", "rows": 10}),
            "copy_summary": forms.Textarea(attrs={"wrap": "soft", "rows": 4}),
            "terms": forms.Textarea(attrs={"wrap": "soft", "rows": 6}),
            "rota_notes": forms.Textarea(attrs={"wrap": "soft", "rows": 4}),
            "pricing": forms.TextInput(
                attrs={
                    "placeholder": (
                        "e.g. '\u00a30 Full / \u00a30 Concession'"
                    ),
                }
            ),
            "film_information": forms.TextInput(
                attrs={
                    "placeholder": "e.g. Dir: [director], 1990, USA, 120 mins, Cert: 15",
                }
            ),
            "cost_flat_fee_gbp": forms.NumberInput(
                attrs={"step": "0.01", "min": "0", "style": "width:9em"}
            ),
            "cost_percentage_split": forms.NumberInput(
                attrs={
                    "step": "0.01",
                    "min": "0",
                    "max": "100",
                    "style": "width:7em",
                }
            ),
            "cost_minimum_guarantee_gbp": forms.NumberInput(
                attrs={"step": "0.01", "min": "0", "style": "width:9em"}
            ),
            "cost_total_gbp": forms.NumberInput(
                attrs={"step": "0.01", "min": "0", "style": "width:9em"}
            ),
        }


class EventTemplateRoleForm(forms.ModelForm):
    class Meta:
        model = toolkit.diary.models.EventTemplateRole
        fields = ("role", "count")
        widgets = {
            "role": forms.Select(attrs={"class": "form-select"}),
            "count": forms.NumberInput(
                attrs={
                    "min": 1,
                    "max": 20,
                    "style": "width:5em",
                    "class": "form-control",
                }
            ),
        }


# Inline formset: one EventTemplateRole row per role slot on the template.
# extra=1 always appends one blank row for adding a new role.
EventTemplateRoleFormSet = inlineformset_factory(
    toolkit.diary.models.EventTemplate,
    toolkit.diary.models.EventTemplateRole,
    form=EventTemplateRoleForm,
    extra=1,
    can_delete=True,
)


class EventTemplateRoomForm(forms.ModelForm):
    class Meta:
        model = toolkit.diary.models.EventTemplateRoom
        fields = ("room", "start_delta_minutes", "end_delta_minutes")
        widgets = {
            "room": forms.Select(attrs={"class": "form-select"}),
            "start_delta_minutes": forms.NumberInput(
                attrs={"style": "width:6em", "class": "form-control"}
            ),
            "end_delta_minutes": forms.NumberInput(
                attrs={"style": "width:6em", "class": "form-control"}
            ),
        }


EventTemplateRoomFormSet = inlineformset_factory(
    toolkit.diary.models.EventTemplate,
    toolkit.diary.models.EventTemplateRoom,
    form=EventTemplateRoomForm,
    extra=1,
    can_delete=True,
)


class DiaryIdeaForm(forms.ModelForm):
    class Meta:
        model = toolkit.diary.models.DiaryIdea
        fields = ("ideas",)


_COST_FIELDS = (
    "cost_type",
    "cost_distributor",
    "cost_flat_fee_gbp",
    "cost_fee_includes_vat",
    "cost_percentage_split",
    "cost_minimum_guarantee_gbp",
    "cost_total_gbp",
    "cost_rider_notes",
    "cost_sound_engineer_name",
    "cost_sound_engineer_fee_gbp",
    "cost_sound_engineer_paid_by",
)


def _card_open(section_id: str, title: str, start_open: bool = True) -> str:
    expanded = "true" if start_open else "false"
    show_class = " show" if start_open else ""
    arrow_style = "transform:rotate(90deg)" if start_open else ""
    return (
        f'<div class="card mb-3">'
        f'<div class="card-header p-2" id="{section_id}-hdr" '
        f'style="cursor:pointer;user-select:none;" '
        f'data-bs-toggle="collapse" data-bs-target="#{section_id}-body" '
        f'aria-expanded="{expanded}" aria-controls="{section_id}-body">'
        f'<span class="section-arrow" style="{arrow_style}">&#9658;</span>'
        f"<strong>{title}</strong>"
        f"</div>"
        f'<div id="{section_id}-body" class="collapse{show_class}">'
        f'<div class="card-body pt-2 pb-1">'
    )


_CARD_CLOSE = "</div></div></div>"


class EventForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.form_class = "form-horizontal"
        self.helper.label_class = "col-sm-2"
        self.helper.field_class = "col-sm-10"
        # Build age restriction choices from site config so venues can use
        # their own rating scheme (BBFC, FSK, etc.) without a code change.
        cfg = get_site_config()
        # Remove structured cost fields when the feature flag is off so they
        # don't appear in the form and can't be submitted.
        if not cfg.structured_cost_terms_enabled:
            for f in _COST_FIELDS:
                self.fields.pop(f, None)
        choices = [("", "Not stated")] + [
            (e["value"], e["label"])
            for e in cfg.age_rating_choices
            if e.get("value")
        ]
        self.fields["age_restriction"].widget = forms.Select(choices=choices)
        self.fields["age_restriction"].widget.attrs.setdefault(
            "class", "form-select"
        )

        if cfg.structured_cost_terms_enabled:
            cost_and_terms = [
                HTML(_card_open("costs", "Cost &amp; terms")),
                "cost_type",
                "cost_distributor",
                "cost_flat_fee_gbp",
                "cost_fee_includes_vat",
                "cost_percentage_split",
                "cost_minimum_guarantee_gbp",
                "cost_total_gbp",
                "terms",
                "cost_rider_notes",
                "cost_sound_engineer_name",
                "cost_sound_engineer_fee_gbp",
                "cost_sound_engineer_paid_by",
                HTML(_CARD_CLOSE),
            ]
        else:
            cost_and_terms = [
                HTML(_card_open("terms", "Terms")),
                "terms",
                HTML(_CARD_CLOSE),
            ]
        self.helper.layout = Layout(
            HTML(_card_open("basics", "Basics")),
            "name",
            "tags",
            HTML(_CARD_CLOSE),
            HTML(_card_open("public", "Public listing")),
            "pricing",
            "ticket_link",
            "trailer_url",
            "film_information",
            "age_restriction",
            "pre_title",
            "post_title",
            HTML(_CARD_CLOSE),
            HTML(_card_open("programming", "Programming")),
            "approval_type",
            "approved_at_meeting_date",
            "meeting_name",
            "meeting_minutes_url",
            "programming_status",
            "programming_notes",
            "duration",
            HTML(_CARD_CLOSE),
            HTML(_card_open("access", "Visibility &amp; access")),
            "outside_hire",
            "hire_name",
            "private",
            HTML(_CARD_CLOSE),
            HTML(_card_open("description", "Description")),
            "copy",
            "copy_summary",
            HTML(_CARD_CLOSE),
            *cost_and_terms,
        )
        for field in self.fields.values():
            field.help_text = ""

    class Meta:
        model = toolkit.diary.models.Event
        # Ensure soft wrapping is set for textareas:
        widgets = {
            # Use the custom WYSIWYG text editor widget:
            "copy": HtmlTextarea(attrs={"wrap": "soft"}),
            "copy_summary": forms.Textarea(attrs={"wrap": "soft"}),
            "terms": forms.Textarea(
                attrs={
                    "wrap": "soft",
                    "placeholder": f"e.g {settings.DEFAULT_TERMS_TEXT}",
                }
            ),
            "cost_flat_fee_gbp": forms.NumberInput(
                attrs={"step": "0.01", "min": "0", "style": "width:9em"}
            ),
            "cost_percentage_split": forms.NumberInput(
                attrs={
                    "step": "0.01",
                    "min": "0",
                    "max": "100",
                    "style": "width:7em",
                }
            ),
            "cost_minimum_guarantee_gbp": forms.NumberInput(
                attrs={"step": "0.01", "min": "0", "style": "width:9em"}
            ),
            "cost_total_gbp": forms.NumberInput(
                attrs={"step": "0.01", "min": "0", "style": "width:9em"}
            ),
            "cost_rider_notes": forms.Textarea(
                attrs={"wrap": "soft", "rows": 3}
            ),
            "cost_sound_engineer_fee_gbp": forms.NumberInput(
                attrs={"step": "0.01", "min": "0", "style": "width:9em"}
            ),
            "cost_sound_engineer_paid_by": forms.Select(
                attrs={"style": "width:auto"}
            ),
            "programming_notes": forms.Textarea(
                attrs={
                    "wrap": "soft",
                    "rows": 5,
                    "placeholder": "e.g. Looking for a Friday in May; tech rider: DCP, 5.1 audio, projector set up by noon",
                }
            ),
            "approved_at_meeting_date": forms.DateInput(
                attrs={"type": "date"}
            ),
            "pricing": forms.TextInput(
                attrs={
                    "placeholder": (
                        "e.g. '\u00a30 Full / \u00a30 Concession' "
                        "or '\u00a30 advance, \u00a30 on the door'"
                    ),
                }
            ),
            "film_information": forms.TextInput(
                attrs={
                    "placeholder": "e.g. Dir: [director], 1990, USA, 120 mins, "
                    "Cert: 15",
                }
            ),
            "pre_title": forms.TextInput(
                attrs={
                    "placeholder": (
                        (
                            f"Text displayed before / above the event"
                            f"name, e.g. '{settings.VENUE['name']} presents'"
                        )
                    ),
                }
            ),
            "post_title": forms.TextInput(
                attrs={
                    "placeholder": (
                        "Text displayed after / below the event name,"
                        " e.g. 'with support from A Band'"
                    ),
                }
            ),
            "tags": TagPillSelect(),
            "trailer_url": forms.URLInput(
                attrs={
                    "placeholder": "e.g. https://www.youtube.com/watch?v=…",
                }
            ),
        }
        order = ("tags",)
        fields = (
            "name",
            "tags",
            "pricing",
            "ticket_link",
            "trailer_url",
            "film_information",
            "age_restriction",
            "pre_title",
            "post_title",
            "approval_type",
            "approved_at_meeting_date",
            "meeting_name",
            "meeting_minutes_url",
            "programming_status",
            "programming_notes",
            "duration",
            "outside_hire",
            "hire_name",
            "private",
            "copy",
            "copy_summary",
            "cost_type",
            "cost_distributor",
            "cost_flat_fee_gbp",
            "cost_fee_includes_vat",
            "cost_percentage_split",
            "cost_minimum_guarantee_gbp",
            "cost_total_gbp",
            "terms",
            "cost_rider_notes",
            "cost_sound_engineer_name",
            "cost_sound_engineer_fee_gbp",
            "cost_sound_engineer_paid_by",
        )

    def clean_terms(self):
        terms = self.cleaned_data.get("terms", "")
        if "[" in terms and "]" in terms:
            raise forms.ValidationError(
                "The terms look like they still contain unfilled placeholders (e.g. [Distributor]). "
                "Please fill in all the bracketed sections before saving."
            )
        return terms

    def clean_film_information(self):
        film_info = self.cleaned_data.get("film_information", "")
        if "[" in film_info and "]" in film_info:
            raise forms.ValidationError(
                "The screening details look like they still contain unfilled placeholders (e.g. [Director]). "
                "Please fill in all the bracketed sections before saving."
            )
        return film_info

    def clean_copy_summary(self):
        copy_summary = self.cleaned_data.get("copy_summary", "")
        max_chars = get_site_config().programme_copy_summary_max_chars
        if len(copy_summary) > max_chars:
            raise forms.ValidationError(
                f"Copy summary must be {max_chars} "
                f"characters or fewer (currently {len(copy_summary)} characters)"
            )
        return copy_summary

    def clean(self):
        cleaned_data = super().clean()
        if (
            cleaned_data.get("approval_type")
            == toolkit.diary.models.Event.APPROVAL_MEETING
        ):
            if not cleaned_data.get("approved_at_meeting_date"):
                self.add_error(
                    "approved_at_meeting_date",
                    "Please enter the date of the meeting at which this was approved.",
                )
            else:
                # Meeting approved with a date set → treat as active.
                cleaned_data["programming_status"] = "active"
        if self.instance.all_showings_confirmed():
            terms = cleaned_data.get("terms", "")
            terms_word_count = len(terms.split())

            terms_not_required = cleaned_data.get(
                "tags"
            ).contains_tag_to_not_need_terms()

            cost_type = cleaned_data.get("cost_type")
            cost_type_set = bool(
                cost_type
                and cost_type != toolkit.diary.models.Event.COST_TYPE_TBC
            )

            cfg = get_site_config()
            min_words = cfg.programme_event_terms_min_words

            if (
                cfg.structured_cost_terms_enabled
                and cfg.structured_cost_required
                and not cost_type_set
                and not terms_not_required
            ):
                self.add_error(
                    "cost_type",
                    f"Cost type must be set (to something other than TBC) before "
                    f"'{self.instance.name}' can be confirmed.",
                )

            if (
                terms_word_count < min_words
                and not terms_not_required
                and not cost_type_set
            ):
                msg = (
                    f"Event terms for confirmed event '{self.instance.name}' "
                    f"are missing or too short. Please enter at least "
                    f"{min_words} words, or set the cost type above."
                )
                self.add_error("terms", msg)
        return cleaned_data


class MediaItemForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.form_class = "form-horizontal"
        self.helper.label_class = "col-sm-2"
        self.helper.field_class = "col-sm-10"

        guidance_url = get_site_config().alt_text_guidance_url or None
        if guidance_url:
            from django.utils.safestring import mark_safe

            base = self.fields["alt_text"].help_text
            self.fields["alt_text"].help_text = mark_safe(
                f'{base} <a href="{guidance_url}" target="_blank" rel="noopener">Guide ↗</a>'
            )

    class Meta:
        model = toolkit.diary.models.MediaItem
        widgets = {
            "media_file": forms.ClearableFileInput(
                attrs={"accept": "image/jpeg,image/gif,image/png"}
            ),
            "alt_text": forms.Textarea(
                attrs={
                    "rows": 3,
                    "style": "resize: vertical;",
                    "class": "form-control",
                }
            ),
            "bar_colour": forms.HiddenInput(),
            "crop_x": forms.HiddenInput(),
            "crop_y": forms.HiddenInput(),
            "crop_w": forms.HiddenInput(),
            "crop_h": forms.HiddenInput(),
        }
        exclude = ("mimetype", "caption")

    def clean_media_file(self):
        media_file = self.cleaned_data.get("media_file", None)
        if media_file:
            size_MB = media_file.size / 1048576.0
            max_MB = get_site_config().programme_media_max_size_mb
            if size_MB > max_MB:
                raise forms.ValidationError(
                    f"Media file must be {max_MB} MB or less "
                    f"(uploaded file is {size_MB:.2f} MB)"
                )
        return media_file


class ShowingForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        # Vertical (stacked) layout — labels sit above their fields. The old
        # form-horizontal layout crammed labels into a narrow 2-column strip,
        # which wrapped awkwardly (and pushed the ⓘ tooltip onto its own line)
        # and indented the status checkboxes oddly on narrow viewports.
        # Spell out what "confirmed" actually does — it's the publish + open-rota
        # switch, not just a tick (see also the per-occurrence buttons on the hub).
        self.fields["confirmed"].label = "Confirmed (public + rota open)"
        # Status/visibility toggles live in their own group below the booking
        # details rather than high up amongst date/time — they're a final step,
        # and the hub's buttons are the main way to set them.
        self.helper.layout = Layout(
            Field("start"),
            Field("booked_by"),
            # Call times grouped on one row — they collapse to stacked below sm.
            Div(
                Div(Field("setup_time"), css_class="col-sm-4"),
                Div(Field("doors_time"), css_class="col-sm-4"),
                Div(Field("final_volunteer_time"), css_class="col-sm-4"),
                css_class="row",
            ),
            Fieldset(
                "Status & visibility",
                "confirmed",
                "cancelled",
                "hide_in_programme",
                "sold_out",
                "discounted",
            ),
        )

    class Meta:
        model = toolkit.diary.models.Showing
        fields = (
            "start",
            "booked_by",
            "confirmed",
            "hide_in_programme",
            "cancelled",
            "sold_out",
            "discounted",
            "setup_time",
            "doors_time",
            "final_volunteer_time",
        )

        widgets = {
            "start": JQueryDateTimePicker(),
            "setup_time": forms.TimeInput(
                attrs={"type": "time", "class": "form-control"}
            ),
            "doors_time": forms.TimeInput(
                attrs={"type": "time", "class": "form-control"}
            ),
            "final_volunteer_time": forms.TimeInput(
                attrs={"type": "time", "class": "form-control"}
            ),
        }

    def clean_confirmed(self):
        confirmed = self.cleaned_data["confirmed"]
        if (
            confirmed
            and self.instance.event_id
            and not self.instance.event.terms_satisfied()
        ):

            raise forms.ValidationError(
                "Events require terms information "
                # TAGS_WITHOUT_TERMS is settings-only — no SiteConfiguration counterpart.
                f'(unless they are tagged with one of {"/".join(sorted(settings.TAGS_WITHOUT_TERMS))}). '
                "Please add more details."
            )
        return confirmed

    def clean(self):
        if self.instance.original_start_in_past():
            self.cleaned_data["start"] = self.instance.start
            noun = get_site_config().occurrence_noun
            raise forms.ValidationError(f"Cannot amend a historic {noun}")
        return super().clean()


ShowingFormSet = forms.modelformset_factory(
    toolkit.diary.models.Showing,
    extra=1,
    form=ShowingForm,
)


class ShowingRotaNotesForm(forms.ModelForm):
    class Meta:
        model = toolkit.diary.models.Showing
        fields = ("rota_notes",)


def rota_form_factory(showing):
    # Dynamically generate a form to edit the rota for the given showing

    # Members for RotaForm class:
    members = OrderedDict()

    # All permanent roles (one-shot roles are handled separately in the view)
    roles = toolkit.diary.models.Role.objects.filter(
        is_one_shot=False
    ).order_by("name")

    # list of role IDs, to get stored in form and used to build rota from
    # submitted form data (as submitted data won't include IDs where rota
    # count is 0)
    _role_ids = []

    # Get all rota entries for showing, annotated with the maximum value of
    # "rank" for the role
    rota_entries = toolkit.diary.models.Role.objects.filter(
        rotaentry__showing_id=showing.pk
    ).annotate(max_rank=django.db.models.Max("rotaentry__rank"))

    # Build dict mapping role ID to max_rank
    rota_entry_count_by_role = dict(
        (role.pk, role.max_rank) for role in rota_entries
    )

    for role in roles:
        _role_ids.append(role.pk)
        # All roles get an IntegerField spinner.
        # Standard roles are prefixed "role_"; non-standard "other_" so the
        # template can render them in two visual groups with the same spinner UI.
        prefix = "role_" if role.standard else "other_"
        members[f"{prefix}{role.pk}"] = forms.IntegerField(
            min_value=0,
            max_value=get_site_config().max_count_per_role,
            required=False,  # Missing field treated as 0 — you don't need to explicitly zero every role
            label=role.name,
            initial=rota_entry_count_by_role.get(role.pk, 0),
            widget=forms.NumberInput(attrs={"class": "rota_count"}),
        )

    def get_rota(self):
        # Build a dict mapping role_id: number from submitted cleaned data.
        # None (missing/blank field) counts as 0.
        result = dict.fromkeys(self._role_ids, 0)
        for field, value in self.cleaned_data.items():
            if value is None:
                continue
            if field.startswith("role_"):
                result[int(field[5:])] = value
            elif field.startswith("other_"):
                result[int(field[6:])] = value
        return result

    members["_role_ids"] = _role_ids
    members["get_rota"] = get_rota

    return type("RotaForm", (forms.Form,), members)


class CloneShowingForm(forms.Form):
    # For cloning a showing, so only need very minimal extra details

    clone_start = forms.DateTimeField(
        required=True,
        validators=[validate_in_future],
        widget=JQueryDateTimePicker(),
    )
    booked_by = forms.CharField(min_length=1, max_length=128, required=True)


class CloneEventForm(forms.Form):
    """Minimal details needed to clone an existing event as a new event.

    The new event inherits all text/config fields (copy, terms, rota, etc.)
    from the source.  The programmer only needs to confirm the name, first
    showing date, and who booked it.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.form_class = "form-horizontal"
        self.helper.label_class = "col-sm-3"
        self.helper.field_class = "col-sm-9"

    event_name = forms.CharField(
        min_length=1,
        max_length=256,
        required=True,
        label="New event name",
        help_text="Pre-filled from source — edit to give the new event a different title.",
    )
    start = forms.DateTimeField(
        required=True,
        validators=[validate_in_future],
        widget=JQueryDateTimePicker(),
        label="First showing date/time",
        help_text="Pre-filled to one week after the source's latest showing.",
    )
    room = forms.ModelChoiceField(
        queryset=toolkit.diary.models.Room.objects.all(),
        required=False,
        label="Room",
        empty_label="— no room —",
    )
    booked_by = forms.CharField(
        min_length=1,
        max_length=128,
        required=True,
        label="Booked by",
    )


_MAX_BATCH_SHOWINGS = 52


class BatchAddShowingsForm(forms.Form):
    """Add multiple showings to an existing event on several dates at once.

    The programmer selects one or more dates via a flatpickr multi-date picker.
    All showings share the same start time, room, booked_by, and confirmed flag.
    """

    def __init__(self, *args, event=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._event = event
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.form_class = "form-horizontal"
        self.helper.label_class = "col-sm-3"
        self.helper.field_class = "col-sm-9"

    dates = forms.CharField(
        widget=MultiDatePickerWidget(),
        label="Dates",
        help_text="Click to select one or more dates (max {}).".format(
            _MAX_BATCH_SHOWINGS
        ),
    )
    start_time = forms.TimeField(
        widget=forms.TimeInput(attrs={"type": "time"}),
        label="Start time",
        help_text="The time each showing starts. Applies to all selected dates.",
    )
    room = forms.ModelChoiceField(
        queryset=toolkit.diary.models.Room.objects.all(),
        required=False,
        label="Room",
        empty_label="— no room —",
    )
    booked_by = forms.CharField(
        min_length=1,
        max_length=128,
        required=True,
        label="Booked by",
    )
    confirmed = forms.BooleanField(
        required=False,
        label="Create as confirmed",
        help_text="Only tick if the event has terms set. Confirmed showings appear in the programme immediately.",
    )

    def clean_dates(self):
        raw = self.cleaned_data.get("dates", "").strip()
        if not raw:
            raise forms.ValidationError("Select at least one date.")
        parsed = []
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                parsed.append(datetime.date.fromisoformat(part))
            except ValueError:
                raise forms.ValidationError(
                    "Unrecognised date: {!r}. Expected YYYY-MM-DD.".format(
                        part
                    )
                )
        if not parsed:
            raise forms.ValidationError("Select at least one date.")
        if len(parsed) > _MAX_BATCH_SHOWINGS:
            raise forms.ValidationError(
                "Maximum {} dates per batch.".format(_MAX_BATCH_SHOWINGS)
            )
        return sorted(set(parsed))

    def clean(self):
        cleaned = super().clean()
        dates = cleaned.get("dates")
        start_time = cleaned.get("start_time")
        if dates and start_time:
            now = datetime.datetime.now()
            past = [
                d
                for d in dates
                if datetime.datetime.combine(d, start_time) < now
            ]
            if past:
                date_strs = ", ".join(d.strftime("%-d %b %Y") for d in past)
                raise forms.ValidationError(
                    f"The following dates are in the past: {date_strs}."
                )
        if cleaned.get("confirmed") and self._event is not None:
            if not self._event.terms_satisfied():
                self.add_error(
                    "confirmed",
                    "Add terms to the event before creating confirmed showings.",
                )
        return cleaned


class EventLinkForm(forms.ModelForm):
    """Single event resource link (label + URL). Used inside EventLinkFormSet."""

    class Meta:
        model = toolkit.diary.models.EventLink
        fields = ("label", "url")
        widgets = {
            "label": forms.TextInput(
                attrs={
                    "placeholder": "e.g. Event folder, Crew chat…",
                    "class": "form-control form-control-sm",
                }
            ),
            "url": forms.URLInput(
                attrs={
                    "placeholder": "https://…",
                    "class": "form-control form-control-sm",
                }
            ),
        }
        labels = {
            "label": "Link name",
            "url": "URL",
        }


# Inline formset: up to 3 EventLink rows per Event.
# extra=3 so Django pads to max_num=3 with blank rows; validate_max=True so
# attempts to submit >3 links are rejected rather than silently truncated.
EventLinkFormSet = inlineformset_factory(
    toolkit.diary.models.Event,
    toolkit.diary.models.EventLink,
    form=EventLinkForm,
    extra=3,
    max_num=3,
    validate_max=True,
    can_delete=True,
)


class EventTemplateLinkForm(forms.ModelForm):
    """Single resource link attached to an event template."""

    class Meta:
        model = toolkit.diary.models.EventTemplateLink
        fields = ("label", "url")
        widgets = {
            "label": forms.TextInput(
                attrs={
                    "placeholder": "e.g. Event folder, Crew chat…",
                    "class": "form-control form-control-sm",
                }
            ),
            "url": forms.URLInput(
                attrs={
                    "placeholder": "https://…",
                    "class": "form-control form-control-sm",
                }
            ),
        }


EventTemplateLinkFormSet = inlineformset_factory(
    toolkit.diary.models.EventTemplate,
    toolkit.diary.models.EventTemplateLink,
    form=EventTemplateLinkForm,
    extra=3,
    max_num=3,
    validate_max=True,
    can_delete=True,
)


class RoomForm(forms.ModelForm):
    class Meta:
        model = toolkit.diary.models.Room
        fields = ("name", "colour", "is_primary", "show_column", "map_slug")
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control form-control-sm"}
            ),
            "colour": forms.TextInput(
                attrs={
                    "type": "color",
                    "class": "form-control form-control-sm",
                    "style": "max-width: 80px; padding: 2px 4px;",
                }
            ),
            "map_slug": forms.TextInput(
                attrs={
                    "class": "form-control form-control-sm",
                    "placeholder": "e.g. room-cinema",
                }
            ),
        }


class RoomBookingForm(forms.ModelForm):
    """A single room booking slot for a Showing (room + time window + notes).

    start_time / end_time are time-only fields; the showing's local date is
    combined with them on save.  date_offset shifts the date relative to the
    Showing's date (0 = same day, -1 = day before, +1 = day after).
    """

    date_offset = forms.TypedChoiceField(
        choices=[(0, "Same day"), (-1, "Day before"), (1, "Day after")],
        coerce=int,
        initial=0,
        required=False,
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
        label="Day",
    )
    start_time = forms.TimeField(
        widget=forms.TimeInput(
            attrs={"type": "time", "class": "form-control form-control-sm"},
            format="%H:%M",
        ),
        label="Start",
    )
    end_time = forms.TimeField(
        required=False,
        widget=forms.TimeInput(
            attrs={"type": "time", "class": "form-control form-control-sm"},
            format="%H:%M",
        ),
        label="End",
    )

    class Meta:
        model = toolkit.diary.models.RoomBooking
        fields = ("room", "date_offset", "notes")
        widgets = {
            "notes": forms.TextInput(
                attrs={
                    "placeholder": "e.g. Tech setup only, not public",
                    "class": "form-control form-control-sm",
                }
            ),
        }
        labels = {"notes": "Notes (optional)"}

    def __init__(self, *args, showing_date=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.showing_date = showing_date
        # Pre-populate time and offset fields from existing instance
        if self.instance and self.instance.pk and self.instance.start:
            import django.utils.timezone as dj_tz

            self.initial["start_time"] = dj_tz.localtime(
                self.instance.start
            ).strftime("%H:%M")
            if self.instance.end:
                self.initial["end_time"] = dj_tz.localtime(
                    self.instance.end
                ).strftime("%H:%M")
            self.initial["date_offset"] = self.instance.date_offset

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.showing_date and self.cleaned_data.get("start_time"):
            import django.utils.timezone as dj_tz

            tz = dj_tz.get_current_timezone()
            offset = self.cleaned_data.get("date_offset") or 0
            actual_date = self.showing_date + datetime.timedelta(days=offset)
            instance.start = dj_tz.make_aware(
                datetime.datetime.combine(
                    actual_date, self.cleaned_data["start_time"]
                ),
                tz,
            )
            end_t = self.cleaned_data.get("end_time")
            instance.end = (
                dj_tz.make_aware(
                    datetime.datetime.combine(actual_date, end_t), tz
                )
                if end_t
                else None
            )
        if commit:
            instance.save()
            self.save_m2m()
        return instance


RoomBookingInlineFormSet = inlineformset_factory(
    toolkit.diary.models.Showing,
    toolkit.diary.models.RoomBooking,
    form=RoomBookingForm,
    extra=0,
    can_delete=True,
    min_num=0,
)


class EventBudgetLineForm(forms.ModelForm):
    """A single budget row (category/item, estimate, actual).

    category/item/direction/order/estimate_source are hidden: they're set
    programmatically by sync_budget_lines_for_event() and by the
    budget-grid's "override" JS, not free-text-editable -- letting a
    programmer silently rename a category would defeat the point of the
    fixed, collectively-agreed category templates. estimate_gbp is shown
    read-only (via the template) for derived rows until "override" unlocks
    it; item is unhidden for ad-hoc rows added via "Add item".
    """

    class Meta:
        model = toolkit.diary.models.EventBudgetLine
        fields = (
            "direction",
            "category",
            "item",
            "estimate_gbp",
            "estimate_source",
            "actual_gbp",
            "notes",
            "order",
        )
        widgets = {
            "direction": forms.HiddenInput(),
            "category": forms.HiddenInput(),
            "item": forms.TextInput(
                attrs={
                    "class": "form-control form-control-sm budget-item-input",
                    "placeholder": "Item (optional)",
                }
            ),
            "estimate_source": forms.HiddenInput(),
            "order": forms.HiddenInput(),
            "estimate_gbp": forms.NumberInput(
                attrs={
                    "step": "0.01",
                    "min": "0",
                    "class": "form-control form-control-sm budget-estimate-input",
                }
            ),
            "actual_gbp": forms.NumberInput(
                attrs={
                    "step": "0.01",
                    "min": "0",
                    "class": "form-control form-control-sm budget-actual-input",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-control form-control-sm",
                    "rows": 2,
                    "wrap": "soft",
                }
            ),
        }


EventBudgetLineInlineFormSet = inlineformset_factory(
    toolkit.diary.models.Event,
    toolkit.diary.models.EventBudgetLine,
    form=EventBudgetLineForm,
    extra=0,
    can_delete=True,
)


def _target_month_choices():
    """Generate (YYYY-MM, "Month YYYY") choices for the next 18 months."""
    today = datetime.date.today()
    choices = [("", "— no target month —")]
    for i in range(18):
        month = today.month - 1 + i
        year = today.year + month // 12
        month = month % 12 + 1
        d = datetime.date(year, month, 1)
        choices.append((d.strftime("%Y-%m"), d.strftime("%B %Y")))
    return choices


class NewEventForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.form_class = "form-horizontal"
        self.helper.label_class = "col-sm-2"
        self.helper.field_class = "col-sm-10"
        self.helper.layout = Layout(
            Field(
                "entry_mode"
            ),  # renders as hidden input; card UI is in the template
            HTML(
                '<div class="new-event-zone new-event-zone--required">'
                '<h3 class="new-event-zone__title">Book it now</h3>'
                '<p class="new-event-zone__hint text-muted">'
                "A placeholder with these four fields is enough to hold a space on the calendar. "
                "Everything else can be filled in from the Event Hub after creating."
                "</p>"
            ),
            Field("event_name"),
            Field("event_template"),
            HTML(
                '<div class="form-group row" id="template-preview-row" style="display:none">'
                '<div class="col-sm-2"></div>'
                '<div class="col-sm-10"><div id="template-preview"></div></div>'
                "</div>"
            ),
            Field("dates"),
            HTML('<div id="target-month-row">'),
            Field("target_month"),
            HTML("</div>"),
            Field("start_time"),
            HTML("</div>"),
            HTML(
                '<div class="new-event-zone new-event-zone--optional">'
                '<h3 class="new-event-zone__title">'
                'Details <small class="text-muted fw-normal">&mdash; amend any time from the Event Hub</small>'
                "</h3>"
            ),
            Field("duration"),
            Field("booked_by"),
            Field("private"),
            Field("outside_hire"),
            Field("discounted"),
            HTML("</div>"),
        )

    ENTRY_MODE_QUEUE = "queue"
    ENTRY_MODE_STANDING = "standing"
    ENTRY_MODE_TENTATIVE = "tentative"
    ENTRY_MODE_CHOICES = [
        ("queue", "Needs meeting approval"),
        ("standing", "Regular / standing event"),
        ("tentative", "Tentative placeholder"),
    ]
    entry_mode = forms.ChoiceField(
        choices=ENTRY_MODE_CHOICES,
        initial="queue",
        widget=forms.HiddenInput,
        label="",
    )

    event_name = forms.CharField(min_length=1, max_length=256, required=True)
    event_template = forms.ModelChoiceField(
        queryset=toolkit.diary.models.EventTemplate.objects.all(),
        required=True,
    )
    dates = forms.CharField(
        widget=MultiDatePickerWidget(),
        label="Date(s)",
        required=False,
        help_text="Optional — leave blank if the date is still TBC. Dates can be added later from the Event Hub.",
    )
    start_time = forms.TimeField(
        widget=forms.TimeInput(attrs={"type": "time"}),
        label="Start time",
        required=False,
        initial=datetime.time(20, 0),
    )
    duration = forms.TimeField(required=True, initial=datetime.time(hour=1))
    booked_by = forms.CharField(min_length=1, max_length=64, required=True)
    target_month = forms.ChoiceField(
        choices=_target_month_choices,
        label="Target month",
        required=False,
        help_text="Which month are you roughly targeting? Shown in the diary to help plan the programme.",
    )
    private = forms.BooleanField(required=False)
    outside_hire = forms.BooleanField(required=False)
    # confirmed = forms.BooleanField(required=False)
    discounted = forms.BooleanField(required=False)

    def clean_target_month(self):
        # ChoiceField gives us YYYY-MM; normalise to the 1st of that month.
        raw = (self.cleaned_data.get("target_month") or "").strip()
        if not raw:
            return None
        if len(raw) == 7:
            raw = raw + "-01"
        try:
            return datetime.date.fromisoformat(raw)
        except ValueError:
            raise forms.ValidationError("Select a valid month.")

    def clean_dates(self):
        raw = self.cleaned_data.get("dates", "").strip()
        if not raw:
            return []
        parsed = []
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                parsed.append(datetime.date.fromisoformat(part))
            except ValueError:
                raise forms.ValidationError(
                    "Unrecognised date: {!r}. Expected YYYY-MM-DD.".format(
                        part
                    )
                )
        if len(parsed) > _MAX_BATCH_SHOWINGS:
            raise forms.ValidationError(
                "Maximum {} dates.".format(_MAX_BATCH_SHOWINGS)
            )
        return sorted(set(parsed))

    def clean(self):
        cleaned = super().clean()
        dates = cleaned.get("dates")
        start_time = cleaned.get("start_time")
        if dates and not start_time:
            self.add_error(
                "start_time", "Select a start time for the date(s) you chose."
            )
        if dates and start_time:
            now = timezone.now()
            past = [
                d
                for d in dates
                if timezone.make_aware(
                    datetime.datetime.combine(d, start_time)
                )
                <= now
            ]
            if past:
                date_strs = ", ".join(d.strftime("%-d %b %Y") for d in past)
                raise forms.ValidationError(
                    "The following dates are in the past: {}.".format(
                        date_strs
                    )
                )
        return cleaned


class QuickCreateOpenSessionForm(forms.Form):
    """Minimal form for a keyholder to announce the building is open."""

    date = forms.DateField(
        widget=forms.DateInput(
            attrs={"type": "date", "class": "form-control"}
        ),
        help_text="Which day? Defaults to today.",
    )
    opens_at = forms.TimeField(
        widget=forms.TimeInput(
            attrs={"type": "time", "class": "form-control"}
        ),
        initial=datetime.time(14, 0),
        help_text="When will you open up?",
    )
    closes_at = forms.TimeField(
        widget=forms.TimeInput(
            attrs={"type": "time", "class": "form-control"}
        ),
        initial=datetime.time(18, 0),
        help_text="When will you be locking up? Volunteers need to be out by this time.",
    )
    note = forms.CharField(
        max_length=256,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "e.g. Print room is free all day",
            }
        ),
        help_text="Optional — anything useful for people dropping in.",
    )


class MailoutForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.html_mailout_enabled = kwargs.pop("html_mailout_enabled")
        super().__init__(*args, **kwargs)
        if not self.html_mailout_enabled:
            del self.fields["send_html"]
            del self.fields["body_html"]

    send_html = forms.BooleanField(
        label="Send HTML mailout", initial=True, required=False
    )

    subject = forms.CharField(max_length=128, required=True, label_suffix="")

    body_text = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={"wrap": "soft", "cols": 80}),
    )

    body_html = forms.CharField(
        required=False,
        widget=HtmlTextarea(
            enable_tables=True, enable_iframes=False, height="120ex"
        ),
    )

    def clean(self):
        cleaned_data = super().clean()
        send_html = cleaned_data.get("send_html")
        body_html = cleaned_data.get("body_html")
        if send_html and not body_html:
            raise forms.ValidationError(
                "HTML body is empty. "
                "If you do not want to send an HTML email unset the 'Send HTML Mailout' option"
            )


class SearchForm(forms.Form):
    search_term = forms.CharField(
        label="Search for", required=False, widget=forms.widgets.SearchInput()
    )
    start_date = forms.DateTimeField(label="Search from", required=False)
    end_date = forms.DateTimeField(label="Search to", required=False)
    search_in_descriptions = forms.BooleanField(
        label="Also search event descriptions", required=False
    )

    def clean(self):
        cleaned_data = super().clean()

        # Check that either a search term or a search start or end date is
        # supplied:
        if len(cleaned_data.get("search_term", "").strip()) == 0 and not (
            cleaned_data.get("start_date") or cleaned_data.get("end_date")
        ):
            raise forms.ValidationError(
                "Must give either a search term or a " "date range"
            )

        return cleaned_data


class NewPrintedProgrammeForm(forms.ModelForm):
    # A custom form, so as to present a month/year choice for the date (if the
    # normal Date select is used there's no trivial way to hide the choice of
    # day of month - plus this allows the available range of years to be
    # limited to Cube founding through next year)

    year = forms.ChoiceField(
        choices=[
            (y, y)
            for y in range(
                settings.DAWN_OF_TIME, datetime.date.today().year + 2
            )
        ],
        initial=datetime.date.today().year,
    )
    # Use 'form_month' to avoid conflicting with 'month' field on the
    # underlying model -- see comment above.
    form_month = forms.ChoiceField(
        label="Month",
        choices=(list(zip(range(13), calendar.month_name))[1:]),
        initial=datetime.date.today().month,
    )

    class Meta:
        model = toolkit.diary.models.PrintedProgramme
        fields = ("form_month", "year", "programme", "designer", "notes")

    def clean(self):
        cleaned_data = super().clean()

        # Sets the "month" field on the model from the form data
        try:
            programme_month = datetime.date(
                int(cleaned_data["year"]), int(cleaned_data["form_month"]), 1
            )
        except (KeyError, ValueError, TypeError):
            raise forms.ValidationError(
                "Invalid/missing value for year " "and/or month"
            )

        self.instance.month = programme_month

        return cleaned_data


class SiteConfigurationForm(forms.ModelForm):
    stats_training_tag_slugs = forms.MultipleChoiceField(
        choices=[],  # populated in __init__ from EventTag queryset
        required=False,
        label="Exclude these event tags from shift counts",
        help_text=(
            "Events tagged with any of these are not counted as confirmed shifts on the "
            "volunteer stats page. Use this to keep induction sessions and training events "
            "separate from the programming eligibility total."
        ),
        widget=forms.CheckboxSelectMultiple(
            attrs={"class": "list-unstyled ps-0 mt-1"}
        ),
    )

    class Meta:
        model = SiteConfiguration
        # Auto-derive the form field set from the model `_meta` so adding a
        # SiteConfiguration field never requires also listing it here. The
        # grouping/ordering for the Panopticon edit page lives in
        # `SITE_CONFIG_FIELD_GROUPS` (see site_config.py), not in this Meta.
        exclude = ("id",)
        widgets = {
            "programme_accent_colour": forms.TextInput(
                attrs={
                    "type": "color",
                    "class": "form-control form-control-sm",
                    "style": "width:60px;height:32px;padding:2px;",
                }
            ),
            "breakeven_guidance_note": forms.Textarea(
                attrs={"rows": 3, "class": "form-control"}
            ),
            "films_start_on_time_banner_text": forms.Textarea(
                attrs={"rows": 3, "class": "form-control"}
            ),
            "rota_clear_email_prompt_text": forms.Textarea(
                attrs={"rows": 3, "class": "form-control"}
            ),
            "images_start_date": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
            "banner_text": forms.Textarea(
                attrs={"rows": 3, "class": "form-control"}
            ),
            "collectives_intro": HtmlTextarea(),
            "donations_intro": HtmlTextarea(),
            "ticket_link_guidance_html": HtmlTextarea(),
            "bulletin_guidance": forms.Textarea(
                attrs={"rows": 6, "class": "form-control"}
            ),
            "eventlink_extra_allowed_domains": forms.Textarea(
                attrs={"rows": 4, "class": "form-control font-monospace"}
            ),
            "age_rating_choices": AgeRatingChoicesWidget(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tag_choices = [
            (tag.slug, tag.name) for tag in EventTag.objects.order_by("name")
        ]
        self.fields["stats_training_tag_slugs"].choices = tag_choices
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(
                widget, (AgeRatingChoicesWidget, forms.CheckboxSelectMultiple)
            ):
                pass  # these widgets manage their own markup; don't inject form-control
            else:
                existing = widget.attrs.get("class", "")
                if "form-control" not in existing:
                    widget.attrs["class"] = (
                        existing + " form-control"
                    ).strip()

    def clean_omdb_api_key(self):
        key = self.cleaned_data.get("omdb_api_key", "").strip()
        if not key:
            return key
        if self.instance.pk and key == self.instance.omdb_api_key:
            # Unchanged — don't re-test OMDb on every unrelated settings save.
            return key

        import urllib.error

        from toolkit.diary.omdb import OmdbAuthError, OmdbRateLimitError, verify_api_key

        try:
            verify_api_key(key)
        except OmdbAuthError:
            raise forms.ValidationError(
                "OMDb rejected this API key. Check it's correct and active at "
                "https://www.omdbapi.com/apikey.aspx, then try again."
            )
        except OmdbRateLimitError:
            raise forms.ValidationError(
                "Could not verify this key — OMDb says its daily request limit "
                "has already been reached (shared across everyone using this "
                "key). This doesn't necessarily mean the key itself is wrong. "
                "The limit resets at midnight UTC; try saving again after that, "
                "or leave the existing key in place for now."
            )
        except (urllib.error.URLError, ValueError):
            raise forms.ValidationError(
                "Could not reach OMDb to verify this key. Check the server's "
                "network connection and try again."
            )
        return key
