"""
کد موقت برای ساخت یک دانش‌آموز و یک دبیر آزمایشی.
اجرا:  python create_test_users.py

هشدار: فقط برای تست است. قبل از راه‌اندازی واقعی این فایل را پاک کنید
و کاربران آزمایشی را از دیتابیس حذف کنید.
"""
from werkzeug.security import generate_password_hash

from models import Students, Teachers, app, db

TEST_PASSWORD = "Test12345"

STUDENT_NATIONAL_ID = "0499370899"
TEACHER_NATIONAL_ID = "1234567891"


def main():
    with app.app_context():

        # ---------- دانش‌آموز ----------
        if Students.query.filter_by(national_id_number=STUDENT_NATIONAL_ID).first():
            print("دانش‌آموز آزمایشی از قبل وجود دارد.")
        else:
            db.session.add(Students(
                first_name="علی",
                last_name="آزمایشی",
                national_id_number=STUDENT_NATIONAL_ID,
                grade_level="دهم",
                type="عادی",
                password=generate_password_hash(TEST_PASSWORD),
            ))
            print("دانش‌آموز آزمایشی ساخته شد.")

        # ---------- دبیر ----------
        if Teachers.query.filter_by(national_id_number=TEACHER_NATIONAL_ID).first():
            print("دبیر آزمایشی از قبل وجود دارد.")
        else:
            db.session.add(Teachers(
                first_name="رضا",
                last_name="آزمایشی",
                national_id_number=TEACHER_NATIONAL_ID,
                personnel_number="1001",
                type="موظف",
                password=generate_password_hash(TEST_PASSWORD),
            ))
            print("دبیر آزمایشی ساخته شد.")

        db.session.commit()

    print()
    print("اطلاعات ورود آزمایشی:")
    print(f"  دانش‌آموز و والدین -> کد ملی: {STUDENT_NATIONAL_ID} | رمز: {TEST_PASSWORD}")
    print(f"  دبیران            -> کد ملی: {TEACHER_NATIONAL_ID} | رمز: {TEST_PASSWORD}")


if __name__ == "__main__":
    main()
