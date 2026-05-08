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
//
// Filtering (added 2026-04-06):
//   - Tags: multi-select, events must match ANY selected tag
//   - Time of day: all/daytime(0-16)/evening(17+)
//   - Status: Unconfirmed, Private, Outside hire, Cancelled (checkbox toggles)
//   - Name: text search on event title
//   - Rooms: multi-select checkbox (multiroom venues only)

function init_calendar_view(CSRF_TOKEN, defaultView, defaultDate, django_urls, resources, initialFilters) {
    "use strict";

    var STORAGE_KEY = 'fc6-calendar-view';
    var FILTER_STORAGE_KEY = 'fc6-calendar-filters';

    // Filter state (mutable)
    var filterState = initialFilters || {
        timeOfDay: 'all',
        showUnconfirmed: true,
        showPrivate: true,
        showOutsideHire: true,
        showCancelled: true,
        nameQuery: '',
        selectedTags: [],
        visibleRooms: resources ? resources.map(function(r) { return r.id; }) : []
    };

    // Calendar instance (set in _init)
    var calendar;

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
        var valid = ['dayGridMonth', 'timeGridWeek', 'threeDay'];
        if (resources && resources.length > 0) {
            valid.push('resourceTimelineWeek', 'resourceTimelineMonth');
        }
        return valid.indexOf(viewName) !== -1;
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

    // ── Filtering logic ───────────────────────────────────────────────────────

    function eventMatchesFilters(event) {
        var classNames = event.classNames || [];
        var title = (event.title || '').toLowerCase();
        var query = filterState.nameQuery.toLowerCase();

        // Name search filter
        if (query && title.indexOf(query) === -1) {
            return false;
        }

        // Time of day filter
        if (filterState.timeOfDay !== 'all') {
            var hour = event.extendedProps?.hour ?? parseInt(event.start.getHours(), 10);
            if (filterState.timeOfDay === 'daytime' && hour >= 17) {
                return false;
            }
            if (filterState.timeOfDay === 'evening' && hour < 17) {
                return false;
            }
        }

        // Status filters (if unchecked, hide events with that status)
        if (!filterState.showUnconfirmed && classNames.indexOf('s_unconfirmed') !== -1) {
            return false;
        }
        if (!filterState.showPrivate && classNames.indexOf('s_private') !== -1) {
            return false;
        }
        if (!filterState.showOutsideHire && classNames.indexOf('s_outside_hire') !== -1) {
            return false;
        }
        if (!filterState.showCancelled && classNames.indexOf('s_cancelled') !== -1) {
            return false;
        }

        // Tag filter (multi-select: event must have AT LEAST ONE of selected tags)
        if (filterState.selectedTags && filterState.selectedTags.length > 0) {
            var eventTags = event.extendedProps?.tags || [];
            var hasMatchingTag = false;
            for (var i = 0; i < filterState.selectedTags.length; i++) {
                if (eventTags.indexOf(filterState.selectedTags[i]) !== -1) {
                    hasMatchingTag = true;
                    break;
                }
            }
            if (!hasMatchingTag) {
                return false;
            }
        }

        // Room filter (multi-select: event must be in one of visible rooms)
        if (resources && resources.length > 0) {
            var eventRoomId = event.getResources ? event.getResources()[0]?.id : event.extendedProps?.resourceId;
            if (eventRoomId && filterState.visibleRooms.indexOf(parseInt(eventRoomId, 10)) === -1) {
                return false;
            }
        }

        return true;
    }

    function applyFilters() {
        if (!calendar) { return; }

        var allEvents = calendar.getEvents();
        var visibleCount = 0;
        var hiddenCount = 0;

        allEvents.forEach(function(event) {
            var shouldShow = eventMatchesFilters(event);
            if (shouldShow) {
                event.setProp('display', 'auto');
                visibleCount++;
            } else {
                event.setProp('display', 'none');
                hiddenCount++;
            }
        });

        // Update filter count indicator
        var countEl = document.getElementById('active-filter-count');
        if (countEl) {
            var activeFilters = [];
            if (filterState.timeOfDay !== 'all') { activeFilters.push('time'); }
            if (filterState.nameQuery) { activeFilters.push('name'); }
            if (!filterState.showUnconfirmed) { activeFilters.push('no-unconfirmed'); }
            if (!filterState.showPrivate) { activeFilters.push('no-private'); }
            if (!filterState.showOutsideHire) { activeFilters.push('no-outside'); }
            if (!filterState.showCancelled) { activeFilters.push('no-cancelled'); }
            if (filterState.selectedTags.length > 0) { activeFilters.push(filterState.selectedTags.length + ' tag(s)'); }
            if (filterState.visibleRooms.length !== resources.length) { activeFilters.push(filterState.visibleRooms.length + ' room(s)'); }

            if (activeFilters.length > 0) {
                countEl.textContent = '(' + visibleCount + ' shown, ' + hiddenCount + ' hidden)';
            } else {
                countEl.textContent = '';
            }
        }
    }

    function updateTimelineHours(timeFilter) {
        if (!calendar) { return; }
        
        var view = calendar.view;
        if (view.type !== 'resourceTimelineWeek') { return; }
        
        var minTime, maxTime;
        switch (timeFilter) {
            case 'daytime':
                minTime = '09:00:00';
                maxTime = '17:00:00';
                break;
            case 'evening':
                minTime = '17:00:00';
                maxTime = '24:00:00';
                break;
            default: // 'all'
                minTime = '09:00:00';
                maxTime = '24:00:00';
                break;
        }
        
        calendar.setOption('slotMinTime', minTime);
        calendar.setOption('slotMaxTime', maxTime);
    }

    function setupFilterListeners() {
        // Time of day buttons
        var timeBtns = document.querySelectorAll('.time-filter-btn');
        timeBtns.forEach(function(btn) {
            btn.addEventListener('click', function() {
                timeBtns.forEach(function(b) { b.classList.remove('active'); });
                btn.classList.add('active');
                filterState.timeOfDay = btn.dataset.timeFilter || 'all';
                applyFilters();
                updateTimelineHours(filterState.timeOfDay);
            });
        });

        // Name search input
        var nameInput = document.getElementById('filter-name');
        if (nameInput) {
            var debounceTimer;
            nameInput.addEventListener('input', function() {
                clearTimeout(debounceTimer);
                debounceTimer = setTimeout(function() {
                    filterState.nameQuery = nameInput.value.trim();
                    applyFilters();
                }, 150);
            });
        }

        // Status checkboxes
        var unconfirmedCb = document.getElementById('filter-unconfirmed');
        var privateCb = document.getElementById('filter-private');
        var outsideCb = document.getElementById('filter-outside');
        var cancelledCb = document.getElementById('filter-cancelled');

        if (unconfirmedCb) {
            unconfirmedCb.addEventListener('change', function() {
                filterState.showUnconfirmed = unconfirmedCb.checked;
                applyFilters();
            });
        }
        if (privateCb) {
            privateCb.addEventListener('change', function() {
                filterState.showPrivate = privateCb.checked;
                applyFilters();
            });
        }
        if (outsideCb) {
            outsideCb.addEventListener('change', function() {
                filterState.showOutsideHire = outsideCb.checked;
                applyFilters();
            });
        }
        if (cancelledCb) {
            cancelledCb.addEventListener('change', function() {
                filterState.showCancelled = cancelledCb.checked;
                applyFilters();
            });
        }

        // Tag filter buttons (multi-select)
        var tagBtns = document.querySelectorAll('.tag-filter-btn[data-tag]');
        tagBtns.forEach(function(btn) {
            btn.addEventListener('click', function() {
                var tag = btn.dataset.tag;
                var isActive = btn.classList.contains('active');

                if (isActive) {
                    // Deselect this tag
                    btn.classList.remove('active');
                    var idx = filterState.selectedTags.indexOf(tag);
                    if (idx !== -1) {
                        filterState.selectedTags.splice(idx, 1);
                    }
                } else {
                    // Select this tag
                    btn.classList.add('active');
                    if (filterState.selectedTags.indexOf(tag) === -1) {
                        filterState.selectedTags.push(tag);
                    }
                }

                applyFilters();
            });
        });

        // Room filter checkboxes
        var roomCbs = document.querySelectorAll('.room-filter-checkbox');
        roomCbs.forEach(function(cb) {
            cb.addEventListener('change', function() {
                var roomId = parseInt(cb.value, 10);
                if (cb.checked) {
                    if (filterState.visibleRooms.indexOf(roomId) === -1) {
                        filterState.visibleRooms.push(roomId);
                    }
                } else {
                    var idx = filterState.visibleRooms.indexOf(roomId);
                    if (idx !== -1) {
                        filterState.visibleRooms.splice(idx, 1);
                    }
                }
                applyFilters();
            });
        });

        // Filter collapse toggle (works on all screen sizes)
        var filterToggle = document.getElementById('filter-toggle');
        var filterBar = document.getElementById('calendar-filters');
        var toggleText = document.getElementById('filter-toggle-text');

        if (filterToggle && filterBar) {
            // Auto-collapse on mobile only; desktop starts expanded
            var isMobile = window.innerWidth <= 768;
            if (isMobile) {
                filterBar.classList.add('collapsed');
                if (toggleText) { toggleText.textContent = 'Show filters'; }
            }

            filterToggle.addEventListener('click', function() {
                var isCollapsed = filterBar.classList.toggle('collapsed');
                if (toggleText) {
                    toggleText.textContent = isCollapsed ? 'Show filters' : 'Hide filters';
                }
                // Re-render calendar after transition
                setTimeout(function() {
                    if (calendar) { calendar.render(); }
                }, 200);
            });
        }
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

                var html = '<h3>Ideas for ' + label + ':</h3>'
                    + '<div class="idea' + (historic ? '-historic' : '') + '" id="' + editId + '">'
                    + (data.ideas !== null ? data.ideas : '')
                    + '</div>';

                // Update both ideas containers (sidebar and bottom)
                var ideasContainers = document.querySelectorAll('#ideas');
                ideasContainers.forEach(function(container) {
                    container.innerHTML = html;
                });

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

    function _init() {
        var calendarEl = document.getElementById('calendar');
        var hasResources = resources && resources.length > 0;

        var isMobile = window.innerWidth <= 768;

        var initialView = getStoredView();
        if (!hasResources && (initialView === 'resourceTimelineWeek' || initialView === 'resourceTimelineMonth')) {
            initialView = 'dayGridMonth';
        }
        if (isMobile && (initialView === 'timeGridWeek' || initialView === 'dayGridMonth')) {
            initialView = 'threeDay';
        }

        var isTouch = ('ontouchstart' in window) || (navigator.maxTouchPoints > 0);

        var calendarOpts = {
            initialView: initialView,
            initialDate: defaultDate,

            schedulerLicenseKey: 'GPL-My-Project-Is-Open-Source',

            height: 'auto',  // Prevent excessive vertical whitespace

            headerToolbar: hasResources
                ? {
                    left:   'prev,next today,fullwidthToggle',
                    center: 'title',
                    right:  'dayGridMonth,timeGridWeek,threeDay,resourceTimelineWeek,resourceTimelineMonth'
                }
                : {
                    left:   'prev,next today,fullwidthToggle',
                    center: 'title',
                    right:  'dayGridMonth,timeGridWeek,threeDay'
                },

            views: {
                threeDay: {
                    type:       'timeGrid',
                    duration:   { days: 3 },
                    buttonText: '3 days',
                    buttonHint: '3-day view'
                }
            },

            customButtons: {
                fullwidthToggle: {
                    text: '⛶',
                    hint: 'Toggle full-width layout',
                    click: function() {
                        var nowFull = document.body.classList.toggle('calendar-fullwidth');
                        try { localStorage.setItem('fc6-calendar-fullwidth', nowFull ? 'true' : 'false'); } catch (e) {}
                        var btn = document.querySelector('.fc-fullwidthToggle-button');
                        if (btn) { btn.classList.toggle('fc-button-active', nowFull); }
                        setTimeout(function() { if (calendar) { calendar.render(); } }, 50);
                    }
                }
            },

            timeZone: false,

            nowIndicator: true,
            dayMaxEvents: true,

            eventTimeFormat: {
                hour:   'numeric',
                minute: '2-digit',
                hour12: false
            },

            displayEventEnd: false,  // Show only start time (full range in tooltip)

            events: django_urls['edit-diary-data'],

            selectable: true,

            longPressDelay: isTouch ? 500 : 300,

            scrollTime: '16:00:00',

            eventClick: function(info) {
                info.jsEvent.preventDefault();
                window.open(info.event.url, '_blank');
            },

            dateClick: function(info) {
                if (info.date < new Date()) { return; }
                if (!info.allDay) { return; }
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
                    url += '&duration=' + Math.round((info.end - info.start) / 1000);
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
                if (classNames.indexOf('s_unconfirmed') !== -1) { statuses.push('Unconfirmed'); }
                if (classNames.indexOf('s_cancelled') !== -1) { statuses.push('Cancelled'); }
                if (classNames.indexOf('s_private') !== -1) { statuses.push('Private'); }
                if (classNames.indexOf('s_outside_hire') !== -1) { statuses.push('Outside hire'); }
                if (classNames.indexOf('s_discounted') !== -1) { statuses.push('Discounted'); }

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
                if (statuses.length > 0) { lines.push(statuses.join(', ')); }
                info.el.title = lines.join('\n');

                // Add status badges inside the event
                var badgesHtml = '';
                if (classNames.indexOf('s_private') !== -1) {
                    badgesHtml += '<span class="fc-event-badge" title="Private">🔒</span>';
                }
                if (classNames.indexOf('s_outside_hire') !== -1) {
                    badgesHtml += '<span class="fc-event-badge" title="Outside hire">👥</span>';
                }
                if (classNames.indexOf('s_cancelled') !== -1) {
                    badgesHtml += '<span class="fc-event-badge" title="Cancelled">🚫</span>';
                }
                if (classNames.indexOf('s_discounted') !== -1) {
                    badgesHtml += '<span class="fc-event-badge" title="Discounted">✻</span>';
                }

                if (badgesHtml) {
                    var titleEl = info.el.querySelector('.fc-event-title');
                    if (titleEl) {
                        var badgeContainer = document.createElement('span');
                        badgeContainer.className = 'fc-event-badges';
                        badgeContainer.innerHTML = badgesHtml;
                        titleEl.appendChild(badgeContainer);
                    }
                }

                // Status label below title (like before)
                if (statuses.length > 0) {
                    var span       = document.createElement('span');
                    span.className = 'fc-event-status';
                    span.textContent = statuses.join(' · ');
                    var statusEl = info.el.querySelector('.fc-event-status');
                    var titleEl = info.el.querySelector('.fc-event-title');
                    if (!statusEl && titleEl) {
                        titleEl.after(span);
                    }
                }

                // Apply initial filters to newly mounted events
                if (!eventMatchesFilters(info.event)) {
                    info.event.setProp('display', 'none');
                }
            },

            datesSet: function(info) {
                setStoredView(info.view.type);
                syncUrl(info.view, calendar.getDate());
                // Re-apply filters and timeline hours when view changes
                setTimeout(function() {
                    applyFilters();
                    updateTimelineHours(filterState.timeOfDay);
                }, 100);
            }
        };

        calendarOpts.views.timeGridWeek = {
            buttonText: 'week'
        };

        if (hasResources) {
            calendarOpts.resources = resources;
            calendarOpts.resourceAreaWidth = '15%';

            calendarOpts.views.resourceTimelineWeek = {
                buttonText: 'week (rooms)',
                slotDuration: '01:00',
                scrollTime: '16:00:00',
                contentHeight: 'auto'
            };
            calendarOpts.views.resourceTimelineMonth = {
                buttonText: 'month (rooms)',
                slotDuration: { day: 1 },
                slotMinWidth: 120,
                contentHeight: 'auto',
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
            };
        }

        calendar = new FullCalendar.Calendar(calendarEl, calendarOpts);
        calendar.render();

        // Apply initial timeline hours if starting in week view
        updateTimelineHours(filterState.timeOfDay);

        // Setup filter UI listeners
        setupFilterListeners();

        // Restore full-width preference from localStorage
        try {
            var storedFull = localStorage.getItem('fc6-calendar-fullwidth') === 'true';
            if (storedFull) {
                document.body.classList.add('calendar-fullwidth');
                var fwBtn = document.querySelector('.fc-fullwidthToggle-button');
                if (fwBtn) { fwBtn.classList.add('fc-button-active'); }
            }
        } catch (e) {}

        var resizeTimer;
        window.addEventListener('resize', function() {
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(function() {
                calendar.render();
            }, 250);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', _init);
    } else {
        _init();
    }
}
