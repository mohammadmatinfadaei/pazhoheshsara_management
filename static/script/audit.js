/* نوار لغزنده‌ی «پاک کردن مخزن» در صفحه‌ی اعمال کاربران */
(function () {
    "use strict";
    var form = document.querySelector(".purge-box");
    if (!form) return;

    var total = parseInt(form.getAttribute("data-total"), 10) || 0;
    var range = form.querySelector(".purge-range");
    var percentOut = form.querySelector("#purge-percent");
    var countOut = form.querySelector("#purge-count");
    var button = form.querySelector("button[type=submit]");
    var chips = form.querySelectorAll(".chip");

    function fa(n) { return String(n); }   // رقم لاتین، مثل بقیه‌ی برنامه

    // همان گرد کردنِ سرور: هر درصد بیشتر از صفر حداقل یک رکورد
    function countFor(percent) {
        return Math.min(total, Math.ceil(total * percent / 100));
    }

    function update() {
        var percent = parseInt(range.value, 10) || 0;
        percentOut.textContent = fa(percent) + "٪";
        countOut.textContent = fa(countFor(percent));
        range.style.setProperty("--fill", percent + "%");
        button.disabled = total === 0 || percent === 0;
        for (var i = 0; i < chips.length; i++) {
            var active = parseInt(chips[i].getAttribute("data-percent"), 10) === percent;
            chips[i].classList.toggle("active", active);
        }
    }

    range.addEventListener("input", update);
    for (var i = 0; i < chips.length; i++) {
        chips[i].addEventListener("click", function () {
            range.value = this.getAttribute("data-percent");
            update();
        });
    }

    form.addEventListener("submit", function (event) {
        var percent = parseInt(range.value, 10) || 0;
        var message = "قدیمی‌ترین " + fa(countFor(percent)) + " رکورد پاک شود؟ این کار برگشت‌پذیر نیست.";
        if (!window.confirm(message)) event.preventDefault();
    });

    update();
})();
