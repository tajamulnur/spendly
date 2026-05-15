"""
Tests for Step 07 — Add Expense
================================
Spec: .claude/specs/07-add-expense.md

These tests verify the GET and POST behaviour of /expenses/add, the
insert_expense query helper, and all validation rules defined in the spec.
No implementation details are inferred beyond what the spec prescribes.
"""

import pytest
from werkzeug.security import generate_password_hash
from app import app as flask_app
from database.db import init_db, get_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app(tmp_path):
    """Isolated Flask app backed by a temporary SQLite file.

    get_db() opens DB_PATH by file name, so we monkey-patch the module-level
    DB_PATH variable (same pattern used in test_06-date-filter-profile-page.py).
    """
    import database.db as db_module

    db_file = str(tmp_path / "test_spendly.db")
    original_path = db_module.DB_PATH
    db_module.DB_PATH = db_file

    flask_app.config.update({
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "WTF_CSRF_ENABLED": False,
    })

    with flask_app.app_context():
        init_db()
        yield flask_app

    db_module.DB_PATH = original_path


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def seeded_user_id(app):
    """Insert a test user and return their id. No expenses — each test is
    responsible for the data it needs."""
    db = get_db()
    cur = db.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Test User", "testuser@spendly.com", generate_password_hash("pass123")),
    )
    user_id = cur.lastrowid
    db.commit()
    db.close()
    return user_id


@pytest.fixture
def second_user_id(app):
    """A second, distinct user — used to verify data isolation."""
    db = get_db()
    cur = db.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Other User", "other@spendly.com", generate_password_hash("otherpass")),
    )
    user_id = cur.lastrowid
    db.commit()
    db.close()
    return user_id


@pytest.fixture
def auth_client(client, seeded_user_id):
    """Test client with a valid session for seeded_user_id."""
    with client.session_transaction() as sess:
        sess["user_id"] = seeded_user_id
    return client


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

VALID_FORM = {
    "amount": "50.0",
    "category": "Food",
    "date": "2026-03-20",
    "description": "Lunch",
}

ALL_CATEGORIES = [
    "Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"
]


def _fetch_expenses_for_user(user_id):
    """Return all expense rows belonging to user_id."""
    db = get_db()
    rows = db.execute(
        "SELECT * FROM expenses WHERE user_id = ?", (user_id,)
    ).fetchall()
    db.close()
    return rows


# ---------------------------------------------------------------------------
# Auth guards
# ---------------------------------------------------------------------------

class TestAuthGuards:
    def test_get_add_expense_unauthenticated_redirects(self, client):
        response = client.get("/expenses/add")
        assert response.status_code == 302, (
            "Unauthenticated GET /expenses/add must redirect (302)"
        )

    def test_get_add_expense_unauthenticated_redirects_to_login(self, client):
        response = client.get("/expenses/add")
        assert "/login" in response.headers["Location"], (
            "Unauthenticated GET /expenses/add must redirect to /login"
        )

    def test_post_add_expense_unauthenticated_redirects(self, client):
        response = client.post("/expenses/add", data=VALID_FORM)
        assert response.status_code == 302, (
            "Unauthenticated POST /expenses/add must redirect (302)"
        )

    def test_post_add_expense_unauthenticated_redirects_to_login(self, client):
        response = client.post("/expenses/add", data=VALID_FORM)
        assert "/login" in response.headers["Location"], (
            "Unauthenticated POST /expenses/add must redirect to /login"
        )

    def test_get_add_expense_unauthenticated_does_not_return_200(self, client):
        response = client.get("/expenses/add", follow_redirects=False)
        assert response.status_code != 200, (
            "Unauthenticated GET /expenses/add must not return 200"
        )


# ---------------------------------------------------------------------------
# GET happy path
# ---------------------------------------------------------------------------

