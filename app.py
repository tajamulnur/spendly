from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, session, redirect, url_for
from functools import wraps
from werkzeug.security import check_password_hash, generate_password_hash
from database.db import get_db, init_db, seed_db

app = Flask(__name__)
app.secret_key = "spendly-secret-key-change-in-production"

CATEGORY_ICONS = {
    "Food": "🍽️",
    "Transport": "🚌",
    "Bills": "🏠",
    "Health": "💊",
    "Entertainment": "🎬",
    "Shopping": "🛍️",
    "Other": "📦",
}

ALL_TIME_FROM = "2000-01-01"
ALL_TIME_TO   = "2999-12-31"
VALID_PERIODS = {"this_month", "last_month", "last_3_months", "all_time"}


def resolve_date_filter(args, today):
    if args.get("from") and args.get("to"):
        try:
            datetime.strptime(args["from"], "%Y-%m-%d")
            datetime.strptime(args["to"], "%Y-%m-%d")
            date_from, date_to = args["from"], args["to"]
            active_period = "custom"
        except ValueError:
            date_from, date_to = ALL_TIME_FROM, ALL_TIME_TO
            active_period = "all_time"
    else:
        period = args.get("period", "all_time")
        if period not in VALID_PERIODS:
            period = "all_time"
        if period == "this_month":
            date_from = today.replace(day=1).isoformat()
            date_to   = today.isoformat()
        elif period == "last_month":
            first_of_this = today.replace(day=1)
            last_of_prev  = first_of_this - timedelta(days=1)
            date_from     = last_of_prev.replace(day=1).isoformat()
            date_to       = last_of_prev.isoformat()
        elif period == "last_3_months":
            date_from = (today - timedelta(days=90)).isoformat()
            date_to   = today.isoformat()
        else:
            date_from, date_to = ALL_TIME_FROM, ALL_TIME_TO
        active_period = period

    if active_period == "all_time":
        showing_label = "All time"
        input_from = input_to = ""
    else:
        showing_label = (
            datetime.strptime(date_from, "%Y-%m-%d").strftime("%b %-d, %Y")
            + " – "
            + datetime.strptime(date_to, "%Y-%m-%d").strftime("%b %-d, %Y")
        )
        input_from, input_to = date_from, date_to

    return date_from, date_to, active_period, showing_label, input_from, input_to


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name     = request.form["name"]
        email    = request.form["email"]
        password = request.form["password"]

        db = get_db()
        existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            db.close()
            return render_template("register.html", error="An account with that email already exists.")

        db.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, generate_password_hash(password)),
        )
        db.commit()
        user = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        db.close()

        session["user_id"] = user["id"]
        return redirect(url_for("profile"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email    = request.form["email"]
        password = request.form["password"]

        db   = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
        db.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            return redirect(url_for("profile"))

        return render_template("login.html", error="Invalid email or password.")

    return render_template("login.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/profile")
@login_required
def profile():
    date_from, date_to, active_period, showing_label, input_from, input_to = \
        resolve_date_filter(request.args, date.today())

    db = get_db()
    uid = session["user_id"]

    row = db.execute(
        "SELECT name, email, created_at FROM users WHERE id = ?", (uid,)
    ).fetchone()
    words = row["name"].split()
    initials = (words[0][0] + (words[-1][0] if len(words) > 1 else "")).upper()
    member_since = datetime.strptime(row["created_at"][:10], "%Y-%m-%d").strftime("%B %Y")
    user = {
        "name": row["name"],
        "email": row["email"],
        "initials": initials,
        "member_since": member_since,
    }

    agg = db.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS cnt "
        "FROM expenses WHERE user_id = ? AND date BETWEEN ? AND ?",
        (uid, date_from, date_to)
    ).fetchone()
    top = db.execute(
        "SELECT category FROM expenses WHERE user_id = ? AND date BETWEEN ? AND ? "
        "GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
        (uid, date_from, date_to)
    ).fetchone()
    stats = {
        "total_spent": f"₹{agg['total']:.2f}",
        "transaction_count": agg["cnt"],
        "top_category": top["category"] if top else "—",
    }

    rows = db.execute(
        "SELECT date, description, category, amount FROM expenses "
        "WHERE user_id = ? AND date BETWEEN ? AND ? ORDER BY date DESC LIMIT 5",
        (uid, date_from, date_to)
    ).fetchall()
    transactions = [
        {
            "date": datetime.strptime(r["date"], "%Y-%m-%d").strftime("%b %d, %Y"),
            "description": r["description"] or "",
            "category": r["category"],
            "amount": f"₹{r['amount']:.2f}",
        }
        for r in rows
    ]

    cat_rows = db.execute(
        "SELECT category, SUM(amount) AS total FROM expenses "
        "WHERE user_id = ? AND date BETWEEN ? AND ? GROUP BY category ORDER BY total DESC",
        (uid, date_from, date_to)
    ).fetchall()
    categories = [
        {
            "name": c["category"],
            "total": f"₹{c['total']:.2f}",
            "icon": CATEGORY_ICONS.get(c["category"], "📦"),
        }
        for c in cat_rows
    ]

    db.close()
    return render_template("profile.html",
                           user=user,
                           stats=stats,
                           transactions=transactions,
                           categories=categories,
                           active_period=active_period,
                           input_from=input_from,
                           input_to=input_to,
                           showing_label=showing_label)


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


with app.app_context():
    init_db()
    seed_db()


if __name__ == "__main__":
    app.run(debug=True, port=5001)
