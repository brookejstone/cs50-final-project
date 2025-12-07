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
def index():
    # if logged in, have personalized homepage saying hello to them
    if "user_id" in session:
        # get user's name from database using user id
        user = db.execute("SELECT name FROM users WHERE id = ?", session["user_id"])
        # in case somehow got around giving us a name
        name = user[0]["name"] if user else "friend"
        return render_template("index.html", name=name, logged_in=True)
    # if not logged in, just have basic homepage saying welcome to Bloom hub
    else:
        return render_template("index.html", logged_in=False)

@app.route("/activities", methods=["GET"])
@login_required
def activities():
    # getting info for daily log cards: same as other pages with the daily cards
    logs = db.execute(
        """
        SELECT 
            DATE(log_date) AS raw_date, 
            strftime('%Y-%m-%d', log_date) AS day, 
            activity_name, 
            total_minutes, 
            enjoyment, 
            reflection 
        FROM activities_log 
        WHERE user_id = ? 
        ORDER BY log_date DESC
        """, 
        session["user_id"]
    )

    # same as the other day cards pages: sort entries by days
    days = []
    logged_days = {}

    for log in logs:
        raw = log["raw_date"]

        if raw not in logged_days:
            logged_days[raw] = {
                "raw_date": raw,
                "day": log["day"],
                "entries": []
            }
            days.append(logged_days[raw])

        # convert total_minutes from table into hours and minutes
        total = log["total_minutes"]
        hours = total // 60
        minutes = total % 60

        # format time strings depending on hour/min values
        if hours > 0 and minutes > 0:
            duration = f"{hours}h {minutes}m"
        elif hours > 0:
            duration = f"{hours}h"
        else:
            duration = f"{minutes}m"

        # add entries
        logged_days[raw]["entries"].append({
            "name": log["activity_name"],
            "duration": duration,
            "enjoyment": log["enjoyment"],
            "reflection": log["reflection"]
        })

    # activity bank: recommended list coming from us(popular effective mindfulness activities)
    recommended = [
        "10-minute stretch session",
        "phone-free walk outside",
        "guided meditation",
        "reading for pleasure",
        "journaling",
        "calling a friend",
        "slow yoga flow",
        "drawing / doodling",
        "making tea and savoring it"
    ]

    # second part of activity bank: user’s own unique past activities taken from activities_log table
    user_activities_rows = db.execute(
        "SELECT DISTINCT activity_name FROM activities_log WHERE user_id = ? ORDER BY activity_name",
        session["user_id"]
    )
    user_activities = [row["activity_name"] for row in user_activities_rows]

    # show activities page
    return render_template("activities.html", days=days, recommended=recommended, user_activities=user_activities)

@app.route("/activities/log", methods=["GET", "POST"])
@login_required
def activities_log():
    # collect input from form if found this route by post
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()

        hours_raw = request.form.get("hours", "0")
        minutes_raw = request.form.get("minutes", "0")

        enjoyment_raw = (request.form.get("enjoyment") or "").strip()
        reflection = (request.form.get("reflection") or "").strip()

        # basic validation: need a name
        if not name:
            error = "you forgot to give your activity a name!"
            return render_template(
                "activitieslog.html",
                error=error,
                name=name,
                selected_hours=hours_raw,
                selected_minutes=minutes_raw,
                enjoyment_value=enjoyment_raw,
                reflection=reflection
            )

        # validate that hours and minutes are valid numbers
        try:
            hours = int(hours_raw)
            minutes = int(minutes_raw)
        except ValueError:
            error = "please input how long the activity took- guesses are ok!"
            return render_template(
                "activitieslog.html",
                error=error,
                name=name,
                selected_hours=hours_raw,
                selected_minutes=minutes_raw,
                enjoyment_value=enjoyment_raw,
                reflection=reflection
            )

        if hours == 0 and minutes == 0:
            error = "please have a value greater than zero for total time spent!"
            return render_template(
                "activitieslog.html",
                error=error,
                name=name,
                selected_hours=hours_raw,
                selected_minutes=minutes_raw,
                enjoyment_value=enjoyment_raw,
                reflection=reflection
            )

        # turn input into form that's easier to put in our activities_log table
        total_minutes = hours * 60 + minutes

        # checking for errors with enjoyment
        enjoyment = None
        if enjoyment_raw:
            # seeing if valid number that can be written with decimal
            try:
                enjoyment_val = float(enjoyment_raw)
            except ValueError:
                error = "please give a number between 0 and 10 for enjoyment!"
                return render_template(
                    "activitieslog.html",
                    error=error,
                    name=name,
                    selected_hours=hours_raw,
                    selected_minutes=minutes_raw,
                    enjoyment_value=enjoyment_raw,
                    reflection=reflection
                )
            # making sure number between 0 and 10
            if enjoyment_val < 0 or enjoyment_val > 10:
                error = "enjoyment value should be between 0 and 10!"
                return render_template(
                    "activitieslog.html",
                    error=error,
                    name=name,
                    selected_hours=hours_raw,
                    selected_minutes=minutes_raw,
                    enjoyment_value=enjoyment_raw,
                    reflection=reflection
                )
            # if passes tests, convert enjoyment to number with 1 decimal place
            enjoyment = round(enjoyment_val, 1)

        if not reflection:
            reflection = "no reflection for today!"

        # put entry into activities_log table to be able to show daily activities cards
        db.execute(
            "INSERT INTO activities_log (user_id, activity_name, total_minutes, enjoyment, reflection) VALUES (?, ?, ?, ?, ?)",
            session["user_id"],
            name.lower(),
            total_minutes,
            enjoyment,
            reflection
        )

        # give notification if logged in successfully
        flash("activity logged!")
        return redirect("/activities")

    # if got here through GET: serve up the log form
    return render_template("activitieslog.html")

