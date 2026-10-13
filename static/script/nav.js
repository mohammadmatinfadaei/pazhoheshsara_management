(function () {
    var nav = document.getElementById("site-nav");
    var toggle = document.querySelector(".nav-toggle");
    var menus = document.querySelectorAll(".menu");

    function closeMenus(except) {
        menus.forEach(function (m) {
            if (m !== except) {
                m.classList.remove("open");
                m.querySelector(".menu-btn").setAttribute("aria-expanded", "false");
            }
        });
    }

    // دکمه منو در موبایل
    if (toggle && nav) {
        toggle.addEventListener("click", function (e) {
            e.stopPropagation();
            var open = !nav.classList.contains("open");
            nav.classList.toggle("open", open);
            toggle.setAttribute("aria-expanded", open ? "true" : "false");
            if (!open) closeMenus(null);
        });
    }

    // زیرمنوها
    menus.forEach(function (m) {
        var btn = m.querySelector(".menu-btn");
        btn.addEventListener("click", function (e) {
            e.stopPropagation();
            var open = !m.classList.contains("open");
            closeMenus(m);
            m.classList.toggle("open", open);
            btn.setAttribute("aria-expanded", open ? "true" : "false");
        });
    });

    document.addEventListener("click", function (e) {
        if (!e.target.closest(".submenu")) closeMenus(null);
    });

    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape") closeMenus(null);
    });
})();
