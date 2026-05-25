// human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-input"
document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".flatpickr-multidate").forEach(function (el) {
        flatpickr(el, {
            mode: "multiple",
            dateFormat: "Y-m-d",
            altInput: true,
            altFormat: "D j M Y",
            conjunction: ", ",
        });
    });
});
