from flask import Flask,render_template,redirect,request,flash,make_response,jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import os

app=Flask(__name__)
CORS(app)
app.app_context().push()
basedir=os.path.abspath(os.path.dirname(__file__)+"/instance/")
app.config['SECRET_KEY']='jhvhijghlkbvhjvjkjhvcj'
app.config['SQLALCHEMY_DATABASE_URI']='sqlite:///'+os.path.join(basedir,'pajohesh_database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db=SQLAlchemy(app)



class Books(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    book_title = db.Column(db.Text)
    author_translator = db.Column(db.Text)
    congress_number = db.Column(db.Text)
    shelf_number = db.Column(db.Text)
    row_number = db.Column(db.Text)
    comprehensive = db.Column(db.Boolean , default=False)
    borrower_code = db.Column(db.Text , default="None")
    available=db.Column(db.Boolean , default=False)
    borrow_count = db.Column(db.Integer, default=0)
    def __repr__(self):
        return f'Books({self.id},{self.book_title},{self.author_translator},{self.congress_number},{self.shelf_number},{self.row_number},{self.brrower_code},{self.borrow_count})'


class Admins(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    first_name = db.Column(db.Text)
    last_name = db.Column(db.Text)
    user_name = db.Column(db.Text)
    password = db.Column(db.Text)
    god_user=db.Column(db.Boolean , default=False)



    def __repr__(self):
        return f'Admins({self.id},{self.first_name},{self.last_name},{self.user_name},{self.password})'


class Actions(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    actions_taken = db.Column(db.Text)
    date = db.Column(db.Text)
    time = db.Column(db.Text)


    def __repr__(self):
        return f'Actions({self.id},{self.actions_taken},{self.date},{self.time})'

class Students(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    first_name = db.Column(db.Text)
    last_name = db.Column(db.Text)
    national_id_code = db.Column(db.Text)
    student_id_code = db.Column(db.Text)
    phone_number = db.Column(db.Text)
    phone_number_two = db.Column(db.Text)
    father_name = db.Column(db.Text)
    birthday = db.Column(db.Text)
    school_name = db.Column(db.Text)
    borrowing_capacity = db.Column(db.Integer)
    registration_date = db.Column(db.Text)
    expiration_date = db.Column(db.Text)
    address = db.Column(db.Text)
    opportunity = db.Column(db.Integer)
    expired=db.Column(db.Boolean , default=False)


    def __repr__(self):
        return f'Students({self.id},{self.first_name},{self.last_name},{self.national_id_code},{self.student_id_code},{self.phone_number},{self.borrowing_capacity},{self.registration_date},{self.expiration_date},{self.address},{self.opportunity})'



class Borrowing(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    student_id_code_borrow = db.Column(db.Text)
    book_id_borrow = db.Column(db.Text)
    date_of_borrowing = db.Column(db.Text)
    return_date = db.Column(db.Text)
    extension = db.Column(db.Boolean , default=False)
    late_penalty_applied = db.Column(db.Boolean, default=False)
   


    def __repr__(self):
        return f'Borrowing({self.id},{self.student_id_code_borrow},{self.book_id_borrow},{self.date_of_borrowing},{self.return_date})'





with app.app_context():
    db.create_all()

