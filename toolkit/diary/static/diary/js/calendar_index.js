function init_calendar_view(jQuery, CSRF_TOKEN, defaultView, defaultDate, django_urls, resources) {
    "use strict";
    var $ = jQuery;

    var currentView = defaultView;
    var currentDate = $.fullCalendar.moment(defaultDate);

    var resources_enabled = resources.length > 0 ? true : false;

    function onEventClick(calEvent, jsEvent, view) {
        window.location.href = calEvent.url;
        return false;
    }

    function showIdeas(intervalStart) {
        $.getJSON(django_urls["edit-ideas"] + intervalStart.format("YYYY/M/"),
            function(data) {
                var monthMoment = moment(data.month, "YYYY-MM-DD");
                var historic = monthMoment.isBefore(moment(), 'month');
                var edit_control_id = 'ideas-' + monthMoment.format("YYYY-M");
                var edit_control_html = '<h3>Ideas for '
                    + monthMoment.format("MMMM YYYY")
                    + ':</h3> <div class="idea'
                    + (historic ? '-historic' : '')
                    + '" id="' + edit_control_id + '">'
                    + (data.ideas !== null ? data.ideas : '')
                    + '</div></p>';

                $('#ideas').html(edit_control_html);

                // XXX: This isn't currently enforced server-side!
                if (!historic) {
                    $('#' + edit_control_id).editable(
                        django_urls["edit-ideas"] + monthMoment.format("YYYY/M/"),
                        {
                            name: 'ideas',
                            placeholder: 'Click to add ideas',
                            submit: "Save",
                            type: 'textarea',
                            rows: 5,
                            width: "auto",
                            submitdata: {
                                csrfmiddlewaretoken: CSRF_TOKEN,
                                source: 'inline',
                            }
                        }
                    );
                }
            }
        );
    }

    function onDayClick(date, jsEvent, view, resource) {
        var url = django_urls["add-event"] + "?date=" + date.format("D-M-YYYY");
        if(date.isBefore(moment())) {
            return;
        }
        if(date.hasTime()) {
            // Timeslot clicks are handled by onSelect; ignore here
            return;
        }
        if(resources_enabled && resource !== null && typeof resource === 'object'
            && resource.hasOwnProperty("id")) {
            url += "&room=" + resource.id;
        }
        window.location.href = url;
    }

    function onSelect(start, end, jsEvent, view, resource) {
        var url = django_urls["add-event"] + "?date=" + start.format("D-M-YYYY");
        var calendar = $('#calendar');
        if(start.isBefore(moment())) {
            calendar.fullCalendar('unselect');
            return;
        }
        if(start.hasTime() && end.hasTime()) {
            url += "&time=" + start.format("H:m");
            url += "&duration=" + (end.unix() - start.unix());
        }
        if(resources_enabled && resource !== null && typeof resource === 'object'
            && resource.hasOwnProperty("id")) {
            url += "&room=" + resource.id;
        }
        window.location.href = url;
    }

    function onViewRender(view, element) {
        var calendar = $('#calendar');
        var newDate = calendar.fullCalendar('getDate');
        if(view.name === 'month' || view.name === 'timelineMonth') {
            var newUrl = django_urls['diary-edit-calendar'] + '/' + newDate.year()
                         + '/' + (newDate.month() + 1) + '/';

            if(!currentDate.isSame(newDate, 'month') || (currentView != view.name)) {
                history.replaceState(null, document.title, newUrl);
            }
        } else if(view.name === "agendaWeek" || view.name === "agendaThreeDay") {
            var newUrl = django_urls['diary-edit-calendar'] + '/' + newDate.year()
                         + '/' + (newDate.month() + 1)
                         + '/' + newDate.date();

            if(!currentDate.isSame(newDate, 'day') || (currentView != view.name)) {
                history.replaceState(null, document.title, newUrl);
            }
        }
        currentView = view.name;
        currentDate = newDate;
        showIdeas(view.intervalStart);
    }

    function init_calendar() {
        var calendar = $('#calendar');
        currentDate = $.fullCalendar.moment(defaultDate);

        // Detect mobile and set default view
        var isMobile = window.innerWidth <= 768;
        var mobileDefaultView = isMobile ? 'month' : defaultView;

        var calendar_options = {
            header: {
                left: 'prev,next today',
                center: 'title',
                right:
                    (resources_enabled && !isMobile ?
                        'agendaThreeDay,agendaWeek,month,timelineMonth'
                        : (resources_enabled ? 'month,timelineMonth' : 'month'))
            },
            allDaySlot: false,
            defaultDate: defaultDate,
            defaultView: mobileDefaultView,
            editable: false,
            selectable: true,
            selectHelper: true,
            // Force events to a single day. It is valid to have a duration >
            // 24hr, but historically we've not done that to indicate multi-day
            // events, so nothing else is expecting it.
            selectConstraint: {
                start: '0:00',
                end: '23:59'
            },
            select: onSelect,
            eventLimit: true,
            timeFormat: 'H:mm',
            scrollTime: '18:00:00',
            nowIndicator: true,
            // The server will provide localised time. Don't mess with them:
            timezone: false,
            views: {
                agendaThreeDay: {
                    type: 'agenda',
                    duration: { days: 3 },
                    groupByResource: true,
                    groupByDateAndResource: true,
                    scrollTime: '10:00:00'
                },
                month: {
                    scrollTime: '10:00:00'
                },
                timelineMonth: {
                    buttonText: 'month timeline',
                }
            },
            events: django_urls["edit-diary-data"],
            eventClick: onEventClick,
            dayClick: onDayClick,
            viewRender: onViewRender,
            // Inject a plain-text status row below the event title for states that
            // CSS alone can't communicate to screen readers (B — accessibility).
            eventRender: function(event, el) {
                var statuses = [];
                if (el.hasClass('s_unconfirmed'))  { statuses.push('Unconfirmed'); }
                if (el.hasClass('s_cancelled'))    { statuses.push('Cancelled'); }
                if (el.hasClass('s_private'))      { statuses.push('Private'); }
                if (el.hasClass('s_outside_hire')) { statuses.push('Outside hire'); }
                if (el.hasClass('s_discounted'))   { statuses.push('Discounted'); }
                if (statuses.length > 0) {
                    el.find('.fc-title').after(
                        $('<span class="fc-event-status">').text(statuses.join(' · '))
                    );
                }
            },
            // Touch event support for mobile
            longPressDelay: 500,
            eventLongPressDelay: 500,
            selectLongPressDelay: 500,
            schedulerLicenseKey: 'GPL-My-Project-Is-Open-Source',
            resourceAreaWidth: "15%"
        };
        if(resources.length) {
            calendar_options.resources = resources;
        }

        calendar.fullCalendar(calendar_options);
    }

    $(document).ready(function() {
        init_calendar();

        // Re-render calendar on resize to handle orientation changes
        var resizeTimer;
        $(window).on('resize', function() {
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(function() {
                $('#calendar').fullCalendar('render');
            }, 250);  // Debounce to avoid excessive re-renders
        });
    });
}