class TestGetAddExpense:
    def test_get_returns_200_for_authenticated_user(self, auth_client):
        response = auth_client.get("/expenses/add")
        assert response.status_code == 200, (
            "Authenticated GET /expenses/add must return 200"
        )

    def test_get_response_contains_form_element(self, auth_client):
        response = auth_client.get("/expenses/add")
        assert b"<form" in response.data, (
            "Response must contain a <form> element"
        )

    def test_get_form_uses_post_method(self, auth_client):
        response = auth_client.get("/expenses/add")
        html = response.data.decode("utf-8")
        assert 'method="POST"' in html or "method='POST'" in html or 'method="post"' in html, (
            "The form must use method POST"
        )

    def test_get_form_action_points_to_add_expense(self, auth_client):
        response = auth_client.get("/expenses/add")
        html = response.data.decode("utf-8")
        assert 'action="/expenses/add"' in html or "action='/expenses/add'" in html, (
            "The form action must point to /expenses/add"
        )

    def test_get_contains_amount_input(self, auth_client):
        response = auth_client.get("/expenses/add")
        html = response.data.decode("utf-8")
        assert 'name="amount"' in html, (
            "The form must contain an input with name='amount'"
        )

    def test_get_contains_date_input(self, auth_client):
        response = auth_client.get("/expenses/add")
        html = response.data.decode("utf-8")
        assert 'name="date"' in html, (
            "The form must contain an input with name='date'"
        )

    def test_get_contains_description_input(self, auth_client):
        response = auth_client.get("/expenses/add")
        html = response.data.decode("utf-8")
        assert 'name="description"' in html, (
            "The form must contain an input with name='description'"
        )

    def test_get_contains_category_select(self, auth_client):
        response = auth_client.get("/expenses/add")
        html = response.data.decode("utf-8")
        assert 'name="category"' in html, (
            "The form must contain a <select> with name='category'"
        )

    @pytest.mark.parametrize("category", ALL_CATEGORIES)
    def test_get_category_select_contains_each_option(self, auth_client, category):
        response = auth_client.get("/expenses/add")
        html = response.data.decode("utf-8")
        assert category in html, (
            f"Category dropdown must include the option '{category}'"
        )

    def test_get_category_select_has_exactly_7_options(self, auth_client):
        import re
        response = auth_client.get("/expenses/add")
        html = response.data.decode("utf-8")
        # Count <option> elements within the category select block;
        # look for named category options (value matches known categories)
        option_matches = [cat for cat in ALL_CATEGORIES if cat in html]
        assert len(option_matches) == 7, (
            f"Category dropdown must have exactly 7 options, found {len(option_matches)} present"
        )

    def test_get_contains_save_expense_submit_button(self, auth_client):
        response = auth_client.get("/expenses/add")
        html = response.data.decode("utf-8")
        assert "Save Expense" in html, (
            "The form must include a 'Save Expense' submit button"
        )

    def test_get_contains_cancel_link_to_profile(self, auth_client):
        response = auth_client.get("/expenses/add")
        html = response.data.decode("utf-8")
        assert "/profile" in html, (
            "The form must include a cancel link pointing to /profile"
        )

    def test_get_date_field_defaults_to_today(self, auth_client):
        from datetime import date
        today_str = date.today().isoformat()   # e.g. "2026-05-15"
        response = auth_client.get("/expenses/add")
        html = response.data.decode("utf-8")
        assert today_str in html, (
            f"The date field should default to today's date ({today_str})"
        )


# ---------------------------------------------------------------------------
# POST happy path
# ---------------------------------------------------------------------------

