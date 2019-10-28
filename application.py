import os
import hashlib
import json
import requests
from flask import Flask, session, render_template, request, url_for, redirect, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))


@app.route("/")
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    else:
        datas = db.execute("SELECT * FROM books ORDER BY RANDOM() LIMIT 12").fetchall()
        return render_template('index.html', username=session['username'], datas=datas)


@app.route("/book/<string:isbn>")
def book(isbn):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    else:
        data = db.execute("SELECT * FROM books WHERE isbn=:isbn", {"isbn": isbn}).first()
        userid = session['userid']
        review = db.execute("SELECT * FROM review WHERE isbn=:isbn AND userid=:userid", {"isbn": isbn, "userid": userid}).fetchone()
        reviews = db.execute("SELECT * FROM review INNER JOIN users ON review.userid = users.id WHERE isbn=:isbn", {"isbn": isbn}).fetchall()
        res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "A22EOp7E8d1c4Y1WqJM3Tg", "isbns": isbn})
        ratings = json.dumps(res.json())
        ratings = json.loads(ratings)
        return render_template('book.html', ratings=ratings, data=data, userid=session['userid'], review=review, reviews=reviews)


@app.route("/api/<string:isbn>")
def api(isbn):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    else:
        data = db.execute("SELECT * FROM books WHERE isbn=:isbn", {"isbn": isbn}).fetchone()
        res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "A22EOp7E8d1c4Y1WqJM3Tg", "isbns": isbn})
        ratings = json.dumps(res.json())
        if data is None:
            return render_template("error.html", message="The ISBN you have entred is wrong, try again..")
        else:
            ratings = json.loads(ratings)
            for rating in ratings['books']:
                review_count = rating['reviews_count']
                average_score = rating['average_rating']

            return jsonify(title=data.title, author=data.author, year=data.year, isbn=data.isbn,review_count=review_count,average_score=average_score)


@app.route("/rate", methods=["POST"])
def rate():
    if request.method == "POST":
        review = request.form.get("review")
        rating = request.form.get("rating")
        isbn = request.form.get("isbn")
        userid = session['userid']
        db.execute("INSERT INTO review (review, isbn, userid, rating) VALUES (:review, :isbn, :userid, :rating)", {"review": review, "isbn": isbn, "userid": userid, "rating": rating})
        db.commit()
        return redirect(url_for('book', isbn=isbn))
    else:
        return redirect(url_for('index'))


@app.route("/search", methods=["POST", "GET"])
def search():
    data= ""
    if request.method == "POST":
        text = request.form.get("query")
        if text:
            data = db.execute("SELECT * FROM books WHERE LOWER(isbn) LIKE LOWER('%"+text+"%') OR LOWER(title) LIKE LOWER('%"+text+"%') OR LOWER(author) LIKE LOWER('%"+text+"%')").fetchall()
        else:
            data=""
        return json.dumps({"results": [dict(row) for row in data]})



#    return json.dumps({"results":result})


@app.route("/login", methods=["POST", "GET"])
def login():
    error = ""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        password = hashlib.md5(password.encode()).hexdigest()
        match = db.execute("SELECT * FROM users WHERE username = :username AND password = :password", {"username": username, "password": password}).fetchone()
        if match is None:
            error = "Username or/and Password aren't correct, try again"
        else:
            session['logged_in'] = True
            session['username'] = username
            session['userid'] = match.id
    if not session.get('logged_in'):
        return render_template("login.html", error=error)
    else:
        return redirect(url_for('index'))

@app.route("/register", methods=["POST", "GET"])
def register():
    error=""
    if request.method == "POST":
        fullname = request.form.get("fullname")
        username = request.form.get("username")
        password = request.form.get("password")
        cpassword = request.form.get("cpassword")
        if password != cpassword:
            error = "Passwords aren't same"
        else:
            existence = db.execute("SELECT * FROM users WHERE username = :username", {"username": username}).fetchone()
            if existence is None:
                password = hashlib.md5(password.encode()).hexdigest()
                db.execute("INSERT INTO users (fullname, username, password) VALUES (:fullname, :username, :password)", {"fullname": fullname, "username": username, "password": password})
                userid = db.execute("SELECT * FROM users WHERE username = :username", {"username": username}).fetchone()
                db.commit()
                session['logged_in'] = True
                session['username'] = username
                session['userid'] = userid.id
            else:
                error = "A user with same username already exist"
    if not session.get('logged_in'):
        return render_template("register.html", error=error)
    else:
        return redirect(url_for('index'))


@app.route("/logout")
def logout():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    else:
        session['logged_in'] = False
        session['username'] = ""
        return redirect(url_for('login'))
