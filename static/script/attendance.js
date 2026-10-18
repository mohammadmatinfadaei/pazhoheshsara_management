(function () {
    var all = document.getElementById("select-all");
    var boxes = document.querySelectorAll(".present-box");
    if (!all || !boxes.length) return;

    function syncAll() {
        var checked = 0;
        boxes.forEach(function (b) { if (b.checked) checked += 1; });
        all.checked = checked === boxes.length;
    }

    all.addEventListener("change", function () {
        boxes.forEach(function (b) { b.checked = all.checked; });
    });
    boxes.forEach(function (b) { b.addEventListener("change", syncAll); });
    syncAll();
})();
