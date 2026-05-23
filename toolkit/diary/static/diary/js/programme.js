/* programme.js — client-side keyword search filter for the public programme page */
(function () {
    "use strict";

    $(document).ready(function () {
        var searchInput = document.getElementById("programme-search");
        var resetBtn    = document.getElementById("filter-reset");

        if (!searchInput) { return; }

        function applyFilter() {
            var term = (searchInput.value || "").toLowerCase().trim();

            resetBtn.hidden = term.length === 0;

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

        resetBtn.addEventListener("click", function () {
            searchInput.value = "";
            applyFilter();
        });

        searchInput.addEventListener("input",  applyFilter);
        searchInput.addEventListener("search", applyFilter);  // fires when native × is clicked

        var initTerm = new URLSearchParams(window.location.search).get("search") || "";
        if (initTerm) {
            searchInput.value = initTerm;
            applyFilter();
        }
    });

})();
