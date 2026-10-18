import hmac
import math
import os
import re
import secrets
import time
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from types import SimpleNamespace
from functools import wraps

from flask import (
    Response, abort, flash, redirect, render_template, request, send_file,
    send_from_directory, session, url_for
)
from sqlalchemy import func, or_
from werkzeug.security import check_password_hash, generate_password_hash

# فایل دیتابیس شما را با نام models.py ذخیره کنید
from models import (
    Admins, Attendance, Classes, Courses, Linking_the_course_to_the_class,
    Linking_the_items_to_the_locker, Linking_the_student_to_the_course, List_of_items, Loans, Lockers, Notes,
    Payments, Renting_out_a_class, Students, TeacherPayments, Teachers, app, db
)


# =========================================================
# SECURITY CONFIG
# =========================================================

def load_secret_key():
    """کلید مخفی از متغیر محیطی یا از فایل instance/secret_key خوانده می‌شود.
    اگر وجود نداشت، یک کلید تصادفی ساخته و ذخیره می‌شود."""
    env_key = os.environ.get("SECRET_KEY")
    if env_key:
        return env_key
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "instance", "secret_key")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    key = secrets.token_hex(32)
    with open(path, "w", encoding="utf-8") as f:
        f.write(key)
    return key


app.config.update(
    SECRET_KEY=load_secret_key(),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    # پس از فعال‌سازی HTTPS مقدار زیر را True کنید
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "0") == "1",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=2),
    MAX_CONTENT_LENGTH=12 * 1024 * 1024,  # دو تصویر ۵ مگابایتی + فیلدهای فرم
)

# کد ورود ثابت کارمندان (از مدیر دریافت می‌شود)
# بهتر است در سرور با متغیر محیطی STAFF_ENTRY_CODE تنظیم شود
STAFF_ENTRY_CODE = os.environ.get("STAFF_ENTRY_CODE", "pss1405")

ROLES = {
    "student_parent": "دانش‌آموز و والدین",
    "teacher": "دبیران",
    "staff": "کارمندان آموزشگاه",
}


# منوی نوار بالای ادمین؛ ترتیب از راست به چپ نمایش داده می‌شود
ADMIN_MENU = [
    {"key": "teachers", "title": "دبیران", "items": [
        ("add", "افزودن دبیر"),
        ("list-obligated", "لیست دبیران موظف"),
        ("list-non-obligated", "لیست دبیران غیر موظف"),
        ("list-misc", "لیست دبیران متفرقه"),
    ]},
    {"key": "students", "title": "دانش‌آموزان", "items": [
        ("add", "افزودن دانش‌آموز"),
        ("list-regular", "لیست تمام دانش‌آموزان عادی"),
        ("list-active", "لیست دانش‌آموزان فعال"),
        ("list-researcher", "لیست دانش‌آموزان پژوهشگر"),
        ("export-excel", "دانلود فایل اکسل تمامی دانش‌آموزان"),
    ]},
    {"key": "classes", "title": "مدیریت کلاس‌ها", "items": [
        ("add-class", "افزودن کلاس"),
        ("list", "لیست کلاس‌ها"),
        ("add-course", "افزودن دوره"),
        ("list-courses", "لیست دوره‌ها"),
        ("enroll", "ثبت دانش‌آموز در دوره"),
        ("rent-misc-teachers", "اجاره کلاس به دبیران متفرقه"),
        ("rentals", "لیست اجاره‌ها"),
        ("rent-courses", "اجاره کلاس برای دوره‌ها"),
        ("course-schedule", "لیست دوره‌ها در کلاس‌ها"),
    ]},
    {"key": "finance", "title": "امور مالی", "items": [
        ("today-turnover", "گردش مالی امروز"),
        ("debts", "بدهی‌ها"),
        ("receivables", "طلب‌های آموزشگاه"),
    ]},
    {"key": "lockers", "title": "کمدها", "items": [
        ("add", "افزودن کمد"),
        ("list", "لیست تمامی کمدها"),
    ]},
    {"key": "equipment", "title": "تمام تجهیزات", "items": [
        ("add", "افزودن وسیله"),
        ("list", "لیست وسایل"),
        ("loan", "امانت دادن وسایل"),
        ("loans", "لیست امانت‌ها"),
    ]},
    {"key": "notes", "title": "یادداشت‌ها", "items": [
        ("write", "نوشتن یادداشت"),
        ("today", "یادداشت‌های امروز"),
    ]},
]

# منوی دانش‌آموز/والدین و دبیران
_PROFILE = {"key": "profile", "title": "پروفایل شما", "link": "profile"}

_CLASSES = {"key": "classes", "title": "کلاس‌ها", "items": [
    ("all", "کل کلاس‌های شما"),
    ("today", "کلاس‌های امروز"),
]}

USER_MENUS = {
    "student_parent": [_PROFILE, _CLASSES],
    "teacher": [
        _PROFILE,
        _CLASSES,
        {"key": "finance", "title": "امور مالی", "items": [
            ("debts", "بدهی‌ها"),
            ("receivables", "طلب‌ها"),
        ]},
    ],
}

MAX_FAILS = 5          # تعداد تلاش ناموفق
LOCK_SECONDS = 10 * 60  # مدت قفل (ثانیه)
FAILED = {}            # {key: {"count": n, "until": t}}

# هش ساختگی برای یکسان‌سازی زمان پاسخ وقتی کاربر وجود ندارد
DUMMY_HASH = generate_password_hash("dummy-password-for-timing")


# =========================================================
# HELPERS
# =========================================================

_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


# نویسه‌های نامرئی که هنگام تایپ/کپی با کیبورد فارسی وارد می‌شوند
# (نیم‌فاصله، علامت‌های جهت متن، BOM) و باعث رد شدن عددهای درست می‌شوند
_INVISIBLE = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u200e\u200f"
                               "\u202a\u202b\u202c\u202d\u202e"
                               "\u2066\u2067\u2068\u2069\ufeff"), None)


def clean(value, max_len=100):
    """حذف فاصله‌های کناری و نویسه‌های نامرئی و تبدیل ارقام فارسی/عربی به انگلیسی"""
    text = (value or "").translate(_INVISIBLE).strip().translate(_DIGITS)
    return text[:max_len]


def clean_digits(value, max_len=40):
    """برای فیلدهای عددی (کد ملی، تلفن، ...): همه فاصله‌ها هم حذف می‌شوند"""
    return re.sub(r"\s+", "", clean(value, 200))[:max_len]


def clean_text(value, max_len=50):
    """فاصله‌های اضافه را حذف و «ي» و «ك» عربی را به «ی» و «ک» فارسی تبدیل می‌کند"""
    text = (value or "").replace("ي", "ی").replace("ك", "ک")
    return re.sub(r"\s+", " ", text.strip())[:max_len]


def verify_password(stored_hash, password):
    if not stored_hash:
        check_password_hash(DUMMY_HASH, password)
        return False
    try:
        return check_password_hash(stored_hash, password)
    except ValueError:
        return False


def password_error(password, confirm):
    if len(password) < 8:
        return "رمز عبور باید حداقل ۸ کاراکتر باشد."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "رمز عبور باید شامل حروف انگلیسی و عدد باشد."
    if password != confirm:
        return "رمز عبور و تکرار آن یکسان نیست."
    return None


def lock_remaining(key):
    rec = FAILED.get(key)
    if rec and rec["until"] > time.time():
        return int(rec["until"] - time.time())
    return 0


def register_fail(key):
    rec = FAILED.get(key)
    if not rec or (rec["until"] and rec["until"] <= time.time()):
        rec = {"count": 0, "until": 0}
    rec["count"] += 1
    if rec["count"] >= MAX_FAILS:
        rec["until"] = time.time() + LOCK_SECONDS
        rec["count"] = 0
    FAILED[key] = rec


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("برای ادامه ابتدا وارد شوید.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapper


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if session.get("role") not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapper
    return decorator


# =========================================================
# CSRF + SECURITY HEADERS
# =========================================================

def get_csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(32)
    return session["csrf"]


app.jinja_env.globals["csrf_token"] = get_csrf_token


def site_url():
    """آدرس پایه سایت برای canonical و sitemap؛ در سرور SITE_URL را تنظیم کنید."""
    return os.environ.get("SITE_URL", "").rstrip("/") or request.url_root.rstrip("/")


app.jinja_env.globals["site_url"] = site_url
app.jinja_env.filters["money"] = lambda value: f"{int(value or 0):,}"


@app.context_processor
def inject_nav_menu():
    """منوی نوبار را براساس نقش کاربر وارد‌شده می‌سازد."""
    role = session.get("role")
    if role == "admin":
        menu, endpoint = ADMIN_MENU, "admin_page"
    elif role in USER_MENUS:
        menu, endpoint = USER_MENUS[role], "panel_page"
    else:
        return {"nav_menu": []}

    nav = []
    for sec in menu:
        if sec.get("link"):
            nav.append({"title": sec["title"], "href": url_for(sec["link"])})
        else:
            nav.append({
                "title": sec["title"],
                "items": [(url_for(endpoint, section=sec["key"], item=key), title)
                          for key, title in sec["items"]],
            })
    return {"nav_menu": nav}


@app.before_request
def csrf_protect():
    if request.method == "POST":
        sent = request.form.get("csrf_token", "")
        real = session.get("csrf", "")
        if not real or not hmac.compare_digest(sent, real):
            abort(400)


@app.after_request
def security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "same-origin"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; frame-ancestors 'none'"
    )
    if request.endpoint in ("login", "register", "dashboard", "admin_page", "panel_page", "profile",
                            "teacher_add", "teacher_edit",
                            "teachers_obligated", "teachers_non_obligated",
                            "teachers_misc", "teacher_profile", "student_add",
                            "students_regular", "students_active",
                            "students_researcher", "student_profile", "student_edit",
                            "student_photo", "students_export_excel",
                            "students_export_excel_type", "class_add", "classes_list", "class_delete",
                            "rent_add", "rentals_list", "rental_cancel",
                            "schedule_add", "schedules_list", "schedule_cancel",
                            "finance_today", "finance_debts", "finance_receivables",
                            "teacher_pay", "teacher_today", "teacher_courses",
                            "attendance_take",
                            "course_add", "courses_list", "course_edit",
                            "enroll_pick", "course_students", "course_payment", "course_delete",
                            "teacher_delete", "student_delete", "note_write",
                            "note_today", "note_done", "locker_add", "lockers_list",
                            "locker_items", "locker_delete", "item_add",
                            "items_list", "item_edit", "item_delete", "loan_add",
                            "loans_list", "loan_return"):
        resp.headers["Cache-Control"] = "no-store"
    # فقط صفحه اصلی باید در گوگل ایندکس شود
    if request.endpoint not in ("index", "robots", "sitemap", "static"):
        resp.headers["X-Robots-Tag"] = "noindex, nofollow"
    return resp


# =========================================================
# ROUTES
# =========================================================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/robots.txt")
def robots():
    body = (
        "User-agent: *\n"
        "Disallow: /admin/\n"
        "Disallow: /panel/\n"
        "Disallow: /dashboard\n"
        "\n"
        f"Sitemap: {site_url()}/sitemap.xml\n"
    )
    return Response(body, mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap():
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"  <url><loc>{site_url()}/</loc></url>\n"
        "</urlset>\n"
    )
    return Response(xml, mimetype="application/xml")


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    selected_role = "student_parent"

    if request.method == "POST":
        selected_role = request.form.get("role", "")
        identifier = clean_digits(request.form.get("identifier"), 20)
        password = request.form.get("password", "")

        if selected_role not in ROLES:
            abort(400)

        key = (request.remote_addr, selected_role, identifier)
        wait = lock_remaining(key)
        if wait:
            flash(f"تلاش‌های ناموفق زیاد بود. {wait // 60 + 1} دقیقه بعد دوباره امتحان کنید.", "error")
            return render_template("login.html", roles=ROLES, selected_role=selected_role), 429

        user, role, name = None, None, None

        if selected_role == "student_parent":
            user = Students.query.filter_by(national_id_number=identifier).first()
            if user:
                role, name = "student_parent", f"{user.first_name or ''} {user.last_name or ''}".strip()

        elif selected_role == "teacher":
            user = Teachers.query.filter_by(national_id_number=identifier).first()
            if user:
                role, name = "teacher", f"{user.first_name or ''} {user.last_name or ''}".strip()

        elif selected_role == "staff":
            # کارمند و مدیر یکی هستند؛ ورود با کد پرسنلی
            user = Admins.query.filter_by(personnel_code=identifier).first()
            if user:
                role = "admin"
                name = f"{user.first_name or ''} {user.last_name or ''}".strip()

        if user and verify_password(user.password, password):
            if role == "teacher" and user.type == "متفرقه":
                # دبیران متفرقه اصلاً وارد سایت نمی‌شوند
                flash("دبیران متفرقه امکان ورود به سامانه را ندارند.", "error")
                return render_template("login.html", roles=ROLES, selected_role=selected_role), 403
            session.clear()
            session.permanent = True
            session["user_id"] = user.id
            session["role"] = role
            session["name"] = name
            session["csrf"] = secrets.token_hex(32)
            FAILED.pop(key, None)
            return redirect(url_for("dashboard"))

        if not user:
            verify_password(None, password)
        register_fail(key)
        # پیام یکسان تا مشخص نشود کدام بخش اشتباه است
        flash("اطلاعات ورود نادرست است.", "error")

    return render_template("login.html", roles=ROLES, selected_role=selected_role)


@app.route("/register", methods=["GET", "POST"])
def register():
    """ثبت‌نام کارمندان؛ فقط با کد ورودی که مدیر داده است."""
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    form = {}

    if request.method == "POST":
        form = {
            "first_name": clean_text(request.form.get("first_name")),
            "last_name": clean_text(request.form.get("last_name")),
            "personnel_code": clean_digits(request.form.get("personnel_code"), 20),
            "national_id_number": clean_digits(request.form.get("national_id_number"), 40),
        }
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        entry_code = request.form.get("entry_code", "").strip()

        key = (request.remote_addr, "register", "")
        wait = lock_remaining(key)
        if wait:
            flash(f"تلاش‌های ناموفق زیاد بود. {wait // 60 + 1} دقیقه بعد دوباره امتحان کنید.", "error")
            return render_template("register.html", form=form), 429

        error = None
        if not hmac.compare_digest(entry_code.encode(), STAFF_ENTRY_CODE.encode()):
            register_fail(key)
            error = "کد ورود نادرست است. این کد را از مدیر دریافت کنید."
        elif not form["first_name"] or not form["last_name"]:
            error = "نام و نام خانوادگی را وارد کنید."
        elif not re.fullmatch(r"\d{3,20}", form["personnel_code"]):
            error = "کد پرسنلی باید فقط عدد باشد (حداقل ۳ رقم)."
        elif not form["national_id_number"]:
            error = "کد ملی را وارد کنید."
        else:
            error = password_error(password, confirm)

        if not error and Admins.query.filter_by(personnel_code=form["personnel_code"]).first():
            error = "این کد پرسنلی قبلاً ثبت شده است."
        if not error and Admins.query.filter_by(national_id_number=form["national_id_number"]).first():
            error = "این کد ملی قبلاً ثبت شده است."

        if error:
            flash(error, "error")
            return render_template("register.html", form=form)

        db.session.add(Admins(
            first_name=form["first_name"],
            last_name=form["last_name"],
            personnel_code=form["personnel_code"],
            national_id_number=form["national_id_number"],
            password=generate_password_hash(password),
        ))
        db.session.commit()
        FAILED.pop(key, None)
        flash("ثبت‌نام انجام شد. اکنون وارد شوید.", "success")
        return redirect(url_for("login"))

    return render_template("register.html", form=form)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("از حساب خود خارج شدید.", "success")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    """ابتدا نقش کاربر بررسی می‌شود و صفحه مناسب همان نقش نمایش داده می‌شود."""
    role = session.get("role")
    if role not in ("admin", "teacher", "student_parent"):
        session.clear()
        return redirect(url_for("login"))
    rows, today = [], None
    if role == "teacher":
        teacher = current_teacher()
        if not teacher:  # مثلاً بعد از ورود، نوعش به «متفرقه» تغییر کرده است
            session.clear()
            flash("دبیران متفرقه به سامانه دسترسی ندارند.", "error")
            return redirect(url_for("login"))
        rows, today = teacher_today_rows(teacher), format_jalali(*today_jalali())
    return render_template("dashboard.html", role=role, rows=rows, today=today)


@app.route("/admin/<section>/<item>")
@login_required
@role_required("admin")
def admin_page(section, item):
    """صفحه‌های زیرمنوی ادمین؛ فعلاً نگه‌دارنده تا هر کدام ساخته شوند."""
    for sec in ADMIN_MENU:
        if sec["key"] == section:
            for key, title in sec["items"]:
                if key == item:
                    return render_template("placeholder_page.html",
                                           section_title=sec["title"],
                                           page_title=title)
    abort(404)


# =========================================================
# TEACHERS (افزودن و لیست دبیران)
# =========================================================

PER_PAGE = 30  # تعداد دبیر در هر صفحه از لیست

TEACHER_TYPES = ["موظف", "غیر موظف", "متفرقه"]

# هر نوع دبیر صفحه، مسیر و قالب مخصوص خودش را دارد
TEACHER_LIST_PAGES = {
    "موظف": {"endpoint": "teachers_obligated", "template": "teachers_obligated.html"},
    "غیر موظف": {"endpoint": "teachers_non_obligated", "template": "teachers_non_obligated.html"},
    "متفرقه": {"endpoint": "teachers_misc", "template": "teachers_misc.html"},
}

EDU_LEVELS = ["دیپلم", "کاردانی", "کارشناسی", "کارشناسی ارشد", "دکتری"]
MARITAL_STATUSES = ["مجرد", "متأهل"]

TEACHER_FIELDS = [
    "first_name", "last_name", "father_name", "date_of_birth",
    "national_id_number", "marital_status",
    "phone_number", "landline_number", "email", "postal_code", "address",
    "personnel_number", "type", "date_of_hire", "place_of_employment",
    "educational_qualification", "university_major",
    "year_of_obtaining_the_degree",
    "credit_card_number", "account_number", "iban", "note",
]

