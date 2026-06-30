/* programme.js — client-side keyword search + category + day-of-week filter for the public programme page */
/* human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 4.6"]; status: "#ai-input" */
(function () {
    "use strict";

    $(document).ready(function () {
        var searchInputs = Array.prototype.slice.call(document.querySelectorAll("[data-prog-search]"));
        var resetBtns    = Array.prototype.slice.call(document.querySelectorAll("[data-prog-reset]"));

        if (!searchInputs.length) { return; }

        var activeGroup = "";  // "" = All
        var activeDow   = "";  // "" = Any day
        var activeAge   = "";  // "" = All ratings
        var filmGroupSlug = window.PROG_FILM_GROUP_SLUG || "film";
        var ageFilterRow = document.querySelector("[data-age-filter-row]");

        function cardMatchesGroup(card, group) {
            if (!group) { return true; }
            var tags = (card.dataset.tags || "").split(" ").filter(Boolean);
            var map  = window.PROG_TAG_FILTER_MAP || {};
            if (group === "__other__") {
                return !tags.some(function (slug) { return !!map[slug]; });
            }
            return tags.some(function (slug) { return map[slug] === group; });
        }

        function cardMatchesDow(card, dow) {
            if (!dow) { return true; }
            return (card.dataset.dow || "") === dow;
        }

        function cardMatchesAge(card, age) {
            if (!age) { return true; }
            var restriction = card.dataset.ageRestriction || "";
            if (age === "__none__") { return restriction === ""; }
            return restriction === age;
        }

        function updateAgeRowVisibility(group) {
            if (!ageFilterRow) { return; }
            ageFilterRow.classList.toggle("is-visible", group === filmGroupSlug);
        }

        function updateFilterButtons(group, dow, age) {
            document.querySelectorAll(".prog-filter-btn[data-filter-group]").forEach(function (btn) {
                btn.classList.toggle("prog-filter-btn--active", btn.dataset.filterGroup === group);
            });
            document.querySelectorAll(".prog-filter-btn[data-dow-filter]").forEach(function (btn) {
                btn.classList.toggle("prog-filter-btn--active", btn.dataset.dowFilter === dow);
            });
            document.querySelectorAll(".prog-filter-btn[data-age-filter]").forEach(function (btn) {
                btn.classList.toggle("prog-filter-btn--active", btn.dataset.ageFilter === age);
            });
        }

        function currentSearchTerm() {
            return searchInputs.length ? searchInputs[0].value : "";
        }

        function applyFilter(term, group, dow, age) {
            if (group === undefined) { group = activeGroup; }
            if (dow   === undefined) { dow   = activeDow; }
            if (age   === undefined) { age   = activeAge; }
            activeGroup = group;
            activeDow   = dow;
            activeAge   = age;
            term = (term || "").toLowerCase().trim();

            searchInputs.forEach(function (inp) { inp.value = term; });
            var anyFilter = term.length > 0 || group !== "" || dow !== "" || age !== "";
            resetBtns.forEach(function (btn) {
                if (btn.classList.contains("filter-reset-btn--nav")) {
                    btn.hidden = !anyFilter;  // compact × in the mobile nav: hide/show
                } else {
                    btn.classList.toggle("filter-reset-btn--inactive", !anyFilter);  // "Clear all": always present, dim when inactive
                }
            });

            document.querySelectorAll(".programme > .showing").forEach(function (card) {
                var textMatch  = !term || (card.dataset.searchText || "").toLowerCase().indexOf(term) !== -1;
                var groupMatch = cardMatchesGroup(card, group);
                var dowMatch   = cardMatchesDow(card, dow);
                var ageMatch   = cardMatchesAge(card, age);
                card.classList.toggle("filter-hidden", !(textMatch && groupMatch && dowMatch && ageMatch));
            });

            updateFilterButtons(group, dow, age);
            updateAgeRowVisibility(group);

            // Switch from list to grid when a filter is active
            if (anyFilter && $(".list").hasClass("active")) {
                $(".list").removeClass("active");
                $(".programme").show().stop().animate({ opacity: 1 });
            }

            var params = new URLSearchParams(window.location.search);
            if (term)  { params.set("search", term);  } else { params.delete("search"); }
            if (group) { params.set("group", group);  } else { params.delete("group"); }
            if (dow)   { params.set("dow", dow);      } else { params.delete("dow"); }
            if (age)   { params.set("age", age);      } else { params.delete("age"); }
            var qs = params.toString();
            history.replaceState(null, "", qs ? "?" + qs : window.location.pathname);
        }

        searchInputs.forEach(function (inp) {
            inp.addEventListener("input",  function () { applyFilter(this.value); });
            inp.addEventListener("search", function () { applyFilter(this.value); });
        });

        resetBtns.forEach(function (btn) {
            btn.addEventListener("click", function () { applyFilter("", "", "", ""); });
        });

        document.querySelectorAll(".prog-filter-btn[data-filter-group]").forEach(function (btn) {
            btn.addEventListener("click", function () {
                // Switching away from the Film group drops the active age filter
                // so it doesn't linger hidden and confuse the user.
                var newGroup = this.dataset.filterGroup;
                var newAge = (newGroup === filmGroupSlug) ? activeAge : "";
                applyFilter(currentSearchTerm(), newGroup, undefined, newAge);
            });
        });

        document.querySelectorAll(".prog-filter-btn[data-dow-filter]").forEach(function (btn) {
            btn.addEventListener("click", function () {
                applyFilter(currentSearchTerm(), undefined, this.dataset.dowFilter);
            });
        });

        document.querySelectorAll(".prog-filter-btn[data-age-filter]").forEach(function (btn) {
            btn.addEventListener("click", function () {
                applyFilter(currentSearchTerm(), undefined, undefined, this.dataset.ageFilter);
            });
        });

        var params = new URLSearchParams(window.location.search);
        var initTerm  = params.get("search") || "";
        var initGroup = params.get("group")  || "";
        var initDow   = params.get("dow")    || "";
        var initAge   = params.get("age")    || "";
        if (initTerm || initGroup || initDow || initAge) { applyFilter(initTerm, initGroup, initDow, initAge); }
    });

})();
