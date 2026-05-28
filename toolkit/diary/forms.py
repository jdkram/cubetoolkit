import datetime
import calendar

from django import forms
from django.forms import inlineformset_factory
import django.db.models
from django.conf import settings
from crispy_forms.helper import FormHelper

# Custom form widgets:
from toolkit.diary.form_widgets import (
    HtmlTextarea,
    JQueryDateTimePicker,
    MultiDatePickerWidget,
    ChosenSelectMultiple,
    TagPillSelect,
)

import toolkit.diary.models
from toolkit.diary.models import SiteConfiguration, get_site_config
from collections import OrderedDict

from toolkit.diary.validators import validate_in_future


class RoleForm(forms.ModelForm):
    class Meta:
        model = toolkit.diary.models.Role
        fields = (
            "name",
            "standard",
            "description",
            "beginner_friendly",
            "wheelchair_accessible",
            "keyholder_only",
        )


class EventTemplateForm(forms.ModelForm):
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
                        "e.g. '\u00A30 Full / \u00A30 Concession'"
                    ),
                }
            ),
            "film_information": forms.TextInput(
                attrs={
                    "placeholder": "e.g. Dir: [director], 1990, USA, 120 mins, Cert: 15",
                }
            ),
        }


class EventTemplateRoleForm(forms.ModelForm):
    class Meta:
        model = toolkit.diary.models.EventTemplateRole
        fields = ("role", "count")
        widgets = {
            "count": forms.NumberInput(attrs={"min": 1, "max": 20, "style": "width:4em"}),
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


class DiaryIdeaForm(forms.ModelForm):
    class Meta:
        model = toolkit.diary.models.DiaryIdea
        fields = ("ideas",)


class EventForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.form_class = "form-horizontal"
        self.helper.label_class = "col-sm-2"
        self.helper.field_class = "col-sm-10"

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
            "notes": forms.Textarea(
                attrs={
                    "wrap": "soft",
                    "rows": 5,  # Arbitrary
                    "placeholder": "Programmer's notes - not visible to public",
                }
            ),
            "approved_at_meeting_date": forms.DateInput(attrs={"type": "date"}),
            "pricing": forms.TextInput(
                attrs={
                    "placeholder": (
                        "e.g. '\u00A30 Full / \u00A30 Concession' "
                        "or '\u00A30 advance, \u00A30 on the door'"
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
            "notes",
            "approval_type",
            "approved_at_meeting_date",
            "meeting_name",
            "meeting_minutes_url",
            "duration",
            "outside_hire",
            "hire_name",
            "private",
            "copy",
            "copy_summary",
            "terms",
        )

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
        if cleaned_data.get("approval_type") == toolkit.diary.models.Event.APPROVAL_MEETING:
            if not cleaned_data.get("approved_at_meeting_date"):
                self.add_error(
                    "approved_at_meeting_date",
                    "Please enter the date of the meeting at which this was approved.",
                )
        if self.instance.all_showings_confirmed():
            terms = cleaned_data.get("terms", "")
            terms_word_count = len(terms.split())

            terms_not_required = cleaned_data.get(
                "tags"
            ).contains_tag_to_not_need_terms()

            min_words = get_site_config().programme_event_terms_min_words
            if (
                terms_word_count < min_words
                and not terms_not_required
            ):
                msg = (
                    f"Event terms for confirmed event '{self.instance.name}' "
                    f"are missing or too short. Please enter at least "
                    f"{min_words} words."
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
                attrs={"rows": 3, "style": "resize: vertical;"}
            ),
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
        self.helper.form_class = "form-horizontal"
        self.helper.label_class = "col-sm-2"
        self.helper.field_class = "col-sm-10"

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
        }

    def clean_confirmed(self):
        confirmed = self.cleaned_data["confirmed"]
        if (
            confirmed
            and self.instance.event_id
            and self.instance.event.terms_required()
            and not self.instance.event.terms_long_enough()
        ):

            raise forms.ValidationError(
                "Events require terms information "
                f'(unless they are tagged with one of {"/".join(sorted(settings.TAGS_WITHOUT_TERMS))}). '
                "Please add more details."
            )
        return confirmed

    def clean(self):
        if self.instance.original_start_in_past():
            self.cleaned_data["start"] = self.instance.start
            raise forms.ValidationError("Cannot amend a historic booking")
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

    # All available roles:
    roles = toolkit.diary.models.Role.objects.order_by("name")

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
                    "Unrecognised date: {!r}. Expected YYYY-MM-DD.".format(part)
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
            past = [d for d in dates if datetime.datetime.combine(d, start_time) < now]
            if past:
                date_strs = ", ".join(d.strftime("%-d %b %Y") for d in past)
                raise forms.ValidationError(
                    f"The following dates are in the past: {date_strs}."
                )
        if cleaned.get("confirmed") and self._event is not None:
            if self._event.terms_required() and not self._event.terms_long_enough():
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
                attrs={"placeholder": "e.g. Event folder, Crew chat…", "class": "form-control form-control-sm"}
            ),
            "url": forms.URLInput(
                attrs={"placeholder": "https://…", "class": "form-control form-control-sm"}
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
                attrs={"placeholder": "e.g. Event folder, Crew chat…", "class": "form-control form-control-sm"}
            ),
            "url": forms.URLInput(
                attrs={"placeholder": "https://…", "class": "form-control form-control-sm"}
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
            "name": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "colour": forms.TextInput(attrs={"type": "color", "class": "form-control form-control-sm", "style": "max-width: 80px; padding: 2px 4px;"}),
            "map_slug": forms.TextInput(attrs={"class": "form-control form-control-sm", "placeholder": "e.g. room-cinema"}),
        }


class RoomBookingForm(forms.ModelForm):
    """A single room booking slot for a Showing (room + time window + notes).

    start_time / end_time are time-only fields; the showing's local date is
    combined with them on save.  The model's start/end DateTimeFields are
    excluded from the form and set programmatically.
    """

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
        fields = ("room", "notes")
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
        # Pre-populate time fields from existing instance
        if self.instance and self.instance.pk and self.instance.start:
            import django.utils.timezone as dj_tz
            self.initial["start_time"] = dj_tz.localtime(self.instance.start).strftime("%H:%M")
            if self.instance.end:
                self.initial["end_time"] = dj_tz.localtime(self.instance.end).strftime("%H:%M")

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.showing_date and self.cleaned_data.get("start_time"):
            import django.utils.timezone as dj_tz
            tz = dj_tz.get_current_timezone()
            instance.start = dj_tz.make_aware(
                datetime.datetime.combine(self.showing_date, self.cleaned_data["start_time"]),
                tz,
            )
            end_t = self.cleaned_data.get("end_time")
            instance.end = (
                dj_tz.make_aware(datetime.datetime.combine(self.showing_date, end_t), tz)
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


class NewEventForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.form_class = "form-horizontal"
        self.helper.label_class = "col-sm-2"
        self.helper.field_class = "col-sm-10"

    room = forms.ModelChoiceField(
        queryset=toolkit.diary.models.Room.objects.all(),
        required=False,
        empty_label="— no room —",
    )
    start = forms.DateTimeField(
        required=True,
        validators=[validate_in_future],
        widget=JQueryDateTimePicker(),
    )
    duration = forms.TimeField(required=True, initial=datetime.time(hour=1))
    number_of_bookings = forms.IntegerField(
        min_value=1,
        max_value=31,
        required=True,
        initial=1,
        help_text="Bookings will be created with the same start time on consecutive days",
    )
    event_name = forms.CharField(min_length=1, max_length=256, required=True)
    event_template = forms.ModelChoiceField(
        queryset=toolkit.diary.models.EventTemplate.objects.all(),
        required=True,
    )
    booked_by = forms.CharField(min_length=1, max_length=64, required=True)
    private = forms.BooleanField(required=False)
    outside_hire = forms.BooleanField(required=False)
    # confirmed = forms.BooleanField(required=False)
    discounted = forms.BooleanField(required=False)


class QuickCreateOpenSessionForm(forms.Form):
    """Minimal form for a keyholder to announce the building is open."""

    date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        help_text="Which day? Defaults to today.",
    )
    opens_at = forms.TimeField(
        widget=forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
        initial=datetime.time(14, 0),
        help_text="When will you open up?",
    )
    closes_at = forms.TimeField(
        widget=forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
        initial=datetime.time(18, 0),
        help_text="When will you be locking up? Volunteers need to be out by this time.",
    )
    note = forms.CharField(
        max_length=256,
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "e.g. Print room is free all day",
        }),
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
    class Meta:
        model = SiteConfiguration
        fields = (
            "films_start_on_time",
            "films_start_on_time_banner_text",
            "rota_show_tags",
            "rota_clear_email_prompt_enabled",
            "rota_clear_email_prompt_text",
            "vols_email",
            "show_archive_images",
            "images_start_date",
            "breakeven_guidance_note",
            "breakeven_fc_standard_threshold",
            "breakeven_fc_music_threshold",
            "max_count_per_role",
            "max_showing_dates_shown",
            "programme_copy_summary_max_chars",
            "programme_event_terms_min_words",
            "programme_media_max_size_mb",
            "mailout_details_days_ahead",
            "mailout_listings_days_ahead",
            "membership_length_days",
            "default_training_expiry_months",
            "volunteer_dormancy_months",
            "rota_gap_min_missing",
            "rota_gap_min_pct",
            "image_copyright_guidance_url",
            "alt_text_guidance_url",
            "access_rider_guidance_url",
            "bulletin_default_expiry_days",
            "bulletin_guidance",
            "bulletin_post_permission",
            "eventlink_extra_allowed_domains",
            "collectives_intro",
            "show_donations_in_public_nav",
            "banner_active",
            "banner_level",
            "banner_text",
            "banner_dismissible",
        )
        widgets = {
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
            "collectives_intro": forms.Textarea(
                attrs={"rows": 4, "class": "form-control"}
            ),
            "eventlink_extra_allowed_domains": forms.Textarea(
                attrs={"rows": 4, "class": "form-control font-monospace"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            else:
                existing = widget.attrs.get("class", "")
                if "form-control" not in existing:
                    widget.attrs["class"] = (existing + " form-control").strip()

