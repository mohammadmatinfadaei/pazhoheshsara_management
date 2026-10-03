  /* =========================
       جستجوی دانش آموز
    ========================= */

    const studentSearch = document.getElementById("student-search");
    const studentResults = document.getElementById("student-results");
    const studentId = document.getElementById("student-id");
    const selectedStudent = document.getElementById("selected-student");


    studentSearch.addEventListener("input", function () {

        const search = this.value.trim();

        studentId.value = "";
        selectedStudent.style.display = "none";

        if (!search) {
            studentResults.innerHTML = "";
            studentResults.style.display = "none";
            return;
        }

        fetch(
            "/search_students?search=" +
            encodeURIComponent(search)
        )
        .then(response => response.json())
        .then(data => {

            studentResults.innerHTML = "";

            if (data.length === 0) {
                studentResults.innerHTML =
                    '<div class="result-item">دانش‌آموزی پیدا نشد</div>';

                studentResults.style.display = "block";
                return;
            }

            data.forEach(student => {

                const item = document.createElement("div");

                item.className = "result-item";

                item.innerHTML = `
                    <div class="result-main">
                        ${student.first_name} ${student.last_name}
                    </div>

                    <div class="result-info">
                        کد دانش‌آموزی:
                        ${student.student_id_code}
                    </div>
                `;

                item.addEventListener("click", function () {

                    studentSearch.value =
                        student.first_name + " " + student.last_name;

                    studentId.value = student.id;

                    selectedStudent.innerHTML = `
                        <strong>
                            👨‍🎓 ${student.first_name}
                            ${student.last_name}
                        </strong>

                        <span>
                            کد دانش‌آموزی:
                            ${student.student_id_code}
                        </span>
                    `;

                    selectedStudent.style.display = "block";

                    studentResults.innerHTML = "";
                    studentResults.style.display = "none";

                });

                studentResults.appendChild(item);

            });

            studentResults.style.display = "block";

        })
        .catch(error => {

            console.error(error);

        });

    });


    /* =========================
       تابع جستجوی کتاب
    ========================= */

    function setupBookSearch(number) {

        const searchInput =
            document.getElementById("book" + number + "-search");

        const results =
            document.getElementById("book" + number + "-results");

        const hiddenId =
            document.getElementById("book" + number + "-id");

        const selected =
            document.getElementById("selected-book" + number);


        searchInput.addEventListener("input", function () {

            const search = this.value.trim();

            hiddenId.value = "";
            selected.style.display = "none";

            if (!search) {

                results.innerHTML = "";
                results.style.display = "none";

                return;

            }


            fetch(
                "/search_books?search=" +
                encodeURIComponent(search)
            )
            .then(response => response.json())
            .then(data => {

                results.innerHTML = "";

                if (data.length === 0) {

                    results.innerHTML =
                        '<div class="result-item">کتابی پیدا نشد</div>';

                    results.style.display = "block";

                    return;
                }


                data.forEach(book => {

                    const item =
                        document.createElement("div");

                    item.className = "result-item";

                    item.innerHTML = `
                        <div class="result-main">
                            ${book.book_title}
                        </div>

                        <div class="result-info">
                            شماره کنگره:
                            ${book.congress_number}
                        </div>
                    `;


                    item.addEventListener("click", function () {

                        searchInput.value =
                            book.book_title;

                        hiddenId.value =
                            book.id;


                        selected.innerHTML = `
                            <strong>
                                📖 ${book.book_title}
                            </strong>

                            <span>
                                شماره کنگره:
                                ${book.congress_number}
                            </span>
                        `;

                        selected.style.display = "block";

                        results.innerHTML = "";
                        results.style.display = "none";

                    });


                    results.appendChild(item);

                });


                results.style.display = "block";

            })
            .catch(error => {

                console.error(error);

            });

        });

    }


    /* فعال کردن جستجوی هر سه کتاب */

    setupBookSearch(1);
    setupBookSearch(2);
    setupBookSearch(3);


    /* =========================
       بستن لیست‌ها با کلیک بیرون
    ========================= */

    document.addEventListener("click", function (event) {

        if (!event.target.closest(".search-group")) {

            document
                .querySelectorAll(".search-results")
                .forEach(function (element) {

                    element.style.display = "none";

                });

        }

    });