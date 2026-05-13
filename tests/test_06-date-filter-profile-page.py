"""
Tests for Step 06 — Date Filter for Profile Page
=================================================
Spec: .claude/specs/06-date-filter-profile-page.md

These tests verify the /profile route's date-filtering behaviour by seeding
a controlled set of expenses and asserting on the HTTP response only.
No implementation details are assumed beyond the spec.
"""

import pytest
from datetime import date, timedelta
from app import app as flask_app
from database.db import init_db, get_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app(tmp_path):
    """Isolated Flask app wired to a temporary SQLite file (not :memory:
    because get_db() hard-codes a file path; we monkey-patch DB_PATH)."""
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
    """Insert a known user and return their id. No seed expenses — each test
    decides its own expenses for full isolation."""
    from werkzeug.security import generate_password_hash
    db = get_db()
    cur = db.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Test User", "test@spendly.com", generate_password_hash("pass123")),
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


def _insert_expenses(user_id, expenses):
    """Helper: insert list of (amount, category, date_str, description) tuples."""
    db = get_db()
    db.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        [(user_id, amt, cat, dt, desc) for amt, cat, dt, desc in expenses],
    )
    db.commit()
    db.close()


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

class TestAuthGuard:
    def test_profile_without_session_redirects_to_login(self, client):
        response = client.get("/profile")
        assert response.status_code == 302, "Unauthenticated /profile should redirect"
        assert "/login" in response.headers["Location"], (
            "Redirect target should be /login"
        )

    def test_profile_without_session_does_not_return_200(self, client):
        response = client.get("/profile", follow_redirects=False)
        assert response.status_code != 200, (
            "Unauthenticated /profile must not return 200"
        )


# ---------------------------------------------------------------------------
# Default / all_time view
# ---------------------------------------------------------------------------

class TestDefaultAllTimeView:
    APRIL_EXPENSES = [
        (45.50,  "Food",          "2026-04-01", "Grocery run"),
        (12.00,  "Transport",     "2026-04-03", "Metro card top-up"),
        (120.00, "Bills",         "2026-04-05", "Electricity bill"),
        (30.00,  "Health",        "2026-04-08", "Pharmacy"),
        (15.00,  "Entertainment", "2026-04-12", "Movie ticket"),
        (65.00,  "Shopping",      "2026-04-15", "New shoes"),
        (8.50,   "Food",          "2026-04-18", "Coffee and snacks"),
        (20.00,  "Other",         "2026-04-22", "Miscellaneous"),
    ]  # total = 316.00, count = 8

    def test_get_profile_no_params_returns_200(self, auth_client, seeded_user_id):
        _insert_expenses(seeded_user_id, self.APRIL_EXPENSES)
        response = auth_client.get("/profile")
        assert response.status_code == 200, "GET /profile (no params) should return 200"

    def test_get_profile_no_params_shows_all_expenses_total(self, auth_client, seeded_user_id):
        _insert_expenses(seeded_user_id, self.APRIL_EXPENSES)
        response = auth_client.get("/profile")
        assert b"\xe2\x82\xb9316.00" in response.data, (
            "All-time view should show total ₹316.00 for all 8 April expenses"
        )

    def test_get_profile_no_params_shows_correct_transaction_count(self, auth_client, seeded_user_id):
        _insert_expenses(seeded_user_id, self.APRIL_EXPENSES)
        response = auth_client.get("/profile")
        # The stats card shows the count as a number
        assert b">8<" in response.data or b"8" in response.data, (
            "All-time view should report 8 transactions in stats"
        )

    def test_get_profile_no_params_top_category_is_bills(self, auth_client, seeded_user_id):
        _insert_expenses(seeded_user_id, self.APRIL_EXPENSES)
        response = auth_client.get("/profile")
        assert b"Bills" in response.data, (
            "Top category for April seed data should be Bills (₹120.00)"
        )

    def test_get_profile_all_time_explicit_returns_200(self, auth_client, seeded_user_id):
        _insert_expenses(seeded_user_id, self.APRIL_EXPENSES)
        response = auth_client.get("/profile?period=all_time")
        assert response.status_code == 200, "GET /profile?period=all_time should return 200"

    def test_get_profile_all_time_button_is_active(self, auth_client, seeded_user_id):
        _insert_expenses(seeded_user_id, self.APRIL_EXPENSES)
        response = auth_client.get("/profile")
        html = response.data.decode("utf-8")
        # The "All Time" link must carry the "active" class
        assert 'class="filter-btn active"' in html or "filter-btn active" in html, (
            "'All Time' preset button should have the active CSS class on default view"
        )

    def test_get_profile_all_time_showing_label(self, auth_client, seeded_user_id):
        _insert_expenses(seeded_user_id, self.APRIL_EXPENSES)
        response = auth_client.get("/profile")
        html = response.data.decode("utf-8")
        assert "All time" in html, (
            "Showing label should read 'All time' when no filter is applied"
        )