_DIGIT_FIELDS = {
    "date_of_birth", "date_of_hire", "national_id_number", "phone_number",
    "landline_number", "postal_code", "personnel_number",
    "year_of_obtaining_the_degree", "credit_card_number", "account_number",
    "iban",
}
_MAX_LEN = {"address": 300, "note": 500}

# فیلدهای اختیاری که اگر پر شدند باید الگوی درست داشته باشند
_OPTIONAL_PATTERNS = {
    "landline_number": (r"\d{5,11}", "تلفن ثابت نامعتبر است."),
    "email": (r"[^@\s]+@[^@\s]+\.[^@\s]+", "ایمیل نامعتبر است."),
    "postal_code": (r"\d{10}", "کد پستی باید ۱۰ رقم باشد."),
    "year_of_obtaining_the_degree": (r"\d{4}", "سال اخذ مدرک باید ۴ رقم باشد."),
    "credit_card_number": (r"\d{16}", "شماره کارت باید ۱۶ رقم باشد."),
    "account_number": (r"[\d.\-]{5,30}", "شماره حساب نامعتبر است."),
    "iban": (r"IR\d{24}", "شماره شبا باید با IR شروع شود و ۲۴ رقم داشته باشد."),
    "date_of_birth": (r"\d{4}/\d{1,2}/\d{1,2}", "تاریخ تولد را به شکل ۱۳۸۰/۰۵/۱۲ وارد کنید."),
    "date_of_hire": (r"\d{4}/\d{1,2}/\d{1,2}", "تاریخ استخدام را به شکل ۱۴۰۳/۰۶/۰۱ وارد کنید."),
}

TEACHER_PROFILE_GROUPS = [
    ("اطلاعات شخصی", [
        ("نام", "first_name"), ("نام خانوادگی", "last_name"),
        ("نام پدر", "father_name"), ("تاریخ تولد", "date_of_birth"),
        ("کد ملی", "national_id_number"), ("وضعیت تأهل", "marital_status"),
    ]),
    ("اطلاعات تماس", [
        ("تلفن همراه", "phone_number"), ("تلفن ثابت", "landline_number"),
        ("ایمیل", "email"), ("کد پستی", "postal_code"), ("آدرس", "address"),
    ]),
    ("اطلاعات شغلی و تحصیلی", [
        ("کد پرسنلی", "personnel_number"), ("نوع دبیر", "type"),
        ("تاریخ استخدام", "date_of_hire"), ("محل اشتغال", "place_of_employment"),
        ("مدرک تحصیلی", "educational_qualification"),
        ("رشته دانشگاهی", "university_major"),
        ("سال اخذ مدرک", "year_of_obtaining_the_degree"),
    ]),
    ("اطلاعات مالی", [
        ("شماره کارت", "credit_card_number"), ("شماره حساب", "account_number"),
        ("شماره شبا", "iban"),
    ]),
    ("توضیحات", [("یادداشت", "note")]),
]


def collect_teacher_form(src):
    """مقادیر فرم را پاک‌سازی می‌کند (ارقام فارسی -> انگلیسی، حذف فاصله اضافه)"""
    form = {}
    for name in TEACHER_FIELDS:
        raw = src.get(name, "")
        if name in _DIGIT_FIELDS:
            value = clean_digits(raw, 40)
            if name == "credit_card_number":
                value = re.sub(r"[\s-]", "", value)
            if name == "iban":
                value = value.replace(" ", "").upper()
                if re.fullmatch(r"\d{24}", value):
                    value = "IR" + value
        else:
            value = clean_text(raw, _MAX_LEN.get(name, 80))
        form[name] = value
    form["email"] = form["email"].lower()
    return form


def validate_teacher_form(form, password, confirm, require_password=True):
    """اعتبارسنجی بدون دیتابیس؛ در صورت خطا متن خطا برمی‌گردد."""
    if not form["first_name"] or not form["last_name"]:
        return "نام و نام خانوادگی را وارد کنید."
    if not form["national_id_number"]:
        return "کد ملی را وارد کنید."
    if not re.fullmatch(r"\d{1,20}", form["personnel_number"]):
        return "شماره پرسنلی باید فقط عدد باشد."
    if not re.fullmatch(r"09\d{9}", form["phone_number"]):
        return "تلفن همراه باید ۱۱ رقم باشد و با ۰۹ شروع شود."
    if form["type"] not in TEACHER_TYPES:
        return "نوع دبیر را انتخاب کنید."
    if form["educational_qualification"] and form["educational_qualification"] not in EDU_LEVELS:
        return "مدرک تحصیلی نامعتبر است."
    if form["marital_status"] and form["marital_status"] not in MARITAL_STATUSES:
        return "وضعیت تأهل نامعتبر است."
    for name, (pattern, message) in _OPTIONAL_PATTERNS.items():
        if form[name] and not re.fullmatch(pattern, form[name]):
            return message
    # در ویرایش، رمز خالی یعنی «رمز تغییر نکند»
    if not require_password and not password and not confirm:
        return None
    return password_error(password, confirm)


def escape_like(text):
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@app.route("/admin/teachers/add", methods=["GET", "POST"])
@login_required
@role_required("admin")
def teacher_add():
    form = {}

    if request.method == "POST":
        form = collect_teacher_form(request.form)
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        error = validate_teacher_form(form, password, confirm)
        if not error and Teachers.query.filter_by(
                national_id_number=form["national_id_number"]).first():
            error = "دبیری با این کد ملی قبلاً ثبت شده است."
        if not error and Teachers.query.filter_by(
                personnel_number=form["personnel_number"]).first():
            error = "دبیری با این شماره پرسنلی قبلاً ثبت شده است."

        if error:
            flash(error, "error")
        else:
            teacher = Teachers(
                **{key: (value or None) for key, value in form.items()},
                password=generate_password_hash(password),
            )
            db.session.add(teacher)
            db.session.commit()
            flash("دبیر با موفقیت ثبت شد.", "success")
            return redirect(url_for(TEACHER_LIST_PAGES[form["type"]]["endpoint"]))

    return render_template("teacher_add.html", form=form, is_edit=False,
                           teacher_types=TEACHER_TYPES,
                           edu_levels=EDU_LEVELS,
                           marital_statuses=MARITAL_STATUSES)


def render_teacher_list(teacher_type):
    """منطق مشترک جستجو و صفحه‌بندی؛ هر نوع دبیر قالب جدا و مسیر جدا دارد."""
    page_cfg = TEACHER_LIST_PAGES[teacher_type]

    q = clean_text(clean(request.args.get("q"), 60), 60)
    query = Teachers.query.filter_by(type=teacher_type)

    # هر کلمه جستجو باید در یکی از ستون‌ها پیدا شود
    for term in q.split():
        like = "%" + escape_like(term) + "%"
        query = query.filter(or_(
            Teachers.first_name.ilike(like, escape="\\"),
            Teachers.last_name.ilike(like, escape="\\"),
            Teachers.national_id_number.ilike(like, escape="\\"),
            Teachers.personnel_number.ilike(like, escape="\\"),
            Teachers.phone_number.ilike(like, escape="\\"),
        ))

    total = query.count()
    pages = max(1, math.ceil(total / PER_PAGE))
    page = min(max(request.args.get("page", 1, type=int), 1), pages)

    pagination = query.order_by(
        Teachers.last_name, Teachers.first_name, Teachers.id
    ).paginate(page=page, per_page=PER_PAGE, error_out=False)

    return render_template(page_cfg["template"],
                           teachers=pagination.items,
                           pagination=pagination,
                           pages=pages,
                           total=total,
                           q=q,
                           list_endpoint=page_cfg["endpoint"])


@app.route("/admin/teachers/list-obligated")
@login_required
@role_required("admin")
def teachers_obligated():
    return render_teacher_list("موظف")


@app.route("/admin/teachers/list-non-obligated")
@login_required
@role_required("admin")
def teachers_non_obligated():
    return render_teacher_list("غیر موظف")


@app.route("/admin/teachers/list-misc")
@login_required
@role_required("admin")
def teachers_misc():
    return render_teacher_list("متفرقه")


@app.route("/admin/teachers/profile/<int:teacher_id>")
@login_required
@role_required("admin")
def teacher_profile(teacher_id):
    teacher = db.session.get(Teachers, teacher_id)
    if not teacher:
        abort(404)
    return render_template("teacher_profile.html", teacher=teacher,
                           groups=TEACHER_PROFILE_GROUPS,
                           back_endpoint=TEACHER_LIST_PAGES.get(teacher.type, TEACHER_LIST_PAGES["موظف"])["endpoint"])


@app.route("/admin/teachers/edit/<int:teacher_id>", methods=["GET", "POST"])
@login_required
@role_required("admin")
def teacher_edit(teacher_id):
    teacher = db.session.get(Teachers, teacher_id)
    if not teacher:
        abort(404)

    # در حالت GET فرم با اطلاعات فعلی دبیر پر می‌شود
    form = {name: getattr(teacher, name) or "" for name in TEACHER_FIELDS}

    if request.method == "POST":
        form = collect_teacher_form(request.form)
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        error = validate_teacher_form(form, password, confirm, require_password=False)
        if not error and Teachers.query.filter(
                Teachers.national_id_number == form["national_id_number"],
                Teachers.id != teacher.id).first():
            error = "دبیر دیگری با این کد ملی ثبت شده است."
        if not error and Teachers.query.filter(
                Teachers.personnel_number == form["personnel_number"],
                Teachers.id != teacher.id).first():
            error = "دبیر دیگری با این شماره پرسنلی ثبت شده است."

        if error:
            flash(error, "error")
        else:
            old_national_id = teacher.national_id_number
            new_national_id = form["national_id_number"]

            for name, value in form.items():
                setattr(teacher, name, value or None)
            if password:
                teacher.password = generate_password_hash(password)

            # دوره‌ها، اجاره‌ها و یادداشت‌ها با کد ملی به دبیر وصل‌اند؛
            # اگر کد ملی عوض شد باید همین‌جا هم به‌روز شوند تا ارتباط‌ها گم نشوند
            if old_national_id and old_national_id != new_national_id:
                Courses.query.filter_by(
                    course_instructor_national_id_number=old_national_id
                ).update({"course_instructor_national_id_number": new_national_id})
                Renting_out_a_class.query.filter_by(
                    teacher_national_id_number=old_national_id
                ).update({"teacher_national_id_number": new_national_id})
                Notes.query.filter_by(
                    national_id_number=old_national_id
                ).update({"national_id_number": new_national_id})

            db.session.commit()
            flash("اطلاعات دبیر ذخیره شد.", "success")
            return redirect(url_for("teacher_profile", teacher_id=teacher.id))

    return render_template("teacher_edit.html", teacher=teacher, form=form,
                           is_edit=True,
                           teacher_types=TEACHER_TYPES,
                           edu_levels=EDU_LEVELS,
                           marital_statuses=MARITAL_STATUSES)


# =========================================================
# STUDENTS (افزودن و لیست دانش‌آموزان)
# =========================================================

STUDENT_TYPES = ["عادی", "فعال", "پژوهشگر"]

# هر نوع دانش‌آموز صفحه، مسیر و قالب مخصوص خودش را دارد
STUDENT_LIST_PAGES = {
    "عادی": {"endpoint": "students_regular", "template": "students_regular.html",
             "export_kind": "regular"},
    "فعال": {"endpoint": "students_active", "template": "students_active.html",
             "export_kind": "active"},
    "پژوهشگر": {"endpoint": "students_researcher", "template": "students_researcher.html",
                "export_kind": "researcher"},
}

# کلید آدرس اکسل -> نوع دانش‌آموز
STUDENT_EXPORT_KINDS = {cfg["export_kind"]: student_type
                        for student_type, cfg in STUDENT_LIST_PAGES.items()}

GRADES = ["اول", "دوم", "سوم", "چهارم", "پنجم", "ششم",
          "هفتم", "هشتم", "نهم", "دهم", "یازدهم", "دوازدهم"]

PARENT_EDU_LEVELS = ["زیر دیپلم", "دیپلم", "کاردانی", "کارشناسی",
                     "کارشناسی ارشد", "دکتری"]

STUDENT_FIELDS = [
    "first_name", "last_name", "date_of_birth", "national_id_number",
    "grade_level", "field_of_study", "school_name", "shad_number",
    "registration_date", "type",
    "father_name", "father_job", "father_educational_qualification",
    "father_number",
    "mother_name_and_last_name", "mother_job",
    "mother_educational_qualification", "mother_number",
    "address", "note",
]

_STUDENT_DIGIT_FIELDS = {
    "date_of_birth", "registration_date", "national_id_number",
    "shad_number", "father_number", "mother_number",
}
_STUDENT_MAX_LEN = {"address": 300, "note": 500}

_STUDENT_OPTIONAL_PATTERNS = {
    "father_number": (r"09\d{9}", "تلفن همراه پدر باید ۱۱ رقم باشد و با ۰۹ شروع شود."),
    "mother_number": (r"09\d{9}", "تلفن همراه مادر باید ۱۱ رقم باشد و با ۰۹ شروع شود."),
    "date_of_birth": (r"\d{4}/\d{1,2}/\d{1,2}", "تاریخ تولد را به شکل ۱۳۹۰/۰۵/۱۲ وارد کنید."),
    "registration_date": (r"\d{4}/\d{1,2}/\d{1,2}", "تاریخ ثبت‌نام را به شکل ۱۴۰۵/۰۶/۰۱ وارد کنید."),
}

STUDENT_PROFILE_GROUPS = [
    ("اطلاعات شخصی", [
        ("نام", "first_name"), ("نام خانوادگی", "last_name"),
        ("تاریخ تولد", "date_of_birth"), ("کد ملی", "national_id_number"),
        ("آدرس", "address"),
    ]),
    ("اطلاعات تحصیلی", [
        ("نوع دانش‌آموز", "type"), ("پایه تحصیلی", "grade_level"),
        ("رشته", "field_of_study"), ("نام مدرسه", "school_name"),
        ("شماره شاد", "shad_number"), ("تاریخ ثبت‌نام", "registration_date"),
    ]),
    ("اطلاعات پدر", [
        ("نام پدر", "father_name"), ("شغل پدر", "father_job"),
        ("تحصیلات پدر", "father_educational_qualification"),
        ("تلفن همراه پدر", "father_number"),
    ]),
    ("اطلاعات مادر", [
        ("نام و نام خانوادگی مادر", "mother_name_and_last_name"),
        ("شغل مادر", "mother_job"),
        ("تحصیلات مادر", "mother_educational_qualification"),
        ("تلفن همراه مادر", "mother_number"),
    ]),
    ("توضیحات", [("یادداشت", "note")]),
]


def collect_student_form(src):
    form = {}
    for name in STUDENT_FIELDS:
        raw = src.get(name, "")
        if name in _STUDENT_DIGIT_FIELDS:
            form[name] = clean_digits(raw, 40)
        else:
            form[name] = clean_text(raw, _STUDENT_MAX_LEN.get(name, 80))
    return form


def validate_student_form(form, password, confirm, require_password=True):
    """اعتبارسنجی بدون دیتابیس؛ در صورت خطا متن خطا برمی‌گردد."""
    if not form["first_name"] or not form["last_name"]:
        return "نام و نام خانوادگی را وارد کنید."
    if not form["national_id_number"]:
        return "کد ملی را وارد کنید."
    if form["grade_level"] not in GRADES:
        return "پایه تحصیلی را انتخاب کنید."
    if form["type"] not in STUDENT_TYPES:
        return "نوع دانش‌آموز را انتخاب کنید."
    for name in ("father_educational_qualification", "mother_educational_qualification"):
        if form[name] and form[name] not in PARENT_EDU_LEVELS:
            return "تحصیلات والدین نامعتبر است."
    for name, (pattern, message) in _STUDENT_OPTIONAL_PATTERNS.items():
        if form[name] and not re.fullmatch(pattern, form[name]):
            return message
    # در ویرایش، رمز خالی یعنی «رمز تغییر نکند»
    if not require_password and not password and not confirm:
        return None
    return password_error(password, confirm)


# ---------------------------------------------------------
# تصاویر دانش‌آموز (عکس چهره و عکس شناسنامه) - اختیاری
# فایل‌ها خارج از پوشه static ذخیره می‌شوند و فقط ادمین از راه
# مسیر student_photo به آن‌ها دسترسی دارد.
# ---------------------------------------------------------

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "instance", "uploads", "students")
os.makedirs(UPLOAD_DIR, exist_ok=True)

MAX_IMAGE_BYTES = 5 * 1024 * 1024  # حداکثر حجم هر تصویر

STUDENT_PHOTOS = {
    "face": {"column": "face_photo", "label": "عکس چهره"},
    "certificate": {"column": "birth_certificate_photo", "label": "عکس شناسنامه"},
}

_STORED_NAME_RE = re.compile(r"^[0-9a-f]{32}\.(jpg|png|webp)$")


def detect_image_ext(data):
    """نوع واقعی تصویر از روی محتوای فایل تشخیص داده می‌شود، نه پسوند آن"""
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def read_upload(field_name, label):
    """فایل آپلودشده را می‌خواند و بررسی می‌کند. خروجی: (data, ext, error)"""
    file = request.files.get(field_name)
    if not file or not file.filename:
        return None, None, None  # چیزی انتخاب نشده؛ اختیاری است
    data = file.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        return None, None, f"حجم {label} نباید بیشتر از ۵ مگابایت باشد."
    ext = detect_image_ext(data)
    if not ext:
        return None, None, f"{label} باید تصویر JPG ، PNG یا WEBP باشد."
    return data, ext, None


def store_image(data, ext):
    name = f"{secrets.token_hex(16)}.{ext}"
    with open(os.path.join(UPLOAD_DIR, name), "wb") as f:
        f.write(data)
    return name


def delete_image(name):
    if name and _STORED_NAME_RE.match(name):
        try:
            os.remove(os.path.join(UPLOAD_DIR, name))
        except OSError:
            pass


