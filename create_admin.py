"""ساخت ادمین اولیه از طریق ترمینال:  python create_admin.py"""
import getpass
import re

from werkzeug.security import generate_password_hash

from models import Admins, app, db


def main():
    first_name = input("نام: ").strip()
    last_name = input("نام خانوادگی: ").strip()
    personnel_code = input("کد پرسنلی: ").strip()
    national_id = input("کد ملی: ").strip()

    if not re.fullmatch(r"\d{3,20}", personnel_code):
        print("کد پرسنلی باید فقط عدد باشد.")
        return
    if not national_id:
        print("کد ملی را وارد کنید.")
        return

    password = getpass.getpass("رمز عبور: ")
    confirm = getpass.getpass("تکرار رمز عبور: ")
    if len(password) < 8 or password != confirm:
        print("رمز عبور حداقل ۸ کاراکتر و باید با تکرارش یکسان باشد.")
        return

    with app.app_context():
        if Admins.query.filter_by(personnel_code=personnel_code).first():
            print("این کد پرسنلی قبلاً ثبت شده است.")
            return
        db.session.add(Admins(
            first_name=first_name,
            last_name=last_name,
            personnel_code=personnel_code,
            national_id_number=national_id,
            password=generate_password_hash(password),
        ))
        db.session.commit()
        print("ادمین ساخته شد.")


if __name__ == "__main__":
    main()