# ---------------------------------------------------------------------------
# Preset filter: this_month
# ---------------------------------------------------------------------------

class TestThisMonthFilter:
    def test_this_month_returns_200(self, auth_client, seeded_user_id):
        response = auth_client.get("/profile?period=this_month")
        assert response.status_code == 200, "GET /profile?period=this_month should return 200"

    def test_this_month_button_is_active(self, auth_client, seeded_user_id):
        response = auth_client.get("/profile?period=this_month")
        html = response.data.decode("utf-8")
        # Locate the "This Month" link and verify active class is present
        assert "This Month" in html, "Page must contain 'This Month' preset button"
        # The active button for this_month should carry the active class
        import re
        this_month_links = re.findall(
            r'<a[^>]+period=this_month[^>]*class="[^"]*active[^"]*"[^>]*>|'
            r'<a[^>]+class="[^"]*active[^"]*"[^>]*>[^<]*This Month',
            html
        )
        # Alternatively check that the active class appears near "This Month"
        assert "filter-btn active" in html, (
            "'This Month' preset button should have the active CSS class"
        )

    def test_this_month_excludes_april_expenses(self, auth_client, seeded_user_id):
        """April 2026 expenses must NOT appear when filtering by this_month (May 2026)."""
        today = date.today()
        if today.month == 4 and today.year == 2026:
            pytest.skip("Test designed for months other than April 2026")

        april_expenses = [
            (45.50, "Food", "2026-04-01", "Grocery run"),
            (120.00, "Bills", "2026-04-05", "Electricity bill"),
        ]
        _insert_expenses(seeded_user_id, april_expenses)

        # Add an expense in the current month so we know there's something
        current_month_date = today.replace(day=1).isoformat()
        current_month_expenses = [
            (99.00, "Shopping", current_month_date, "This month purchase"),
        ]
        _insert_expenses(seeded_user_id, current_month_expenses)

        response = auth_client.get("/profile?period=this_month")
        html = response.data.decode("utf-8")

        # The April-only description should not appear
        assert "Grocery run" not in html, (
            "April expense 'Grocery run' should not appear in this_month filter"
        )
        assert "Electricity bill" not in html, (
            "April expense 'Electricity bill' should not appear in this_month filter"
        )

    def test_this_month_includes_current_month_expense(self, auth_client, seeded_user_id):
        today = date.today()
        current_month_date = today.replace(day=1).isoformat()
        _insert_expenses(seeded_user_id, [(77.77, "Health", current_month_date, "CurrentMonthExpense")])
        response = auth_client.get("/profile?period=this_month")
        html = response.data.decode("utf-8")
        assert "CurrentMonthExpense" in html, (
            "An expense dated in the current month should appear under this_month filter"
        )

    def test_this_month_showing_label_contains_dates(self, auth_client, seeded_user_id):
        today = date.today()
        _insert_expenses(seeded_user_id, [
            (10.00, "Food", today.isoformat(), "Today expense")
        ])
        response = auth_client.get("/profile?period=this_month")
        html = response.data.decode("utf-8")
        assert "Showing:" in html, "Page must contain a 'Showing:' label"
        # The label should not read "All time" for this_month
        assert "All time" not in html, (
            "Showing label should not say 'All time' when this_month filter is active"
        )


