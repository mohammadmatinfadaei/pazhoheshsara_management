import openpyxl

from database import app, db, Books,Admins


# ==========================================
# # باز کردن فایل Excel
# # ==========================================

# workbook = openpyxl.load_workbook("Books.xlsx")

# # گرفتن اولین Sheet
# sheet = workbook.active


# # ==========================================
# # ورود اطلاعات به دیتابیس
# # ==========================================

# with app.app_context():

#     # از ردیف دوم شروع می‌کنیم
#     # چون ردیف اول عنوان ستون‌هاست

#     for row in sheet.iter_rows(
#         min_row=2,
#         values_only=True
#     ):

#         # اگر ردیف کاملاً خالی بود
#         if not any(
#             value not in (None, "")
#             for value in row
#         ):
#             continue


#         # ==========================================
#         # اطلاعات Excel
#         # ==========================================

#         book_title = row[0]

#         author_translator = row[1]

#         congress_number = row[2]

#         shelf_number = row[3]

#         row_number = row[4]

#         comprehensive = row[5]

#         borrower_code = row[6]

#         available = row[7]


#         # ==========================================
#         # بررسی اطلاعات ضروری
#         # ==========================================

#         if not book_title or not author_translator:

#             continue


#         # ==========================================
#         # مقدار borrower_code
#         # ==========================================

#         if borrower_code in (None, ""):

#             borrower_code = "None"

#         else:

#             borrower_code = str(
#                 borrower_code
#             )


#         # ==========================================
#         # ساخت کتاب
#         # ==========================================

#         book = Books(

#             book_title=str(
#                 book_title
#             ),

#             author_translator=str(
#                 author_translator
#             ),

#             congress_number=(
#                 str(congress_number)
#                 if congress_number is not None
#                 else None
#             ),

#             shelf_number=(
#                 str(shelf_number)
#                 if shelf_number is not None
#                 else None
#             ),

#             row_number=(
#                 str(row_number)
#                 if row_number is not None
#                 else None
#             ),

#             comprehensive=(
#                 comprehensive
#                 if isinstance(comprehensive, bool)
#                 else str(comprehensive).lower()
#                 in ["true", "1", "بله", "مرجع"]
#             ),

#             borrower_code=borrower_code,

#             available=(
#                 available
#                 if isinstance(available, bool)
#                 else str(available).lower()
#                 in ["true", "1", "بله", "در دسترس"]
#             )
#         )


#         # اضافه کردن کتاب به دیتابیس

#         db.session.add(book)


#     # ==========================================
#     # ذخیره اطلاعات
#     # ==========================================

#     db.session.commit()


# print(
#     "تمام کتاب‌ها با موفقیت وارد دیتابیس شدند."
# )

admin = Admins(user_name="amin1234", password="amin1234",last_name="کتابخانه",first_name="مدیر",god_user=True)
db.session.add(admin)
db.session.commit()