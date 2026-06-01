/* programme.js — client-side keyword search filter for the public programme page */
/* human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 4.6"]; status: "#ai-input" */
(function () {
    "use strict";

    $(document).ready(function () {
        var searchInputs = Array.prototype.slice.call(document.querySelectorAll("[data-prog-search]"));
        var resetBtns    = Array.prototype.slice.call(document.querySelectorAll("[data-prog-reset]"));

        if (!searchInputs.length) { return; }

        function applyFilter(term) {
            term = (term || "").toLowerCase().trim();

            searchInputs.forEach(function (inp) { inp.value = term; });
            resetBtns.forEach(function (btn) { btn.hidden = term.length === 0; });

            document.querySelectorAll(".programme > .showing").forEach(function (card) {
                var match = !term || (card.dataset.searchText || "").toLowerCase().indexOf(term) !== -1;
                card.classList.toggle("filter-hidden", !match);
            });

            $(".programme").masonry("layout");

            // Switch from list to grid when a filter is active
            if (term && $(".list").hasClass("active")) {
                $(".list").removeClass("active");
                $(".programme").show().stop().animate({ opacity: 1 });
            }

            var params = new URLSearchParams(window.location.search);
            if (term) { params.set("search", term); } else { params.delete("search"); }
            var qs = params.toString();
            history.replaceState(null, "", qs ? "?" + qs : window.location.pathname);
        }

        searchInputs.forEach(function (inp) {
            inp.addEventListener("input",  function () { applyFilter(this.value); });
            inp.addEventListener("search", function () { applyFilter(this.value); });
        });

        resetBtns.forEach(function (btn) {
            btn.addEventListener("click", function () { applyFilter(""); });
        });

        var initTerm = new URLSearchParams(window.location.search).get("search") || "";
        if (initTerm) { applyFilter(initTerm); }
    });

})();
