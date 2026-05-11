# Spec: Backend Routes for Profile Page

## Overview
This step replaces every hardcoded dict and list in the `/profile` route with real SQLite queries so the page reflects the actual logged-in user's data. Step 4 established the complete UI layout using static data; Step 5 wires that layout to the `users` and `expenses` tables without touching any template markup. After this step, every value shown on the profile page — name, email, member-since date, total spent, transaction count, top category, transaction list, and per-category totals — comes from the database.

## Depends on
- Step 1 — `get_db()` must return a connection with `row_factory = sqlite3.Row` and `PRAGMA foreign_keys = ON`
- Step 2 — `users` and `expenses` tables must exist with the schema defined in `database/db.py`
- Step 3 — session must store `user_id` after login; `login_required` decorator must be in place
- Step 4 — `templates/profile.html` must exist and accept `user`, `stats`, `transactions`, and `categories` context variables

## Routes
No new routes. The existing route is modified:
- `GET /profile` — replace hardcoded context with live DB queries — logged-in only (decorator already in place)

## Database changes
No database changes. The existing `users` and `expenses` tables provide all required data.

## Templates
- **Modify:** none — `templates/profile.html` already uses `{{ user.name }}`, `{{ stats.total_spent }}`, etc. The variable names and structure must stay identical so the template requires zero changes.
- **Create:** none

## Files to change
- `app.py` — replace the hardcoded `user`, `stats`, `transactions`, and `categories` dicts/lists inside the `profile()` view function with parameterised SQLite queries. Keep the same variable names passed to `render_template`.

## Files to create
None.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — every `WHERE` clause must use `?` placeholders, never f-strings or `%` formatting
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Open one `get_db()` connection per request and close it before returning; do not leave connections open
- Format `created_at` from the `users` table into a human-readable "Month YYYY" string in Python, not in the template
- Format `amount` values as `₹X.XX` strings in Python before passing to the template so the template stays logic-free
- Format expense `date` values (stored as `YYYY-MM-DD`) into `Mon DD, YYYY` in Python before passing to the template
- Derive `initials` from `user["name"]` in Python (first letter of each word, max 2)
- Compute `top_category` by summing expenses per category and picking the highest; if the user has no expenses return `"—"`
- The `transactions` list must be ordered by `date DESC`, limited to the 5 most recent
- The `categories` list must include only categories that have at least one expense for this user, ordered by total descending

## Query breakdown

### User info
```sql
SELECT id, name, email, created_at FROM users WHERE id = ?
```
Map to: `user = { "name", "email", "initials", "member_since" }`

### Stats
```sql
-- total spent and count
SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS cnt
FROM expenses WHERE user_id = ?

-- top category
SELECT category, SUM(amount) AS cat_total
FROM expenses WHERE user_id = ?
GROUP BY category ORDER BY cat_total DESC LIMIT 1
```
Map to: `stats = { "total_spent", "transaction_count", "top_category" }`

### Recent transactions (last 5)
```sql
SELECT date, description, category, amount
FROM expenses WHERE user_id = ?
ORDER BY date DESC LIMIT 5
```
Map to: list of `{ "date", "description", "category", "amount" }`

### Category breakdown
```sql
SELECT category, SUM(amount) AS total
FROM expenses WHERE user_id = ?
GROUP BY category ORDER BY total DESC
```
Map to: list of `{ "name", "total" }` — icon mapping handled in Python using the fixed category list

## Category icon map (Python dict in app.py)
```python
CATEGORY_ICONS = {
    "Food": "🍽️",
    "Transport": "🚌",
    "Bills": "🏠",
    "Health": "💊",
    "Entertainment": "🎬",
    "Shopping": "🛍️",
    "Other": "📦",
}
```

## Definition of done
- [ ] `/profile` returns HTTP 200 for the seeded demo user (`demo@spendly.com` / `demo123`)
- [ ] The name displayed matches the name stored in the `users` table (not "Alex Johnson")
- [ ] The email displayed matches the email stored in the `users` table (not `alex@example.com`)
- [ ] "Member since" reflects the `created_at` date from the `users` table
- [ ] "Total spent" equals the sum of all expenses for the logged-in user
- [ ] "Transactions" count equals the number of expense rows for the logged-in user
- [ ] "Top category" is the category with the highest total spend for the logged-in user
- [ ] The transaction table shows the 5 most recent expenses, ordered newest first
- [ ] The category breakdown lists only categories with at least one expense, ordered by total descending
- [ ] All amounts display as `₹X.XX` (two decimal places)
- [ ] Creating a second user and logging in as them shows only their own data, not the demo user's
- [ ] No hardcoded names, emails, amounts, or dates remain in the `profile()` function
- [ ] The DB connection is closed before the response is returned
