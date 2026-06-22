/* Command palette — Ctrl+K / Cmd+K opens fuzzy-search over all admin commands.
   Depends on window.TOOLKIT_COMMANDS (injected by base_admin.html).
   human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 4.6"]; status: "#ai-input" */
(function () {
    "use strict";

    // ── CSS (injected once) ──────────────────────────────────────────────────
    (function () {
        var s = document.createElement("style");
        s.textContent = [
            "#tk-cp-backdrop{position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:10000;display:flex;align-items:flex-start;justify-content:center;padding-top:6rem;}",
            ".tk-cp-dialog{background:#fff;border:1px solid #dee2e6;border-radius:8px;box-shadow:0 16px 48px rgba(0,0,0,.25);width:100%;max-width:560px;overflow:hidden;}",
            ".tk-cp-input-wrap{display:flex;align-items:center;padding:.7em 1em;border-bottom:1px solid #dee2e6;gap:.6em;}",
            ".tk-cp-search-icon{color:#6c757d;flex-shrink:0;font-size:1em;line-height:1;}",
            ".tk-cp-input{border:none;outline:none;font-size:1em;width:100%;background:transparent;color:#212529;padding:0;}",
            ".tk-cp-input::placeholder{color:#adb5bd;}",
            ".tk-cp-results{max-height:360px;overflow-y:auto;padding:.25em 0;}",
            ".tk-cp-category{font-size:.72em;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#6c757d;padding:.6em 1em .25em;}",
            ".tk-cp-option{display:flex;align-items:center;padding:.45em 1em;cursor:pointer;text-decoration:none;color:#212529;font-size:.93em;gap:.5em;}",
            ".tk-cp-option:hover,.tk-cp-option[aria-selected='true']{background:#eef2ff;color:#000;text-decoration:none;}",
            ".tk-cp-option-label{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}",
            ".tk-cp-shortcut{font-family:monospace;font-size:.8em;background:#f8f9fa;border:1px solid #dee2e6;border-radius:3px;padding:.05em .35em;color:#6c757d;white-space:nowrap;flex-shrink:0;}",
            ".tk-cp-empty{text-align:center;padding:2em 1em;color:#6c757d;font-size:.9em;}",
            ".tk-cp-hint-btn{background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.3);border-radius:4px;color:rgba(255,255,255,.8);font-size:.76em;padding:.2em .55em;cursor:pointer;font-family:inherit;white-space:nowrap;line-height:1.5;letter-spacing:.03em;}",
            ".tk-cp-hint-btn:hover{background:rgba(255,255,255,.22);color:#fff;}"
        ].join("");
        document.head.appendChild(s);
    }());

    // ── State ────────────────────────────────────────────────────────────────
    var _open = false;
    var _selectedIdx = 0;

    // ── Search ───────────────────────────────────────────────────────────────
    function _search(query) {
        var commands = window.TOOLKIT_COMMANDS || [];
        if (!query.trim()) { return commands.slice(); }
        var tokens = query.trim().toLowerCase().split(/\s+/);
        var matched = commands.filter(function (cmd) {
            var hay = ((cmd.label || "") + " " + (cmd.category || "") + " " + (cmd.keywords || "")).toLowerCase();
            return tokens.every(function (t) { return hay.indexOf(t) !== -1; });
        });
        // Sort: exact label match first, then starts-with, then rest
        var q = query.trim().toLowerCase();
        matched.sort(function (a, b) {
            var al = (a.label || "").toLowerCase();
            var bl = (b.label || "").toLowerCase();
            var ae = al === q ? 0 : al.indexOf(q) === 0 ? 1 : 2;
            var be = bl === q ? 0 : bl.indexOf(q) === 0 ? 1 : 2;
            return ae - be;
        });
        return matched;
    }

    // ── Selection ────────────────────────────────────────────────────────────
    function _setSelected(idx) {
        var options = document.querySelectorAll(".tk-cp-option");
        if (!options.length) { _selectedIdx = 0; return; }
        idx = ((idx % options.length) + options.length) % options.length;
        _selectedIdx = idx;
        options.forEach(function (el, i) {
            el.setAttribute("aria-selected", i === idx ? "true" : "false");
        });
        var input = document.getElementById("tk-cp-input");
        if (input) { input.setAttribute("aria-activedescendant", "tk-cp-opt-" + idx); }
        options[idx].scrollIntoView({ block: "nearest" });
    }

    function _activate() {
        var options = document.querySelectorAll(".tk-cp-option");
        if (options[_selectedIdx]) {
            var href = options[_selectedIdx].getAttribute("data-href");
            if (href) { closePalette(); window.location.href = href; }
        }
    }

    // ── Render results ───────────────────────────────────────────────────────
    function _render(query) {
        var filtered = _search(query);
        var listbox = document.getElementById("tk-cp-listbox");
        if (!listbox) { return; }

        if (!filtered.length) {
            listbox.innerHTML = '<p class="tk-cp-empty">No commands matching "' + _escHtml(query) + '"</p>';
            _selectedIdx = 0;
            var inp = document.getElementById("tk-cp-input");
            if (inp) { inp.setAttribute("aria-activedescendant", ""); }
            return;
        }

        var html = "";
        var lastCat = null;
        var idx = 0;
        filtered.forEach(function (cmd) {
            if (cmd.category !== lastCat) {
                lastCat = cmd.category;
                html += '<div class="tk-cp-category" aria-hidden="true">' + _escHtml(cmd.category) + "</div>";
            }
            html += '<a class="tk-cp-option" role="option" id="tk-cp-opt-' + idx + '"' +
                ' aria-selected="' + (idx === 0 ? "true" : "false") + '"' +
                ' href="' + _escHtml(cmd.href) + '"' +
                ' data-href="' + _escHtml(cmd.href) + '">' +
                '<span class="tk-cp-option-label">' + _escHtml(cmd.label) + "</span>";
            if (cmd.shortcut) {
                html += '<kbd class="tk-cp-shortcut">' + _escHtml(cmd.shortcut) + "</kbd>";
            }
            html += "</a>";
            idx++;
        });
        listbox.innerHTML = html;
        _selectedIdx = 0;

        var input = document.getElementById("tk-cp-input");
        if (input) { input.setAttribute("aria-activedescendant", "tk-cp-opt-0"); }

        // Wire up click handlers
        document.querySelectorAll(".tk-cp-option").forEach(function (el) {
            el.addEventListener("click", function (e) {
                e.preventDefault();
                var href = el.getAttribute("data-href");
                if (href) { closePalette(); window.location.href = href; }
            });
        });
    }

    // ── Open ─────────────────────────────────────────────────────────────────
    function openPalette() {
        if (_open) { return; }
        _open = true;

        var backdrop = document.createElement("div");
        backdrop.id = "tk-cp-backdrop";
        backdrop.setAttribute("role", "dialog");
        backdrop.setAttribute("aria-modal", "true");
        backdrop.setAttribute("aria-label", "Command palette");

        backdrop.innerHTML =
            '<div class="tk-cp-dialog">' +
            '<div class="tk-cp-input-wrap">' +
            '<span class="tk-cp-search-icon" aria-hidden="true">&#x1F50D;</span>' +
            '<input type="text" id="tk-cp-input" class="tk-cp-input" placeholder="Search commands…"' +
            ' role="combobox" aria-expanded="true" aria-controls="tk-cp-listbox"' +
            ' aria-autocomplete="list" autocomplete="off" spellcheck="false">' +
            '</div>' +
            '<div class="tk-cp-results"><div id="tk-cp-listbox" role="listbox" aria-label="Commands"></div></div>' +
            "</div>";

        document.body.appendChild(backdrop);
        _render("");

        var input = document.getElementById("tk-cp-input");
        input.focus();

        input.addEventListener("input", function () { _render(input.value); });

        input.addEventListener("keydown", function (e) {
            var opts = document.querySelectorAll(".tk-cp-option");
            if (e.key === "ArrowDown") {
                e.preventDefault();
                _setSelected(_selectedIdx + 1);
            } else if (e.key === "ArrowUp") {
                e.preventDefault();
                _setSelected(opts.length ? _selectedIdx - 1 : 0);
            } else if (e.key === "Enter") {
                e.preventDefault();
                _activate();
            } else if (e.key === "Escape") {
                e.preventDefault();
                e.stopImmediatePropagation();
                closePalette();
            } else if (e.key === "Tab") {
                e.preventDefault();
                closePalette();
            }
        });

        backdrop.addEventListener("click", function (e) {
            if (e.target === backdrop) { closePalette(); }
        });
    }

    // ── Close ────────────────────────────────────────────────────────────────
    function closePalette() {
        _open = false;
        var el = document.getElementById("tk-cp-backdrop");
        if (el) { el.remove(); }
    }

    // ── Escape passthrough to other handlers ─────────────────────────────────
    // Handled inside the input keydown above with stopImmediatePropagation.

    // ── Helpers ───────────────────────────────────────────────────────────────
    function _escHtml(str) {
        return (str || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
    }

    // ── Global trigger — Ctrl+K or Ctrl+/ ───────────────────────────────────
    // Ctrl+K is the industry standard (Linear, GitHub, Notion). Firefox focuses
    // its search bar on Ctrl+K, but our preventDefault() intercepts it when the
    // page has focus. Ctrl+/ is a safe fallback with no browser default.
    document.addEventListener("keydown", function (e) {
        if (!window.TOOLKIT_COMMANDS) { return; }
        if ((e.ctrlKey || e.metaKey) && !e.shiftKey && !e.altKey) {
            if (e.key === "k" || e.key === "/") {
                e.preventDefault();
                _open ? closePalette() : openPalette();
            }
        }
    });

    // Expose for navbar hint button
    window.TKCommandPalette = { open: openPalette, close: closePalette };
}());
