"""
ساخت «ادمین کل» (مدیر آموزشگاه، is_god) از طریق ترمینال:   python create_god.py

فقط یک نفر می‌تواند ادمین کل باشد (دیتابیس دوتا را رد می‌کند). این اسکریپت:
  - اگر ادمین کل از قبل هست، فقط اسمش را نشان می‌دهد و تغییری نمی‌دهد.
  - اگر کد پرسنلی واردشده مال یک ادمین موجود است، همان را ادمین کل می‌کند (رمزش عوض نمی‌شود).
  - در غیر این صورت یک ادمین جدید با همین نقش می‌سازد.
ادمین کل از صفحه‌ی ورود «کارمند» و با کد پرسنلی وارد می‌شود و منوی «اعمال کاربران» را می‌بیند.

اختیاری: مسیر دیتابیس دیگر را به‌عنوان آرگومان بدهید:  python create_god.py مسیر/فایل.db
"""
import getpass
import os
import re
import sqlite3
import sys

from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "instance", "pajoheshsara_management_database.db")

# ارقام فارسی/عربی را هنگام تایپ به انگلیسی تبدیل می‌کند
DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def ask(prompt):
    return input(prompt).strip().translate(DIGITS)


def password_error(password, confirm):
    """همان قاعده‌ی رمز در ثبت‌نام برنامه"""
    if len(password) < 8:
        return "رمز عبور باید حداقل ۸ کاراکتر باشد."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "رمز عبور باید شامل حروف انگلیسی و عدد باشد."
    if password != confirm:
        return "رمز عبور و تکرار آن یکسان نیست."
    return None


def main(db_path=DB_PATH):
    if not os.path.exists(db_path):
        print(f"فایل دیتابیس پیدا نشد: {db_path}")
        return 1

    conn = sqlite3.connect(db_path)
    try:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'admins'").fetchone():
            print("جدول admins پیدا نشد؛ ابتدا یک بار برنامه را اجرا کنید تا جدول‌ها ساخته شوند.")
            return 1

        god = conn.execute("SELECT first_name, last_name, personnel_code FROM admins "
                           "WHERE is_god = 1").fetchone()
        if god:
            print(f"ادمین کل از قبل وجود دارد: {god[0] or ''} {god[1] or ''} (کد پرسنلی {god[2]}).")
            print("فقط یک نفر می‌تواند ادمین کل باشد؛ تغییری داده نشد.")
            return 1

        personnel_code = ask("کد پرسنلی: ")
        if not re.fullmatch(r"\d{3,20}", personnel_code):
            print("کد پرسنلی باید فقط عدد (۳ تا ۲۰ رقم) باشد.")
            return 1

        existing = conn.execute("SELECT id, first_name, last_name FROM admins "
                                "WHERE personnel_code = ?", (personnel_code,)).fetchone()
        if existing:
            print(f"این کد پرسنلی مال «{existing[1] or ''} {existing[2] or ''}» است.")
            if ask("همین ادمین، ادمین کل شود؟ (y/n): ").lower() != "y":
                print("لغو شد.")
                return 1
            conn.execute("UPDATE admins SET is_god = 1 WHERE id = ?", (existing[0],))
            conn.commit()
            print("انجام شد؛ این ادمین از این پس ادمین کل است (رمزش تغییر نکرد).")
            return 0

        first_name = ask("نام: ")
        last_name = ask("نام خانوادگی: ")
        national_id = ask("کد ملی: ")
        if not first_name or not last_name or not national_id:
            print("نام، نام خانوادگی و کد ملی را وارد کنید.")
            return 1
        if conn.execute("SELECT 1 FROM admins WHERE national_id_number = ?", (national_id,)).fetchone():
            print("این کد ملی قبلاً برای یک ادمین ثبت شده است.")
            return 1

        password = getpass.getpass("رمز عبور: ")
        error = password_error(password, getpass.getpass("تکرار رمز عبور: "))
        if error:
            print(error)
            return 1

        conn.execute(
            "INSERT INTO admins (first_name, last_name, personnel_code, national_id_number, "
            "password, is_god) VALUES (?, ?, ?, ?, ?, 1)",
            (first_name, last_name, personnel_code, national_id, generate_password_hash(password)))
        conn.commit()
        print(f"ادمین کل ساخته شد: {first_name} {last_name} (کد پرسنلی {personnel_code}).")
        print("با «کارمند» + همین کد پرسنلی وارد شوید.")
        return 0
    except sqlite3.IntegrityError as error:
        conn.rollback()
        print(f"ثبت انجام نشد (تکراری یا نامعتبر): {error}")
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else DB_PATH))