# route for users to login: mostly taken from finance
@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return render_template("login.html", error="please fill out username field :)")

        # Ensure password was submitted
        elif not request.form.get("password"):
            return render_template("login.html", error="please fill out both password fields :)")

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return render_template("login.html", error="invalid username and/or password!")

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        flash("login successful!")
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

# lets user log out
@app.route("/logout", methods=["GET", "POST"])
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")

# route for users to be able to log moods and see their history for moods
@app.route("/mood", methods=["GET"])
@login_required
def mood():
    # get list of mood entry dictionaries to use for showing history
    # strftime helps me format the date that we get back from the table
    logs = db.execute(
        """
        SELECT 
            DATE(mood_log.log_date) AS raw_date,
            strftime('%Y-%m-%d', mood_log.log_date) AS day, 
            strftime('%H:%M', mood_log.log_date) AS time, 
            moods.mood, 
            moods.vibe, 
            mood_log.cause 
        FROM moods 
        JOIN mood_log 
        ON mood_log.mood_id = moods.id
        WHERE mood_log.user_id = ? 
        ORDER BY mood_log.log_date DESC
        """, 
        session["user_id"]
    )
    

    # sort entries by day in days, keep track of which ones already in list using logged_days
    days = []
    logged_days = {}

    # iterate through logs, if a new day then add day with info, if not new day just add info to day
    for log in logs:
        raw = log["raw_date"]
        if raw not in logged_days:
            logged_days[raw] = {
                "raw_date": raw,
                "day": log["day"],
                "entries": []
            }
            days.append(logged_days[raw])
        # add details from entry to day
        logged_days[raw]["entries"].append({
            "time": log["time"],       
            "mood": log["mood"],
            "vibe": log["vibe"],
            "cause": log["cause"]
        })
    return render_template("mood.html", days=days)


@app.route("/mood/log", methods=["GET", "POST"])
@login_required
def moodlog():    
    if request.method == "POST":
        # strip() gets rid of unnecessary characters so just have letters typed
        # get response for the mood field
        custom = (request.form.get("custom_mood") or "").strip()
        selected = request.form.get("mood_select")

        # if user chose to answer with custom mood
        if custom:
            mood_label = custom.lower()
            vibe = "personal"
            # insert new mood into table if it doesn't exist in table for that user yet
            db.execute(
                "INSERT OR IGNORE INTO moods (user_id, mood, vibe) VALUES (?, ?, ?)",
                session["user_id"],
                mood_label,
                vibe,
            )
        # if user just selected from dropdown
        elif selected:
            mood_label = selected

        # error if no mood given:
        else:
            return render_template("moodlog.html", error="you forgot to enter your mood!")
        
        # get cause from form- okay if nothing
        cause = (request.form.get("cause") or "").strip()

        # get id of mood just inserted into moods for insertion into the mood_log table
        row = db.execute("SELECT id FROM moods WHERE (user_id=? OR user_id IS NULL) AND mood=? ORDER BY user_id DESC LIMIT 1", 
                         session["user_id"], mood_label)
        mood_id = row[0]["id"]
        
        # add mood entry into mood_log table
        db.execute("INSERT INTO mood_log (user_id, mood_id, cause) VALUES(?,?,?)",
                    session["user_id"], mood_id, cause)
        
        # give popup that successfully logged
        flash("mood logged!")
        return redirect("/mood")

    else:
        # getting moods with their vibes to create dropdown in moodlog html
        moods = db.execute(
            "SELECT mood, vibe FROM moods WHERE user_id IS NULL OR user_id = ? ORDER BY vibe, mood",
            session["user_id"]
        )

        # create dictionary where key is the vibe and value is a list of moods 
        # underneath that vibe- for dropdown in moodlog
        moods_by_vibe = {}
        for mood in moods:
            vibe = mood["vibe"]
            # this sees if a new vibe- if so, creates new empty list for that to append to, if not just
            # appends to preexisting list
            moods_by_vibe.setdefault(vibe, []).append(mood["mood"])

        # send the moods to the moodlog template for users to be able to create new entry using menu
        return render_template("moodlog.html", moodlist=moods_by_vibe)