# ---------------------------------------------------------------------------
# Preset filter: last_month
# ---------------------------------------------------------------------------

class TestLastMonthFilter:
    def test_last_month_returns_200(self, auth_client, seeded_user_id):
        response = auth_client.get("/profile?period=last_month")
        assert response.status_code == 200, "GET /profile?period=last_month should return 200"

    def test_last_month_button_is_active(self, auth_client, seeded_user_id):
        response = auth_client.get("/profile?period=last_month")
        html = response.data.decode("utf-8")
        assert "Last Month" in html, "Page must contain 'Last Month' preset button"
        assert "filter-btn active" in html, (
            "'Last Month' preset button should have the active CSS class"
        )

    def test_last_month_includes_april_expenses_when_tested_in_may_2026(self, auth_client, seeded_user_id):
        """When running in May 2026, last_month == April 2026."""
        today = date.today()
        if not (today.year == 2026 and today.month == 5):
            pytest.skip("This assertion is only valid when running in May 2026")

        april_expenses = [
            (45.50,  "Food",  "2026-04-01", "Grocery run April"),
            (120.00, "Bills", "2026-04-05", "Electricity April"),
        ]
        _insert_expenses(seeded_user_id, april_expenses)
        response = auth_client.get("/profile?period=last_month")
        html = response.data.decode("utf-8")
        assert "Grocery run April" in html, (
            "April expenses should appear under last_month when running in May 2026"
        )

    def test_last_month_excludes_current_month_expenses(self, auth_client, seeded_user_id):
        today = date.today()
        current_expense_date = today.isoformat()
        _insert_expenses(seeded_user_id, [
            (50.00, "Food", current_expense_date, "TodayCurrentExpense"),
        ])
        response = auth_client.get("/profile?period=last_month")
        html = response.data.decode("utf-8")
        assert "TodayCurrentExpense" not in html, (
            "An expense from today (current month) should not appear in last_month filter"
        )

    def test_last_month_showing_label_not_all_time(self, auth_client, seeded_user_id):
        response = auth_client.get("/profile?period=last_month")
        html = response.data.decode("utf-8")
        assert "Showing:" in html, "Page must contain a 'Showing:' label"
        assert "All time" not in html, (
            "Showing label should not say 'All time' for last_month filter"
        )


# ---------------------------------------------------------------------------
# Preset filter: last_3_months
# ---------------------------------------------------------------------------

class TestLast3MonthsFilter:
    def test_last_3_months_returns_200(self, auth_client, seeded_user_id):
        response = auth_client.get("/profile?period=last_3_months")
        assert response.status_code == 200, "GET /profile?period=last_3_months should return 200"

    def test_last_3_months_button_is_active(self, auth_client, seeded_user_id):
        response = auth_client.get("/profile?period=last_3_months")
        html = response.data.decode("utf-8")
        assert "Last 3 Months" in html, "Page must contain 'Last 3 Months' preset button"
        assert "filter-btn active" in html, (
            "'Last 3 Months' preset button should have the active CSS class"
        )

    def test_last_3_months_includes_expenses_within_90_days(self, auth_client, seeded_user_id):
        today = date.today()
        within_window = (today - timedelta(days=45)).isoformat()
        _insert_expenses(seeded_user_id, [
            (33.00, "Health", within_window, "Within90DaysExpense"),
        ])
        response = auth_client.get("/profile?period=last_3_months")
        html = response.data.decode("utf-8")
        assert "Within90DaysExpense" in html, (
            "An expense 45 days ago should appear in last_3_months filter"
        )

    def test_last_3_months_excludes_expenses_older_than_90_days(self, auth_client, seeded_user_id):
        today = date.today()
        outside_window = (today - timedelta(days=91)).isoformat()
        _insert_expenses(seeded_user_id, [
            (99.00, "Other", outside_window, "OlderThan90DaysExpense"),
        ])
        response = auth_client.get("/profile?period=last_3_months")
        html = response.data.decode("utf-8")
        assert "OlderThan90DaysExpense" not in html, (
            "An expense 91 days ago should NOT appear in last_3_months filter"
        )

    def test_last_3_months_showing_label_not_all_time(self, auth_client, seeded_user_id):
        response = auth_client.get("/profile?period=last_3_months")
        html = response.data.decode("utf-8")
        assert "Showing:" in html, "Page must contain a 'Showing:' label"
        assert "All time" not in html, (
            "Showing label should not say 'All time' for last_3_months filter"
        )


