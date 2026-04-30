// human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 4.6"]; status: "#ai-written"
// "Add to calendar" dropdown. The button is a bare flex item (no wrapper element).
// The menu is position:fixed, placed by JS using getBoundingClientRect so it
// never affects surrounding layout. See TASKS.md 9.10.4a.
(function () {
    "use strict";

    function closeAll() {
        document.querySelectorAll(".add-to-calendar__menu.is-open").forEach(function (menu) {
            menu.classList.remove("is-open");
        });
        document.querySelectorAll(".add-to-calendar__trigger[aria-expanded='true']").forEach(function (btn) {
            btn.setAttribute("aria-expanded", "false");
        });
    }

    function openMenu(trigger) {
        var menu = document.getElementById(trigger.getAttribute("data-cal-target"));
        if (!menu) return;
        var rect = trigger.getBoundingClientRect();
        menu.style.top  = (rect.bottom + 4) + "px";
        menu.style.left = rect.left + "px";
        menu.classList.add("is-open");
        // Nudge left if it would clip the right edge
        var mr = menu.getBoundingClientRect();
        if (mr.right > window.innerWidth - 8) {
            menu.style.left = Math.max(8, rect.right - mr.width) + "px";
        }
        trigger.setAttribute("aria-expanded", "true");
    }

    document.addEventListener("click", function (event) {
        var trigger = event.target.closest(".add-to-calendar__trigger");
        if (trigger) {
            event.stopPropagation();
            var isOpen = trigger.getAttribute("aria-expanded") === "true";
            closeAll();
            if (!isOpen) openMenu(trigger);
            return;
        }
        if (!event.target.closest(".add-to-calendar__menu")) {
            closeAll();
        }
    });

    document.addEventListener("keydown", function (event) {
        if (event.key !== "Escape") return;
        var trigger = document.querySelector(".add-to-calendar__trigger[aria-expanded='true']");
        closeAll();
        if (trigger) trigger.focus();
    });

    // Reposition open menus on scroll or resize (keeps menu anchored to button)
    function repositionOpen() {
        document.querySelectorAll(".add-to-calendar__menu.is-open").forEach(function (menu) {
            var trigger = document.querySelector("[data-cal-target='" + menu.id + "']");
            if (trigger) openMenu(trigger);
        });
    }
    window.addEventListener("scroll", repositionOpen, { passive: true });
    window.addEventListener("resize", repositionOpen, { passive: true });
})();