# route for users to register: if do something wrong, serves up register
# page again with line of text telling them their error- mostly taken from finance
@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":

        username = request.form.get("username")

        # error if no username typed in:
        if not username:
            return render_template("register.html", error="please enter a username :)")

        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # error for no password/confirmation typed
        if not password or not confirmation:
            return render_template("register.html", error="please fill out both password fields :)")

        # error if passwords don't match
        if password != confirmation:
            return render_template("register.html", error="please make sure passwords match :)")
        
        name = request.form.get("name")

        # error if don't give us their name
        if not name:
            return render_template("register.html", error="you forgot to tell us your name :)")


        # insert into table if unique username
        try:
            db.execute("INSERT INTO users (username, hash, name) VALUES(?, ?, ?)",
                       username, generate_password_hash(password), name)
        # give error if username not unique
        except ValueError:
            return render_template("register.html", error="sorry, this username is already taken!")
        # if successful brings them to login & gives alert of success
        flash("welcome to bloom hub!")
        return redirect("/login")

    else:
        # if just got to page and not from filling out form
        return render_template("register.html")
    
@app.route("/sleep", methods=["GET"])
@login_required
def sleep():
    # get list of logs & do essentially same code as for mood but for sleep
    logs = db.execute(
        """
        SELECT 
            DATE(log_date) AS raw_date, 
            strftime('%Y-%m-%d', log_date) AS day,
            strftime('%H:%M', log_date) AS time,
            total_minutes,
            feeling,
            reflection
        FROM sleep_log
        WHERE user_id = ?
        ORDER BY log_date DESC
        """, 
        session["user_id"]
    )

    days = []
    logged_days = {}

    for log in logs:
        raw = log["raw_date"]

        if raw not in logged_days:
            logged_days[raw] = {
                "raw_date": raw,
                "day": log["day"],
                "entries": []
            }
            days.append(logged_days[raw])

        # convert total_minutes into hours and minutes
        total = log["total_minutes"]
        hours = total // 60
        minutes = total % 60

        # create formatted string for sleep time display in daily cards
        if hours > 0 and minutes > 0:
            sleep_str = f"{hours}h {minutes}m"
        elif hours > 0:
            sleep_str = f"{hours}h"
        else:
            sleep_str = f"{minutes}m"

        logged_days[raw]["entries"].append({
            "time": log["time"], 
            "sleep_str": sleep_str,
            "feeling": log["feeling"],
            "reflection": log["reflection"]
        })

    return render_template("sleep.html", days=days)

    

@app.route("/sleep/log", methods=["GET", "POST"])
@login_required
def sleeplog(): 

    # feelings for the dropdown menu
    feelings = [
        "groggy",
        "tired",
        "okay",
        "rested",
        "energized"
    ]

    # if came from filling out form, save input or autofill to avoid crashes
    if request.method == "POST":
        hours_raw = request.form.get("hours", "0")
        minutes_raw = request.form.get("minutes", "0")
        feeling = request.form.get("feeling") or ""
        reflection = (request.form.get("reflection") or "").strip()

        # make sure that inputted numbers we can handle for hours and minutes
        try:
            hours = int(hours_raw)
            minutes = int(minutes_raw)
        except ValueError:
            error = "please choose how many hours and minutes you slept."
            return render_template(
                "sleeplog.html",
                feelings=feelings,
                error=error,
                selected_hours=hours_raw,
                selected_minutes=minutes_raw,
                selected_feeling=feeling,
                reflection=reflection
            )
        
        # make sure not inputting no sleep at all
        if hours == 0 and minutes == 0:
            error = "please input a nonzero amount of sleep!"
            return render_template(
                "sleeplog.html",
                feelings=feelings,
                error=error,
                selected_hours=hours_raw,
                selected_minutes=minutes_raw,
                selected_feeling=feeling,
                reflection=reflection
            )
        
        # convert hours & minutes to total minutes to put into sleep_log
        total_minutes = hours * 60 + minutes

        # allow empty reflection and feeling
        if not reflection:
            reflection = "no reflection for today!"

        if not feeling:
            feeling = "no feeling input for today!"

        # if have gotten this far, add entry to sleep_log table
        db.execute(
            "INSERT INTO sleep_log (user_id, total_minutes, feeling, reflection) VALUES (?, ?, ?, ?)",
            session["user_id"],
            total_minutes,
            feeling,
            reflection
        )

        # send message that successfully logged
        flash("sleep logged!")
        return redirect("/sleep")
    
    # if got here through get:
    return render_template("sleeplog.html", feelings=feelings)