def read_student_uploads():
    """هر دو تصویر را می‌خواند. خروجی: ({kind: (data, ext)}, error)"""
    uploads = {}
    for kind, cfg in STUDENT_PHOTOS.items():
        data, ext, error = read_upload(cfg["column"], cfg["label"])
        if error:
            return {}, error
        if data:
            uploads[kind] = (data, ext)
    return uploads, None


@app.route("/admin/students/add", methods=["GET", "POST"])
@login_required
@role_required("admin")
def student_add():
    form = {}

    if request.method == "POST":
        form = collect_student_form(request.form)
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        error = validate_student_form(form, password, confirm)
        if not error and Students.query.filter_by(
                national_id_number=form["national_id_number"]).first():
            error = "دانش‌آموزی با این کد ملی قبلاً ثبت شده است."

        uploads = {}
        if not error:
            uploads, error = read_student_uploads()

        if error:
            flash(error, "error")
        else:
            saved = []
            try:
                student = Students(
                    **{key: (value or None) for key, value in form.items()},
                    password=generate_password_hash(password),
                )
                for kind, (data, ext) in uploads.items():
                    name = store_image(data, ext)
                    saved.append(name)
                    setattr(student, STUDENT_PHOTOS[kind]["column"], name)
                db.session.add(student)
                db.session.commit()
            except Exception:
                db.session.rollback()
                for name in saved:
                    delete_image(name)
                raise
            flash("دانش‌آموز با موفقیت ثبت شد.", "success")
            return redirect(url_for(STUDENT_LIST_PAGES[form["type"]]["endpoint"]))

    return render_template("student_add.html", form=form, is_edit=False,
                           student_types=STUDENT_TYPES,
                           grades=GRADES,
                           parent_edu_levels=PARENT_EDU_LEVELS)


def render_student_list(student_type):
    """منطق مشترک جستجو و صفحه‌بندی؛ هر نوع دانش‌آموز قالب جدا و مسیر جدا دارد."""
    page_cfg = STUDENT_LIST_PAGES[student_type]

    q = clean_text(clean(request.args.get("q"), 60), 60)
    query = Students.query.filter_by(type=student_type)

    # هر کلمه جستجو باید در یکی از ستون‌ها پیدا شود
    for term in q.split():
        like = "%" + escape_like(term) + "%"
        query = query.filter(or_(
            Students.first_name.ilike(like, escape="\\"),
            Students.last_name.ilike(like, escape="\\"),
            Students.national_id_number.ilike(like, escape="\\"),
            Students.father_number.ilike(like, escape="\\"),
            Students.mother_number.ilike(like, escape="\\"),
        ))

    total = query.count()
    pages = max(1, math.ceil(total / PER_PAGE))
    page = min(max(request.args.get("page", 1, type=int), 1), pages)

    pagination = query.order_by(
        Students.last_name, Students.first_name, Students.id
    ).paginate(page=page, per_page=PER_PAGE, error_out=False)

    return render_template(page_cfg["template"],
                           students=pagination.items,
                           pagination=pagination,
                           pages=pages,
                           total=total,
                           q=q,
                           list_endpoint=page_cfg["endpoint"],
                           export_kind=page_cfg["export_kind"])


@app.route("/admin/students/list-regular")
@login_required
@role_required("admin")
def students_regular():
    return render_student_list("عادی")


@app.route("/admin/students/list-active")
@login_required
@role_required("admin")
def students_active():
    return render_student_list("فعال")


@app.route("/admin/students/list-researcher")
@login_required
@role_required("admin")
def students_researcher():
    return render_student_list("پژوهشگر")


@app.route("/admin/students/profile/<int:student_id>")
@login_required
@role_required("admin")
def student_profile(student_id):
    student = db.session.get(Students, student_id)
    if not student:
        abort(404)
    back = STUDENT_LIST_PAGES.get(student.type, STUDENT_LIST_PAGES["عادی"])
    return render_template("student_profile.html", student=student,
                           groups=STUDENT_PROFILE_GROUPS,
                           back_endpoint=back["endpoint"])


@app.route("/admin/students/photo/<int:student_id>/<kind>")
@login_required
@role_required("admin")
def student_photo(student_id, kind):
    """نمایش یا دانلود تصویر دانش‌آموز؛ با ?download=1 به‌صورت فایل دانلود می‌شود."""
    cfg = STUDENT_PHOTOS.get(kind)
    student = db.session.get(Students, student_id)
    if not cfg or not student:
        abort(404)
    filename = getattr(student, cfg["column"])
    if not filename or not _STORED_NAME_RE.match(filename):
        abort(404)
    return send_from_directory(
        UPLOAD_DIR, filename,
        as_attachment=request.args.get("download") == "1",
        download_name=f"student-{student.id}-{kind}.{filename.rsplit('.', 1)[1]}",
    )