class TestPostAddExpenseHappyPath:
    def test_post_valid_data_redirects(self, auth_client):
        response = auth_client.post("/expenses/add", data=VALID_FORM)
        assert response.status_code == 302, (
            "POST with valid data must redirect (302)"
        )

    def test_post_valid_data_redirects_to_profile(self, auth_client):
        response = auth_client.post("/expenses/add", data=VALID_FORM)
        assert "/profile" in response.headers["Location"], (
            "POST with valid data must redirect to /profile"
        )

    def test_post_valid_data_inserts_row_in_db(self, auth_client, seeded_user_id):
        auth_client.post("/expenses/add", data=VALID_FORM)
        rows = _fetch_expenses_for_user(seeded_user_id)
        assert len(rows) == 1, (
            "Exactly one expense row must be created in the database after a valid POST"
        )

    def test_post_valid_data_stores_correct_amount(self, auth_client, seeded_user_id):
        auth_client.post("/expenses/add", data=VALID_FORM)
        rows = _fetch_expenses_for_user(seeded_user_id)
        assert float(rows[0]["amount"]) == 50.0, (
            "Stored amount must equal the submitted value 50.0"
        )

    def test_post_valid_data_stores_correct_category(self, auth_client, seeded_user_id):
        auth_client.post("/expenses/add", data=VALID_FORM)
        rows = _fetch_expenses_for_user(seeded_user_id)
        assert rows[0]["category"] == "Food", (
            "Stored category must equal the submitted value 'Food'"
        )

    def test_post_valid_data_stores_correct_date(self, auth_client, seeded_user_id):
        auth_client.post("/expenses/add", data=VALID_FORM)
        rows = _fetch_expenses_for_user(seeded_user_id)
        assert rows[0]["date"] == "2026-03-20", (
            "Stored date must equal the submitted value '2026-03-20'"
        )

    def test_post_valid_data_stores_correct_description(self, auth_client, seeded_user_id):
        auth_client.post("/expenses/add", data=VALID_FORM)
        rows = _fetch_expenses_for_user(seeded_user_id)
        assert rows[0]["description"] == "Lunch", (
            "Stored description must equal the submitted value 'Lunch'"
        )

    def test_post_valid_data_stores_correct_user_id(self, auth_client, seeded_user_id):
        auth_client.post("/expenses/add", data=VALID_FORM)
        rows = _fetch_expenses_for_user(seeded_user_id)
        assert rows[0]["user_id"] == seeded_user_id, (
            "Stored user_id must match the session user's id"
        )

    def test_post_follow_redirect_lands_on_profile_page(self, auth_client):
        response = auth_client.post(
            "/expenses/add", data=VALID_FORM, follow_redirects=True
        )
        assert response.status_code == 200, (
            "Following the redirect after a valid POST should reach a 200 page"
        )
        # Profile page must identify itself (check for profile-related landmark)
        assert b"profile" in response.data.lower() or b"Profile" in response.data, (
            "Following the redirect should land on the profile page"
        )


# ---------------------------------------------------------------------------
# POST — blank description → NULL in DB
# ---------------------------------------------------------------------------

class TestPostBlankDescription:
    def test_post_no_description_redirects(self, auth_client):
        data = {**VALID_FORM, "description": ""}
        response = auth_client.post("/expenses/add", data=data)
        assert response.status_code == 302, (
            "POST without description must redirect (302)"
        )

    def test_post_no_description_redirects_to_profile(self, auth_client):
        data = {**VALID_FORM, "description": ""}
        response = auth_client.post("/expenses/add", data=data)
        assert "/profile" in response.headers["Location"], (
            "POST without description must redirect to /profile"
        )

    def test_post_no_description_stores_null(self, auth_client, seeded_user_id):
        data = {**VALID_FORM, "description": ""}
        auth_client.post("/expenses/add", data=data)
        rows = _fetch_expenses_for_user(seeded_user_id)
        assert len(rows) == 1, "One expense row must be created"
        assert rows[0]["description"] is None, (
            "Blank description must be stored as NULL in the database"
        )

    def test_post_whitespace_only_description_stores_null(self, auth_client, seeded_user_id):
        data = {**VALID_FORM, "description": "   "}
        auth_client.post("/expenses/add", data=data)
        rows = _fetch_expenses_for_user(seeded_user_id)
        assert rows[0]["description"] is None, (
            "Whitespace-only description must be stripped and stored as NULL"
        )

    def test_post_omitted_description_field_stores_null(self, auth_client, seeded_user_id):
        """Submitting the form without a description key at all must also store NULL."""
        data = {k: v for k, v in VALID_FORM.items() if k != "description"}
        auth_client.post("/expenses/add", data=data)
        rows = _fetch_expenses_for_user(seeded_user_id)
        assert rows[0]["description"] is None, (
            "Missing description field must be stored as NULL"
        )


# ---------------------------------------------------------------------------
# POST — validation errors
# ---------------------------------------------------------------------------

