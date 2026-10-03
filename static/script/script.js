
    const themeBtn = document.getElementById("themeBtn");

    const themeIcon = document.getElementById("themeIcon");

    const themeText = document.getElementById("themeText");


    // بررسی حالت ذخیره شده

    const savedTheme = localStorage.getItem("theme");


    if (savedTheme === "light") {

        document.body.classList.add("light-mode");

        themeIcon.textContent = "🌙";

        themeText.textContent = "حالت تاریک";

    }


    // تغییر حالت

    themeBtn.addEventListener("click", function () {

        document.body.classList.toggle("light-mode");


        if (document.body.classList.contains("light-mode")) {

            // حالت روشن

            themeIcon.textContent = "🌙";

            themeText.textContent = "حالت تاریک";

            localStorage.setItem("theme", "light");

        }

        else {

            // حالت تاریک

            themeIcon.textContent = "☀️";

            themeText.textContent = "حالت روشن";

            localStorage.setItem("theme", "dark");

        }

    });



    