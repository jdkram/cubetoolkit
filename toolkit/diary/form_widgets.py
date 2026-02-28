from django import forms


class ChosenSelectMultiple(forms.SelectMultiple):
    """
    SelectMultiple widget using the "Chosen" jquery plugin:
    http://harvesthq.github.io/chosen/
    """

    template_name = "widgets/chosenselectmultiple.html"

    class Media:
        # Define media (CSS & JS) used by this control. To include this
        # automatically the template containing the form must have the
        # {{ form.media }} tag
        js = ("js/lib/chosen.jquery.js",)
        css = {
            "all": ("css/lib/chosen.min.css",),
        }

    def __init__(self, *args, **kwargs):
        self.width = kwargs.pop("width", None)
        super().__init__(*args, **kwargs)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"].update(
            {
                "width": self.width,
            }
        )
        return context


class HtmlTextarea(forms.Textarea):
    """TextArea widget overloaded to provide a wysiwyg HTML editor, using the
    'CKEditor' editor
    """

    template_name = "widgets/htmltextarea.html"

    class Media:
        # Define media (CSS & JS) used by this control. To include this
        # automatically the template containing the form must have the
        # {{ form.media }} tag
        js = ("js/lib/ckeditor/ckeditor.js",)

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