def build_students_workbook(students, title="دانش‌آموزان"):
    """فایل اکسل (در حافظه) از فهرست دانش‌آموزان می‌سازد؛ بدون رمز و بدون عکس."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    # ستون‌ها همان اطلاعاتی‌اند که در فرم ثبت دانش‌آموز گرفته می‌شود
    columns = [(label, attr)
               for _, rows in STUDENT_PROFILE_GROUPS for label, attr in rows]
    wrap_columns = {"address", "note"}

    wb = Workbook()
    ws = wb.active
    ws.title = title
    ws.sheet_view.rightToLeft = True

    header_font = Font(name="Arial", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="1B2A41")
    body_font = Font(name="Arial", size=11)

    headers = ["ردیف"] + [label for label, _ in columns]
    widths = [len(h) for h in headers]

    for col, title in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col, value=title)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for row_no, student in enumerate(students, start=2):
        ws.cell(row=row_no, column=1, value=row_no - 1).font = body_font
        for col, (_, attr) in enumerate(columns, start=2):
            text = str(getattr(student, attr) or "")
            cell = ws.cell(row=row_no, column=col, value=text)
            # همه‌چیز متن ذخیره می‌شود: صفر ابتدای کد ملی و تلفن حفظ شود
            # و مقداری که با «=» شروع شود به‌عنوان فرمول اجرا نشود
            cell.data_type = "s"
            cell.number_format = "@"
            cell.font = body_font
            cell.alignment = Alignment(horizontal="right", vertical="top",
                                       wrap_text=attr in wrap_columns)
            widths[col - 1] = max(widths[col - 1], min(len(text), 45))

    for col, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(col)].width = max(12, min(width + 3, 48))

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


def send_students_excel(students, sheet_title, file_label):
    """فایل اکسل دانش‌آموزان را برای دانلود می‌فرستد"""
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        flash("برای ساخت اکسل باید کتابخانه openpyxl نصب باشد: pip install openpyxl", "error")
        return redirect(url_for("dashboard"))

    buffer = build_students_workbook(students, sheet_title)
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"students-{file_label}-{date.today().isoformat()}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.route("/admin/students/export-excel")
@login_required
@role_required("admin")
def students_export_excel():
    """دانلود اکسل همه‌ی دانش‌آموزان (همه‌ی نوع‌ها در یک شیت، با ستون «نوع دانش‌آموز»)."""
    students = Students.query.order_by(
        Students.type, Students.last_name, Students.first_name, Students.id
    ).all()
    return send_students_excel(students, "دانش‌آموزان", "all")


@app.route("/admin/students/export-excel/<kind>")
@login_required
@role_required("admin")
def students_export_excel_type(kind):
    """دانلود اکسل فقط دانش‌آموزان یک نوع: regular (عادی) / active (فعال) / researcher (پژوهشگر).
    خروجی همه‌ی دانش‌آموزان آن نوع است، نه فقط نتیجه‌ی جستجوی فعلی."""
    student_type = STUDENT_EXPORT_KINDS.get(kind)
    if not student_type:
        abort(404)
    students = Students.query.filter_by(type=student_type).order_by(
        Students.last_name, Students.first_name, Students.id
    ).all()
    return send_students_excel(students, f"دانش‌آموزان {student_type}", kind)


@app.route("/admin/students/edit/<int:student_id>", methods=["GET", "POST"])
@login_required
@role_required("admin")
def student_edit(student_id):
    student = db.session.get(Students, student_id)
    if not student:
        abort(404)

    # در حالت GET فرم با اطلاعات فعلی دانش‌آموز پر می‌شود
    form = {name: getattr(student, name) or "" for name in STUDENT_FIELDS}

    if request.method == "POST":
        form = collect_student_form(request.form)
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        error = validate_student_form(form, password, confirm, require_password=False)
        if not error and Students.query.filter(
                Students.national_id_number == form["national_id_number"],
                Students.id != student.id).first():
            error = "دانش‌آموز دیگری با این کد ملی ثبت شده است."

        uploads = {}
        if not error:
            uploads, error = read_student_uploads()

        if error:
            flash(error, "error")
        else:
            old_national_id = student.national_id_number
            new_national_id = form["national_id_number"]

            for name, value in form.items():
                setattr(student, name, value or None)
            if password:
                student.password = generate_password_hash(password)

            # ثبت‌نام در دوره‌ها، حضور و غیاب و یادداشت‌ها با کد ملی به دانش‌آموز
            # وصل‌اند؛ اگر کد ملی عوض شد باید همین‌جا هم به‌روز شوند
            if old_national_id and old_national_id != new_national_id:
                Linking_the_student_to_the_course.query.filter_by(
                    student_national_id_number=old_national_id
                ).update({"student_national_id_number": new_national_id})
                Attendance.query.filter_by(
                    student_national_id_number=old_national_id
                ).update({"student_national_id_number": new_national_id})
                Notes.query.filter_by(
                    national_id_number=old_national_id
                ).update({"national_id_number": new_national_id})

            # تصاویر: جایگزینی با فایل جدید یا حذف با تیک «حذف عکس فعلی»
            saved, old_files = [], []
            try:
                for kind, cfg in STUDENT_PHOTOS.items():
                    column = cfg["column"]
                    current = getattr(student, column)
                    if kind in uploads:
                        data, ext = uploads[kind]
                        name = store_image(data, ext)
                        saved.append(name)
                        setattr(student, column, name)
                        old_files.append(current)
                    elif request.form.get(f"remove_{column}") == "1" and current:
                        setattr(student, column, None)
                        old_files.append(current)
                db.session.commit()
            except Exception:
                db.session.rollback()
                for name in saved:
                    delete_image(name)
                raise
            for name in old_files:
                delete_image(name)

            flash("اطلاعات دانش‌آموز ذخیره شد.", "success")
            return redirect(url_for("student_profile", student_id=student.id))

    return render_template("student_edit.html", student=student, form=form,
                           is_edit=True,
                           student_types=STUDENT_TYPES,
                           grades=GRADES,
                           parent_edu_levels=PARENT_EDU_LEVELS)


# =========================================================
# DELETE (حذف دبیر و دانش‌آموز)
# =========================================================

def teacher_delete_block_reason(courses, rentals):
    """اگر دوره یا اجاره‌ی کلاس به دبیر وصل است، حذف مجاز نیست."""
    if courses:
        return (f"این دبیر مدرس {courses} دوره است. ابتدا مدرس آن دوره‌ها را "
                "عوض کنید، بعد دبیر را حذف کنید.")
    if rentals:
        return (f"برای این دبیر {rentals} اجاره‌ی کلاس ثبت شده است. "
                "ابتدا آن اجاره‌ها را حذف کنید.")
    return None


def student_delete_block_reason(enrollments):
    """اگر بدهی یا ودیعه‌ی ثبت‌شده دارد، حذف مجاز نیست تا سابقه‌ی مالی از بین نرود."""
    with_money = sum(1 for e in enrollments if (e.debt or 0) > 0 or (e.deposit or 0) > 0)
    if with_money:
        return (f"این دانش‌آموز در {with_money} دوره بدهی یا ودیعه‌ی ثبت‌شده دارد. "
                "ابتدا وضعیت مالی را تسویه کنید، بعد حذف کنید.")
    return None


@app.route("/admin/teachers/delete/<int:teacher_id>", methods=["GET", "POST"])
@login_required
@role_required("admin")
def teacher_delete(teacher_id):
    teacher = db.session.get(Teachers, teacher_id)
    if not teacher:
        abort(404)

    national_id = teacher.national_id_number
    courses = rentals = notes = 0
    if national_id:
        courses = Courses.query.filter_by(
            course_instructor_national_id_number=national_id).count()
        rentals = Renting_out_a_class.query.filter_by(
            teacher_national_id_number=national_id).count()
        notes = Notes.query.filter_by(national_id_number=national_id).count()
    blocked = teacher_delete_block_reason(courses, rentals)

    if request.method == "POST":
        if blocked:
            flash(blocked, "error")
            return redirect(url_for("teacher_profile", teacher_id=teacher.id))
        back = TEACHER_LIST_PAGES.get(teacher.type, TEACHER_LIST_PAGES["موظف"])["endpoint"]
        if national_id:
            Notes.query.filter_by(national_id_number=national_id).delete()
        db.session.delete(teacher)
        db.session.commit()
        flash("دبیر حذف شد.", "success")
        return redirect(url_for(back))

    return render_template(
        "confirm_delete.html",
        crumb="دبیران", kind="دبیر",
        person_name=f"{teacher.first_name or ''} {teacher.last_name or ''}".strip(),
        links=[("یادداشت", notes)] if notes else [],
        blocked=blocked,
        form_action=url_for("teacher_delete", teacher_id=teacher.id),
        cancel_url=url_for("teacher_profile", teacher_id=teacher.id),
    )


@app.route("/admin/students/delete/<int:student_id>", methods=["GET", "POST"])
@login_required
@role_required("admin")
def student_delete(student_id):
    student = db.session.get(Students, student_id)
    if not student:
        abort(404)

    national_id = student.national_id_number
    enrollments = []
    attendance = notes = 0
    if national_id:
        enrollments = Linking_the_student_to_the_course.query.filter_by(
            student_national_id_number=national_id).all()
        attendance = Attendance.query.filter_by(
            student_national_id_number=national_id).count()
        notes = Notes.query.filter_by(national_id_number=national_id).count()
    blocked = student_delete_block_reason(enrollments)

    if request.method == "POST":
        if blocked:
            flash(blocked, "error")
            return redirect(url_for("student_profile", student_id=student.id))
        back = STUDENT_LIST_PAGES.get(student.type, STUDENT_LIST_PAGES["عادی"])["endpoint"]
        photo_files = [student.face_photo, student.birth_certificate_photo]
        course_codes = {e.course_code for e in enrollments if e.course_code}
        if national_id:
            Linking_the_student_to_the_course.query.filter_by(
                student_national_id_number=national_id).delete()
            Attendance.query.filter_by(
                student_national_id_number=national_id).delete()
            Notes.query.filter_by(national_id_number=national_id).delete()
        for code in course_codes:
            sync_course_student_count(code)  # تعداد دانش‌آموزان دوره‌ها به‌روز شود
        db.session.delete(student)
        db.session.commit()
        for name in photo_files:
            delete_image(name)
        flash("دانش‌آموز حذف شد.", "success")
        return redirect(url_for(back))

    links = [(label, count) for label, count in (
        ("ثبت‌نام در دوره", len(enrollments)),
        ("حضور و غیاب", attendance),
        ("یادداشت", notes),
    ) if count]
    return render_template(
        "confirm_delete.html",
        crumb="دانش‌آموزان", kind="دانش‌آموز",
        person_name=f"{student.first_name or ''} {student.last_name or ''}".strip(),
        links=links,
        blocked=blocked,
        form_action=url_for("student_delete", student_id=student.id),
        cancel_url=url_for("student_profile", student_id=student.id),
    )


# =========================================================
# NOTES (یادداشت‌ها) + تاریخ شمسی
# =========================================================

# ایران ساعت تابستانی ندارد؛ «امروز» را براساس ساعت تهران حساب می‌کنیم
# نه ساعت سرور (UTC+3:30)
IRAN_TZ = timezone(timedelta(hours=3, minutes=30))

_G_DAYS_BEFORE_MONTH = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]


def gregorian_to_jalali(gy, gm, gd):
    gy2 = gy + 1 if gm > 2 else gy
    days = (355666 + 365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100
            + (gy2 + 399) // 400 + gd + _G_DAYS_BEFORE_MONTH[gm - 1])
    jy = -1595 + 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm, jd = 1 + days // 31, 1 + days % 31
    else:
        jm, jd = 7 + (days - 186) // 30, 1 + (days - 186) % 30
    return jy, jm, jd


def jalali_to_gregorian(jy, jm, jd):
    jy += 1595
    days = (-355668 + 365 * jy + (jy // 33) * 8 + ((jy % 33) + 3) // 4 + jd
            + ((jm - 1) * 31 if jm < 7 else (jm - 7) * 30 + 186))
    gy = 400 * (days // 146097)
    days %= 146097
    if days > 36524:
        days -= 1
        gy += 100 * (days // 36524)
        days %= 36524
        if days >= 365:
            days += 1
    gy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365
    gd = days + 1
    leap = (gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0
    month_lengths = [0, 31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 0
    while gm < 13 and gd > month_lengths[gm]:
        gd -= month_lengths[gm]
        gm += 1
    return gy, gm, gd


def today_jalali():
    """تاریخ امروز به شمسی، مثل (1405, 7, 18)"""
    now = datetime.now(IRAN_TZ)
    return gregorian_to_jalali(now.year, now.month, now.day)


def format_jalali(jy, jm, jd):
    return f"{jy:04d}/{jm:02d}/{jd:02d}"


def parse_jalali_date(text):
    """تاریخ شمسی تایپ‌شده را بررسی و به شکل 1405/07/18 برمی‌گرداند؛ نامعتبر = None.
    جداکننده‌ها / - . و ارقام فارسی پذیرفته می‌شوند."""
    parts = re.split(r"[/.\-]", clean_digits(text, 20))
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        return None
    jy, jm, jd = (int(p) for p in parts)
    if not (1300 <= jy <= 1600 and 1 <= jm <= 12 and 1 <= jd <= 31):
        return None
    # روز نامعتبر (مثل ۳۱ شهریور... یا ۳۰ اسفند سال کبیسه‌نشده) در رفت‌وبرگشت تغییر می‌کند
    if gregorian_to_jalali(*jalali_to_gregorian(jy, jm, jd)) != (jy, jm, jd):
        return None
    return format_jalali(jy, jm, jd)


@app.route("/admin/notes/write", methods=["GET", "POST"])
@login_required
@role_required("admin")
def note_write():
    """کد ملی یادداشت همان کد ملی ادمینی است که آن را می‌نویسد؛ از حساب او خوانده می‌شود."""
    writer = db.session.get(Admins, session["user_id"])
    if not writer or not writer.national_id_number:
        flash("برای حساب شما کد ملی ثبت نشده است؛ ابتدا کد ملی را در حساب خود ثبت کنید.", "error")
        return redirect(url_for("dashboard"))

    today = format_jalali(*today_jalali())
    form = {"date_of_show": today}
    writer_name = f"{writer.first_name or ''} {writer.last_name or ''}".strip()

    if request.method == "POST":
        text = (request.form.get("text") or "").replace("ي", "ی").replace("ك", "ک")
        form = {
            "text": text.replace("\r\n", "\n").strip()[:1000],
            "date_of_show": clean_digits(request.form.get("date_of_show"), 20),
        }

        show_date = parse_jalali_date(form["date_of_show"])
        error = None
        if not form["text"]:
            error = "متن یادداشت را بنویسید."
        elif not show_date:
            error = "تاریخ نمایش نامعتبر است. تاریخ شمسی را مثل ۱۴۰۵/۰۷/۱۸ وارد کنید."

        if error:
            flash(error, "error")
        else:
            db.session.add(Notes(national_id_number=writer.national_id_number,
                                 text=form["text"],
                                 date_of_show=show_date))
            db.session.commit()
            if show_date == today:
                flash("یادداشت ثبت شد و در یادداشت‌های امروز دیده می‌شود.", "success")
                return redirect(url_for("note_today"))
            flash(f"یادداشت ثبت شد؛ در تاریخ {show_date} نمایش داده می‌شود.", "success")
            return redirect(url_for("note_write"))

    return render_template("note_write.html", form=form, today=today,
                           writer_name=writer_name)


@app.route("/admin/notes/today")
@login_required
@role_required("admin")
def note_today():
    jy, jm, jd = today_jalali()
    # هم 1405/07/08 و هم 1405/7/8 را می‌پذیریم تا یادداشت‌های قدیمی گم نشوند
    wanted = {format_jalali(jy, jm, jd), f"{jy}/{jm}/{jd}"}
    notes = Notes.query.filter(Notes.date_of_show.in_(wanted)).order_by(Notes.id.desc()).all()

    ids = {n.national_id_number for n in notes if n.national_id_number}
    writers = {}
    if ids:
        for a in Admins.query.filter(Admins.national_id_number.in_(ids)).all():
            writers[a.national_id_number] = f"{a.first_name or ''} {a.last_name or ''}".strip()

    rows = [{"id": n.id,
             "writer": writers.get(n.national_id_number, "—"),
             "national_id": n.national_id_number,
             "text": n.text} for n in notes]

    return render_template("notes_today.html", rows=rows,
                           today=format_jalali(jy, jm, jd))


@app.route("/admin/notes/done/<int:note_id>", methods=["POST"])
@login_required
@role_required("admin")
def note_done(note_id):
    """با زدن «انجام شد» یادداشت حذف می‌شود."""
    note = db.session.get(Notes, note_id)
    if not note:
        abort(404)
    db.session.delete(note)
    db.session.commit()
    flash("یادداشت انجام شد و حذف شد.", "success")
    return redirect(url_for("note_today"))


# =========================================================
# LOCKERS & EQUIPMENT (کمدها و تجهیزات)
# =========================================================

def parse_locker_number(text):
    """شماره کمد باید عدد صحیح مثبت باشد (ستون دیتابیس عددی است)"""
    text = clean_digits(text, 10)
    if not text.isascii() or not text.isdigit():
        return None
    number = int(text)
    return number if 0 < number <= 999999 else None


def locker_options():
    return Lockers.query.order_by(Lockers.number_of_locker, Lockers.id).all()


def item_locker(item_id):
    """کمدی که وسیله داخل آن است؛ اگر بی‌کمد باشد None"""
    link = Linking_the_items_to_the_locker.query.filter_by(item_id=item_id).first()
    return db.session.get(Lockers, link.locker_id) if link else None


def items_with_lockers():
    """همه‌ی وسایل همراه کمدشان؛ [(item, locker یا None)]"""
    return (db.session.query(List_of_items, Lockers)
            .outerjoin(Linking_the_items_to_the_locker,
                       Linking_the_items_to_the_locker.item_id == List_of_items.id)
            .outerjoin(Lockers, Lockers.id == Linking_the_items_to_the_locker.locker_id)
            .order_by(List_of_items.name_of_item, List_of_items.id).all())


def active_loans_by_item():
    """امانت‌های فعال به‌صورت {item_id: امانت}. هر وسیله‌ای که اینجا باشد موجود نیست.
    امانت‌های قدیمی که شناسه‌ی وسیله ندارند، فقط وقتی به وسیله وصل می‌شوند که
    نام آن وسیله بین وسایل ثبت‌شده یکتا باشد."""
    name_to_ids = {}
    for item_id, name in db.session.query(
            List_of_items.id, List_of_items.name_of_item).all():
        name_to_ids.setdefault(name, []).append(item_id)

    by_item = {}
    for loan in Loans.query.all():
        item_id = loan.item_id
        if item_id is None:
            ids = name_to_ids.get(loan.item_name, [])
            item_id = ids[0] if len(ids) == 1 else None
        if item_id is not None:
            by_item[item_id] = loan
    return by_item


def loan_info(loan):
    """اطلاعات نمایشی امانت برای لیست وسایل؛ اگر امانت نیست None"""
    if not loan:
        return None
    overdue, _ = loan_status(jalali_days_left(loan.due_date))
    return {"borrower": loan.borrower_name, "due": loan.due_date, "overdue": overdue}


def set_item_locker(item_id, locker_id):
    """وسیله را در یک کمد می‌گذارد (جابه‌جا می‌کند)؛ locker_id=None یعنی بی‌کمد.
    هر وسیله فقط در یک کمد است."""
    links = Linking_the_items_to_the_locker.query.filter_by(item_id=item_id).all()
    if locker_id is None:
        for link in links:
            db.session.delete(link)
        return
    if links:
        links[0].locker_id = locker_id
        for extra in links[1:]:
            db.session.delete(extra)
    else:
        db.session.add(Linking_the_items_to_the_locker(
            item_id=item_id, locker_id=locker_id))


# ---------------------------- کمدها ----------------------------

@app.route("/admin/lockers/add", methods=["GET", "POST"])
@login_required
@role_required("admin")
def locker_add():
    number_text = ""
    if request.method == "POST":
        number_text = clean_digits(request.form.get("number_of_locker"), 10)
        number = parse_locker_number(number_text)
        if number is None:
            flash("شماره کمد باید یک عدد صحیح مثبت باشد.", "error")
        elif Lockers.query.filter_by(number_of_locker=number).first():
            flash(f"کمد شماره {number} قبلاً ثبت شده است.", "error")
        else:
            db.session.add(Lockers(number_of_locker=number))
            db.session.commit()
            flash(f"کمد شماره {number} اضافه شد.", "success")
            return redirect(url_for("lockers_list"))
    return render_template("locker_add.html", number_text=number_text)


@app.route("/admin/lockers/list")
@login_required
@role_required("admin")
def lockers_list():
    lockers = locker_options()
    counts = dict(db.session.query(
        Linking_the_items_to_the_locker.locker_id,
        func.count(Linking_the_items_to_the_locker.id),
    ).group_by(Linking_the_items_to_the_locker.locker_id).all())
    rows = [{"id": l.id, "number": l.number_of_locker, "count": counts.get(l.id, 0)}
            for l in lockers]
    return render_template("lockers_list.html", rows=rows)


@app.route("/admin/lockers/<int:locker_id>/items")
@login_required
@role_required("admin")
def locker_items(locker_id):
    locker = db.session.get(Lockers, locker_id)
    if not locker:
        abort(404)
    items = (List_of_items.query
             .join(Linking_the_items_to_the_locker,
                   Linking_the_items_to_the_locker.item_id == List_of_items.id)
             .filter(Linking_the_items_to_the_locker.locker_id == locker.id)
             .order_by(List_of_items.name_of_item, List_of_items.id).all())
    loans = active_loans_by_item()
    loan_of = {item.id: loan_info(loans.get(item.id)) for item in items}
    return render_template("locker_items.html", locker=locker, items=items,
                           loan_of=loan_of)


@app.route("/admin/lockers/delete/<int:locker_id>", methods=["GET", "POST"])
@login_required
@role_required("admin")
def locker_delete(locker_id):
    locker = db.session.get(Lockers, locker_id)
    if not locker:
        abort(404)

    count = Linking_the_items_to_the_locker.query.filter_by(locker_id=locker.id).count()

    if request.method == "POST":
        # وسایل حذف نمی‌شوند؛ فقط ارتباطشان با کمد قطع می‌شود و بی‌کمد می‌شوند
        Linking_the_items_to_the_locker.query.filter_by(locker_id=locker.id).delete()
        db.session.delete(locker)
        db.session.commit()
        flash("کمد حذف شد." + (f" {count} وسیله‌ی داخل آن بی‌کمد شد." if count else ""), "success")
        return redirect(url_for("lockers_list"))

    note = (f"{count} وسیله داخل این کمد است. با حذف کمد، وسایل حذف نمی‌شوند؛ "
            "از کمد خارج می‌شوند و «بی‌کمد» باقی می‌مانند." if count else None)
    return render_template(
        "confirm_delete.html",
        crumb="کمدها", kind="کمد", person_name=f"شماره {locker.number_of_locker}",
        links=[], extra_note=note, blocked=None,
        form_action=url_for("locker_delete", locker_id=locker.id),
        cancel_url=url_for("lockers_list"),
    )


# ---------------------------- وسایل ----------------------------

def read_item_form():
    """نام وسیله و کمد انتخاب‌شده را از فرم می‌خواند. خروجی: (form, locker_id, error)"""
    form = {
        "name_of_item": clean_text(request.form.get("name_of_item"), 100),
        "locker_id": clean_digits(request.form.get("locker_id"), 10),
    }
    if not form["name_of_item"]:
        return form, None, "نام وسیله را وارد کنید."
    locker_id = None
    if form["locker_id"]:
        if not form["locker_id"].isascii() or not form["locker_id"].isdigit():
            return form, None, "کمد انتخاب‌شده نامعتبر است."
        locker_id = int(form["locker_id"])
        if not db.session.get(Lockers, locker_id):
            return form, None, "کمد انتخاب‌شده وجود ندارد."
    return form, locker_id, None


@app.route("/admin/equipment/add", methods=["GET", "POST"])
@login_required
@role_required("admin")
def item_add():
    # با ?locker=<id> (دکمه در صفحه‌ی وسایل کمد) همان کمد از قبل انتخاب می‌شود
    form = {"name_of_item": "", "locker_id": clean_digits(request.args.get("locker"), 10)}

    if request.method == "POST":
        form, locker_id, error = read_item_form()
        if error:
            flash(error, "error")
        else:
            item = List_of_items(name_of_item=form["name_of_item"])
            db.session.add(item)
            db.session.flush()  # گرفتن id وسیله
            set_item_locker(item.id, locker_id)
            db.session.commit()
            flash("وسیله اضافه شد.", "success")
            return redirect(url_for("items_list"))

    return render_template("item_form.html", form=form, lockers=locker_options(),
                           heading="افزودن وسیله", submit_label="ثبت وسیله",
                           form_action=url_for("item_add"),
                           cancel_url=url_for("items_list"))


@app.route("/admin/equipment/list")
@login_required
@role_required("admin")
def items_list():
    loans = active_loans_by_item()
    items = [{"id": item.id, "name": item.name_of_item,
              "locker_id": locker.id if locker else None,
              "locker_number": locker.number_of_locker if locker else None,
              "loan": loan_info(loans.get(item.id))}
             for item, locker in items_with_lockers()]
    available = sum(1 for i in items if not i["loan"])
    return render_template("items_list.html", items=items, available=available)


@app.route("/admin/equipment/edit/<int:item_id>", methods=["GET", "POST"])
@login_required
@role_required("admin")
def item_edit(item_id):
    item = db.session.get(List_of_items, item_id)
    if not item:
        abort(404)

    current = item_locker(item.id)
    form = {"name_of_item": item.name_of_item or "",
            "locker_id": str(current.id) if current else ""}

    if request.method == "POST":
        form, locker_id, error = read_item_form()
        if error:
            flash(error, "error")
        else:
            item.name_of_item = form["name_of_item"]
            Loans.query.filter_by(item_id=item.id).update(
                {"item_name": form["name_of_item"]})
            set_item_locker(item.id, locker_id)
            db.session.commit()
            flash("اطلاعات وسیله ذخیره شد.", "success")
            return redirect(url_for("items_list"))

    return render_template("item_form.html", form=form, lockers=locker_options(),
                           heading=f"ویرایش وسیله: {item.name_of_item}",
                           submit_label="ذخیره تغییرات",
                           form_action=url_for("item_edit", item_id=item.id),
                           cancel_url=url_for("items_list"))


@app.route("/admin/equipment/delete/<int:item_id>", methods=["GET", "POST"])
@login_required
@role_required("admin")
def item_delete(item_id):
    item = db.session.get(List_of_items, item_id)
    if not item:
        abort(404)

    loan = active_loans_by_item().get(item.id)
    blocked = None
    if loan:
        blocked = (f"این وسیله هم‌اکنون به {loan.borrower_name} امانت داده شده است. "
                   "ابتدا بازگشت امانت را ثبت کنید، بعد وسیله را حذف کنید.")

    if request.method == "POST":
        if blocked:
            flash(blocked, "error")
            return redirect(url_for("items_list"))
        Linking_the_items_to_the_locker.query.filter_by(item_id=item.id).delete()
        db.session.delete(item)
        db.session.commit()
        flash("وسیله حذف شد.", "success")
        return redirect(url_for("items_list"))

    locker = item_locker(item.id)
    note = f"این وسیله الان داخل کمد {locker.number_of_locker} است." if locker else None
    return render_template(
        "confirm_delete.html",
        crumb="تجهیزات", kind="وسیله", person_name=item.name_of_item or "",
        links=[], extra_note=note, blocked=blocked,
        form_action=url_for("item_delete", item_id=item.id),
        cancel_url=url_for("items_list"),
    )


# =========================================================
# LOANS (امانت دادن وسایل)
# =========================================================

def jalali_days_left(due_text):
    """چند روز تا تاریخ مقرر مانده؛ منفی یعنی مهلت گذشته. تاریخ نامعتبر = None"""
    parsed = parse_jalali_date(due_text)
    if not parsed:
        return None
    due = date(*jalali_to_gregorian(*(int(part) for part in parsed.split("/"))))
    return (due - datetime.now(IRAN_TZ).date()).days


def loan_status(days_left):
    """متن و وضعیت نمایش امانت. خروجی: (overdue, متن)"""
    if days_left is None:
        return False, "تاریخ نامعتبر"
    if days_left < 0:
        return True, f"مهلت تمام شده ({-days_left} روز گذشته)"
    if days_left == 0:
        return False, "امروز آخرین مهلت است"
    return False, f"{days_left} روز تا بازگشت"


@app.route("/admin/equipment/loan", methods=["GET", "POST"])
@login_required
@role_required("admin")
def loan_add():
    today = format_jalali(*today_jalali())
    form = {"item_id": clean_digits(request.args.get("item"), 10),
            "borrower_name": "", "borrower_number": "", "borrower_school": "",
            "registration_date": today, "due_date": ""}

    loans = active_loans_by_item()

    if request.method == "POST":
        form = {
            "item_id": clean_digits(request.form.get("item_id"), 10),
            "borrower_name": clean_text(request.form.get("borrower_name"), 80),
            "borrower_number": clean_digits(request.form.get("borrower_number"), 20),
            "borrower_school": clean_text(request.form.get("borrower_school"), 80),
            "registration_date": clean_digits(request.form.get("registration_date"), 20),
            "due_date": clean_digits(request.form.get("due_date"), 20),
        }
        registered = parse_jalali_date(form["registration_date"])
        due = parse_jalali_date(form["due_date"])

        item = None
        if form["item_id"].isascii() and form["item_id"].isdigit():
            item = db.session.get(List_of_items, int(form["item_id"]))

        error = None
        if not item:
            error = "وسیله‌ای انتخاب نشده یا در لیست وسایل وجود ندارد."
        elif item.id in loans:
            other = loans[item.id]
            error = (f"وسیله‌ی «{item.name_of_item}» موجود نیست؛ هم‌اکنون به "
                     f"{other.borrower_name} امانت داده شده (مقرر بازگشت: {other.due_date}).")
        elif not form["borrower_name"]:
            error = "نام امانت‌گیر را وارد کنید."
        elif not form["borrower_number"]:
            error = "شماره امانت‌گیر را وارد کنید."
        elif not registered:
            error = "تاریخ ثبت امانت نامعتبر است. تاریخ شمسی را مثل ۱۴۰۵/۰۷/۱۸ وارد کنید."
        elif not due:
            error = "تاریخ مقرر برای بازگشت نامعتبر است. تاریخ شمسی را مثل ۱۴۰۵/۰۷/۲۵ وارد کنید."
        elif due < registered:  # تاریخ‌ها با صفر ابتدایی ذخیره می‌شوند، مقایسه‌ی متنی درست است
            error = "تاریخ بازگشت نمی‌تواند قبل از تاریخ ثبت امانت باشد."

        if error:
            flash(error, "error")
        else:
            db.session.add(Loans(
                item_id=item.id,
                item_name=item.name_of_item,
                borrower_name=form["borrower_name"],
                borrower_number=form["borrower_number"],
                borrower_school=form["borrower_school"] or None,
                registration_date=registered,
                due_date=due,
            ))
            db.session.commit()
            flash("امانت ثبت شد.", "success")
            return redirect(url_for("loans_list"))

    # فقط وسایل موجود (غیرامانت) برای انتخاب نشان داده می‌شوند
    loans = active_loans_by_item()
    all_items = items_with_lockers()
    choices = []
    for item, locker in all_items:
        if item.id in loans:
            continue
        where = f"کمد {locker.number_of_locker}" if locker else "بی‌کمد"
        choices.append({"id": item.id, "label": f"{item.name_of_item} — {where}"})
    total_items = len(all_items)
    return render_template("loan_form.html", form=form, choices=choices,
                           total_items=total_items, today=today)


@app.route("/admin/equipment/loans")
@login_required
@role_required("admin")
def loans_list():
    loans = Loans.query.all()
    rows = []
    for loan in loans:
        days_left = jalali_days_left(loan.due_date)
        overdue, status = loan_status(days_left)
        rows.append({
            "id": loan.id, "item": loan.item_name, "borrower": loan.borrower_name,
            "number": loan.borrower_number, "school": loan.borrower_school,
            "registered": loan.registration_date, "due": loan.due_date,
            "overdue": overdue, "status": status,
            "sort": days_left if days_left is not None else 10 ** 9,
        })
    rows.sort(key=lambda r: (r["sort"], r["id"]))  # مهلت‌گذشته‌ها و نزدیک‌ترها اول
    overdue_count = sum(1 for r in rows if r["overdue"])
    return render_template("loans_list.html", rows=rows, overdue_count=overdue_count)


@app.route("/admin/equipment/loan-return/<int:loan_id>", methods=["POST"])
@login_required
@role_required("admin")
def loan_return(loan_id):
    """با ثبت بازگشت، امانت از لیست حذف می‌شود."""
    loan = db.session.get(Loans, loan_id)
    if not loan:
        abort(404)
    db.session.delete(loan)
    db.session.commit()
    flash("بازگشت وسیله ثبت شد و از لیست امانت‌ها حذف شد.", "success")
    return redirect(url_for("loans_list"))


# =========================================================
# CLASSES (افزودن کلاس و لیست کلاس‌ها)
# =========================================================

def natural_key(text):
    """ترتیب طبیعی شماره کلاس‌ها: A2 قبل از A10 و 2 قبل از 10"""
    return [(0, int(part), "") if part.isdigit() else (1, 0, part.lower())
            for part in re.split(r"(\d+)", text or "") if part != ""]


# آموزشگاه فقط دو طبقه دارد: ۱ و ۲
CLASS_FLOORS = (1, 2)


def parse_floor(text):
    """شماره طبقه: فقط ۱ یا ۲ مجاز است. نامعتبر = None"""
    if re.fullmatch(r"[0-9]{1,2}", text) and int(text) in CLASS_FLOORS:
        return int(text)
    return None


@app.route("/admin/classes/add-class", methods=["GET", "POST"])
@login_required
@role_required("admin")
def class_add():
    """وضعیت کلاس از کاربر گرفته نمی‌شود: کلاس جدید همیشه «غیرفعال» ساخته می‌شود
    و فقط وقتی کلاسی در آن برگزار شود فعال می‌شود."""
    form = {"class_number": "", "floor_number": ""}

    if request.method == "POST":
        form = {
            "class_number": clean_digits(request.form.get("class_number"), 20),
            "floor_number": clean_digits(request.form.get("floor_number"), 5),
        }
        floor = parse_floor(form["floor_number"])

        error = None
        if not form["class_number"]:
            error = "شماره کلاس را وارد کنید."
        elif floor is None:
            error = "طبقه را انتخاب کنید (۱ یا ۲)."
        elif Classes.query.filter(
                func.lower(Classes.class_number) == form["class_number"].lower()).first():
            error = f"کلاس شماره {form['class_number']} قبلاً ثبت شده است."

        if error:
            flash(error, "error")
        else:
            db.session.add(Classes(class_number=form["class_number"],
                                   floor_number=floor,
                                   status=False))
            db.session.commit()
            flash(f"کلاس {form['class_number']} اضافه شد.", "success")
            return redirect(url_for("classes_list"))

    return render_template("class_add.html", form=form, floors=CLASS_FLOORS)


@app.route("/admin/classes/list")
@login_required
@role_required("admin")
def classes_list():
    """وضعیت هر کلاس از روی رزروها (اجاره‌ها و جلسات دوره‌ها) حساب می‌شود:
    فعال = همین الان کلاسی در آن برگزار می‌شود؛ رزرو شده = رزرو در پیش‌رو دارد؛
    غیرفعال = آزاد."""
    now = now_text()
    busy = busy_classes()
    items = []
    for c in Classes.query.all():
        booking = busy.get(c.class_number)
        running = bool(booking and booking["start"] <= now)
        reserved = bool(booking and not running)
        when = ""
        if booking:
            when = (f"{booking['label']} | {booking['start'][:10]} | "
                    f"{booking['start'][11:16]} تا {booking['end'][11:16]}")
        items.append(SimpleNamespace(id=c.id, class_number=c.class_number,
                                     floor_number=c.floor_number, status=running,
                                     reserved=reserved, when=when))
    classes = sorted(items, key=lambda c: (c.floor_number if c.floor_number is not None else 10 ** 6,
                                           natural_key(c.class_number)))
    return render_template("classes_list.html", classes=classes,
                           active=sum(1 for c in classes if c.status),
                           reserved=sum(1 for c in classes if c.reserved))


def class_delete_block_reason(active, pending):
    """کلاس فعال (در حال برگزاری) حذف نمی‌شود؛ رزروهای تمام‌نشده (اجاره یا جلسه‌ی دوره) هم
    مانع حذف‌اند. رزروهای گذشته مانع نیستند و به‌عنوان سابقه می‌مانند."""
    if active:
        return "کلاس فعال حذف نمی‌شود؛ در این کلاس هم‌اکنون کلاسی در حال برگزاری است."
    if pending:
        return (f"برای این کلاس {pending} رزرو تمام‌نشده (اجاره یا جلسه‌ی دوره) ثبت شده است. "
                "ابتدا آن‌ها را لغو کنید.")
    return None


@app.route("/admin/classes/delete/<int:class_id>", methods=["GET", "POST"])
@login_required
@role_required("admin")
def class_delete(class_id):
    cls = db.session.get(Classes, class_id)
    if not cls:
        abort(404)

    blocked = class_delete_block_reason(cls.class_number in classes_in_session(),
                                        pending_bookings(cls.class_number))

    if request.method == "POST":
        if blocked:
            flash(blocked, "error")
            return redirect(url_for("classes_list"))
        db.session.delete(cls)
        db.session.commit()
        flash(f"کلاس {cls.class_number} حذف شد.", "success")
        return redirect(url_for("classes_list"))

    return render_template(
        "confirm_delete.html",
        crumb="مدیریت کلاس‌ها", kind="کلاس", person_name=f"شماره {cls.class_number}",
        links=[], extra_note=None, blocked=blocked,
        form_action=url_for("class_delete", class_id=cls.id),
        cancel_url=url_for("classes_list"),
    )


# =========================================================
# RENTALS (اجاره‌ی کلاس به دبیران متفرقه) + فعال بودن کلاس
# کلاس وقتی «فعال» است که الان در آن کلاسی در حال برگزاری باشد؛
# این وضعیت هنگام نمایش از روی ساعت‌ها حساب می‌شود، نه از ستون status.
# زمان‌ها به شکل «1405/07/20 14:00» (شمسی، ساعت تهران) ذخیره می‌شوند و چون
# با صفر ابتدایی نوشته می‌شوند، مقایسه‌ی متنی‌شان درست است.
# =========================================================

def now_text():
    now = datetime.now(IRAN_TZ)
    return f"{format_jalali(*gregorian_to_jalali(now.year, now.month, now.day))} {now.hour:02d}:{now.minute:02d}"


def normalize_time(text):
    """ساعت 24ساعته مثل 14:30 یا ۹:۰۵ را به 09:05 تبدیل می‌کند؛ نامعتبر = None"""
    match = re.fullmatch(r"([0-9]{1,2})[:.٫]([0-9]{2})", clean_digits(text, 10))
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    if hour > 23 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


def rental_state(start, end, now):
    """upcoming (شروع نشده) / running (در حال برگزاری) / ended (تمام شده)"""
    if end and end <= now:
        return "ended"
    if start and start <= now:
        return "running"
    return "upcoming"


def all_bookings():
    """همه‌ی بازه‌هایی که کلاس‌ها اشغال‌اند: اجاره‌ها (rental) و جلسات برنامه‌ریزی‌شده‌ی دوره‌ها (course)"""
    courses = {c.course_code: c for c in Courses.query.all()}
    bookings = []
    for r in Renting_out_a_class.query.all():
        if r.class_number and r.class_start_time and r.class_end_time:
            bookings.append({"class": r.class_number, "start": r.class_start_time,
                             "end": r.class_end_time, "kind": "rental", "label": "اجاره"})
    for link in Linking_the_course_to_the_class.query.all():
        if link.class_number and link.class_start_time and link.class_end_time:
            course = courses.get(link.course_code)
            name = course.course_name if course and course.course_name else link.course_code
            bookings.append({"class": link.class_number, "start": link.class_start_time,
                             "end": link.class_end_time, "kind": "course",
                             "label": f"دوره‌ی {name}"})
    return bookings


def classes_in_session():
    """شماره‌ی کلاس‌هایی که همین الان در آن‌ها کلاسی (اجاره یا جلسه‌ی دوره) برگزار می‌شود"""
    now = now_text()
    return {b["class"] for b in all_bookings() if b["start"] <= now < b["end"]}


def busy_classes():
    """کلاس‌هایی که رزرو تمام‌نشده دارند (در حال برگزاری یا در پیش‌رو)؛ {کلاس: زودترین رزرو}"""
    now = now_text()
    busy = {}
    for b in all_bookings():
        if b["end"] > now:
            current = busy.get(b["class"])
            if current is None or b["start"] < current["start"]:
                busy[b["class"]] = b
    return busy


def pending_bookings(class_number):
    """تعداد رزروهای تمام‌نشده‌ی یک کلاس (اجاره یا جلسه‌ی دوره)"""
    now = now_text()
    return sum(1 for b in all_bookings() if b["class"] == class_number and b["end"] > now)


def booking_conflicts(class_number, start, end):
    """رزروهای تمام‌نشده‌ی این کلاس که با بازه‌ی جدید همپوشانی دارند (خالی = تداخل ندارد).
    فقط رزروهایی که هنوز تمام نشده‌اند (در حال برگزاری یا در پیش‌رو) تداخل حساب می‌شوند؛
    رزرو تمام‌شده یا لغوشده (که پایانش به لحظه‌ی لغو رسیده) مانع نیست، پس می‌شود همان دوره را
    دوباره در همان کلاس و همان ساعت ثبت کرد.
    پایان هر بازه شامل نمی‌شود: ۱۶ تا ۱۸ و ۱۸ تا ۱۹ با هم تداخل ندارند."""
    now = now_text()
    return sorted((b for b in all_bookings()
                   if b["class"] == class_number and b["end"] > now
                   and start < b["end"] and b["start"] < end),
                  key=lambda b: b["start"])


def describe_bookings(bookings):
    return "؛ ".join(f"{b['start'][:10]} از {b['start'][11:16]} تا {b['end'][11:16]} ({b['label']})"
                     for b in bookings)


def upcoming_bookings():
    """رزروهای تمام‌نشده‌ی هر کلاس برای نمایش زیر فرم: {کلاس: [(تاریخ، از، تا، نوع)]}"""
    now = now_text()
    booked = {}
    for b in all_bookings():
        if b["end"] > now:
            booked.setdefault(b["class"], []).append(
                (b["start"][:10], b["start"][11:16], b["end"][11:16], b["label"]))
    return {num: sorted(slots) for num, slots in booked.items()}


def class_choices():
    """همه‌ی کلاس‌ها؛ رزرو بودن مانع نیست و فقط تداخل ساعت‌ها بررسی می‌شود"""
    classes = sorted(Classes.query.all(),
                     key=lambda c: (c.floor_number if c.floor_number is not None else 10 ** 6,
                                    natural_key(c.class_number)))
    return [(c.id, f"کلاس {c.class_number}" + (f" (طبقه {c.floor_number})" if c.floor_number is not None else ""))
            for c in classes]


def misc_teacher_choices():
    teachers = Teachers.query.filter_by(type="متفرقه").order_by(
        Teachers.last_name, Teachers.first_name, Teachers.id).all()
    return [(t.id, f"{t.first_name or ''} {t.last_name or ''}".strip()) for t in teachers]


@app.route("/admin/classes/rent-misc-teachers", methods=["GET", "POST"])
@login_required
@role_required("admin")
def rent_add():
    today = format_jalali(*today_jalali())
    form = {"class_id": "", "teacher_id": "", "date": today,
            "start_time": "", "end_time": "", "amount": ""}

    if request.method == "POST":
        form = {
            "class_id": clean_digits(request.form.get("class_id"), 10),
            "teacher_id": clean_digits(request.form.get("teacher_id"), 10),
            "date": clean_digits(request.form.get("date"), 20),
            "start_time": clean_digits(request.form.get("start_time"), 10),
            "end_time": clean_digits(request.form.get("end_time"), 10),
            "amount": clean_digits(request.form.get("amount"), 25),
        }
        cls = teacher = None
        if form["class_id"].isascii() and form["class_id"].isdigit():
            cls = db.session.get(Classes, int(form["class_id"]))
        if form["teacher_id"].isascii() and form["teacher_id"].isdigit():
            teacher = db.session.get(Teachers, int(form["teacher_id"]))
        day = parse_jalali_date(form["date"])
        start_hm = normalize_time(form["start_time"])
        end_hm = normalize_time(form["end_time"])
        amount = parse_money(form["amount"])

        error = None
        if not cls:
            error = "کلاس را انتخاب کنید."
        elif not teacher or teacher.type != "متفرقه":
            error = "دبیر متفرقه را انتخاب کنید."
        elif not teacher.national_id_number:
            error = "برای این دبیر کد ملی ثبت نشده است؛ ابتدا اطلاعات دبیر را کامل کنید."
        elif not day:
            error = "تاریخ نامعتبر است. تاریخ شمسی را مثل ۱۴۰۵/۰۷/۲۰ وارد کنید."
        elif not start_hm or not end_hm:
            error = "ساعت شروع و پایان را به شکل 14:30 وارد کنید."
        elif end_hm <= start_hm:
            error = "ساعت پایان باید بعد از ساعت شروع باشد."
        elif not amount:
            error = "مبلغ اجاره‌ی دریافتی را به عدد وارد کنید (بیشتر از صفر)."
        else:
            start, end = f"{day} {start_hm}", f"{day} {end_hm}"
            conflicts = booking_conflicts(cls.class_number, start, end)
            if end <= now_text():
                error = "این بازه‌ی زمانی گذشته است."
            elif conflicts:
                error = (f"تداخل دارد: بازه‌ی انتخابی شما ({day} از {start_hm} تا {end_hm}) با "
                         f"رزرو قبلی کلاس {cls.class_number} هم‌پوشانی دارد: "
                         f"{describe_bookings(conflicts)}. ساعت دیگری انتخاب کنید.")

        if error:
            flash(error, "error")
        else:
            db.session.add(Renting_out_a_class(
                class_number=cls.class_number,
                teacher_national_id_number=teacher.national_id_number,
                class_start_time=start,
                class_end_time=end,
                amount=amount,
                registration_date=today,  # روز دریافت پول
            ))
            db.session.commit()
            name = f"{teacher.first_name or ''} {teacher.last_name or ''}".strip()
            flash(f"کلاس {cls.class_number} در {day} از {start_hm} تا {end_hm} به {name} اجاره داده شد؛ "
                  f"مبلغ دریافتی: {amount:,}.", "success")
            return redirect(url_for("rentals_list"))

    bookings = sorted(upcoming_bookings().items(), key=lambda item: natural_key(item[0]))
    return render_template("rent_form.html", form=form, classes=class_choices(),
                           teachers=misc_teacher_choices(), today=today, bookings=bookings)


@app.route("/admin/classes/rentals")
@login_required
@role_required("admin")
def rentals_list():
    now = now_text()
    rentals = Renting_out_a_class.query.all()
    ids = {r.teacher_national_id_number for r in rentals if r.teacher_national_id_number}
    names = {}
    if ids:
        for t in Teachers.query.filter(Teachers.national_id_number.in_(ids)).all():
            names[t.national_id_number] = f"{t.first_name or ''} {t.last_name or ''}".strip()

    labels = {"upcoming": "در پیش‌رو", "running": "در حال برگزاری", "ended": "تمام شده"}
    rows = []
    for r in sorted(rentals, key=lambda r: r.class_start_time or "", reverse=True):
        state = rental_state(r.class_start_time, r.class_end_time, now)
        start, end = r.class_start_time or "", r.class_end_time or ""
        rows.append({"id": r.id, "class_number": r.class_number,
                     "teacher": names.get(r.teacher_national_id_number, "—"),
                     "date": start[:10], "from": start[11:16], "to": end[11:16],
                     "amount": r.amount or 0, "state": state, "label": labels[state],
                     "paid_on": r.registration_date})
    return render_template("rentals_list.html", rows=rows,
                           total=sum(r["amount"] for r in rows),
                           running=sum(1 for r in rows if r["state"] == "running"))


@app.route("/admin/classes/rental-cancel/<int:rental_id>", methods=["GET", "POST"])
@login_required
@role_required("admin")
def rental_cancel(rental_id):
    """رفتار براساس وضعیت اجاره:
    در پیش‌رو  -> لغو (حذف)؛
    در حال برگزاری -> لغو: ساعت پایان همین لحظه می‌شود و کلاس تمام اعلام می‌شود (اجاره و مبلغ می‌ماند)؛
    تمام‌شده -> حذف کامل اجاره."""
    rental = db.session.get(Renting_out_a_class, rental_id)
    if not rental:
        abort(404)

    now = now_text()
    state = rental_state(rental.class_start_time, rental.class_end_time, now)
    amount = rental.amount or 0
    label = f"کلاس {rental.class_number} ({rental.class_start_time})"

    if request.method == "POST":
        if state == "running":
            rental.class_end_time = now  # از همین لحظه کلاس تمام شده و آزاد است
            db.session.commit()
            flash(f"اجاره لغو شد و کلاس {rental.class_number} تمام اعلام شد.", "success")
        else:
            db.session.delete(rental)
            db.session.commit()
            flash("اجاره حذف شد." if state == "ended" else "اجاره لغو شد.", "success")
        return redirect(url_for("rentals_list"))

    context = dict(
        crumb="مدیریت کلاس‌ها", kind="اجاره", person_name=label, links=[], blocked=None,
        form_action=url_for("rental_cancel", rental_id=rental.id),
        cancel_url=url_for("rentals_list"),
    )
    if state == "running":
        context.update(
            title=f"لغو اجاره‌ی در حال برگزاری: {label}",
            question=("با لغو، کلاس همین الان تمام اعلام می‌شود و ساعت پایان اجاره به همین لحظه "
                      "تغییر می‌کند. اجاره از لیست حذف نمی‌شود."),
            extra_note=f"مبلغ دریافتی ({amount:,}) تغییری نمی‌کند و در سابقه می‌ماند.",
            submit_label="بله، لغو شود و کلاس تمام شود",
        )
    elif state == "ended":
        context.update(extra_note=f"مبلغ ثبت‌شده‌ی این اجاره ({amount:,}) هم از سابقه حذف می‌شود.")
    else:
        context.update(extra_note=(f"مبلغ ثبت‌شده‌ی این اجاره ({amount:,}) از سابقه حذف می‌شود؛ "
                                   "پس‌دادن پول به دبیر با خود شماست."))
    return render_template("confirm_delete.html", **context)


# =========================================================
# COURSES (افزودن دوره)
# قاعده: دوره تا وقتی مدرس در آن ثبت نشده باشد فعال نمی‌شود.
# =========================================================

# هر دوره ۱۰ جلسه دارد. ستون number_of_session شماره‌ی «جلسه‌ی فعلی» دوره است
# (۰ = هنوز جلسه‌ای برگزار نشده)، نه تعداد کل جلسات.
COURSE_TOTAL_SESSIONS = 10


def session_label(current):
    current = current or 0
    if current <= 0:
        return "شروع نشده"
    return f"جلسه {current} از {COURSE_TOTAL_SESSIONS}"


def read_start_date(raw):
    """تاریخ شروع دوره (شمسی) اختیاری است. خروجی: (تاریخ یا None, error)"""
    raw = clean_digits(raw, 20)
    if not raw:
        return None, None
    parsed = parse_jalali_date(raw)
    if not parsed:
        return None, "تاریخ شروع نامعتبر است. تاریخ شمسی را مثل ۱۴۰۵/۰۸/۰۱ وارد کنید (یا خالی بگذارید)."
    return parsed, None


def teacher_choices():
    """فهرست دبیران برای انتخاب مدرس؛ [(id, برچسب)]. دبیران متفرقه مدرس دوره نمی‌شوند."""
    teachers = Teachers.query.filter(
        or_(Teachers.type != "متفرقه", Teachers.type.is_(None))
    ).order_by(Teachers.last_name, Teachers.first_name, Teachers.id).all()
    return [(t.id, f"{t.first_name or ''} {t.last_name or ''}".strip()
             + (f" ({t.type})" if t.type else "")) for t in teachers]


def read_course_teacher(raw_id):
    """مدرس انتخاب‌شده را برمی‌گرداند. خروجی: (teacher یا None, error)"""
    raw_id = clean_digits(raw_id, 10)
    if not raw_id:
        return None, None  # مدرس اختیاری است؛ بدون مدرس دوره غیرفعال می‌ماند
    if not raw_id.isascii() or not raw_id.isdigit():
        return None, "مدرس انتخاب‌شده نامعتبر است."
    teacher = db.session.get(Teachers, int(raw_id))
    if not teacher:
        return None, "مدرس انتخاب‌شده وجود ندارد."
    if teacher.type == "متفرقه":
        return None, "دبیر متفرقه نمی‌تواند مدرس دوره باشد."
    if not teacher.national_id_number:
        return None, "برای این دبیر کد ملی ثبت نشده است؛ ابتدا اطلاعات دبیر را کامل کنید."
    return teacher, None


@app.route("/admin/classes/add-course", methods=["GET", "POST"])
@login_required
@role_required("admin")
def course_add():
    form = {"course_name": "", "course_code": "", "price": "", "teacher_salary": "",
            "teacher_id": "", "activation_date": ""}

    if request.method == "POST":
        form = {
            "course_name": clean_text(request.form.get("course_name"), 100),
            "course_code": clean_digits(request.form.get("course_code"), 30),
            "price": clean_digits(request.form.get("price"), 25),
            "teacher_salary": clean_digits(request.form.get("teacher_salary"), 25),
            "teacher_id": clean_digits(request.form.get("teacher_id"), 10),
            "activation_date": clean_digits(request.form.get("activation_date"), 20),
        }
        teacher, teacher_error = read_course_teacher(form["teacher_id"])
        start_date, start_error = read_start_date(form["activation_date"])
        price = parse_money(form["price"])
        salary = parse_money(form["teacher_salary"])

        error = None
        if not form["course_name"]:
            error = "نام دوره را وارد کنید."
        elif not form["course_code"]:
            error = "کد دوره را وارد کنید."
        elif Courses.query.filter(
                func.lower(Courses.course_code) == form["course_code"].lower()).first():
            error = f"دوره‌ای با کد {form['course_code']} قبلاً ثبت شده است."
        elif not price:
            error = "قیمت دوره را به عدد وارد کنید (بیشتر از صفر)."
        elif not salary:
            error = "حقوق مدرس برای این دوره را به عدد وارد کنید (بیشتر از صفر)."
        elif teacher_error:
            error = teacher_error
        elif start_error:
            error = start_error

        if error:
            flash(error, "error")
        else:
            # بدون مدرس: غیرفعال. با مدرس: فعال. تاریخ شروع اختیاری است
            active = teacher is not None
            db.session.add(Courses(
                course_name=form["course_name"],
                course_code=form["course_code"],
                price=price,
                teacher_salary=salary,
                course_instructor_national_id_number=teacher.national_id_number if teacher else None,
                number_of_students=0,
                number_of_session=0,  # هنوز جلسه‌ای برگزار نشده
                activation_date=start_date,
                active=active,
                end_of_course=False,
            ))
            db.session.commit()
            if active:
                flash("دوره ثبت و فعال شد.", "success")
            else:
                flash("دوره ثبت شد؛ تا وقتی مدرس در آن ثبت نشود غیرفعال می‌ماند.", "success")
            return redirect(url_for("courses_list"))

    return render_template("course_form.html", form=form, teachers=teacher_choices(),
                           is_edit=False, heading="افزودن دوره",
                           submit_label="ثبت دوره", form_action=url_for("course_add"),
                           cancel_url=url_for("courses_list"))


# =========================================================
# ENROLLMENT (ثبت دانش‌آموز در دوره + دریافت بیعانه)
# دانش‌آموزها یکی‌یکی به دوره اضافه می‌شوند و number_of_students دوره
# همیشه از روی تعداد ثبت‌نام‌ها به‌روز می‌شود.
# =========================================================

def parse_money(text):
    """مبلغ به عدد صحیح؛ جداکننده‌ی هزارگان (, ، ٬) پذیرفته می‌شود. نامعتبر = None"""
    text = re.sub(r"[,،٬]", "", clean_digits(text, 25))
    if not re.fullmatch(r"[0-9]{1,12}", text):
        return None
    return int(text)


def sync_course_student_count(course_code):
    """تعداد دانش‌آموزان دوره را از روی ثبت‌نام‌ها دوباره حساب می‌کند"""
    if not course_code:
        return 0
    count = Linking_the_student_to_the_course.query.filter_by(course_code=course_code).count()
    course = Courses.query.filter_by(course_code=course_code).first()
    if course:
        course.number_of_students = count
    return count


def course_delete_reasons(courses):
    """دلیل حذف‌نشدنِ هر دوره: {course_id: متن یا None (قابل حذف)}.
    قاعده: وقتی دوره مدرس دارد، حقوق او باید کاملاً پرداخت شده باشد. دانش‌آموزی که هنوز
    بدهی دارد و جلسه‌ی تمام‌نشده هم مانع حذف‌اند تا طلب یا برنامه‌ای گم نشود."""
    paid = teacher_paid_map()
    now = now_text()
    owing, unfinished = {}, {}
    for l in Linking_the_student_to_the_course.query.all():
        if (l.debt or 0) > 0:
            owing[l.course_code] = owing.get(l.course_code, 0) + 1
    for l in Linking_the_course_to_the_class.query.all():
        if l.class_end_time and l.class_end_time > now:
            unfinished[l.course_code] = unfinished.get(l.course_code, 0) + 1

    reasons = {}
    for c in courses:
        code = c.course_code
        reason = None
        if c.course_instructor_national_id_number:
            if not c.teacher_salary:
                reason = "حقوق این دوره ثبت نشده است؛ ابتدا حقوق را ثبت و به مدرس پرداخت کنید."
            else:
                remaining = c.teacher_salary - paid.get(code, 0)
                if remaining > 0:
                    reason = (f"حقوق مدرس هنوز تسویه نشده است (باقی‌مانده: {remaining:,}). "
                              "بعد از پرداخت کامل حقوق، دوره قابل حذف است.")
        if reason is None and owing.get(code):
            reason = f"{owing[code]} دانش‌آموز هنوز بدهی این دوره را نپرداخته‌اند."
        if reason is None and unfinished.get(code):
            reason = f"{unfinished[code]} جلسه‌ی تمام‌نشده برای این دوره برنامه‌ریزی شده است؛ ابتدا آن‌ها را لغو کنید."
        reasons[c.id] = reason
    return reasons


def build_course_rows(courses):
    """ردیف‌های نمایشی دوره‌ها (برای لیست دوره‌ها و انتخاب دوره)"""
    ids = {c.course_instructor_national_id_number for c in courses
           if c.course_instructor_national_id_number}
    names = {}
    if ids:
        for t in Teachers.query.filter(Teachers.national_id_number.in_(ids)).all():
            names[t.national_id_number] = f"{t.first_name or ''} {t.last_name or ''}".strip()

    delete_reasons = course_delete_reasons(courses)
    rows = []
    for c in courses:
        teacher_name = names.get(c.course_instructor_national_id_number)
        if c.end_of_course:
            state, label = "ended", "دوره تمام شده"
        elif c.active and c.course_instructor_national_id_number:
            state, label = "active", "فعال"
        else:
            state, label = "waiting", "غیرفعال (منتظر ثبت مدرس)"
        rows.append({"id": c.id, "code": c.course_code, "name": c.course_name,
                     "teacher": teacher_name or ("نامشخص" if c.course_instructor_national_id_number else None),
                     "session": session_label(c.number_of_session), "students": c.number_of_students or 0,
                     "price": c.price,
                     "activation": c.activation_date, "state": state, "label": label,
                     "delete_reason": delete_reasons.get(c.id)})
    return rows


@app.route("/admin/classes/list-courses")
@login_required
@role_required("admin")
def courses_list():
    rows = build_course_rows(Courses.query.order_by(Courses.id.desc()).all())
    active_count = sum(1 for r in rows if r["state"] == "active")
    return render_template("courses_list.html", rows=rows, active_count=active_count)


@app.route("/admin/classes/enroll")
@login_required
@role_required("admin")
def enroll_pick():
    """انتخاب دوره برای ثبت دانش‌آموز؛ دوره‌های تمام‌شده نمایش داده نمی‌شوند"""
    courses = Courses.query.filter(
        or_(Courses.end_of_course.is_(None), Courses.end_of_course.is_(False))
    ).order_by(Courses.id.desc()).all()
    return render_template("course_pick.html", rows=build_course_rows(courses))


def settled_amount(student_national_id, course_code):
    """مجموع تسویه‌های (پرداخت‌های بعد از بیعانه) یک دانش‌آموز در یک دوره"""
    payments = Payments.query.filter_by(student_national_id_number=student_national_id,
                                        course_code=course_code, kind="تسویه").all()
    return sum(p.amount or 0 for p in payments)


def paid_so_far(link):
    return (link.deposit or 0) + settled_amount(link.student_national_id_number, link.course_code)


def recompute_course_debts(course):
    """بعد از تغییر قیمت دوره: بدهی هر دانش‌آموز = قیمت - بیعانه - تسویه‌های قبلی"""
    if course.price is None or not course.course_code:
        return
    for link in Linking_the_student_to_the_course.query.filter_by(
            course_code=course.course_code).all():
        link.debt = max(course.price - paid_so_far(link), 0)


def max_paid_in_course(course):
    """بیشترین مبلغی که یک دانش‌آموز تا الان در این دوره پرداخته (حداقل قیمت مجاز)"""
    if not course.course_code:
        return 0
    links = Linking_the_student_to_the_course.query.filter_by(course_code=course.course_code).all()
    return max((paid_so_far(l) for l in links), default=0)


@app.route("/admin/classes/course/<int:course_id>/students", methods=["GET", "POST"])
@login_required
@role_required("admin")
def course_students(course_id):
    course = db.session.get(Courses, course_id)
    if not course:
        abort(404)

    form = {"national_id_number": "", "deposit": ""}

    if request.method == "POST":
        form = {
            "national_id_number": clean_digits(request.form.get("national_id_number"), 40),
            "deposit": clean_digits(request.form.get("deposit"), 25),
        }
        student = None
        if form["national_id_number"]:
            student = Students.query.filter_by(
                national_id_number=form["national_id_number"]).first()
        deposit = parse_money(form["deposit"])

        error = None
        if course.end_of_course:
            error = "این دوره تمام شده است و دانش‌آموز جدید نمی‌پذیرد."
        elif not course.course_code:
            error = "برای این دوره کد ثبت نشده است."
        elif not course.price:
            error = "قیمت این دوره ثبت نشده است؛ ابتدا از «ویرایش دوره» قیمت را ثبت کنید."
        elif not form["national_id_number"]:
            error = "کد ملی دانش‌آموز را وارد کنید."
        elif not student:
            error = "دانش‌آموزی با این کد ملی پیدا نشد."
        elif Linking_the_student_to_the_course.query.filter_by(
                student_national_id_number=student.national_id_number,
                course_code=course.course_code).first():
            error = f"{student.first_name or ''} {student.last_name or ''} قبلاً در این دوره ثبت شده است.".strip()
        elif deposit is None:
            error = "مبلغ بیعانه را به عدد وارد کنید (۰ هم قبول است)."
        elif deposit > course.price:
            error = f"بیعانه نمی‌تواند از قیمت دوره ({course.price:,}) بیشتر باشد."

        if error:
            flash(error, "error")
        else:
            debt = course.price - deposit  # بیعانه از قیمت دوره کم می‌شود
            db.session.add(Linking_the_student_to_the_course(
                student_national_id_number=student.national_id_number,
                course_code=course.course_code,
                deposit=deposit,
                debt=debt,
            ))
            if deposit > 0:
                db.session.add(Payments(
                    student_national_id_number=student.national_id_number,
                    course_code=course.course_code,
                    amount=deposit, kind="بیعانه",
                    payment_date=format_jalali(*today_jalali())))
            db.session.flush()
            count = sync_course_student_count(course.course_code)
            db.session.commit()
            full_name = f"{student.first_name or ''} {student.last_name or ''}".strip()
            flash(f"{full_name} در دوره ثبت شد؛ بیعانه: {deposit:,} | بدهی باقی‌مانده: {debt:,} | "
                  f"تعداد دانش‌آموزان دوره: {count}.", "success")
            return redirect(url_for("course_students", course_id=course.id))

    links = Linking_the_student_to_the_course.query.filter_by(
        course_code=course.course_code).order_by(
        Linking_the_student_to_the_course.id).all() if course.course_code else []
    enrolled_ids = {l.student_national_id_number for l in links}
    people = {}
    all_students = Students.query.order_by(Students.last_name, Students.first_name).all()
    for st in all_students:
        people[st.national_id_number] = f"{st.first_name or ''} {st.last_name or ''}".strip()

    price = course.price or 0
    rows = []
    for l in links:
        deposit_paid = l.deposit or 0
        debt_left = l.debt or 0
        rows.append({"link_id": l.id,
                     "name": people.get(l.student_national_id_number, "—"),
                     "national_id": l.student_national_id_number,
                     "deposit": deposit_paid,
                     "settled": max(price - deposit_paid - debt_left, 0),
                     "debt": debt_left})
    suggestions = [(st.national_id_number, people[st.national_id_number])
                   for st in all_students
                   if st.national_id_number and st.national_id_number not in enrolled_ids]

    teacher = None
    if course.course_instructor_national_id_number:
        t = Teachers.query.filter_by(
            national_id_number=course.course_instructor_national_id_number).first()
        teacher = f"{t.first_name or ''} {t.last_name or ''}".strip() if t else None

    return render_template("course_students.html", course=course, form=form, rows=rows,
                           suggestions=suggestions, teacher=teacher,
                           total_deposit=sum(r["deposit"] for r in rows),
                           total_debt=sum(r["debt"] for r in rows))


@app.route("/admin/classes/payment/<int:link_id>", methods=["POST"])
@login_required
@role_required("admin")
def course_payment(link_id):
    """تسویه‌ی بخشی از بدهی: هر مبلغی (تا سقف بدهی) را می‌توان پرداخت کرد، لازم نیست همه‌اش باشد."""
    link = db.session.get(Linking_the_student_to_the_course, link_id)
    if not link:
        abort(404)
    course = Courses.query.filter_by(course_code=link.course_code).first()
    back = url_for("course_students", course_id=course.id) if course else url_for("courses_list")

    amount = parse_money(request.form.get("amount"))
    debt = link.debt or 0

    if debt <= 0:
        flash("این دانش‌آموز بدهی‌ای ندارد.", "error")
    elif amount is None or amount < 1:
        flash("مبلغ پرداخت را به عدد و بیشتر از صفر وارد کنید.", "error")
    elif amount > debt:
        flash(f"مبلغ پرداخت نمی‌تواند از بدهی باقی‌مانده ({debt:,}) بیشتر باشد.", "error")
    else:
        link.debt = debt - amount
        db.session.add(Payments(
            student_national_id_number=link.student_national_id_number,
            course_code=link.course_code,
            amount=amount, kind="تسویه",
            payment_date=format_jalali(*today_jalali())))
        db.session.commit()
        if link.debt == 0:
            flash(f"پرداخت {amount:,} ثبت شد و بدهی کاملاً تسویه شد.", "success")
        else:
            flash(f"پرداخت {amount:,} ثبت شد؛ بدهی باقی‌مانده: {link.debt:,}.", "success")
    return redirect(back)


@app.route("/admin/classes/delete-course/<int:course_id>", methods=["GET", "POST"])
@login_required
@role_required("admin")
def course_delete(course_id):
    """حذف دوره؛ فقط بعد از تسویه‌ی حقوق مدرس (و نبودن بدهی دانش‌آموز و جلسه‌ی تمام‌نشده)."""
    course = db.session.get(Courses, course_id)
    if not course:
        abort(404)

    code = course.course_code
    blocked = course_delete_reasons([course])[course.id]
    enrolled = sessions = attendance = 0
    if code:
        enrolled = Linking_the_student_to_the_course.query.filter_by(course_code=code).count()
        sessions = Linking_the_course_to_the_class.query.filter_by(course_code=code).count()
        attendance = Attendance.query.filter_by(course_code=code).count()

    if request.method == "POST":
        if blocked:
            flash(blocked, "error")
            return redirect(url_for("courses_list"))
        if code:
            Linking_the_student_to_the_course.query.filter_by(course_code=code).delete()
            Linking_the_course_to_the_class.query.filter_by(course_code=code).delete()
            Attendance.query.filter_by(course_code=code).delete()
        db.session.delete(course)
        db.session.commit()
        flash(f"دوره «{course.course_name}» حذف شد.", "success")
        return redirect(url_for("courses_list"))

    links = [(label, count) for label, count in (
        ("دانش‌آموز ثبت‌نام‌شده", enrolled),
        ("جلسه‌ی برنامه‌ریزی‌شده", sessions),
        ("حضور و غیاب", attendance),
    ) if count]
    return render_template(
        "confirm_delete.html",
        crumb="مدیریت کلاس‌ها", kind="دوره", person_name=course.course_name or code or "",
        links=links, blocked=blocked,
        extra_note="سابقه‌ی پرداخت‌های دانش‌آموزان و پرداخت حقوق مدرس برای گزارش مالی باقی می‌ماند.",
        form_action=url_for("course_delete", course_id=course.id),
        cancel_url=url_for("courses_list"),
    )


@app.route("/admin/classes/edit-course/<int:course_id>", methods=["GET", "POST"])
@login_required
@role_required("admin")
def course_edit(course_id):
    course = db.session.get(Courses, course_id)
    if not course:
        abort(404)

    current = None
    if course.course_instructor_national_id_number:
        current = Teachers.query.filter_by(
            national_id_number=course.course_instructor_national_id_number).first()
    form = {"course_name": course.course_name or "",
            "course_code": course.course_code or "",
            "price": str(course.price or ""),
            "teacher_salary": str(course.teacher_salary or ""),
            "teacher_id": str(current.id) if current else "",
            "activation_date": course.activation_date or ""}

    if request.method == "POST":
        form.update({
            "course_name": clean_text(request.form.get("course_name"), 100),
            "price": clean_digits(request.form.get("price"), 25),
            "teacher_salary": clean_digits(request.form.get("teacher_salary"), 25),
            "teacher_id": clean_digits(request.form.get("teacher_id"), 10),
            "activation_date": clean_digits(request.form.get("activation_date"), 20),
        })
        teacher, teacher_error = read_course_teacher(form["teacher_id"])
        start_date, start_error = read_start_date(form["activation_date"])
        price = parse_money(form["price"])
        salary = parse_money(form["teacher_salary"])
        min_price = max_paid_in_course(course)
        salary_paid = teacher_paid_map().get(course.course_code, 0)

        error = None
        if not form["course_name"]:
            error = "نام دوره را وارد کنید."
        elif not price:
            error = "قیمت دوره را به عدد وارد کنید (بیشتر از صفر)."
        elif price < min_price:
            error = (f"قیمت نمی‌تواند کمتر از مبلغی باشد که یک دانش‌آموز تا الان "
                     f"پرداخته است ({min_price:,}).")
        elif not salary:
            error = "حقوق مدرس برای این دوره را به عدد وارد کنید (بیشتر از صفر)."
        elif salary < salary_paid:
            error = (f"حقوق نمی‌تواند کمتر از مبلغی باشد که تا الان به مدرس پرداخت شده "
                     f"({salary_paid:,}).")
        elif teacher_error:
            error = teacher_error
        elif start_error:
            error = start_error

        if error:
            flash(error, "error")
        else:
            was_active = bool(course.active)
            # فعال بودن همیشه به وجود مدرس بسته است (و دوره‌ی پایان‌یافته فعال نمی‌شود)
            now_active = teacher is not None and not course.end_of_course

            course.course_name = form["course_name"]
            course.price = price
            course.teacher_salary = salary
            recompute_course_debts(course)  # با تغییر قیمت، بدهی دانش‌آموزان دوباره حساب شود
            course.course_instructor_national_id_number = (
                teacher.national_id_number if teacher else None)
            course.active = now_active
            course.activation_date = start_date
            db.session.commit()

            if now_active and not was_active:
                flash("مدرس ثبت شد و دوره فعال شد.", "success")
            elif not now_active and was_active:
                flash("مدرس برداشته شد؛ دوره غیرفعال شد.", "success")
            else:
                flash("اطلاعات دوره ذخیره شد.", "success")
            return redirect(url_for("courses_list"))

    return render_template("course_form.html", form=form, teachers=teacher_choices(),
                           is_edit=True, heading=f"ویرایش دوره: {course.course_name}",
                           submit_label="ذخیره تغییرات",
                           form_action=url_for("course_edit", course_id=course.id),
                           cancel_url=url_for("courses_list"))


# =========================================================
# COURSE SCHEDULE (برگزاری دوره در کلاس: «اجاره کلاس برای دوره‌ها»)
# هر برنامه یک جلسه است: دوره‌ی X در کلاس Y از ساعت A تا B.
# با شروع هر جلسه یکی به شماره‌ی جلسه‌ی دوره اضافه می‌شود (فقط یک بار).
# =========================================================

def sync_course_sessions():
    """با رسیدن ساعت شروع هر جلسه‌ی برنامه‌ریزی‌شده، یکی به number_of_session دوره اضافه می‌شود.
    هر جلسه فقط یک بار شمرده می‌شود (session_counted). وقتی جلسه‌ی دهم هم تمام شد، دوره
    پایان می‌یابد. این تابع در هر درخواستِ کاربر واردشده اجرا می‌شود."""
    now = now_text()
    changed = False

    pending = [l for l in Linking_the_course_to_the_class.query.all()
               if not l.session_counted and l.class_start_time and l.class_start_time <= now]
    for link in sorted(pending, key=lambda l: l.class_start_time):
        link.session_counted = True
        course = Courses.query.filter_by(course_code=link.course_code).first()
        if course:
            course.number_of_session = min((course.number_of_session or 0) + 1,
                                           COURSE_TOTAL_SESSIONS)
            link.session_number = course.number_of_session
        changed = True

    for course in Courses.query.filter(Courses.number_of_session >= COURSE_TOTAL_SESSIONS).all():
        if course.end_of_course:
            continue
        unfinished = [l for l in Linking_the_course_to_the_class.query.filter_by(
            course_code=course.course_code).all() if l.class_end_time and l.class_end_time > now]
        if not unfinished:
            course.end_of_course = True
            course.active = False
            changed = True

    if changed:
        db.session.commit()


@app.before_request
def keep_course_sessions_in_sync():
    if "user_id" in session and request.endpoint not in (None, "static"):
        try:
            sync_course_sessions()
        except Exception:  # صفحه به‌خاطر خطای همگام‌سازی از کار نیفتد
            db.session.rollback()
            app.logger.exception("sync_course_sessions failed")


def pending_sessions(course_code):
    """جلسه‌های برنامه‌ریزی‌شده‌ای که هنوز شروع نشده‌اند (شمرده نشده‌اند)"""
    return sum(1 for l in Linking_the_course_to_the_class.query.filter_by(
        course_code=course_code).all() if not l.session_counted)


def schedulable_courses():
    """دوره‌هایی که می‌شود برایشان کلاس برنامه‌ریزی کرد: فعال، با مدرس، پایان‌نیافته،
    و هنوز جلسه‌ی خالی دارند"""
    result = []
    for c in Courses.query.order_by(Courses.id.desc()).all():
        if c.end_of_course or not c.active or not c.course_instructor_national_id_number:
            continue
        if (c.number_of_session or 0) + pending_sessions(c.course_code) >= COURSE_TOTAL_SESSIONS:
            continue
        result.append((c.id, f"{c.course_code} — {c.course_name} ({session_label(c.number_of_session)})"))
    return result


def course_time_conflicts(course, start, end):
    """تداخل با جلسه‌های تمام‌نشده‌ی دیگرِ همین دوره، یا دوره‌های دیگری که مدرس یکسان دارند.
    خروجی: فهرست متن‌های تداخل"""
    courses = {c.course_code: c for c in Courses.query.all()}
    now = now_text()
    messages = []
    for link in Linking_the_course_to_the_class.query.all():
        # جلسه‌ی تمام‌شده یا لغوشده (پایانش گذشته) تداخل حساب نمی‌شود
        if not (link.class_start_time and link.class_end_time and link.class_end_time > now
                and start < link.class_end_time and link.class_start_time < end):
            continue
        when = (f"{link.class_start_time[:10]} از {link.class_start_time[11:16]} "
                f"تا {link.class_end_time[11:16]}")
        other = courses.get(link.course_code)
        if link.course_code == course.course_code:
            messages.append(f"خود این دوره در این زمان کلاس دارد ({when}، کلاس {link.class_number})")
        elif (other and course.course_instructor_national_id_number
              and other.course_instructor_national_id_number == course.course_instructor_national_id_number):
            messages.append(f"مدرس این دوره در این زمان دوره‌ی «{other.course_name}» را دارد ({when})")
    return messages


@app.route("/admin/classes/rent-courses", methods=["GET", "POST"])
@login_required
@role_required("admin")
def schedule_add():
    today = format_jalali(*today_jalali())
    form = {"course_id": "", "class_id": "", "date": today, "start_time": "", "end_time": ""}

    if request.method == "POST":
        form = {
            "course_id": clean_digits(request.form.get("course_id"), 10),
            "class_id": clean_digits(request.form.get("class_id"), 10),
            "date": clean_digits(request.form.get("date"), 20),
            "start_time": clean_digits(request.form.get("start_time"), 10),
            "end_time": clean_digits(request.form.get("end_time"), 10),
        }
        course = cls = None
        if form["course_id"].isascii() and form["course_id"].isdigit():
            course = db.session.get(Courses, int(form["course_id"]))
        if form["class_id"].isascii() and form["class_id"].isdigit():
            cls = db.session.get(Classes, int(form["class_id"]))
        day = parse_jalali_date(form["date"])
        start_hm = normalize_time(form["start_time"])
        end_hm = normalize_time(form["end_time"])

        error = None
        if not course:
            error = "دوره را انتخاب کنید."
        elif course.end_of_course:
            error = "این دوره تمام شده است؛ جلسه‌ی بعدی برگزار نمی‌شود."
        elif not course.active or not course.course_instructor_national_id_number:
            error = "این دوره فعال نیست؛ تا وقتی مدرس در آن ثبت نشود برایش کلاس برنامه‌ریزی نمی‌شود."
        elif (course.number_of_session or 0) + pending_sessions(course.course_code) >= COURSE_TOTAL_SESSIONS:
            error = f"همه‌ی {COURSE_TOTAL_SESSIONS} جلسه‌ی این دوره برگزار یا برنامه‌ریزی شده است."
        elif not cls:
            error = "کلاس را انتخاب کنید."
        elif not day:
            error = "تاریخ نامعتبر است. تاریخ شمسی را مثل ۱۴۰۵/۰۷/۲۰ وارد کنید."
        elif not start_hm or not end_hm:
            error = "ساعت شروع و پایان را به شکل 14:30 وارد کنید."
        elif end_hm <= start_hm:
            error = "ساعت پایان باید بعد از ساعت شروع باشد."
        else:
            start, end = f"{day} {start_hm}", f"{day} {end_hm}"
            class_conflicts = booking_conflicts(cls.class_number, start, end)
            other_conflicts = course_time_conflicts(course, start, end)
            if end <= now_text():
                error = "این بازه‌ی زمانی گذشته است."
            elif class_conflicts:
                error = (f"تداخل دارد: کلاس {cls.class_number} در این بازه رزرو است: "
                         f"{describe_bookings(class_conflicts)}. ساعت یا کلاس دیگری انتخاب کنید.")
            elif other_conflicts:
                error = "تداخل دارد: " + "؛ ".join(other_conflicts) + "."

        if error:
            flash(error, "error")
        else:
            db.session.add(Linking_the_course_to_the_class(
                course_code=course.course_code,
                class_number=cls.class_number,
                number_of_students=course.number_of_students or 0,
                class_start_time=start,
                class_end_time=end,
                session_counted=False,
            ))
            db.session.commit()
            flash(f"دوره‌ی «{course.course_name}» در کلاس {cls.class_number} در {day} از {start_hm} "
                  f"تا {end_hm} برنامه‌ریزی شد. با شروع کلاس، شماره‌ی جلسه‌ی دوره یکی اضافه می‌شود "
                  f"(الان: {session_label(course.number_of_session)}).", "success")
            return redirect(url_for("schedules_list"))

    bookings = sorted(upcoming_bookings().items(), key=lambda item: natural_key(item[0]))
    return render_template("schedule_form.html", form=form, courses=schedulable_courses(),
                           classes=class_choices(), today=today, bookings=bookings)


@app.route("/admin/classes/course-schedule")
@login_required
@role_required("admin")
def schedules_list():
    now = now_text()
    names = {c.course_code: c.course_name for c in Courses.query.all()}
    labels = {"upcoming": "در پیش‌رو", "running": "در حال برگزاری", "ended": "تمام شده"}
    rows = []
    for l in sorted(Linking_the_course_to_the_class.query.all(),
                    key=lambda l: l.class_start_time or "", reverse=True):
        state = rental_state(l.class_start_time, l.class_end_time, now)
        start, end = l.class_start_time or "", l.class_end_time or ""
        rows.append({"id": l.id, "course": names.get(l.course_code, l.course_code),
                     "code": l.course_code, "class_number": l.class_number or "—",
                     "date": start[:10], "from": start[11:16], "to": end[11:16],
                     "session": f"جلسه {l.session_number}" if l.session_counted and l.session_number else "پس از شروع",
                     "state": state, "label": labels[state]})
    return render_template("schedules_list.html", rows=rows,
                           running=sum(1 for r in rows if r["state"] == "running"))


@app.route("/admin/classes/schedule-cancel/<int:link_id>", methods=["GET", "POST"])
@login_required
@role_required("admin")
def schedule_cancel(link_id):
    """مثل لغو اجاره: در پیش‌رو -> حذف؛ در حال برگزاری -> کلاس همین لحظه تمام اعلام می‌شود
    (جلسه‌ی شروع‌شده از شماره‌ی جلسه‌ی دوره کم نمی‌شود)؛ تمام‌شده -> حذف از لیست."""
    link = db.session.get(Linking_the_course_to_the_class, link_id)
    if not link:
        abort(404)

    now = now_text()
    state = rental_state(link.class_start_time, link.class_end_time, now)
    course = Courses.query.filter_by(course_code=link.course_code).first()
    label = f"دوره‌ی {course.course_name if course else link.course_code} در کلاس {link.class_number} ({link.class_start_time})"

    if request.method == "POST":
        if state == "running":
            link.class_end_time = now  # از همین لحظه کلاس تمام شده و آزاد است
            db.session.commit()
            flash(f"جلسه لغو شد و کلاس {link.class_number} تمام اعلام شد.", "success")
        else:
            db.session.delete(link)
            db.session.commit()
            flash("برنامه‌ی جلسه حذف شد." if state == "ended" else "برنامه‌ی جلسه لغو شد.", "success")
        return redirect(url_for("schedules_list"))

    context = dict(crumb="مدیریت کلاس‌ها", kind="برنامه‌ی جلسه", person_name=label, links=[],
                   blocked=None, extra_note=None,
                   form_action=url_for("schedule_cancel", link_id=link.id),
                   cancel_url=url_for("schedules_list"))
    if state == "running":
        context.update(
            title=f"لغو جلسه‌ی در حال برگزاری: {label}",
            question=("با لغو، کلاس همین الان تمام اعلام می‌شود و ساعت پایان به همین لحظه تغییر می‌کند."),
            extra_note="این جلسه با شروعش شمرده شده و از شماره‌ی جلسه‌ی دوره کم نمی‌شود.",
            submit_label="بله، لغو شود و کلاس تمام شود",
        )
    elif state == "ended":
        context.update(extra_note="شماره‌ی جلسه‌ی دوره تغییری نمی‌کند؛ فقط این ردیف از برنامه حذف می‌شود.")
    return render_template("confirm_delete.html", **context)


# =========================================================
# FINANCE (امور مالی)
# دریافتی‌ها: بیعانه و تسویه‌ی دانش‌آموزان (Payments) و اجاره‌ی کلاس‌ها
# پرداختی‌ها: حقوق دبیران (TeacherPayments)؛ هر دوره یک حقوق دارد (Courses.teacher_salary)
# =========================================================

def student_name_map(national_ids):
    names = {}
    ids = {i for i in national_ids if i}
    if ids:
        for st in Students.query.filter(Students.national_id_number.in_(ids)).all():
            names[st.national_id_number] = f"{st.first_name or ''} {st.last_name or ''}".strip()
    return names


def teacher_name_map(national_ids):
    names = {}
    ids = {i for i in national_ids if i}
    if ids:
        for t in Teachers.query.filter(Teachers.national_id_number.in_(ids)).all():
            names[t.national_id_number] = f"{t.first_name or ''} {t.last_name or ''}".strip()
    return names


def course_name_map():
    return {c.course_code: c for c in Courses.query.all()}


def teacher_paid_map():
    """مجموع حقوقی که تا الان برای هر دوره به مدرس پرداخت شده: {کد دوره: مبلغ}"""
    paid = {}
    for p in TeacherPayments.query.all():
        paid[p.course_code] = paid.get(p.course_code, 0) + (p.amount or 0)
    return paid


@app.route("/admin/finance/today-turnover")
@login_required
@role_required("admin")
def finance_today():
    """گردش مالی یک روز (پیش‌فرض امروز): دریافتی‌ها (بیعانه، تسویه، اجاره‌ی کلاس) و
    پرداختی‌ها (حقوق دبیران) و مبلغ خالص."""
    today = format_jalali(*today_jalali())
    raw = clean_digits(request.args.get("date"), 20)
    day = today
    if raw:
        parsed = parse_jalali_date(raw)
        if parsed:
            day = parsed
        else:
            flash("تاریخ نامعتبر است؛ امروز نمایش داده شد. تاریخ شمسی را مثل ۱۴۰۵/۰۷/۲۰ وارد کنید.", "error")

    payments = Payments.query.filter_by(payment_date=day).order_by(Payments.id).all()
    rentals = Renting_out_a_class.query.filter_by(registration_date=day).order_by(
        Renting_out_a_class.id).all()
    salaries = TeacherPayments.query.filter_by(payment_date=day).order_by(TeacherPayments.id).all()

    students = student_name_map(p.student_national_id_number for p in payments)
    teachers = teacher_name_map([r.teacher_national_id_number for r in rentals]
                                + [s.teacher_national_id_number for s in salaries])
    courses = course_name_map()

    entries = []
    for p in payments:
        course = courses.get(p.course_code)
        entries.append({"kind": p.kind or "پرداخت", "out": False,
                        "who": students.get(p.student_national_id_number, p.student_national_id_number or "—"),
                        "what": course.course_name if course and course.course_name else (p.course_code or "—"),
                        "amount": p.amount or 0})
    for r in rentals:
        entries.append({"kind": "اجاره کلاس", "out": False,
                        "who": teachers.get(r.teacher_national_id_number, r.teacher_national_id_number or "—"),
                        "what": f"کلاس {r.class_number} ({(r.class_start_time or '')[11:16]} تا {(r.class_end_time or '')[11:16]})",
                        "amount": r.amount or 0})
    for sal in salaries:
        course = courses.get(sal.course_code)
        entries.append({"kind": "حقوق دبیر", "out": True,
                        "who": teachers.get(sal.teacher_national_id_number, sal.teacher_national_id_number or "—"),
                        "what": course.course_name if course and course.course_name else (sal.course_code or "—"),
                        "amount": sal.amount or 0})

    totals = {}
    for e in entries:
        totals[e["kind"]] = totals.get(e["kind"], 0) + e["amount"]
    income = sum(e["amount"] for e in entries if not e["out"])
    outgo = totals.get("حقوق دبیر", 0)
    return render_template("finance_today.html", entries=entries, day=day, today=today,
                           deposits=totals.get("بیعانه", 0), settlements=totals.get("تسویه", 0),
                           rents=totals.get("اجاره کلاس", 0), income=income,
                           salaries=outgo, net=income - outgo)


@app.route("/admin/finance/debts")
@login_required
@role_required("admin")
def finance_debts():
    """بدهی‌های آموزشگاه: حقوق دبیران. هر دوره یک حقوق دارد و مدرس دوره تا پرداخت کامل
    طلبکار است؛ حقوق را می‌شود در چند قسط پرداخت کرد."""
    courses = [c for c in Courses.query.all() if c.course_instructor_national_id_number]
    paid_map = teacher_paid_map()
    teachers = teacher_name_map(c.course_instructor_national_id_number for c in courses)

    rows = []
    for c in courses:
        salary = c.teacher_salary or None
        paid = paid_map.get(c.course_code, 0)
        remaining = max(salary - paid, 0) if salary else None
        rows.append({"id": c.id, "code": c.course_code, "name": c.course_name,
                     "teacher": teachers.get(c.course_instructor_national_id_number, "—"),
                     "salary": salary, "paid": paid, "remaining": remaining,
                     "ended": bool(c.end_of_course)})
    # ابتدا دوره‌هایی که حقوق باقی‌مانده دارند (بیشتر به کمتر)، بعد حقوق‌ثبت‌نشده‌ها، بعد تسویه‌شده‌ها
    rows.sort(key=lambda r: (0 if r["remaining"] else (1 if r["remaining"] is None else 2),
                             -(r["remaining"] or 0), -r["id"]))
    return render_template(
        "finance_debts.html", rows=rows,
        total_salary=sum(r["salary"] or 0 for r in rows),
        total_paid=sum(r["paid"] for r in rows if r["salary"]),
        total_remaining=sum(r["remaining"] or 0 for r in rows))


@app.route("/admin/finance/pay-teacher/<int:course_id>", methods=["POST"])
@login_required
@role_required("admin")
def teacher_pay(course_id):
    """پرداخت بخشی از حقوق مدرس یک دوره (هر مبلغی تا سقف حقوق باقی‌مانده)"""
    course = db.session.get(Courses, course_id)
    if not course:
        abort(404)

    amount = parse_money(request.form.get("amount"))
    teacher_id = course.course_instructor_national_id_number
    salary = course.teacher_salary or 0
    remaining = salary - teacher_paid_map().get(course.course_code, 0)

    if not teacher_id:
        flash("برای این دوره مدرسی ثبت نشده است.", "error")
    elif not salary:
        flash("حقوق این دوره ثبت نشده است؛ ابتدا از «ویرایش دوره» حقوق را ثبت کنید.", "error")
    elif remaining <= 0:
        flash("حقوق این دوره کاملاً پرداخت شده است.", "error")
    elif amount is None or amount < 1:
        flash("مبلغ پرداخت را به عدد و بیشتر از صفر وارد کنید.", "error")
    elif amount > remaining:
        flash(f"مبلغ پرداخت نمی‌تواند از حقوق باقی‌مانده ({remaining:,}) بیشتر باشد.", "error")
    else:
        db.session.add(TeacherPayments(
            teacher_national_id_number=teacher_id, course_code=course.course_code,
            amount=amount, payment_date=format_jalali(*today_jalali())))
        db.session.commit()
        left = remaining - amount
        if left == 0:
            flash(f"{amount:,} پرداخت شد و حقوق دوره «{course.course_name}» کاملاً تسویه شد.", "success")
        else:
            flash(f"{amount:,} از حقوق دوره «{course.course_name}» پرداخت شد؛ باقی‌مانده: {left:,}.", "success")
    return redirect(url_for("finance_debts"))


@app.route("/admin/finance/receivables")
@login_required
@role_required("admin")
def finance_receivables():
    """طلب‌های آموزشگاه: شهریه‌ای که دانش‌آموزان هنوز نپرداخته‌اند؛ هم به تفکیک دوره
    و هم دانش‌آموز به دانش‌آموز."""
    all_links = Linking_the_student_to_the_course.query.all()
    links_by_course = {}
    for l in all_links:
        links_by_course.setdefault(l.course_code, []).append(l)
    courses = course_name_map()

    rows = []
    for course in sorted(courses.values(), key=lambda c: c.id, reverse=True):
        links = links_by_course.get(course.course_code, [])
        if not links:
            continue
        outstanding = sum(l.debt or 0 for l in links)
        if course.price:
            expected = course.price * len(links)
            received = max(expected - outstanding, 0)
            percent = round(received * 100 / expected) if expected else 100
        else:
            expected = received = percent = None
        rows.append({"id": course.id, "code": course.course_code, "name": course.course_name,
                     "price": course.price, "students": len(links), "expected": expected,
                     "received": received, "outstanding": outstanding, "percent": percent,
                     "ended": bool(course.end_of_course)})

    debt_links = [l for l in all_links if (l.debt or 0) > 0]
    students = student_name_map(l.student_national_id_number for l in debt_links)
    debt_rows = []
    for l in debt_links:
        course = courses.get(l.course_code)
        price = course.price if course and course.price else None
        debt_rows.append({"name": students.get(l.student_national_id_number, "—"),
                          "national_id": l.student_national_id_number,
                          "course": course.course_name if course and course.course_name else l.course_code,
                          "course_id": course.id if course else None,
                          "price": price,
                          "paid": (price - l.debt) if price else (l.deposit or 0),
                          "debt": l.debt})
    debt_rows.sort(key=lambda r: r["debt"], reverse=True)

    return render_template(
        "finance_receivables.html", rows=rows, debt_rows=debt_rows,
        debtors=len({r["national_id"] for r in debt_rows}),
        total_expected=sum(r["expected"] or 0 for r in rows),
        total_received=sum(r["received"] or 0 for r in rows),
        total_outstanding=sum(r["outstanding"] for r in rows))


# =========================================================
# TEACHER PANEL (کلاس‌های امروز و حضور و غیاب دبیر)
# دبیر متفرقه اصلاً وارد سایت نمی‌شود؛ فقط دبیران موظف و غیر موظف.
# =========================================================

def current_teacher():
    """دبیر واردشده؛ اگر دبیر نباشد یا متفرقه باشد None"""
    if session.get("role") != "teacher":
        return None
    teacher = db.session.get(Teachers, session.get("user_id"))
    if not teacher or teacher.type == "متفرقه":
        return None
    return teacher


def teacher_today_rows(teacher):
    """جلسه‌های امروزِ دوره‌های این دبیر (به ترتیب ساعت) همراه وضعیت حضور و غیاب"""
    national_id = teacher.national_id_number
    if not national_id:
        return []
    now = now_text()
    today = format_jalali(*today_jalali())
    courses = {c.course_code: c for c in
               Courses.query.filter_by(course_instructor_national_id_number=national_id).all()}
    links = sorted((l for l in Linking_the_course_to_the_class.query.all()
                    if l.course_code in courses and l.class_start_time
                    and l.class_start_time[:10] == today),
                   key=lambda l: l.class_start_time)
    if not links:
        return []

    attendance = {}
    for a in Attendance.query.all():
        if a.course_code in courses:
            attendance.setdefault((a.course_code, a.number_of_session), []).append(a)
    enrolled = {}
    for l in Linking_the_student_to_the_course.query.all():
        enrolled[l.course_code] = enrolled.get(l.course_code, 0) + 1

    labels = {"upcoming": "در پیش‌رو", "running": "در حال برگزاری", "ended": "تمام شده"}
    rows = []
    for l in links:
        course = courses[l.course_code]
        state = rental_state(l.class_start_time, l.class_end_time, now)
        records = attendance.get((l.course_code, l.session_number), []) if l.session_number else []
        rows.append({
            "id": l.id, "course": course.course_name, "code": l.course_code,
            "class_number": l.class_number or "—",
            "from": l.class_start_time[11:16], "to": (l.class_end_time or "")[11:16],
            "session": f"جلسه {l.session_number}" if l.session_number else "جلسه‌ی بعدی",
            "state": state, "label": labels[state],
            "can_take": state == "running" and bool(l.session_number),
            "students": enrolled.get(l.course_code, 0),
            "recorded": bool(records),
            "present": sum(1 for a in records if a.presence),
        })
    return rows


@app.route("/panel/classes/today")
@login_required
@role_required("teacher", "student_parent")
def teacher_today():
    """کلاس‌های امروز دبیر (برای دانش‌آموز فعلاً صفحه‌ی نگه‌دارنده)"""
    if session.get("role") != "teacher":
        return panel_page("classes", "today")
    teacher = current_teacher()
    if not teacher:
        session.clear()
        flash("دبیران متفرقه به سامانه دسترسی ندارند.", "error")
        return redirect(url_for("login"))
    return render_template("teacher_today.html", rows=teacher_today_rows(teacher),
                           today=format_jalali(*today_jalali()))


@app.route("/panel/classes/all")
@login_required
@role_required("teacher", "student_parent")
def teacher_courses():
    """کل دوره‌های دبیر (فعال و تمام‌شده) با پیشرفت و جلسه‌ی بعدی (برای دانش‌آموز فعلاً نگه‌دارنده)"""
    if session.get("role") != "teacher":
        return panel_page("classes", "all")
    teacher = current_teacher()
    if not teacher:
        session.clear()
        flash("دبیران متفرقه به سامانه دسترسی ندارند.", "error")
        return redirect(url_for("login"))

    national_id = teacher.national_id_number
    courses = (Courses.query.filter_by(course_instructor_national_id_number=national_id)
               .order_by(Courses.id.desc()).all()) if national_id else []
    codes = {c.course_code for c in courses}

    # شماره‌ی جلسه‌هایی که برایشان حضور و غیاب ثبت شده: {کد دوره: {شماره‌ی جلسه}}
    recorded = {}
    for a in Attendance.query.all():
        if a.course_code in codes and a.number_of_session:
            recorded.setdefault(a.course_code, set()).add(a.number_of_session)

    now = now_text()
    next_session = {}
    for l in sorted(Linking_the_course_to_the_class.query.all(), key=lambda l: l.class_start_time or ""):
        if (l.course_code in codes and l.class_start_time and l.class_end_time
                and l.class_end_time > now and l.course_code not in next_session):
            next_session[l.course_code] = (f"{l.class_start_time[:10]} | {l.class_start_time[11:16]} تا "
                                           f"{l.class_end_time[11:16]} | کلاس {l.class_number}")

    rows = []
    for c in courses:
        rows.append({"code": c.course_code, "name": c.course_name,
                     "state": "ended" if c.end_of_course else "active",
                     "session": session_label(c.number_of_session),
                     "students": c.number_of_students or 0,
                     "start": c.activation_date,
                     "recorded": len(recorded.get(c.course_code, ())),
                     "held": c.number_of_session or 0,
                     "next": next_session.get(c.course_code)})
    return render_template("teacher_courses.html", rows=rows,
                           total=len(rows), active=sum(1 for r in rows if r["state"] == "active"))


@app.route("/panel/attendance/<int:link_id>", methods=["GET", "POST"])
@login_required
@role_required("teacher")
def attendance_take(link_id):
    """ثبت حضور و غیاب یک جلسه؛ فقط برای جلسه‌ی در حال برگزاریِ دوره‌ی خودِ دبیر."""
    teacher = current_teacher()
    if not teacher:
        abort(403)
    link = db.session.get(Linking_the_course_to_the_class, link_id)
    if not link:
        abort(404)
    course = Courses.query.filter_by(course_code=link.course_code).first()
    if (not course or not teacher.national_id_number
            or course.course_instructor_national_id_number != teacher.national_id_number):
        abort(403)

    if (rental_state(link.class_start_time, link.class_end_time, now_text()) != "running"
            or not link.session_number):
        flash("حضور و غیاب فقط برای کلاسی که در حال برگزاری است ثبت می‌شود.", "error")
        return redirect(url_for("dashboard"))

    enrolled = Linking_the_student_to_the_course.query.filter_by(
        course_code=course.course_code).order_by(Linking_the_student_to_the_course.id).all()
    names = student_name_map(l.student_national_id_number for l in enrolled)
    existing = {a.student_national_id_number: a for a in Attendance.query.filter_by(
        course_code=course.course_code, number_of_session=link.session_number).all()}

    if request.method == "POST":
        present_ids = {int(v) for v in request.form.getlist("present") if v.isascii() and v.isdigit()}
        present_count = 0
        for e in enrolled:
            is_present = e.id in present_ids
            present_count += is_present
            record = existing.get(e.student_national_id_number)
            if record:
                record.presence = is_present
            else:
                db.session.add(Attendance(student_national_id_number=e.student_national_id_number,
                                          course_code=course.course_code,
                                          number_of_session=link.session_number,
                                          presence=is_present))
        db.session.commit()
        flash(f"حضور و غیاب جلسه {link.session_number} دوره «{course.course_name}» ذخیره شد: "
              f"{present_count} حاضر از {len(enrolled)} دانش‌آموز.", "success")
        return redirect(url_for("attendance_take", link_id=link.id))

    rows = [{"id": e.id, "name": names.get(e.student_national_id_number, "—"),
             "national_id": e.student_national_id_number,
             "present": bool(existing.get(e.student_national_id_number)
                             and existing[e.student_national_id_number].presence)}
            for e in enrolled]
    return render_template("attendance.html", course=course, link=link, rows=rows,
                           recorded=bool(existing))


@app.route("/panel/profile")
@login_required
@role_required("student_parent", "teacher")
def profile():
    """پروفایل دانش‌آموز/والدین و دبیر؛ فعلاً نگه‌دارنده."""
    return render_template("placeholder_page.html",
                           section_title="پروفایل",
                           page_title="پروفایل شما")


@app.route("/panel/<section>/<item>")
@login_required
@role_required("student_parent", "teacher")
def panel_page(section, item):
    """زیرمنوهای دانش‌آموز/والدین و دبیر؛ فقط آیتم‌های منوی همان نقش معتبرند."""
    for sec in USER_MENUS[session["role"]]:
        if sec["key"] == section:
            for key, title in sec.get("items", []):
                if key == item:
                    return render_template("placeholder_page.html",
                                           section_title=sec["title"],
                                           page_title=title)
    abort(404)


@app.errorhandler(400)
def bad_request(_e):
    return render_template("error.html", code=400,
                           message="درخواست نامعتبر بود. صفحه را دوباره بارگذاری کنید."), 400


@app.errorhandler(413)
def too_large(_e):
    return render_template("error.html", code=413,
                           message="حجم فایل‌های ارسالی زیاد است. هر تصویر حداکثر ۵ مگابایت."), 413


@app.errorhandler(403)
def forbidden(_e):
    return render_template("error.html", code=403, message="به این صفحه دسترسی ندارید."), 403


@app.errorhandler(404)
def not_found(_e):
    return render_template("error.html", code=404, message="صفحه پیدا نشد."), 404


if __name__ == "__main__":
    # در محیط واقعی debug را خاموش کنید و از gunicorn / waitress استفاده کنید
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1")
