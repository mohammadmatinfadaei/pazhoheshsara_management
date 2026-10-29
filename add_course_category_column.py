"""
افزودن ستون دسته‌بندی (category) به جدول دوره‌ها در دیتابیس موجود (بدون پاک شدن اطلاعات).

اجرا (قبل از اجرای نسخه‌ی جدید برنامه):  python add_course_category_column.py

کارهایی که انجام می‌دهد:
  1. از دیتابیس یک نسخه‌ی پشتیبان کنارش می‌سازد (…db.backup-تاریخ).
  2. اگر ستون category نبود، آن را به جدول courses اضافه می‌کند.
  3. همه‌ی دوره‌هایی که تا الان ثبت شده‌اند (و دسته‌بندی ندارند) را «موارد دیگر» می‌کند.
اگر دوباره اجرا شود، دسته‌بندی دوره‌هایی که قبلاً تعیین شده است تغییر نمی‌کند.

دسته‌بندی‌های مجاز: رباتیک - الکترونیک - پایتون - اسکرچ - علوم پایه - موارد دیگر
بعد از اجرا، از «ویرایش دوره» می‌توانید دسته‌ی هر دوره را عوض کنید.
"""
import os
import shutil
import sqlite3
import sys
from datetime import datetime

DEFAULT_CATEGORY = "موارد دیگر"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "instance", "pajoheshsara_management_database.db")


def main(db_path=DB_PATH):
    if not os.path.exists(db_path):
        print(f"فایل دیتابیس پیدا نشد: {db_path}")
        return 1

    backup = f"{db_path}.backup-{datetime.now():%Y%m%d-%H%M%S}"
    counter = 1
    while os.path.exists(backup):  # اجرای دوباره در همان ثانیه، پشتیبان قبلی را بازنویسی نکند
        counter += 1
        backup = f"{db_path}.backup-{datetime.now():%Y%m%d-%H%M%S}-{counter}"
    shutil.copy2(db_path, backup)
    print(f"نسخه‌ی پشتیبان ساخته شد: {backup}")

    conn = sqlite3.connect(db_path)
    try:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(courses)")}
        if not columns:
            print("جدول courses پیدا نشد؛ ابتدا یک بار برنامه را اجرا کنید تا جدول‌ها ساخته شوند.")
            return 1

        if "category" in columns:
            print("ستون category از قبل وجود دارد.")
        else:
            conn.execute("ALTER TABLE courses ADD COLUMN category TEXT")
            print("ستون category اضافه شد.")

        cursor = conn.execute(
            "UPDATE courses SET category = ? WHERE category IS NULL OR TRIM(category) = ''",
            (DEFAULT_CATEGORY,))
        conn.commit()
        print(f"دسته‌بندی {cursor.rowcount} دوره «{DEFAULT_CATEGORY}» شد.")

        total = conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0]
        print(f"تعداد کل دوره‌ها: {total}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    # اختیاری: مسیر دیتابیس دیگر را به‌عنوان آرگومان بدهید
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else DB_PATH))
