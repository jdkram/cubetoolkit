import json

from django import forms
from django.utils.html import format_html, escape
from django.utils.safestring import mark_safe


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


class AgeRatingChoicesWidget(forms.Widget):
    """
    Renders the age_rating_choices JSONField as a friendly table of rows
    (one row per rating, each with a short code and a display label), rather
    than a raw JSON textarea.

    Serialises back to JSON on submit via value_from_datadict.
    """

    def render(self, name, value, attrs=None, renderer=None):
        if isinstance(value, str):
            try:
                entries = json.loads(value) if value else []
            except (json.JSONDecodeError, TypeError):
                entries = []
        elif isinstance(value, list):
            entries = value
        else:
            entries = []

        widget_id = (attrs or {}).get("id", f"id_{name}")
        rows_html = ""
        for i, entry in enumerate(entries):
            v = escape(entry.get("value", ""))
            l = escape(entry.get("label", ""))
            rows_html += (
                f'<tr class="arc-row">'
                f'<td><input type="text" name="{name}_value_{i}" value="{v}" '
                f'class="form-control form-control-sm" placeholder="U" '
                f'aria-label="Rating code"></td>'
                f'<td><input type="text" name="{name}_label_{i}" value="{l}" '
                f'class="form-control form-control-sm" placeholder="U — Universal" '
                f'aria-label="Display label"></td>'
                f'<td><button type="button" class="btn btn-sm btn-outline-danger arc-remove" '
                f'aria-label="Remove row">&times;</button></td>'
                f'</tr>'
            )

        html = f"""
<table class="table table-sm table-bordered arc-table" id="{widget_id}" style="max-width:38rem;">
  <thead class="table-light">
    <tr>
      <th style="width:8rem;">Code</th>
      <th>Display label</th>
      <th style="width:3rem;"></th>
    </tr>
  </thead>
  <tbody id="{widget_id}_tbody">
    {rows_html}
  </tbody>
</table>
<button type="button" class="btn btn-sm btn-outline-secondary arc-add" data-target="{widget_id}_tbody" data-name="{name}">
  + Add rating
</button>
<script>
(function () {{
  var tbody = document.getElementById("{widget_id}_tbody");

  function reindex() {{
    tbody.querySelectorAll("tr.arc-row").forEach(function(row, i) {{
      row.querySelectorAll("input")[0].name = "{name}_value_" + i;
      row.querySelectorAll("input")[1].name = "{name}_label_" + i;
    }});
  }}

  tbody.addEventListener("click", function(e) {{
    if (e.target.classList.contains("arc-remove")) {{
      e.target.closest("tr").remove();
      reindex();
    }}
  }});

  document.querySelector(".arc-add[data-target='{widget_id}_tbody']").addEventListener("click", function() {{
    var count = tbody.querySelectorAll("tr.arc-row").length;
    var row = document.createElement("tr");
    row.className = "arc-row";
    row.innerHTML =
      "<td><input type=\\"text\\" name=\\"{name}_value_" + count + "\\" " +
      "class=\\"form-control form-control-sm\\" placeholder=\\"U\\" aria-label=\\"Rating code\\"></td>" +
      "<td><input type=\\"text\\" name=\\"{name}_label_" + count + "\\" " +
      "class=\\"form-control form-control-sm\\" placeholder=\\"U — Universal\\" aria-label=\\"Display label\\"></td>" +
      "<td><button type=\\"button\\" class=\\"btn btn-sm btn-outline-danger arc-remove\\" " +
      "aria-label=\\"Remove row\\">&times;</button></td>";
    tbody.appendChild(row);
  }});
}})();
</script>
"""
        return mark_safe(html)

    def value_from_datadict(self, data, files, name):
        entries = []
        i = 0
        while True:
            val_key = f"{name}_value_{i}"
            if val_key not in data:
                break
            code = data[val_key].strip()
            label = data.get(f"{name}_label_{i}", "").strip()
            if code:
                entries.append({"value": code, "label": label or code})
            i += 1
        return json.dumps(entries)
