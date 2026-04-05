// human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 4.6"]; status: "#ai-input"
//
// FC6 calendar for the edit diary view.
// Views: dayGridMonth, resourceTimelineWeek, resourceTimelineMonth.
//
// FC3 → FC6 migration notes:
//   - No jQuery dependency for the calendar itself (jQuery still loaded for jeditable)
//   - new FullCalendar.Calendar(el, opts) replaces $('#cal').fullCalendar(opts)
//   - initialView/initialDate replace defaultView/defaultDate
//   - headerToolbar replaces header
//   - datesSet replaces viewRender (fires on every date-range change)
//   - dateClick replaces dayClick; select callback shape changed
//   - eventDidMount replaces eventRender
//   - dayMaxEvents: true replaces eventLimit: true
//   - CSS class .fc-event-title replaces .fc-title
//   - FC6 global bundle injects its own CSS; no separate <link> needed

function init_calendar_view(CSRF_TOKEN, defaultView, defaultDate, django_urls, resources) {
    "use strict";

    var STORAGE_KEY = 'fc6-calendar-view';

    // ── Helpers ──────────────────────────────────────────────────────────────

    function fmtDateDMY(d) {
        return d.getDate() + '-' + (d.getMonth() + 1) + '-' + d.getFullYear();
    }

    function fmtHM(d) {
        return d.getHours() + ':' + d.getMinutes();
    }

    function fmtTimePretty(d) {
        var h = d.getHours();
        var m = d.getMinutes();
        return (h < 10 ? '0' : '') + h + ':' + (m < 10 ? '0' : '') + m;
    }

    function fmtDuration(start, end) {
        var mins = Math.round((end - start) / 60000);
        var h = Math.floor(mins / 60);
        var m = mins % 60;
        if (h > 0 && m > 0) return h + 'h ' + m + 'm';
        if (h > 0) return h + 'h';
        return m + 'm';
    }

    function getStoredView() {
        try {
            var stored = localStorage.getItem(STORAGE_KEY);
            if (stored && isValidView(stored)) {
                return stored;
            }
        } catch (e) {
            console.warn('localStorage not available:', e);
        }
        return 'dayGridMonth';
    }

    function isValidView(viewName) {
        if (resources && resources.length > 0) {
            return ['dayGridMonth', 'resourceTimelineWeek', 'resourceTimelineMonth'].indexOf(viewName) !== -1;
        }
        return viewName === 'dayGridMonth';
    }

    function setStoredView(viewName) {
        try {
            localStorage.setItem(STORAGE_KEY, viewName);
        } catch (e) {}
    }

    // ── URL sync ──────────────────────────────────────────────────────────────

    function syncUrl(view, date) {
        var newUrl;
        if (view.type === 'dayGridMonth' || view.type === 'resourceTimelineMonth') {
            newUrl = django_urls['diary-edit-calendar'] + '/'
                   + date.getFullYear() + '/' + (date.getMonth() + 1) + '/';
        } else {
            newUrl = django_urls['diary-edit-calendar'] + '/'
                   + date.getFullYear() + '/' + (date.getMonth() + 1)
                   + '/' + date.getDate();
        }
        history.replaceState(null, document.title, newUrl);
    }

    // ── Ideas panel (jQuery/jeditable) ────────────────────────────────────────

    function showIdeas(viewStart) {
        var year  = viewStart.getFullYear();
        var month = viewStart.getMonth() + 1;
        $.getJSON(
            django_urls['edit-ideas'] + year + '/' + month + '/',
            function(data) {
                var monthDate = new Date(data.month + 'T00:00:00');
                var now       = new Date();
                var historic  = monthDate < new Date(now.getFullYear(), now.getMonth(), 1);
                var editId    = 'ideas-' + year + '-' + month;
                var label     = monthDate.toLocaleDateString('en-GB', { month: 'long', year: 'numeric' });

                document.getElementById('ideas').innerHTML =
                    '<h3>Ideas for ' + label + ':</h3>'
                    + '<div class="idea' + (historic ? '-historic' : '') + '" id="' + editId + '">'
                    + (data.ideas !== null ? data.ideas : '')
                    + '</div>';

                if (!historic) {
                    $('#' + editId).editable(
                        django_urls['edit-ideas'] + year + '/' + month + '/',
                        {
                            name:    'ideas',
                            placeholder: 'Click to add ideas',
                            submit:  'Save',
                            type:    'textarea',
                            rows:    5,
                            width:   'auto',
                            submitdata: {
                                csrfmiddlewaretoken: CSRF_TOKEN,
                                source: 'inline'
                            }
                        }
                    );
                }
            }
        );
    }

    // ── Main init (deferred until DOM is ready) ───────────────────────────────

    // ── Time-range toggle state for week timeline ─────────────────────────────
    // Cycles: all → hide early (09:00+) → evening only (17:00+) → all
    var TIME_RANGES = [
        { label: 'all hours', min: '00:00:00', max: '24:00:00' },
        { label: '09:00+',    min: '09:00:00', max: '24:00:00' },
        { label: 'evening',   min: '17:00:00', max: '24:00:00' }
    ];
    var timeRangeIdx = 0;

    function _init() {
        var calendarEl = document.getElementById('calendar');
        var calendar;
        var hasResources = resources && resources.length > 0;

        var isMobile = window.innerWidth <= 768;

        var initialView = getStoredView();
        if (!hasResources && initialView !== 'dayGridMonth') {
            initialView = 'dayGridMonth';
        }
        if (isMobile && initialView !== 'dayGridMonth') {
            initialView = 'dayGridMonth';
        }

        var isTouch = ('ontouchstart' in window) || (navigator.maxTouchPoints > 0);

        var calendarOpts = {
            initialView: initialView,
            initialDate: defaultDate,

            schedulerLicenseKey: 'GPL-My-Project-Is-Open-Source',

            headerToolbar: hasResources
                ? {
                    left:   'prev,next today',
                    center: 'title',
                    right:  'dayGridMonth,resourceTimelineWeek,resourceTimelineMonth'
                }
                : {
                    left:   'prev,next today',
                    center: 'title',
                    right:  'dayGridMonth'
                },

            timeZone: false,

            nowIndicator: true,
            dayMaxEvents: true,

            eventTimeFormat: {
                hour:   'numeric',
                minute: '2-digit',
                hour12: false
            },

            events: django_urls['edit-diary-data'],

            selectable: true,

            longPressDelay: isTouch ? 500 : 300,

            scrollTime: '16:00:00',

            eventClick: function(info) {
                info.jsEvent.preventDefault();
                window.open(info.event.url, '_blank');
            },

            dateClick: function(info) {
                if (info.date < new Date()) return;
                if (!info.allDay) return;
                var url = django_urls['add-event'] + '?date=' + fmtDateDMY(info.date);
                if (hasResources && info.resource) {
                    url += '&room=' + info.resource.id;
                }
                window.open(url, '_blank');
            },

            select: function(info) {
                if (info.start < new Date()) {
                    calendar.unselect();
                    return;
                }
                var url = django_urls['add-event'] + '?date=' + fmtDateDMY(info.start);
                if (!info.allDay) {
                    url += '&time=' + fmtHM(info.start);
                    url += '&duration=' + Math.round((info.end - info.start) /1000);
                }
                if (hasResources && info.resource) {
                    url += '&room=' + info.resource.id;
                }
                window.open(url, '_blank');
                calendar.unselect();
            },

            eventDidMount: function(info) {
                var classNames = info.event.classNames || [];
                var statuses   = [];
                if (classNames.indexOf('s_unconfirmed')  !== -1) statuses.push('Unconfirmed');
                if (classNames.indexOf('s_cancelled')    !== -1) statuses.push('Cancelled');
                if (classNames.indexOf('s_private')      !== -1) statuses.push('Private');
                if (classNames.indexOf('s_outside_hire') !== -1) statuses.push('Outside hire');
                if (classNames.indexOf('s_discounted')   !== -1) statuses.push('Discounted');

                // Multi-line tooltip: title, time range, duration, room, statuses
                var lines = [info.event.title];
                var s = info.event.start, e = info.event.end;
                if (s && e) {
                    lines.push(fmtTimePretty(s) + ' – ' + fmtTimePretty(e) + '  (' + fmtDuration(s, e) + ')');
                } else if (s) {
                    lines.push(fmtTimePretty(s));
                }
                var roomResources = info.event.getResources ? info.event.getResources() : [];
                if (roomResources.length > 0) {
                    lines.push(roomResources[0].title);
                }
                if (statuses.length > 0) lines.push(statuses.join(', '));
                info.el.title = lines.join('\n');

                if (statuses.length > 0) {
                    var span       = document.createElement('span');
                    span.className = 'fc-event-status';
                    span.textContent = statuses.join(' · ');
                    var titleEl = info.el.querySelector('.fc-event-title');
                    if (titleEl) titleEl.after(span);
                }
            },

            datesSet: function(info) {
                setStoredView(info.view.type);
                syncUrl(info.view, calendar.getDate());
                showIdeas(info.view.currentStart);
                var ctrl = document.getElementById('time-range-control');
                if (ctrl) {
                    ctrl.style.display = (info.view.type === 'resourceTimelineWeek') ? 'block' : 'none';
                }
            }
        };

        if (hasResources) {
            calendarOpts.resources = resources;
            calendarOpts.resourceAreaWidth = '15%';

            calendarOpts.views = {
                resourceTimelineWeek: {
                    buttonText: 'week (rooms)',
                    slotDuration: '01:00',
                    scrollTime: '16:00:00'
                },
                resourceTimelineMonth: {
                    buttonText: 'month (rooms)',
                    slotDuration: { day: 1 },
                    slotMinWidth: 50,
                    slotLabelContent: function(arg) {
                        var days = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];
                        return {
                            html: '<span style="display:block;font-weight:600;line-height:1.1">'
                                + days[arg.date.getDay()]
                                + '</span><span style="line-height:1.1">'
                                + arg.date.getDate()
                                + '</span>'
                        };
                    }
                }
            };
        }

        calendar = new FullCalendar.Calendar(calendarEl, calendarOpts);
        calendar.render();

        // External time-range toggle (only visible in week timeline view)
        var timeRangeBtn = document.getElementById('time-range-btn');
        if (timeRangeBtn) {
            timeRangeBtn.addEventListener('click', function() {
                timeRangeIdx = (timeRangeIdx + 1) % TIME_RANGES.length;
                var range = TIME_RANGES[timeRangeIdx];
                timeRangeBtn.textContent = range.label;
                calendar.setOption('slotMinTime', range.min);
                calendar.setOption('slotMaxTime', range.max);
            });
        }

        var resizeTimer;
        window.addEventListener('resize', function() {
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(function() {
                calendar.render();
            }, 250);
        });

        var diaryKey = document.getElementById('diary-key');
        if (diaryKey) {
            diaryKey.addEventListener('toggle', function() {
                var ctrl = document.getElementById('controls');
                if (ctrl) ctrl.classList.toggle('controls-collapsed', !diaryKey.open);
                setTimeout(function() { calendar.render(); }, 210);
            });
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', _init);
    } else {
        _init();
    }
}