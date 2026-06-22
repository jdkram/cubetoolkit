/* Public sidebar (g-key) keyboard navigation — mirrors keyboard-nav-admin.js
   but targets #site-nav and uses plain jQuery show/hide (no Bootstrap).
   human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 4.6"]; status: "#ai-input" */
(function ($) {
    "use strict";

    var navMode    = false;
    var subNavMode = false;
    var subNavItems = {};
    var openSubMenu = null;

    function escHtml(str) {
        return $("<span>").text(str || "").html();
    }

    // ── ? help modal ─────────────────────────────────────────────────────────
    (function () {
        var s = document.createElement("style");
        s.textContent = [
            ".pub-kb-help{position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:9999;display:flex;align-items:center;justify-content:center;}",
            ".pub-kb-card{background:#fff;border:1px solid #dee2e6;border-radius:6px;padding:1.2em 1.5em 1em;max-width:28em;width:90vw;box-shadow:0 8px 32px rgba(0,0,0,.2);font-size:.9em;max-height:80vh;overflow-y:auto;}",
            ".pub-kb-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:.8em;padding-bottom:.5em;border-bottom:1px solid #dee2e6;}",
            ".pub-kb-close{background:none;border:none;font-size:1.1em;color:#6c757d;cursor:pointer;line-height:1;padding:0;}",
            ".pub-kb-section{margin-top:.75em;}",
            ".pub-kb-section:first-child{margin-top:0;}",
            ".pub-kb-heading{font-weight:600;font-size:.8em;text-transform:uppercase;letter-spacing:.06em;color:#6c757d;margin-bottom:.3em;padding-bottom:.2em;border-bottom:1px solid #f0f0f0;}",
            ".pub-kb-row{display:flex;align-items:baseline;gap:.75em;padding:.15em 0;}",
            ".pub-kb-row kbd{display:inline-block;min-width:5em;text-align:right;font-family:monospace;font-size:.85em;color:#212529;background:#f8f9fa;border:1px solid #ced4da;border-radius:3px;padding:.1em .4em;white-space:nowrap;flex-shrink:0;}",
            ".pub-kb-row span{color:#495057;}"
        ].join("");
        document.head.appendChild(s);
    }());

    var _HELP_SECTIONS = [
        { heading: "Navigation", rows: [
            ["g",          "Enter navigation mode (badges appear on sidebar)"],
            ["g → letter", "Jump to a section"],
            ["Esc",        "Exit navigation mode"]
        ]},
        { heading: "Help", rows: [["?", "Toggle this panel"]] }
    ];

    function _togglePublicHelp() {
        var existing = document.getElementById("pub-kb-help");
        if (existing) { existing.remove(); return; }

        var html = "<div id=\"pub-kb-help\" class=\"pub-kb-help\" tabindex=\"-1\" role=\"dialog\" aria-modal=\"true\" aria-label=\"Keyboard shortcuts\"><div class=\"pub-kb-card\">";
        html += "<div class=\"pub-kb-header\"><strong>Keyboard shortcuts</strong><button class=\"pub-kb-close\" aria-label=\"Close\">&#x2715;</button></div>";
        _HELP_SECTIONS.forEach(function (s) {
            html += "<div class=\"pub-kb-section\"><div class=\"pub-kb-heading\">" + escHtml(s.heading) + "</div>";
            s.rows.forEach(function (r) {
                html += "<div class=\"pub-kb-row\"><kbd>" + escHtml(r[0]) + "</kbd><span>" + escHtml(r[1]) + "</span></div>";
            });
            html += "</div>";
        });
        html += "</div></div>";

        document.body.insertAdjacentHTML("beforeend", html);
        var modal = document.getElementById("pub-kb-help");
        modal.addEventListener("click", function (e) {
            if (e.target === modal || e.target.classList.contains("pub-kb-close")) {
                modal.remove();
            }
        });
        modal.focus();
    }

    function enterNavMode() {
        navMode = true;
        $("#site-nav a[data-nav-key]").each(function () {
            $(this).append('<kbd class="pub-nav-key-badge">' + escHtml($(this).data("nav-key")) + "</kbd>");
        });
    }

    function exitNavMode() {
        navMode = false;
        $(".pub-nav-key-badge").remove();
    }

    function enterSubNavMode(subMenu) {
        subNavMode = true;
        openSubMenu = subMenu;
        subMenu.show();
        var used = {};
        subNavItems = {};
        subMenu.find("a").each(function () {
            var link = $(this);
            var href = link.attr("href");
            if (!href || href === "#") { return; }
            var text = link.text().trim().toLowerCase();
            var letter = null;
            for (var i = 0; i < text.length; i++) {
                var c = text[i];
                if (/[a-z]/.test(c) && !used[c]) { letter = c; used[c] = true; break; }
            }
            if (letter) {
                link.prepend('<kbd class="pub-nav-key-badge">' + letter + "</kbd> ");
                subNavItems[letter] = href;
            }
        });
    }

    function exitSubNavMode(hideMenu) {
        subNavMode = false;
        subNavItems = {};
        $(".pub-nav-key-badge").remove();
        if (hideMenu && openSubMenu) { openSubMenu.hide(); }
        openSubMenu = null;
    }

    $(document).on("keydown", function (e) {
        if (e.ctrlKey || e.altKey || e.metaKey) { return; }
        var tag    = (document.activeElement || {}).tagName || "";
        var inInput = /^(INPUT|TEXTAREA|SELECT)$/i.test(tag);
        var inEdit  = !!(document.activeElement && document.activeElement.isContentEditable);

        if (e.key === "Escape") {
            var pubHelp = document.getElementById("pub-kb-help");
            if (pubHelp) { pubHelp.remove(); e.stopImmediatePropagation(); return; }
            if (subNavMode) { exitSubNavMode(true); e.stopImmediatePropagation(); return; }
            if (navMode)    { exitNavMode();         e.stopImmediatePropagation(); return; }
            return;
        }

        if (inInput || inEdit) { return; }

        if (e.key === "?") {
            e.preventDefault();
            _togglePublicHelp();
            return;
        }

        var key = e.key;

        if (key === "g") {
            e.preventDefault();
            e.stopImmediatePropagation();
            if (subNavMode) { exitSubNavMode(true); return; }
            if (navMode) { exitNavMode(); } else { enterNavMode(); }
            return;
        }

        if (subNavMode) {
            e.stopImmediatePropagation();
            var sdest = subNavItems[key.toLowerCase()];
            if (sdest) { e.preventDefault(); exitSubNavMode(false); window.location.href = sdest; }
            else        { exitSubNavMode(true); }
            return;
        }

        if (navMode) {
            exitNavMode();
            var link = $("#site-nav a[data-nav-key='" + key.toLowerCase() + "']");
            if (link.length) {
                e.preventDefault();
                e.stopImmediatePropagation();
                var href = link.attr("href");
                if (link.attr("aria-haspopup") === "true" || href === "#") {
                    var subMenu = link.next("ul.sub-menu");
                    if (subMenu.length) { enterSubNavMode(subMenu); }
                } else {
                    window.location.href = href;
                }
            } else {
                e.stopImmediatePropagation();
            }
            return;
        }
    });
}(jQuery));