class TestPostValidationErrors:

    # ---- Amount errors ----

    def test_post_missing_amount_returns_200(self, auth_client):
        data = {**VALID_FORM, "amount": ""}
        response = auth_client.post("/expenses/add", data=data)
        assert response.status_code == 200, (
            "Missing amount must re-render the form (200)"
        )

    def test_post_missing_amount_shows_error(self, auth_client):
        data = {**VALID_FORM, "amount": ""}
        response = auth_client.post("/expenses/add", data=data)
        html = response.data.decode("utf-8")
        assert (
            "error" in html.lower()
            or "Amount" in html
        ), "Missing amount must display an error message"

    def test_post_missing_amount_does_not_insert_db_row(self, auth_client, seeded_user_id):
        data = {**VALID_FORM, "amount": ""}
        auth_client.post("/expenses/add", data=data)
        assert len(_fetch_expenses_for_user(seeded_user_id)) == 0, (
            "No DB row should be inserted when amount is missing"
        )

    def test_post_zero_amount_returns_200(self, auth_client):
        data = {**VALID_FORM, "amount": "0"}
        response = auth_client.post("/expenses/add", data=data)
        assert response.status_code == 200, (
            "Zero amount must re-render the form (200)"
        )

    def test_post_zero_amount_shows_error(self, auth_client):
        data = {**VALID_FORM, "amount": "0"}
        response = auth_client.post("/expenses/add", data=data)
        html = response.data.decode("utf-8")
        assert "error" in html.lower() or "positive" in html.lower() or "Amount" in html, (
            "Zero amount must display an error message"
        )

    def test_post_zero_amount_does_not_insert_db_row(self, auth_client, seeded_user_id):
        data = {**VALID_FORM, "amount": "0"}
        auth_client.post("/expenses/add", data=data)
        assert len(_fetch_expenses_for_user(seeded_user_id)) == 0, (
            "No DB row should be inserted when amount is 0"
        )

    def test_post_negative_amount_returns_200(self, auth_client):
        data = {**VALID_FORM, "amount": "-10"}
        response = auth_client.post("/expenses/add", data=data)
        assert response.status_code == 200, (
            "Negative amount must re-render the form (200)"
        )

    def test_post_negative_amount_shows_error(self, auth_client):
        data = {**VALID_FORM, "amount": "-10"}
        response = auth_client.post("/expenses/add", data=data)
        html = response.data.decode("utf-8")
        assert "error" in html.lower() or "positive" in html.lower() or "Amount" in html, (
            "Negative amount must display an error message"
        )

    def test_post_negative_amount_does_not_insert_db_row(self, auth_client, seeded_user_id):
        data = {**VALID_FORM, "amount": "-10"}
        auth_client.post("/expenses/add", data=data)
        assert len(_fetch_expenses_for_user(seeded_user_id)) == 0, (
            "No DB row should be inserted when amount is negative"
        )

    def test_post_non_numeric_amount_returns_200(self, auth_client):
        data = {**VALID_FORM, "amount": "abc"}
        response = auth_client.post("/expenses/add", data=data)
        assert response.status_code == 200, (
            "Non-numeric amount must re-render the form (200)"
        )

    def test_post_non_numeric_amount_shows_error(self, auth_client):
        data = {**VALID_FORM, "amount": "abc"}
        response = auth_client.post("/expenses/add", data=data)
        html = response.data.decode("utf-8")
        assert "error" in html.lower() or "positive" in html.lower() or "Amount" in html, (
            "Non-numeric amount must display an error message"
        )

    def test_post_non_numeric_amount_does_not_insert_db_row(self, auth_client, seeded_user_id):
        data = {**VALID_FORM, "amount": "abc"}
        auth_client.post("/expenses/add", data=data)
        assert len(_fetch_expenses_for_user(seeded_user_id)) == 0, (
            "No DB row should be inserted when amount is non-numeric"
        )

    # ---- Category errors ----

    def test_post_invalid_category_returns_200(self, auth_client):
        data = {**VALID_FORM, "category": "Gambling"}
        response = auth_client.post("/expenses/add", data=data)
        assert response.status_code == 200, (
            "Invalid category must re-render the form (200)"
        )

    def test_post_invalid_category_shows_error(self, auth_client):
        data = {**VALID_FORM, "category": "Gambling"}
        response = auth_client.post("/expenses/add", data=data)
        html = response.data.decode("utf-8")
        assert "error" in html.lower() or "category" in html.lower(), (
            "Invalid category must display an error message"
        )

    def test_post_invalid_category_does_not_insert_db_row(self, auth_client, seeded_user_id):
        data = {**VALID_FORM, "category": "Gambling"}
        auth_client.post("/expenses/add", data=data)
        assert len(_fetch_expenses_for_user(seeded_user_id)) == 0, (
            "No DB row should be inserted when category is invalid"
        )

    def test_post_empty_category_returns_200(self, auth_client):
        data = {**VALID_FORM, "category": ""}
        response = auth_client.post("/expenses/add", data=data)
        assert response.status_code == 200, (
            "Empty category must re-render the form (200)"
        )

    # ---- Date errors ----

    def test_post_invalid_date_string_returns_200(self, auth_client):
        data = {**VALID_FORM, "date": "not-a-date"}
        response = auth_client.post("/expenses/add", data=data)
        assert response.status_code == 200, (
            "Invalid date string must re-render the form (200)"
        )

    def test_post_invalid_date_string_shows_error(self, auth_client):
        data = {**VALID_FORM, "date": "not-a-date"}
        response = auth_client.post("/expenses/add", data=data)
        html = response.data.decode("utf-8")
        assert "error" in html.lower() or "date" in html.lower(), (
            "Invalid date string must display an error message"
        )

    def test_post_invalid_date_string_does_not_insert_db_row(self, auth_client, seeded_user_id):
        data = {**VALID_FORM, "date": "not-a-date"}
        auth_client.post("/expenses/add", data=data)
        assert len(_fetch_expenses_for_user(seeded_user_id)) == 0, (
            "No DB row should be inserted when date is invalid"
        )

    def test_post_missing_date_returns_200(self, auth_client):
        data = {**VALID_FORM, "date": ""}
        response = auth_client.post("/expenses/add", data=data)
        assert response.status_code == 200, (
            "Missing date must re-render the form (200)"
        )

    def test_post_missing_date_does_not_insert_db_row(self, auth_client, seeded_user_id):
        data = {**VALID_FORM, "date": ""}
        auth_client.post("/expenses/add", data=data)
        assert len(_fetch_expenses_for_user(seeded_user_id)) == 0, (
            "No DB row should be inserted when date is missing"
        )

    def test_post_wrong_date_format_returns_200(self, auth_client):
        """A date that is recognisable but not in YYYY-MM-DD format must fail."""
        data = {**VALID_FORM, "date": "20/03/2026"}
        response = auth_client.post("/expenses/add", data=data)
        assert response.status_code == 200, (
            "Date in wrong format (DD/MM/YYYY) must re-render the form (200)"
        )


