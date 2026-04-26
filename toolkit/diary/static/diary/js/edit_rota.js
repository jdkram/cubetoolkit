function edit_rota(jQuery, rota_edit_base_url, edit_rota_notes_url_prefix, vol_email, CSRF_TOKEN, rota_clear_email_prompt_enabled) {
    "use strict";
    var $ = jQuery;

    function parse_date_from_control(control_id) {
        // Native date inputs give ISO format "YYYY-MM-DD". Parse without
        // using Date constructor string parsing (avoids UTC-vs-local issues).
        var parts = $(control_id)[0].value.split("-");
        return new Date(
            parseInt(parts[0], 10),
            parseInt(parts[1], 10) - 1,
            parseInt(parts[2], 10)
        );
    }

    function dateRangeSelected() {
        var from_date = parse_date_from_control('#id_from_date'),
            to_date = parse_date_from_control('#id_to_date'),
            days_ahead = Math.ceil(
                (to_date.getTime() - from_date.getTime()) / 86400000
            );
        if (days_ahead <= 0) {
            days_ahead = 0;
        }
        window.location.href = rota_edit_base_url + "/" +
            (from_date.getFullYear()) + "/" + (from_date.getMonth() + 1) +
            "/" + from_date.getDate() + "?daysahead=" + days_ahead;
    }

    function configureDatePickerControls() {
        // Restrict date inputs to today or later, then navigate on any change.
        var today = new Date().toISOString().split('T')[0];
        $('#id_from_date, #id_to_date').attr('min', today);

        $('#id_from_date, #id_to_date').on('change', function() {
            if ($('#id_from_date')[0].value && $('#id_to_date')[0].value) {
                dateRangeSelected();
            }
        });
        $('#daterange')[0].onsubmit = function() {
            dateRangeSelected();
            return false;
        };
    }

    function nameEditedCallback(value) {
        if (value === "" && this.revert !== "" && rota_clear_email_prompt_enabled) {
            window.alert("Rota entry cleared.\nPlease consider emailing " +
                         vol_email +
                         " to say that the shift needs covering.");
        }
    }

    function configureRotaNameEditInPlaceControls() {
        $('.rota_name').editable('', {
            width: "25%",
            placeholder: '<span class="na">Click to edit</span>',
            submit: "Save",
            submitdata: {
                csrfmiddlewaretoken: CSRF_TOKEN
            },
            callback: nameEditedCallback
        });
    }

    function configureRotaNotesEditInPlaceControls() {
        var showing_id_re = /showing_rota_notes_(\d+)/;

        $('.showing_rota_notes span').each(function () {
            var showing_id,
                element = $(this),
                showing_id_match = showing_id_re.exec(element.attr('id'));

            if (showing_id_match) {
                showing_id = showing_id_match[1];
                element.editable(
                    edit_rota_notes_url_prefix + showing_id + "/rota_notes/",
                    {
                        name: 'rota_notes',
                        type: 'textarea',
                        rows: 5,
                        width: '90%',
                        placeholder: '<span class="na">General notes (click to edit)</span>',
                        submit: 'Save',
                        submitdata: {
                            csrfmiddlewaretoken: CSRF_TOKEN
                        },
                        // Decode HTML entities before populating the textarea.
                        // jeditable populates the editor from $(element).html()
                        // (raw innerHTML), which contains Django's auto-escaped
                        // entities (& → &amp;, < → &lt; etc.). Without this,
                        // those entities appear as literal text in the editor
                        // and get double-encoded on the next save.
                        //
                        // IMPORTANT: use the 'data' option, NOT 'loaddata'.
                        // 'loaddata' as a function only runs when 'loadurl' is
                        // set (it provides extra POST params for the AJAX load).
                        // 'data' as a function is the value-transform callback.
                        //
                        // IMPORTANT: the server response must be returned as
                        // unescaped plain text. After save, jeditable calls
                        // $(self).html(result) — the browser's innerHTML setter
                        // re-encodes & to &amp;, so the next 'data' call sees
                        // &amp; and decodes it correctly. If the server returns
                        // escape(value) instead, jeditable's .html() call
                        // double-encodes it (&amp; → &amp;amp;).
                        data: function(value) {
                            return value
                                .replace(/&amp;/g,  '&')
                                .replace(/&lt;/g,   '<')
                                .replace(/&gt;/g,   '>')
                                .replace(/&quot;/g, '"')
                                .replace(/&#x27;/g, "'")
                                .replace(/&#39;/g,  "'");
                        }
                    }
                );
            }
        });
    }

    $(document).ready(function() {
        configureDatePickerControls();
        configureRotaNameEditInPlaceControls();
        configureRotaNotesEditInPlaceControls();
    });
}
