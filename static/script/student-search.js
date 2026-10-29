/* جستجوی لحظه‌ای دانش‌آموز در صفحه‌ی «ثبت دانش‌آموز در دوره»: نام، نام پدر یا کد ملی */
(function () {
    "use strict";
    var combo = document.querySelector(".combo");
    if (!combo) return;

    var input = combo.querySelector("#student-search");
    var hidden = combo.querySelector("#national_id_number");
    var list = combo.querySelector("#student-results");
    var note = document.getElementById("student-selected");
    var form = combo.closest("form");
    var url = combo.getAttribute("data-url");

    var timer = null, controller = null, items = [], active = -1;

    function closeList() {
        list.hidden = true;
        list.textContent = "";
        items = [];
        active = -1;
        input.setAttribute("aria-expanded", "false");
        input.removeAttribute("aria-activedescendant");
    }

    function showNote(text, isError) {
        note.hidden = !text;
        note.textContent = text || "";
        note.classList.toggle("error", !!isError);
    }

    function describe(r) {
        return r.name + (r.father ? " — پدر: " + r.father : "") + " — کد ملی: " + r.nid;
    }

    function highlight(index) {
        var nodes = list.querySelectorAll(".combo-item");
        for (var i = 0; i < nodes.length; i++) {
            nodes[i].classList.toggle("active", i === index);
            nodes[i].setAttribute("aria-selected", i === index ? "true" : "false");
        }
        active = index;
        if (index >= 0) input.setAttribute("aria-activedescendant", "student-opt-" + index);
        else input.removeAttribute("aria-activedescendant");
    }

    function choose(index) {
        var r = items[index];
        if (!r) return;
        hidden.value = r.nid;
        input.value = r.name;
        closeList();
        showNote("انتخاب شد: " + describe(r), false);
    }

    function render(results) {
        list.textContent = "";
        items = results;
        active = -1;
        if (!results.length) {
            var empty = document.createElement("li");
            empty.className = "combo-empty";
            empty.textContent = "دانش‌آموزی پیدا نشد (یا قبلاً در این دوره ثبت شده است).";
            list.appendChild(empty);
        }
        results.forEach(function (r, i) {
            var li = document.createElement("li");
            li.id = "student-opt-" + i;
            li.className = "combo-item";
            li.setAttribute("role", "option");
            var name = document.createElement("strong");
            name.textContent = r.name;
            var meta = document.createElement("span");
            meta.textContent = (r.father ? "پدر: " + r.father + " — " : "") + "کد ملی: " + r.nid;
            li.appendChild(name);
            li.appendChild(meta);
            // mousedown (نه click) تا قبل از بسته شدن لیست با blur انتخاب شود
            li.addEventListener("mousedown", function (event) {
                event.preventDefault();
                choose(i);
            });
            list.appendChild(li);
        });
        list.hidden = false;
        input.setAttribute("aria-expanded", "true");
    }

    function search(q) {
        if (controller) controller.abort();
        controller = new AbortController();
        fetch(url + "?q=" + encodeURIComponent(q), {
            headers: { "Accept": "application/json" },
            credentials: "same-origin",
            signal: controller.signal
        })
            .then(function (response) { return response.ok ? response.json() : { results: [] }; })
            .then(function (data) {
                if (input.value.trim() === q) render(data.results || []);   // جواب قدیمی را نشان نده
            })
            .catch(function (error) {
                if (error.name !== "AbortError") closeList();
            });
    }

    input.addEventListener("input", function () {
        hidden.value = "";            // با هر تغییر متن، انتخاب قبلی باطل می‌شود
        showNote("", false);
        clearTimeout(timer);
        var q = input.value.trim();
        if (q.length < 2) {
            if (controller) controller.abort();
            closeList();
            return;
        }
        timer = setTimeout(function () { search(q); }, 200);
    });

    input.addEventListener("keydown", function (event) {
        if (list.hidden || !items.length) return;
        if (event.key === "ArrowDown") {
            event.preventDefault();
            highlight((active + 1) % items.length);
        } else if (event.key === "ArrowUp") {
            event.preventDefault();
            highlight((active - 1 + items.length) % items.length);
        } else if (event.key === "Enter" && active >= 0) {
            event.preventDefault();
            choose(active);
        } else if (event.key === "Escape") {
            closeList();
        }
    });

    input.addEventListener("blur", function () { setTimeout(closeList, 120); });

    form.addEventListener("submit", function (event) {
        var typed = input.value.trim();
        // کد ملی کامل را مستقیم تایپ/چسبانده و انتخاب نکرده؛ همان را بفرست
        if (!hidden.value && /^[0-9]{5,}$/.test(typed)) hidden.value = typed;
        if (!hidden.value) {
            event.preventDefault();
            showNote("ابتدا دانش‌آموز را از بین نتایج جستجو انتخاب کنید.", true);
            input.focus();
        }
    });
})();