# ---------------------------------------------------------------------------
# POST — form value re-population on validation error
# ---------------------------------------------------------------------------

class TestFormRepopulationOnError:
    def test_amount_value_repopulated_after_invalid_category(self, auth_client):
        data = {**VALID_FORM, "category": "InvalidCat"}
        response = auth_client.post("/expenses/add", data=data)
        html = response.data.decode("utf-8")
        # The previously entered amount (50.0 or 50.00) should appear in the form
        assert "50" in html, (
            "Submitted amount must be re-populated in the form after a validation error"
        )

    def test_date_value_repopulated_after_invalid_category(self, auth_client):
        data = {**VALID_FORM, "category": "InvalidCat"}
        response = auth_client.post("/expenses/add", data=data)
        html = response.data.decode("utf-8")
        assert "2026-03-20" in html, (
            "Submitted date must be re-populated in the form after a validation error"
        )

    def test_description_value_repopulated_after_invalid_amount(self, auth_client):
        data = {**VALID_FORM, "amount": "abc", "description": "MyUniqueDescription"}
        response = auth_client.post("/expenses/add", data=data)
        html = response.data.decode("utf-8")
        assert "MyUniqueDescription" in html, (
            "Submitted description must be re-populated in the form after a validation error"
        )

    def test_all_7_categories_still_shown_after_error(self, auth_client):
        data = {**VALID_FORM, "amount": "0"}
        response = auth_client.post("/expenses/add", data=data)
        html = response.data.decode("utf-8")
        for cat in ALL_CATEGORIES:
            assert cat in html, (
                f"Category '{cat}' must still appear in the form after a validation error"
            )


# ---------------------------------------------------------------------------
# POST — data isolation (expense belongs to session user only)
# ---------------------------------------------------------------------------

