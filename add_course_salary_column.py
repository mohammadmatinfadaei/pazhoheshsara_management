"""
افزودن ستون حقوق مدرس (teacher_salary) به جدول دوره‌ها در دیتابیس موجود (بدون پاک شدن اطلاعات).
اجرا:  python add_course_salary_column.py
فقط یک بار لازم است؛ اگر ستون از قبل باشد، چیزی تغییر نمی‌کند.
(models.py جدید این ستون را در کلاس Courses دارد.)

جدول جدید TeacherPayments (پرداخت حقوق) با اجرای برنامه خودکار ساخته می‌شود.
دوره‌هایی که قبلاً ساخته‌اید حقوق ندارند؛ از «ویرایش دوره» حقوقشان را ثبت کنید.
"""
from sqlalchemy import inspect, text

from models import Courses, app, db


def main():
    table = Courses.__table__.name
    with app.app_context():
        existing = {col["name"] for col in inspect(db.engine).get_columns(table)}
        if "teacher_salary" in existing:
            print("ستون teacher_salary از قبل وجود دارد.")
        else:
            db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN teacher_salary INTEGER"))
            db.session.commit()
            print("ستون teacher_salary اضافه شد.")


if __name__ == "__main__":
    main()