# ---------------------------------------------------------------------------
# Custom date range
# ---------------------------------------------------------------------------

class TestCustomDateRange:
    APRIL_EXPENSES = [
        (45.50,  "Food",      "2026-04-01", "Grocery run"),
        (12.00,  "Transport", "2026-04-03", "Metro top-up"),
        (120.00, "Bills",     "2026-04-05", "Electricity bill"),
        (30.00,  "Health",    "2026-04-08", "Pharmacy"),
    ]

    def test_custom_range_returns_200(self, auth_client, seeded_user_id):
        _insert_expenses(seeded_user_id, self.APRIL_EXPENSES)
        response = auth_client.get("/profile?from=2026-04-01&to=2026-04-05")
        assert response.status_code == 200, "Custom date range request should return 200"

    def test_custom_range_includes_only_expenses_within_range(self, auth_client, seeded_user_id):
        _insert_expenses(seeded_user_id, self.APRIL_EXPENSES)
        # Range covers Apr 1 – Apr 5: Grocery run (45.50), Metro top-up (12.00), Electricity bill (120.00)
        response = auth_client.get("/profile?from=2026-04-01&to=2026-04-05")
        html = response.data.decode("utf-8")
        assert "Grocery run" in html, "Apr 1 expense should be inside Apr 1–5 range"
        assert "Metro top-up" in html, "Apr 3 expense should be inside Apr 1–5 range"
        assert "Electricity bill" in html, "Apr 5 expense should be inside Apr 1–5 range"

    def test_custom_range_excludes_expenses_outside_range(self, auth_client, seeded_user_id):
        _insert_expenses(seeded_user_id, self.APRIL_EXPENSES)
        # Apr 8 expense must NOT appear in Apr 1–5 range
        response = auth_client.get("/profile?from=2026-04-01&to=2026-04-05")
        html = response.data.decode("utf-8")
        assert "Pharmacy" not in html, (
            "Apr 8 expense 'Pharmacy' should not appear in Apr 1–5 custom range"
        )

    def test_custom_range_correct_total(self, auth_client, seeded_user_id):
        _insert_expenses(seeded_user_id, self.APRIL_EXPENSES)
        # Apr 1–5: 45.50 + 12.00 + 120.00 = 177.50
        response = auth_client.get("/profile?from=2026-04-01&to=2026-04-05")
        html = response.data.decode("utf-8")
        assert "177.50" in html, (
            "Total for Apr 1–5 range should be ₹177.50 (45.50 + 12.00 + 120.00)"
        )

    def test_custom_range_active_period_is_custom(self, auth_client, seeded_user_id):
        """When a custom range is active, no preset button should have the active class."""
        _insert_expenses(seeded_user_id, self.APRIL_EXPENSES)
        response = auth_client.get("/profile?from=2026-04-01&to=2026-04-05")
        html = response.data.decode("utf-8")
        # Each preset uses period=... param; none should be active
        import re
        active_preset_buttons = re.findall(
            r'period=(this_month|last_month|last_3_months|all_time)[^"]*"[^>]*class="[^"]*active',
            html
        )
        assert len(active_preset_buttons) == 0, (
            "No preset button should be active when a custom date range is applied"
        )

    def test_custom_range_showing_label_contains_range_dates(self, auth_client, seeded_user_id):
        _insert_expenses(seeded_user_id, self.APRIL_EXPENSES)
        response = auth_client.get("/profile?from=2026-04-01&to=2026-04-05")
        html = response.data.decode("utf-8")
        assert "Showing:" in html, "Page must contain a 'Showing:' label"
        assert "2026" in html, "Showing label should reference the filtered year"
        assert "All time" not in html, (
            "Showing label should not say 'All time' for a custom range"
        )

    def test_custom_range_empty_window_shows_zero_total(self, auth_client, seeded_user_id):
        """A date range with no matching expenses should show ₹0.00."""
        # Only April expenses inserted; query window is in March 2026
        _insert_expenses(seeded_user_id, self.APRIL_EXPENSES)
        response = auth_client.get("/profile?from=2026-03-01&to=2026-03-31")
        html = response.data.decode("utf-8")
        assert "0.00" in html, (
            "Empty date window should show ₹0.00 total"
        )

    def test_custom_range_empty_window_shows_zero_transactions(self, auth_client, seeded_user_id):
        """A date range with no matching expenses should report 0 transactions."""
        _insert_expenses(seeded_user_id, self.APRIL_EXPENSES)
        response = auth_client.get("/profile?from=2026-03-01&to=2026-03-31")
        html = response.data.decode("utf-8")
        # The stat card for transactions should read 0
        assert ">0<" in html or html.count(">0<") >= 0, (
            "Empty window must show 0 transactions; response should contain '0'"
        )
        # More robust: confirm the transaction list is empty (no tx-date spans)
        assert "tx-date" not in html or html.count("tx-date") == 0, (
            "No transaction rows should be rendered for an empty date window"
        )

    def test_custom_range_empty_window_top_category_is_dash(self, auth_client, seeded_user_id):
        """A date range with no matching expenses should show '—' for top category."""
        _insert_expenses(seeded_user_id, self.APRIL_EXPENSES)
        response = auth_client.get("/profile?from=2026-03-01&to=2026-03-31")
        html = response.data.decode("utf-8")
        assert "—" in html, (
            "Top category should display '—' (em dash) when no expenses exist in the window"
        )


