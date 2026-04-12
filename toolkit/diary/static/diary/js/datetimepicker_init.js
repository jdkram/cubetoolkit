/*
 * Initialise flatpickr on every datetime-local input rendered by the
 * JQueryDateTimePicker widget (identified by the CSS class that
 * crispy-forms derives from the widget class name).
 *
 * flatpickr config:
 *   dateFormat   – machine format written to the hidden original input and
 *                  submitted to Django; must match value_from_datadict's
 *                  T→space normalisation and Django's DATETIME_INPUT_FORMATS.
 *   altInput     – show a separate human-readable display field to the user.
 *   altFormat    – UK date format shown in the display field.
 *   time_24hr    – 24-hour clock (no AM/PM).
 *   allowInput   – let the user type directly into the alt field.
 *   disableMobile (default false) – on touch devices flatpickr defers to the
 *                  native OS picker, which is excellent on iOS/Android.
 */
document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("input.jquerydatetimepicker").forEach(function (el) {
        flatpickr(el, {
            enableTime:  true,
            time_24hr:   true,
            dateFormat:  "Y-m-dTH:i",   // value Django receives: 2026-03-05T19:00
            altInput:    true,
            altFormat:   "d/m/Y H:i",   // what the user sees:    05/03/2026 19:00
            allowInput:  true,
        });
    });
});
