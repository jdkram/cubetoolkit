// human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Opus 4.7"]; status: "#ai-written"
// Tiny enhancement for <details class="add-to-calendar"> popovers:
// close on outside click and on ESC. Native <details> handles toggle +
// keyboard activation; this just adds the dismiss behaviour users expect
// from a menu. See TASKS.md 9.10.4a.
(function () {
    "use strict";

    document.addEventListener("click", function (event) {
        document.querySelectorAll("details.add-to-calendar[open]").forEach(function (d) {
            if (!d.contains(event.target)) {
                d.removeAttribute("open");
            }
        });
    });

    document.addEventListener("keydown", function (event) {
        if (event.key !== "Escape") return;
        var open = document.querySelectorAll("details.add-to-calendar[open]");
        if (open.length === 0) return;
        open.forEach(function (d) {
            d.removeAttribute("open");
            var trigger = d.querySelector("summary");
            if (trigger) trigger.focus();
        });
    });
})();