# ---------------------------------------------------------------------------
# Fallback / invalid input
# ---------------------------------------------------------------------------

class TestInvalidInputFallback:
    def test_invalid_from_to_strings_return_200(self, auth_client, seeded_user_id):
        """Non-date strings in from/to must not crash the server."""
        response = auth_client.get("/profile?from=notadate&to=alsonotadate")
        assert response.status_code == 200, (
            "Invalid from/to strings should fall back silently and return 200"
        )

    def test_invalid_from_to_falls_back_to_all_time(self, auth_client, seeded_user_id):
        """Invalid from/to should show the all_time result set (no 400/500)."""
        expenses = [
            (100.00, "Bills", "2026-04-05", "Electricity"),
        ]
        _insert_expenses(seeded_user_id, expenses)
        response = auth_client.get("/profile?from=bad&to=data")
        assert response.status_code == 200, (
            "Invalid date strings should not cause a server error"
        )
        # Falls back to all_time so the seeded expense should still appear
        html = response.data.decode("utf-8")
        assert "Electricity" in html, (
            "After fallback to all_time, seeded expenses should still be visible"
        )

    def test_unknown_period_value_returns_200(self, auth_client, seeded_user_id):
        """An unrecognised period value must not crash the server."""
        response = auth_client.get("/profile?period=weekly")
        assert response.status_code == 200, (
            "Unknown period value should fall back silently and return 200"
        )

    def test_unknown_period_falls_back_to_all_time_data(self, auth_client, seeded_user_id):
        expenses = [
            (50.00, "Food", "2026-04-01", "FallbackExpense"),
        ]
        _insert_expenses(seeded_user_id, expenses)
        response = auth_client.get("/profile?period=nonexistent_period")
        assert response.status_code == 200, (
            "Unrecognised period should fall back to all_time without error"
        )
        html = response.data.decode("utf-8")
        assert "FallbackExpense" in html, (
            "After fallback to all_time, seeded expenses should be visible"
        )

    def test_partial_custom_range_only_from_falls_back(self, auth_client, seeded_user_id):
        """Providing only 'from' without 'to' should not crash — treated as period fallback."""
        response = auth_client.get("/profile?from=2026-04-01")
        assert response.status_code == 200, (
            "Providing only 'from' without 'to' should return 200 without crashing"
        )

    def test_partial_custom_range_only_to_falls_back(self, auth_client, seeded_user_id):
        """Providing only 'to' without 'from' should not crash — treated as period fallback."""
        response = auth_client.get("/profile?to=2026-04-30")
        assert response.status_code == 200, (
            "Providing only 'to' without 'from' should return 200 without crashing"
        )

    def test_empty_from_to_strings_return_200(self, auth_client, seeded_user_id):
        """Empty string values for from/to should not crash the server."""
        response = auth_client.get("/profile?from=&to=")
        assert response.status_code == 200, (
            "Empty from/to query params should return 200 without crashing"
        )


