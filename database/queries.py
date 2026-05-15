from database.db import get_db


def insert_expense(user_id, amount, category, date, description):
    db = get_db()
    db.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description)"
        " VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, category, date, description),
    )
    db.commit()
    db.close()
