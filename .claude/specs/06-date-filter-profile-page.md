# Spec: Date Filter for Profile Page

## Overview
This step adds a date range filter to the profile page so users can narrow all displayed data — stats, transaction history, and category breakdown — to a chosen time window. The filter is implemented as a GET query-string parameter on the existing `/profile` route; no new routes are needed. Quick presets (This Month, Last Month, Last 3 Months, All Time) are rendered as a segmented button bar, and an optional custom date-range picker lets users choose any arbitrary range. All SQL queries are updated to respect the active date window using parameterised `WHERE date BETWEEN ? AND ?` clauses.

## Depends on
- Step 1 — `get_db()` must return a connection with `row_factory = sqlite3.Row`
- Step 2 — `expenses` table must exist with a `date` column in `YYYY-MM-DD` format
- Step 3 — `login_required` decorator must be in place
- Step 4 — `templates/profile.html` must exist
- Step 5 — all profile data must be driven by real DB queries; the filter builds on top of those queries

## Routes
No new routes. The existing route accepts new query parameters:
- `GET /profile?period=<preset>` — preset options: `this_month`, `last_month`, `last_3_months`, `all_time` (default: `all_time`)
- `GET /profile?from=YYYY-MM-DD&to=YYYY-MM-DD` — custom date range; takes precedence over `period` when both `from` and `to` are present

## Database changes
No database changes. The `expenses.date` column (`TEXT`, `YYYY-MM-DD`) already supports range comparisons with `BETWEEN`.

## Templates
- **Modify:** `templates/profile.html`
  - Add a filter bar above the stats section containing:
    - Four preset buttons: "This Month", "Last Month", "Last 3 Months", "All Time"
    - Two `<input type="date">` fields ("From" / "To") for a custom range
    - A small "Apply" button to submit the custom range
  - The active preset button must have a visually distinct active state (use a CSS class, not inline styles)
  - All four sections (stats, transaction table, category breakdown, and the filter bar itself) must reflect the active filter window
  - Display the active date range as a human-readable label below the filter bar (e.g. "Showing: Apr 1 – Apr 30, 2026")

## Files to change
- `app.py` — update the `profile()` view function:
  - Read `from`, `to`, and `period` from `request.args`
  - Compute `date_from` and `date_to` as `YYYY-MM-DD` strings based on the active filter
  - Pass `date_from` and `date_to` as `?` parameters to all four expense queries
  - Pass `active_period`, `date_from`, and `date_to` to the template context
- `templates/profile.html` — add the filter bar UI (see Templates section above)
- `static/css/style.css` — add styles for the filter bar and active button state using CSS variables only

## Files to create
None.

## New dependencies
No new dependencies. Date arithmetic uses Python's standard `datetime` module (already imported).

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — pass `date_from` and `date_to` as `?` placeholders, never f-strings or `%` formatting
- Passwords hashed with werkzeug (no auth changes)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No JavaScript frameworks — vanilla JS only (used only for wiring the preset buttons to populate the date inputs before form submission, if desired; the page must work without JS via a plain form GET)
- Invalid or missing query params must fall back to `all_time` silently — never return a 400 or 500
- `date_from` and `date_to` passed to SQL must always be valid `YYYY-MM-DD` strings; compute them in Python, not in the template
- Open one `get_db()` connection per request and close it before returning
- The filter must affect all three data sections: stats aggregate, transaction list, and category breakdown
- The transaction list remains limited to 5 rows (most recent within the filtered window)

## Date range logic (Python, in `app.py`)

```python
from datetime import date, timedelta

today = date.today()

if request.args.get("from") and request.args.get("to"):
    date_from = request.args["from"]   # already YYYY-MM-DD from the date input
    date_to   = request.args["to"]
    active_period = "custom"
else:
    period = request.args.get("period", "all_time")
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
    else:  # all_time
        date_from = "2000-01-01"
        date_to   = "2999-12-31"
    active_period = period
```

## Definition of done
- [ ] `/profile` (no params) loads without errors and shows all expenses (all-time view)
- [ ] Clicking "This Month" filters stats, transactions, and categories to the current calendar month
- [ ] Clicking "Last Month" filters to the previous calendar month
- [ ] Clicking "Last 3 Months" filters to the last 90 days
- [ ] Clicking "All Time" removes the date filter and shows all data
- [ ] The active preset button is visually highlighted
- [ ] Entering a custom From / To date and clicking Apply filters all three sections to that range
- [ ] The "Showing: …" label updates to reflect the active date range
- [ ] A user with no expenses in the selected window sees ₹0.00, 0 transactions, and "—" for top category
- [ ] All amounts still display as `₹X.XX`
- [ ] No hardcoded hex values appear in any changed file
- [ ] The page works correctly with no JavaScript enabled (plain form GET submission)
