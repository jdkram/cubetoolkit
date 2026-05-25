from django import forms


class TagPillSelect(forms.CheckboxSelectMultiple):
    """
    Renders a ManyToMany tag field as a row of Bootstrap pill-badge toggles.

    Each tag is a hidden checkbox wrapped in a <label>.  CSS drives the
    checked/unchecked visual state via `input:checked + span` — no JS needed.

    The `pill_select = True` class attribute is checked by the project-level
    override of crispy-bootstrap4's checkboxselectmultiple.html template to
    switch to pill rendering (crispy normally ignores widget.template_name).
    """

    template_name = "widgets/tagpillselect.html"
    pill_select = True


class ChosenSelectMultiple(forms.SelectMultiple):
    """
    SelectMultiple widget. Formerly used the deprecated 'Chosen' jQuery plugin;
    now renders as a standard HTML <select multiple>.
    """

    def __init__(self, *args, **kwargs):
        kwargs.pop("width", None)  # width was a Chosen option; no longer used
        super().__init__(*args, **kwargs)


class HtmlTextarea(forms.Textarea):
    """TextArea widget providing a WYSIWYG HTML editor via Quill 2."""

    template_name = "widgets/htmltextarea.html"

    class Media:
        css = {
            "all": ("css/lib/quill.snow.css",),
        }
        js = ("js/lib/quill/quill.js",)

    def build_attrs(self, base_attrs, extra_attrs=None):
        # Remove `required` — the textarea is CSS-hidden by Quill; let
        # server-side validation handle the required check instead.
        attrs = super().build_attrs(base_attrs, extra_attrs)
        attrs.pop("required", None)
        return attrs

    def __init__(self, *args, **kwargs):
        self.enable_tables = kwargs.pop("enable_tables", False)
        self.enable_iframes = kwargs.pop("enable_iframes", True)
        self.height = kwargs.pop("height", None)
        super().__init__(*args, **kwargs)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["enable_tables"] = self.enable_tables
        context["widget"]["enable_iframes"] = self.enable_iframes
        if self.height:
            context["widget"]["height"] = self.height
        return context


class MultiDatePickerWidget(forms.TextInput):
    """Text input enhanced by flatpickr in multiple-date mode.

    Submits a comma-separated list of ISO dates (YYYY-MM-DD).  The form field
    using this widget is responsible for parsing and validating that string.
    """

    class Media:
        css = {
            "all": ("css/lib/flatpickr.min.css",),
        }
        js = (
            "js/lib/flatpickr.min.js",
            "diary/js/multidatepicker_init.js",
        )

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("attrs", {})
        kwargs["attrs"]["class"] = (
            kwargs["attrs"].get("class", "") + " flatpickr-multidate"
        ).strip()
        kwargs["attrs"]["autocomplete"] = "off"
        kwargs["attrs"]["placeholder"] = "Click to select dates…"
        super().__init__(*args, **kwargs)


class JQueryDateTimePicker(forms.DateTimeInput):
    """
    datetime-local input enhanced by flatpickr on desktop.

    On desktop browsers flatpickr replaces the native datetime-local UI with a
    combined calendar + time spinner popup (much nicer than Firefox's split
    date/time text fields).  On mobile devices flatpickr defers to the native
    OS picker automatically (disableMobile defaults to false).

    The underlying input type stays datetime-local so there is a reasonable
    fallback if JS is unavailable.
    """

    input_type = "datetime-local"

    class Media:
        css = {
            "all": ("css/lib/flatpickr.min.css",),
        }
        js = (
            "js/lib/flatpickr.min.js",
            "diary/js/datetimepicker_init.js",
        )

    def __init__(self, *args, **kwargs):
        if "format" not in kwargs:
            kwargs["format"] = "%Y-%m-%dT%H:%M"
        super().__init__(*args, **kwargs)

    def value_from_datadict(self, data, files, name):
        # datetime-local submits "YYYY-MM-DDTHH:MM"; normalise the T to a
        # space so Django's DATETIME_INPUT_FORMATS can parse it.
        # Guard: if data already holds a Python datetime object (e.g. set
        # programmatically), leave it untouched.
        value = super().value_from_datadict(data, files, name)
        if isinstance(value, str):
            value = value.replace("T", " ", 1)
        return value