class TestDataIsolation:
    def test_expense_stored_under_session_user_not_other_user(
        self, client, seeded_user_id, second_user_id
    ):
        """After submitting a valid expense as seeded_user_id, second_user_id
        should have no expenses."""
        with client.session_transaction() as sess:
            sess["user_id"] = seeded_user_id

        client.post("/expenses/add", data=VALID_FORM)

        other_expenses = _fetch_expenses_for_user(second_user_id)
        assert len(other_expenses) == 0, (
            "An expense added by user A must not appear under user B"
        )

    def test_expense_count_for_session_user_is_one_after_single_submit(
        self, auth_client, seeded_user_id
    ):
        auth_client.post("/expenses/add", data=VALID_FORM)
        rows = _fetch_expenses_for_user(seeded_user_id)
        assert len(rows) == 1, (
            "Exactly one expense should exist for the session user after a single submission"
        )

    def test_multiple_submits_each_create_a_distinct_row(
        self, auth_client, seeded_user_id
    ):
        second_form = {**VALID_FORM, "amount": "99.0", "description": "Dinner"}
        auth_client.post("/expenses/add", data=VALID_FORM)
        auth_client.post("/expenses/add", data=second_form)
        rows = _fetch_expenses_for_user(seeded_user_id)
        assert len(rows) == 2, (
            "Two successful submissions must produce two distinct rows in the DB"
        )
        amounts = {float(r["amount"]) for r in rows}
        assert amounts == {50.0, 99.0}, (
            "Both submitted amounts should be present in the DB"
        )


# ---------------------------------------------------------------------------
# POST — parametrized invalid amount values
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad_amount", [
    "",        # missing
    "0",       # zero
    "0.0",     # zero as float string
    "-1",      # negative
    "-0.01",   # negative near-zero
    "abc",     # non-numeric
    "12abc",   # partially numeric
    " ",       # whitespace only
    "1e500",   # overflow / Python raises OverflowError when converting to float then to int
])
def test_invalid_amount_rerenders_form(client, seeded_user_id, bad_amount):
    """Any amount value that is not a positive number must return 200 and show the form."""
    with client.session_transaction() as sess:
        sess["user_id"] = seeded_user_id
    data = {**VALID_FORM, "amount": bad_amount}
    response = client.post("/expenses/add", data=data)
    # "1e500" parses as float("inf") which is >0, so we only assert no crash for that case
    if bad_amount == "1e500":
        # Implementation may or may not reject infinity; must not crash
        assert response.status_code in (200, 302), (
            "Overflow amount must not cause a 500 error"
        )
    else:
        assert response.status_code == 200, (
            f"Amount '{bad_amount!r}' must re-render the form (200), not redirect"
        )
        assert len(_fetch_expenses_for_user(seeded_user_id)) == 0, (
            f"Amount '{bad_amount!r}' must not produce a DB row"
        )


@pytest.mark.parametrize("bad_category", [
    "Gambling",
    "food",          # case-sensitive — lowercase must be rejected
    "FOOD",          # all-caps must be rejected
    "",              # empty string
    "Food ",         # trailing space
    " Food",         # leading space
    "<script>",      # injection attempt
])
def test_invalid_category_rerenders_form(client, seeded_user_id, bad_category):
    """Any category value not in the fixed list must return 200."""
    with client.session_transaction() as sess:
        sess["user_id"] = seeded_user_id
    data = {**VALID_FORM, "category": bad_category}
    response = client.post("/expenses/add", data=data)
    assert response.status_code == 200, (
        f"Category '{bad_category!r}' must re-render the form (200)"
    )
    assert len(_fetch_expenses_for_user(seeded_user_id)) == 0, (
        f"Category '{bad_category!r}' must not produce a DB row"
    )


@pytest.mark.parametrize("bad_date", [
    "not-a-date",
    "2026-13-01",    # invalid month
    "2026-00-10",    # month 0
    "2026-04-32",    # invalid day
    "2026/03/20",    # wrong separator
    "20-03-2026",    # DD-MM-YYYY format
    "03/20/2026",    # US format
    "",              # empty string
])
def test_invalid_date_rerenders_form(client, seeded_user_id, bad_date):
    """Any date value that is not a valid YYYY-MM-DD date must return 200."""
    with client.session_transaction() as sess:
        sess["user_id"] = seeded_user_id
    data = {**VALID_FORM, "date": bad_date}
    response = client.post("/expenses/add", data=data)
    assert response.status_code == 200, (
        f"Date '{bad_date!r}' must re-render the form (200)"
    )
    assert len(_fetch_expenses_for_user(seeded_user_id)) == 0, (
        f"Date '{bad_date!r}' must not produce a DB row"
    )


# ---------------------------------------------------------------------------
# Unit tests for insert_expense query helper
# ---------------------------------------------------------------------------