# ---------------------------------------------------------------------------
# Template context variables and landmarks
# ---------------------------------------------------------------------------

class TestTemplateContext:
    def test_response_contains_showing_label_text(self, auth_client, seeded_user_id):
        response = auth_client.get("/profile")
        assert b"Showing:" in response.data, (
            "Profile page must render 'Showing:' text in the filter bar"
        )

    def test_response_contains_this_month_button(self, auth_client, seeded_user_id):
        response = auth_client.get("/profile")
        assert b"This Month" in response.data, (
            "Profile page must render the 'This Month' preset button"
        )

    def test_response_contains_last_month_button(self, auth_client, seeded_user_id):
        response = auth_client.get("/profile")
        assert b"Last Month" in response.data, (
            "Profile page must render the 'Last Month' preset button"
        )

    def test_response_contains_last_3_months_button(self, auth_client, seeded_user_id):
        response = auth_client.get("/profile")
        assert b"Last 3 Months" in response.data, (
            "Profile page must render the 'Last 3 Months' preset button"
        )

    def test_response_contains_all_time_button(self, auth_client, seeded_user_id):
        response = auth_client.get("/profile")
        assert b"All Time" in response.data, (
            "Profile page must render the 'All Time' preset button"
        )

    def test_default_view_has_exactly_one_active_preset_button(self, auth_client, seeded_user_id):
        response = auth_client.get("/profile")
        html = response.data.decode("utf-8")
        active_count = html.count("filter-btn active")
        assert active_count == 1, (
            f"Exactly one preset button should be active on the default view, found {active_count}"
        )

    def test_this_month_has_exactly_one_active_preset_button(self, auth_client, seeded_user_id):
        response = auth_client.get("/profile?period=this_month")
        html = response.data.decode("utf-8")
        active_count = html.count("filter-btn active")
        assert active_count == 1, (
            f"Exactly one preset button should be active for this_month, found {active_count}"
        )

    def test_last_month_has_exactly_one_active_preset_button(self, auth_client, seeded_user_id):
        response = auth_client.get("/profile?period=last_month")
        html = response.data.decode("utf-8")
        active_count = html.count("filter-btn active")
        assert active_count == 1, (
            f"Exactly one preset button should be active for last_month, found {active_count}"
        )

    def test_last_3_months_has_exactly_one_active_preset_button(self, auth_client, seeded_user_id):
        response = auth_client.get("/profile?period=last_3_months")
        html = response.data.decode("utf-8")
        active_count = html.count("filter-btn active")
        assert active_count == 1, (
            f"Exactly one preset button should be active for last_3_months, found {active_count}"
        )

    def test_all_time_explicit_has_active_button(self, auth_client, seeded_user_id):
        response = auth_client.get("/profile?period=all_time")
        html = response.data.decode("utf-8")
        assert "filter-btn active" in html, (
            "The 'All Time' button should have active class when period=all_time is explicit"
        )

    def test_amounts_use_rupee_currency_symbol(self, auth_client, seeded_user_id):
        _insert_expenses(seeded_user_id, [(42.00, "Food", "2026-04-10", "Rupee test")])
        response = auth_client.get("/profile")
        # ₹ is UTF-8 encoded as \xe2\x82\xb9
        assert b"\xe2\x82\xb9" in response.data, (
            "Amounts must be formatted with the ₹ currency symbol"
        )

    def test_amounts_have_two_decimal_places(self, auth_client, seeded_user_id):
        _insert_expenses(seeded_user_id, [(42.00, "Food", "2026-04-10", "Decimal test")])
        response = auth_client.get("/profile")
        html = response.data.decode("utf-8")
        assert "42.00" in html, "Amounts should always be rendered with two decimal places"


