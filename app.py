# import necessary tools/packages for this to run properly
import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps

# make Flask app
app = Flask(__name__)

# means don't have to restart server to update HTML changes
app.config["TEMPLATES_AUTO_RELOAD"] = True

# makes sessions not pernament and info stored locally
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# connect to bloom database
db = SQL("sqlite:///bloom.db")

# allows us to force user to be logged in for certain routes
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

# route for homepage: serves up index.html by default
@app.route("/")
@login_required
def index():
    return render_template("index.html")

# route for users to register: if do something wrong, serves up register
# page again with line of text telling them their error
@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":

        username = request.form.get("username")

        # error handling:
        if not username:
            return render_template("register.html", error="please enter a username :)")

        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if not password or not confirmation:
            return render_template("register.html", error="please fill out both password fields :)")

        if password != confirmation:
            return render_template("register.html", error="please make sure passwords match :)")

        # insert into table if unique username
        try:
            db.execute("INSERT INTO users (username, hash) VALUES(?, ?)",
                       username, generate_password_hash(password))
        except ValueError:
            return render_template("register.html", error="sorry, this username is already taken!")

        return redirect("/login")

    else:
        return render_template("register.html")
