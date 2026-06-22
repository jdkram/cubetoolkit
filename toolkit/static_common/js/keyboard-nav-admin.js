/* Global keyboard navigation for admin pages.
   g-key nav mode with top-level badges, then submenu drill-down.
   Site-wide ? help modal with per-page registration.
   Exposes window.AdminKeyboardNav for page-specific handlers.
   human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 4.6"]; status: "#ai-input" */
(function ($) {
    "use strict";

    var navMode    = false;
    var subNavMode = false;
    var subNavItems = {};
    var _pageHelp = null;      // set by registerHelp(); array of {heading, rows} sections
    var _suppressGlobal = false; // set by suppressGlobalHelp(); rota uses its own ? handler

    // ── Global help modal CSS (injected once) ────────────────────────────────
    (function () {
        var s = document.createElement("style");
        s.textContent = [
            "#tk-kb-help{position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:9999;display:flex;align-items:center;justify-content:center;}",
            ".tk-kb-card{background:#fff;border:1px solid #dee2e6;border-radius:6px;padding:1.2em 1.5em 1em;max-width:30em;width:90vw;box-shadow:0 8px 32px rgba(0,0,0,.2);font-size:.9em;max-height:80vh;overflow-y:auto;}",
            ".tk-kb-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:.8em;padding-bottom:.5em;border-bottom:1px solid #dee2e6;}",
            ".tk-kb-close{background:none;border:none;font-size:1.1em;color:#6c757d;cursor:pointer;line-height:1;padding:0;}",
            ".tk-kb-section{margin-top:.75em;}",
            ".tk-kb-section:first-child{margin-top:0;}",
            ".tk-kb-heading{font-weight:600;font-size:.8em;text-transform:uppercase;letter-spacing:.06em;color:#6c757d;margin-bottom:.3em;padding-bottom:.2em;border-bottom:1px solid #f0f0f0;}",
            ".tk-kb-row{display:flex;align-items:baseline;gap:.75em;padding:.15em 0;}",
            ".tk-kb-row kbd{display:inline-block;min-width:5em;text-align:right;font-family:monospace;font-size:.85em;color:#212529;background:#f8f9fa;border:1px solid #ced4da;border-radius:3px;padding:.1em .4em;white-space:nowrap;flex-shrink:0;}",
            ".tk-kb-row span{color:#495057;}"
        ].join("");
        document.head.appendChild(s);
    }());

    // Global shortcuts always shown at top of the help modal.
    var GLOBAL_SECTIONS = [
        { heading: "Global navigation", rows: [
            ["g",          "Enter navigation mode (badges appear on nav)"],
            ["g → letter", "Navigate to a section or page"],
            ["Esc",        "Exit navigation mode"]
        ]}
    ];

    function _toggleGlobalHelp() {
        var existing = document.getElementById("tk-kb-help");
        if (existing) { existing.remove(); return; }

        var sections = GLOBAL_SECTIONS.concat(_pageHelp || []).concat([
            { heading: "Help", rows: [["?", "Toggle this panel"]] }
        ]);

        var html = "<div id=\"tk-kb-help\" tabindex=\"-1\" role=\"dialog\" aria-modal=\"true\" aria-label=\"Keyboard shortcuts\"><div class=\"tk-kb-card\">";
        html += "<div class=\"tk-kb-header\"><strong>Keyboard shortcuts</strong><button class=\"tk-kb-close\" aria-label=\"Close\">&#x2715;</button></div>";
        sections.forEach(function (s) {
            html += "<div class=\"tk-kb-section\"><div class=\"tk-kb-heading\">" + escHtml(s.heading) + "</div>";
            s.rows.forEach(function (r) {
                html += "<div class=\"tk-kb-row\"><kbd>" + escHtml(r[0]) + "</kbd><span>" + escHtml(r[1]) + "</span></div>";
            });
            html += "</div>";
        });
        html += "</div></div>";

        document.body.insertAdjacentHTML("beforeend", html);
        var modal = document.getElementById("tk-kb-help");
        modal.addEventListener("click", function (e) {
            if (e.target === modal || e.target.classList.contains("tk-kb-close")) {
                modal.remove();
            }
        });
        modal.focus();
    }

    function escHtml(str) {
        return $("<span>").text(str || "").html();
    }

    function enterNavMode() {
        navMode = true;
        $(".navbar-nav .nav-link[data-nav-key]").each(function () {
            $(this).append('<kbd class="rota-nav-key-badge">' + escHtml($(this).data("nav-key")) + "</kbd>");
        });
    }

    function exitNavMode() {
        navMode = false;
        $(".rota-nav-key-badge").remove();
    }

    function enterSubNavMode(dropdownToggle) {
        subNavMode = true;
        if (typeof bootstrap !== "undefined") {
            bootstrap.Dropdown.getOrCreateInstance(dropdownToggle).show();
        }
        var menu = $(dropdownToggle).closest(".nav-item").find(".dropdown-menu");
        var used = {};
        subNavItems = {};
        menu.find(".dropdown-item").each(function () {
            var link = $(this);
            var href = link.attr("href");
            if (!href || href === "#") { return; }
            // Strip trailing "labs" label text before picking a letter
            var text = link.text().replace(/\s+labs\s*$/i, "").trim().toLowerCase();
            var letter = null;
            for (var i = 0; i < text.length; i++) {
                var c = text[i];
                if (/[a-z]/.test(c) && !used[c]) { letter = c; used[c] = true; break; }
            }
            if (letter) {
                link.prepend('<kbd class="rota-nav-key-badge">' + letter + "</kbd> ");
                subNavItems[letter] = href;
            }
        });
    }

    function exitSubNavMode() {
        subNavMode = false;
        subNavItems = {};
        $(".rota-nav-key-badge").remove();
        if (typeof bootstrap !== "undefined") {
            document.querySelectorAll('[data-bs-toggle="dropdown"]').forEach(function (el) {
                var instance = bootstrap.Dropdown.getInstance(el);
                if (instance) { instance.hide(); }
            });
        }
    }

    $(document).on("keydown", function (e) {
        if (e.ctrlKey || e.altKey || e.metaKey) { return; }
        var tag    = (document.activeElement || {}).tagName || "";
        var inInput = /^(INPUT|TEXTAREA|SELECT)$/i.test(tag);
        var inEdit  = !!(document.activeElement && document.activeElement.isContentEditable);

        // Escape: close global help first, then sub-nav, then nav mode
        if (e.key === "Escape") {
            var globalHelp = document.getElementById("tk-kb-help");
            if (globalHelp) { globalHelp.remove(); e.stopImmediatePropagation(); return; }
            if (subNavMode) { exitSubNavMode(); e.stopImmediatePropagation(); return; }
            if (navMode)    { exitNavMode();    e.stopImmediatePropagation(); return; }
            return;
        }

        if (inInput || inEdit) { return; }

        // ? — global help modal (skip if page has its own ? handler)
        if (e.key === "?") {
            if (_suppressGlobal) { return; }
            e.preventDefault();
            _toggleGlobalHelp();
            return;
        }

        var key = e.key;

        // g: enter nav mode; g again = exit nav mode and scroll to first rota showing (if any)
        if (key === "g") {
            e.preventDefault();
            e.stopImmediatePropagation();
            if (subNavMode) { exitSubNavMode(); return; }
            if (navMode) {
                exitNavMode();
                var first = $(".rota-showing:visible").first()[0];
                if (first) { first.scrollIntoView({ behavior: "smooth", block: "start" }); }
            } else {
                enterNavMode();
            }
            return;
        }

        // Sub-nav mode: letter navigates to a dropdown item
        if (subNavMode) {
            e.stopImmediatePropagation();
            var sdest = subNavItems[key.toLowerCase()];
            if (sdest) { e.preventDefault(); exitSubNavMode(); window.location.href = sdest; }
            else        { exitSubNavMode(); }
            return;
        }

        // Nav mode: letter navigates to page or drills into dropdown sub-nav
        if (navMode) {
            exitNavMode();
            var navTarget = $(".navbar-nav .nav-link[data-nav-key='" + key.toLowerCase() + "']");
            if (navTarget.length) {
                e.preventDefault();
                e.stopImmediatePropagation();
                if (navTarget.attr("data-bs-toggle") === "dropdown") {
                    enterSubNavMode(navTarget[0]);
                } else {
                    window.location.href = navTarget.attr("href");
                }
            } else {
                e.stopImmediatePropagation();
            }
            return;
        }
    });

    window.AdminKeyboardNav = {
        isNavMode:          function ()         { return navMode || subNavMode; },
        registerHelp:       function (sections) { _pageHelp = sections; },
        suppressGlobalHelp: function ()         { _suppressGlobal = true; }
    };
}(jQuery));