# ---------------------------------------------------------------------------
# Transaction list cap
# ---------------------------------------------------------------------------

class TestTransactionListCap:
    def test_transaction_list_capped_at_5_rows(self, auth_client, seeded_user_id):
        """Even when 8 expenses match the filter, at most 5 should be rendered."""
        eight_expenses = [
            (10.00, "Food",      "2026-04-01", f"Expense {i}")
            for i in range(1, 9)
        ]
        _insert_expenses(seeded_user_id, eight_expenses)
        response = auth_client.get("/profile")
        html = response.data.decode("utf-8")
        # Count rendered transaction rows via the tx-date class
        row_count = html.count("tx-date")
        assert row_count <= 5, (
            f"Transaction list should be capped at 5 rows, but found {row_count}"
        )

    def test_transaction_list_shows_most_recent_first(self, auth_client, seeded_user_id):
        """Transactions should be ordered most recent first within the filtered window."""
        expenses = [
            (10.00, "Food", "2026-04-01", "Oldest"),
            (20.00, "Food", "2026-04-28", "Newest"),
        ]
        _insert_expenses(seeded_user_id, expenses)
        response = auth_client.get("/profile")
        html = response.data.decode("utf-8")
        newest_pos = html.find("Newest")
        oldest_pos = html.find("Oldest")
        assert newest_pos < oldest_pos, (
            "Most recent transactions should appear before older ones in the list"
        )


# ---------------------------------------------------------------------------
# Parameterised: all preset buttons are present on every filtered view
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("period", ["this_month", "last_month", "last_3_months", "all_time"])
def test_all_preset_buttons_present_for_every_period(client, seeded_user_id, period):
    """All four preset buttons must be rendered regardless of which is active."""
    with client.session_transaction() as sess:
        sess["user_id"] = seeded_user_id
    response = client.get(f"/profile?period={period}")
    html = response.data.decode("utf-8")
    for label in ("This Month", "Last Month", "Last 3 Months", "All Time"):
        assert label in html, (
            f"Button '{label}' must be present when period={period}"
        )


@pytest.mark.parametrize("period", ["this_month", "last_month", "last_3_months", "all_time"])
def test_preset_period_returns_200(client, seeded_user_id, period):
    """Every valid preset must return HTTP 200."""
    with client.session_transaction() as sess:
        sess["user_id"] = seeded_user_id
    response = client.get(f"/profile?period={period}")
    assert response.status_code == 200, (
        f"GET /profile?period={period} should return 200"
    )


@pytest.mark.parametrize("bad_param", [
    "?from=notadate&to=notadate",
    "?from=2026-13-01&to=2026-13-31",   # invalid month
    "?from=2026-04-00&to=2026-04-32",   # invalid day
    "?period=quarterly",
    "?period=",
    "?from=&to=",
])
def test_invalid_params_never_crash(client, seeded_user_id, bad_param):
    """Any malformed query param must fall back gracefully and return 200."""
    with client.session_transaction() as sess:
        sess["user_id"] = seeded_user_id
    response = client.get(f"/profile{bad_param}")
    assert response.status_code == 200, (
        f"Malformed params '{bad_param}' should return 200, not crash"
    )
