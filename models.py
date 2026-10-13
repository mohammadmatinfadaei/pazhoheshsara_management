from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os


# =========================================================
# APP CONFIG
# =========================================================

app = Flask(__name__)

# نکته: SECRET_KEY و تنظیمات امنیتی کوکی در app.py انجام می‌شود.
# CORS هم عمداً حذف شده است؛ با CORS(app) همه‌ی سایت‌ها اجازه‌ی
# درخواست به برنامه را داشتند.


# =========================================================
# DATABASE PATH
# =========================================================

# مسیر پوشه instance
basedir = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "instance"
)

# اگر پوشه instance وجود نداشت، ساخته شود
os.makedirs(basedir, exist_ok=True)


# =========================================================
# DATABASE CONFIG
# =========================================================

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(
    basedir,
    'pajoheshsara_management_database.db'
)

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# =========================================================
# ADMINS (کارمندان / ادمین‌های آموزشگاه)
# =========================================================

class Admins(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    first_name = db.Column(db.Text)
    last_name = db.Column(db.Text)

    # کد پرسنلی یکتا؛ ورود با همین کد انجام می‌شود
    personnel_code = db.Column(db.Text, unique=True, nullable=False)

    # کد ملی ادمین (یکتا)
    national_id_number = db.Column(db.Text, unique=True, nullable=False)

    # فقط Hash رمز ذخیره می‌شود
    password = db.Column(db.Text, nullable=False)

    # کاربر God؛ پیش‌فرض False است و فقط یک نفر می‌تواند True باشد
    # (ایندکس یکتای جزئی در پایین، دوتا True شدن را در خود دیتابیس رد می‌کند)
    is_god = db.Column(db.Boolean, default=False, nullable=False)

    __table_args__ = (
        db.Index(
            "only_one_god",
            "is_god",
            unique=True,
            sqlite_where=db.text("is_god = 1"),
        ),
    )


    def __repr__(self):

        return (
            f"Admins("
            f"{self.id},"
            f"{self.first_name},"
            f"{self.last_name},"
            f"{self.personnel_code},"
            f"{self.national_id_number},"
            f"{self.is_god}"
            f")"
        )


# =========================================================
# STUDENTS
# =========================================================

class Students(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    first_name = db.Column(db.Text)
    last_name = db.Column(db.Text)

    date_of_birth = db.Column(db.Text)

    # کد ملی را Text نگه می‌داریم
    # چون ممکن است صفر اول داشته باشد
    national_id_number = db.Column(db.Text)

    grade_level = db.Column(db.Text)

    # شماره شاد ممکن است فرمت خاص داشته باشد
    shad_number = db.Column(db.Text)

    field_of_study = db.Column(db.Text)
    school_name = db.Column(db.Text)

    father_name = db.Column(db.Text)
    mother_name_and_last_name = db.Column(db.Text)

    father_number = db.Column(db.Text)
    mother_number = db.Column(db.Text)

    father_job = db.Column(db.Text)
    mother_job = db.Column(db.Text)

    father_educational_qualification = db.Column(db.Text)
    mother_educational_qualification = db.Column(db.Text)

    registration_date = db.Column(db.Text)

    address = db.Column(db.Text)

    # نوع دانش‌آموز: عادی / فعال / پژوهشگر
    type = db.Column(db.Text)

    note = db.Column(db.Text)

    # در اینجا فقط Hash ذخیره می‌شود
    # منطق Hash کردن در فایل اصلی برنامه قرار دارد
    password = db.Column(db.Text)

    # نام فایل تصاویر (اختیاری)؛ خود فایل‌ها در instance/uploads/students هستند
    face_photo = db.Column(db.Text)
    birth_certificate_photo = db.Column(db.Text)


    # -----------------------------------------------------
    # REPR
    # -----------------------------------------------------

    def __repr__(self):

        return (
            f"Students("
            f"{self.id},"
            f"{self.first_name},"
            f"{self.last_name},"
            f"{self.national_id_number},"
            f"{self.date_of_birth},"
            f"{self.grade_level},"
            f"{self.shad_number},"
            f"{self.field_of_study},"
            f"{self.registration_date},"
            f"{self.school_name},"
            f"{self.address},"
            f"{self.note},"
            f"{self.type},"
            f"{self.password},"
            f"{self.father_name},"
            f"{self.father_educational_qualification},"
            f"{self.father_job},"
            f"{self.father_number},"
            f"{self.mother_name_and_last_name},"
            f"{self.mother_educational_qualification},"
            f"{self.mother_job},"
            f"{self.mother_number}"
            f")"
        )


# =========================================================
# TEACHERS
# =========================================================

class Teachers(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    first_name = db.Column(db.Text)
    last_name = db.Column(db.Text)

    date_of_birth = db.Column(db.Text)

    # کد ملی Text
    national_id_number = db.Column(db.Text)

    # کد پرسنلی Text
    # چون ممکن است صفر اول داشته باشد
    personnel_number = db.Column(db.Text)

    landline_number = db.Column(db.Text)
    phone_number = db.Column(db.Text)

    father_name = db.Column(db.Text)

    email = db.Column(db.Text)

    # شماره کارت Text
    # چون ممکن است صفر اول داشته باشد
    credit_card_number = db.Column(db.Text)

    # شماره حساب Text
    account_number = db.Column(db.Text)

    # شبا Text
    iban = db.Column(db.Text)

    educational_qualification = db.Column(db.Text)

    university_major = db.Column(db.Text)

    year_of_obtaining_the_degree = db.Column(db.Text)

    place_of_employment = db.Column(db.Text)

    marital_status = db.Column(db.Text)

    # کد پستی Text
    postal_code = db.Column(db.Text)

    date_of_hire = db.Column(db.Text)

    address = db.Column(db.Text)

    # نوع دبیر: موظف / غیر موظف / متفرقه
    type = db.Column(db.Text)

    note = db.Column(db.Text)

    # در اینجا فقط Hash ذخیره می‌شود
    # منطق Hash کردن در فایل اصلی برنامه قرار دارد
    password = db.Column(db.Text)


    # -----------------------------------------------------
    # REPR
    # -----------------------------------------------------

    def __repr__(self):

        return (
            f"Teachers("
            f"{self.id},"
            f"{self.first_name},"
            f"{self.last_name},"
            f"{self.national_id_number},"
            f"{self.personnel_number},"
            f"{self.landline_number},"
            f"{self.phone_number},"
            f"{self.email},"
            f"{self.educational_qualification},"
            f"{self.address},"
            f"{self.note},"
            f"{self.type},"
            f"{self.password},"
            f"{self.father_name},"
            f"{self.credit_card_number},"
            f"{self.account_number},"
            f"{self.iban},"
            f"{self.university_major},"
            f"{self.year_of_obtaining_the_degree},"
            f"{self.marital_status},"
            f"{self.place_of_employment},"
            f"{self.date_of_hire},"
            f"{self.postal_code}"
            f")"
        )


# =========================================================
# CLASSES
# =========================================================

class Classes(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    # شماره کلاس را Text نگه می‌داریم
    # چون ممکن است کلاس‌هایی مثل A1 هم وجود داشته باشند
    class_number = db.Column(db.Text)

    # شماره طبقه عددی است
    floor_number = db.Column(db.Integer)

    # وضعیت پیش‌فرض همیشه غیرفعال است؛ فقط وقتی کلاسی در این کلاس
    # در حال برگزاری باشد فعال می‌شود (از کاربر گرفته نمی‌شود)
    # توجه: وضعیت «فعال» کلاس دیگر از این ستون خوانده نمی‌شود؛ هنگام نمایش از روی
    # اجاره‌ها (و بعداً جلسات دوره‌ها) حساب می‌شود. ستون فقط برای سازگاری مانده است.
    status = db.Column(
        db.Boolean,
        default=False
    )


    def __repr__(self):

        return (
            f"Classes("
            f"{self.id},"
            f"{self.class_number},"
            f"{self.floor_number}"
            f")"
        )


# =========================================================
# COURSES
# =========================================================

class Courses(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    course_name = db.Column(db.Text)

    course_instructor_national_id_number = db.Column(db.Text)

    # تعداد دانش‌آموزان
    number_of_students = db.Column(db.Integer)

    # شماره‌ی جلسه‌ی فعلی دوره: ۰ یعنی هنوز جلسه‌ای برگزار نشده، حداکثر ۱۰
    # (هر دوره ۱۰ جلسه دارد؛ این ستون تعداد کل جلسات نیست)
    number_of_session = db.Column(db.Integer, default=0)

    # تاریخ شروع دوره (شمسی، اختیاری)
    activation_date = db.Column(db.Text)

    course_code = db.Column(db.Text)

    # قیمت دوره برای هر دانش‌آموز (عدد صحیح)
    price = db.Column(db.Integer)

    active = db.Column(
        db.Boolean,
        default=False
    )

    end_of_course = db.Column(
        db.Boolean,
        default=False
    )


    def __repr__(self):

        return (
            f"Courses("
            f"{self.id},"
            f"{self.course_name},"
            f"{self.course_instructor_national_id_number},"
            f"{self.number_of_students},"
            f"{self.number_of_session},"
            f"{self.activation_date},"
            f"{self.course_code},"
            f"{self.price}"
            f")"
        )


# =========================================================
# RENTING OUT A CLASS
# =========================================================

class Renting_out_a_class(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    class_number = db.Column(db.Text)

    teacher_national_id_number = db.Column(db.Text)

    # شروع و پایان؛ شمسی و به شکل "1405/07/20 14:00" (ساعت تهران)
    class_start_time = db.Column(db.Text)

    class_end_time = db.Column(db.Text)

    # مبلغ اجاره‌ای که از دبیر دریافت شده
    amount = db.Column(db.Integer)

    # روز دریافت پول (شمسی)
    registration_date = db.Column(db.Text)


    def __repr__(self):

        return (
            f"Renting_out_a_class("
            f"{self.id},"
            f"{self.class_number},"
            f"{self.teacher_national_id_number},"
            f"{self.class_start_time},"
            f"{self.class_end_time},"
            f"{self.amount}"
            f")"
        )


# =========================================================
# LINKING COURSE TO CLASS
# =========================================================

class Linking_the_course_to_the_class(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    course_code = db.Column(db.Text)

    # شماره‌ی کلاسی که این جلسه در آن برگزار می‌شود
    class_number = db.Column(db.Text)

    # تعداد دانش‌آموزان دوره هنگام برنامه‌ریزی این جلسه
    number_of_students = db.Column(db.Integer)

    # شروع و پایان؛ شمسی و به شکل "1405/07/20 14:00" (ساعت تهران)
    class_start_time = db.Column(db.Text)

    # اصلاح اشتباه calss_end_time
    class_end_time = db.Column(db.Text)

    # آیا با شروع این جلسه، یکی به شماره‌ی جلسه‌ی دوره اضافه شده؟ (فقط یک بار)
    session_counted = db.Column(db.Boolean, default=False)

    # شماره‌ی جلسه‌ی دوره که این برنامه است (بعد از شروع پر می‌شود)
    session_number = db.Column(db.Integer)


    def __repr__(self):

        return (
            f"Linking_the_course_to_the_class("
            f"{self.id},"
            f"{self.course_code},"
            f"{self.class_number},"
            f"{self.number_of_students},"
            f"{self.class_start_time},"
            f"{self.class_end_time}"
            f")"
        )


# =========================================================
# LINKING STUDENT TO COURSE
# =========================================================

class Linking_the_student_to_the_course(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    student_national_id_number = db.Column(db.Text)

    course_code = db.Column(db.Text)

    # بیعانه‌ای که هنگام ثبت‌نام دریافت شده (از قیمت دوره کم می‌شود)
    deposit = db.Column(db.Integer)

    # بدهی باقی‌مانده = قیمت دوره - بیعانه - پرداخت‌های بعدی (تسویه‌ها)
    debt = db.Column(db.Integer)


    def __repr__(self):

        return (
            f"Linking_the_student_to_the_course("
            f"{self.id},"
            f"{self.student_national_id_number},"
            f"{self.course_code},"
            f"{self.deposit},"
            f"{self.debt}"
            f")"
        )


# =========================================================
# PAYMENTS (پرداخت‌های دانش‌آموزان: بیعانه و تسویه)
# هر دریافت پول یک ردیف است؛ برای «گردش مالی امروز» استفاده می‌شود.
# جدول جدید است و با اجرای برنامه خودکار ساخته می‌شود.
# =========================================================

class Payments(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    student_national_id_number = db.Column(db.Text)

    course_code = db.Column(db.Text)

    # مبلغ پرداخت‌شده
    amount = db.Column(db.Integer)

    # نوع پرداخت: بیعانه / تسویه
    kind = db.Column(db.Text)

    # تاریخ پرداخت؛ شمسی و به شکل 1405/07/18
    payment_date = db.Column(db.Text)


    def __repr__(self):

        return (
            f"Payments("
            f"{self.id},"
            f"{self.student_national_id_number},"
            f"{self.course_code},"
            f"{self.amount},"
            f"{self.kind},"
            f"{self.payment_date}"
            f")"
        )


# =========================================================
# LIST OF ITEMS
# =========================================================

class List_of_items(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    name_of_item = db.Column(db.Text)


    def __repr__(self):

        return (
            f"List_of_items("
            f"{self.id},"
            f"{self.name_of_item}"
            f")"
        )


# =========================================================
# LOCKERS
# =========================================================

class Lockers(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    # شماره کمد عددی
    number_of_locker = db.Column(db.Integer)


    def __repr__(self):

        return (
            f"Lockers("
            f"{self.id},"
            f"{self.number_of_locker}"
            f")"
        )


# =========================================================
# LINKING ITEMS TO LOCKER
# =========================================================

class Linking_the_items_to_the_locker(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    # شناسه کمد
    locker_id = db.Column(db.Integer)

    # شناسه وسیله
    item_id = db.Column(db.Integer)


    def __repr__(self):

        return (
            f"Linking_the_items_to_the_locker("
            f"{self.id},"
            f"{self.locker_id},"
            f"{self.item_id}"
            f")"
        )


# =========================================================
# LOANS (امانت دادن وسایل)
# =========================================================

class Loans(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    # شناسه وسیله در جدول List_of_items؛ برای تشخیص «موجود بودن» لازم است
    item_id = db.Column(db.Integer)

    item_name = db.Column(db.Text)

    borrower_name = db.Column(db.Text)

    # شماره امانت‌گیر Text (صفر ابتدایی حفظ شود)
    borrower_number = db.Column(db.Text)

    borrower_school = db.Column(db.Text)

    # تاریخ‌ها شمسی و به شکل 1405/07/18
    registration_date = db.Column(db.Text)

    due_date = db.Column(db.Text)


    def __repr__(self):

        return (
            f"Loans("
            f"{self.id},"
            f"{self.item_id},"
            f"{self.item_name},"
            f"{self.borrower_name},"
            f"{self.borrower_number},"
            f"{self.borrower_school},"
            f"{self.registration_date},"
            f"{self.due_date}"
            f")"
        )


# =========================================================
# NOTES
# =========================================================

class Notes(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    # کد ملی ادمینی که یادداشت را نوشته (خودکار از حساب او ثبت می‌شود)
    national_id_number = db.Column(db.Text)

    text = db.Column(db.Text)

    # تاریخ نمایش یادداشت؛ شمسی و به شکل 1405/07/18
    date_of_show = db.Column(db.Text)


    def __repr__(self):

        return (
            f"Notes("
            f"{self.id},"
            f"{self.national_id_number},"
            f"{self.text},"
            f"{self.date_of_show}"
            f")"
        )


# =========================================================
# ATTENDANCE
# =========================================================

class Attendance(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    student_national_id_number = db.Column(db.Text)

    course_code = db.Column(db.Text)

    # شماره جلسه عددی
    number_of_session = db.Column(db.Integer)

    presence = db.Column(
        db.Boolean,
        default=False
    )


    def __repr__(self):

        return (
            f"Attendance("
            f"{self.id},"
            f"{self.student_national_id_number},"
            f"{self.course_code},"
            f"{self.number_of_session}"
            f")"
        )


# =========================================================
# CREATE DATABASE TABLES
# =========================================================

with app.app_context():

    db.create_all()