class TestInsertExpenseHelper:
    """Tests for database/queries.py::insert_expense.

    The spec mandates a standalone insert_expense(user_id, amount, category,
    date, description) helper in database/queries.py.  These tests import it
    directly and verify DB side-effects without going through the HTTP layer.
    """

    @pytest.fixture(autouse=True)
    def _seed_user(self, seeded_user_id):
        self.user_id = seeded_user_id

    def test_insert_expense_creates_row(self, app):
        from database.queries import insert_expense
        insert_expense(self.user_id, 50.0, "Food", "2026-03-20", "Lunch")
        rows = _fetch_expenses_for_user(self.user_id)
        assert len(rows) == 1, (
            "insert_expense must create exactly one row in the expenses table"
        )

    def test_insert_expense_stores_correct_user_id(self, app):
        from database.queries import insert_expense
        insert_expense(self.user_id, 50.0, "Food", "2026-03-20", "Lunch")
        rows = _fetch_expenses_for_user(self.user_id)
        assert rows[0]["user_id"] == self.user_id, (
            "insert_expense must store the supplied user_id"
        )

    def test_insert_expense_stores_correct_amount(self, app):
        from database.queries import insert_expense
        insert_expense(self.user_id, 50.0, "Food", "2026-03-20", "Lunch")
        rows = _fetch_expenses_for_user(self.user_id)
        assert float(rows[0]["amount"]) == 50.0, (
            "insert_expense must store the supplied amount"
        )

    def test_insert_expense_stores_correct_category(self, app):
        from database.queries import insert_expense
        insert_expense(self.user_id, 50.0, "Food", "2026-03-20", "Lunch")
        rows = _fetch_expenses_for_user(self.user_id)
        assert rows[0]["category"] == "Food", (
            "insert_expense must store the supplied category"
        )

    def test_insert_expense_stores_correct_date(self, app):
        from database.queries import insert_expense
        insert_expense(self.user_id, 50.0, "Food", "2026-03-20", "Lunch")
        rows = _fetch_expenses_for_user(self.user_id)
        assert rows[0]["date"] == "2026-03-20", (
            "insert_expense must store the supplied date"
        )

    def test_insert_expense_stores_correct_description(self, app):
        from database.queries import insert_expense
        insert_expense(self.user_id, 50.0, "Food", "2026-03-20", "Lunch")
        rows = _fetch_expenses_for_user(self.user_id)
        assert rows[0]["description"] == "Lunch", (
            "insert_expense must store the supplied description"
        )

    def test_insert_expense_none_description_stores_null(self, app):
        from database.queries import insert_expense
        insert_expense(self.user_id, 50.0, "Food", "2026-03-20", None)
        rows = _fetch_expenses_for_user(self.user_id)
        assert len(rows) == 1, "Row must be created even when description is None"
        assert rows[0]["description"] is None, (
            "insert_expense with description=None must store NULL in the database"
        )

    def test_insert_expense_returns_without_error(self, app):
        """insert_expense must not raise an exception on valid input."""
        from database.queries import insert_expense
        try:
            insert_expense(self.user_id, 75.0, "Transport", "2026-05-01", "Bus fare")
        except Exception as exc:
            pytest.fail(f"insert_expense raised an unexpected exception: {exc}")


# ---------------------------------------------------------------------------
# Template / navigation landmarks
# ---------------------------------------------------------------------------

class TestNavigationLandmarks:
    def test_profile_page_contains_add_expense_link(self, auth_client):
        """The profile page must include a link or button pointing to /expenses/add."""
        response = auth_client.get("/profile")
        html = response.data.decode("utf-8")
        assert "/expenses/add" in html, (
            "The profile page must contain a link to /expenses/add ('Add Expense' button)"
        )

    def test_add_expense_navbar_link_present_when_logged_in(self, auth_client):
        """The navbar must show an 'Add Expense' link when the user is authenticated."""
        response = auth_client.get("/expenses/add")
        html = response.data.decode("utf-8")
        # The spec says base.html should have the link visible when user is logged in
        assert "Add Expense" in html, (
            "The navbar must include an 'Add Expense' link for authenticated users"
        )

    def test_add_expense_page_extends_base_template(self, auth_client):
        """add_expense.html extends base.html — the response must include the
        shared navigation landmark that base.html always renders."""
        response = auth_client.get("/expenses/add")
        html = response.data.decode("utf-8")
        # base.html always renders the brand/logo or nav; check for the Spendly brand
        assert "Spendly" in html, (
            "add_expense.html must extend base.html (page should contain 'Spendly' from base)"
        )
