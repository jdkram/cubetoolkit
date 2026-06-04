/* programme.js — client-side keyword search + category filter for the public programme page */
/* human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 4.6"]; status: "#ai-input" */
(function () {
    "use strict";

    $(document).ready(function () {
        var searchInputs = Array.prototype.slice.call(document.querySelectorAll("[data-prog-search]"));
        var resetBtns    = Array.prototype.slice.call(document.querySelectorAll("[data-prog-reset]"));

        if (!searchInputs.length) { return; }

        var activeGroup = "";  // "" = All

        function cardMatchesGroup(card, group) {
            if (!group) { return true; }
            var tags = (card.dataset.tags || "").split(" ").filter(Boolean);
            var map  = window.PROG_TAG_FILTER_MAP || {};
            if (group === "__other__") {
                return !tags.some(function (slug) { return !!map[slug]; });
            }
            return tags.some(function (slug) { return map[slug] === group; });
        }

        function updateFilterButtons(group) {
            document.querySelectorAll(".prog-filter-btn").forEach(function (btn) {
                btn.classList.toggle("prog-filter-btn--active", btn.dataset.filterGroup === group);
            });
        }

        function currentSearchTerm() {
            return searchInputs.length ? searchInputs[0].value : "";
        }

        function applyFilter(term, group) {
            if (group === undefined) { group = activeGroup; }
            activeGroup = group;
            term = (term || "").toLowerCase().trim();

            searchInputs.forEach(function (inp) { inp.value = term; });
            resetBtns.forEach(function (btn) { btn.hidden = term.length === 0 && group === ""; });

            document.querySelectorAll(".programme > .showing").forEach(function (card) {
                var textMatch  = !term || (card.dataset.searchText || "").toLowerCase().indexOf(term) !== -1;
                var groupMatch = cardMatchesGroup(card, group);
                card.classList.toggle("filter-hidden", !(textMatch && groupMatch));
            });

            updateFilterButtons(group);

            // Switch from list to grid when a filter is active
            if ((term || group) && $(".list").hasClass("active")) {
                $(".list").removeClass("active");
                $(".programme").show().stop().animate({ opacity: 1 });
            }

            var params = new URLSearchParams(window.location.search);
            if (term)  { params.set("search", term);  } else { params.delete("search"); }
            if (group) { params.set("group", group);  } else { params.delete("group"); }
            var qs = params.toString();
            history.replaceState(null, "", qs ? "?" + qs : window.location.pathname);
        }

        searchInputs.forEach(function (inp) {
            inp.addEventListener("input",  function () { applyFilter(this.value); });
            inp.addEventListener("search", function () { applyFilter(this.value); });
        });

        resetBtns.forEach(function (btn) {
            btn.addEventListener("click", function () { applyFilter("", ""); });
        });

        document.querySelectorAll(".prog-filter-btn").forEach(function (btn) {
            btn.addEventListener("click", function () {
                applyFilter(currentSearchTerm(), this.dataset.filterGroup);
            });
        });

        var params = new URLSearchParams(window.location.search);
        var initTerm  = params.get("search") || "";
        var initGroup = params.get("group") || "";
        if (initTerm || initGroup) { applyFilter(initTerm, initGroup); }
    });

})();
