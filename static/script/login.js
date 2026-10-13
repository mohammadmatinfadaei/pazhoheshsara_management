(function () {
    var labels = {
        student_parent: "کد ملی دانش‌آموز",
        teacher: "کد ملی",
        staff: "کد پرسنلی"
    };
    var label = document.getElementById("identifier-label");
    var radios = document.querySelectorAll('input[name="role"]');

    function update() {
        radios.forEach(function (r) {
            if (r.checked) label.textContent = labels[r.value];
        });
    }
    radios.forEach(function (r) { r.addEventListener("change", update); });
    update();

    var toggle = document.getElementById("toggle-password");
    var pass = document.getElementById("password");
    toggle.addEventListener("click", function () {
        var show = pass.type === "password";
        pass.type = show ? "text" : "password";
        toggle.textContent = show ? "پنهان" : "نمایش";
    });
})();
