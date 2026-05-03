# Spec: Login and Logout

## Overview
This step wires up Flask session management so users can authenticate with their email and password and maintain a logged-in state across requests. It implements the `POST /login` handler that verifies credentials against the hashed password stored in the database, stores the authenticated user's id in the server-side session, and implements `GET /logout` to clear that session. A reusable `login_required` decorator is also introduced here so that later steps (profile, expenses) can protect their routes without duplicating redirect logic.

## Depends on
- Step 1 — `database/db.py` must expose `get_db()` (connection with `row_factory` and foreign keys ON)
- Step 2 — `users` table must exist with `email` and `password_hash` columns

## Routes
- `POST /login` — accept email + password form fields, verify credentials, set `session['user_id']`, redirect to `/profile` on success or re-render `login.html` with an `error` on failure — public
- `GET /logout` — clear the session, redirect to `/login` — public (safe to call even when not logged in)

## Database changes
No database changes. The `users` table already has `email` and `password_hash` columns.

## Templates
- **Modify:** `templates/login.html` — already has the `{% if error %}` block; no structural changes needed. Verify the `action="/login"` form attribute and `name="email"` / `name="password"` input names match what the POST handler reads.
- **Create:** none

## Files to change
- `app.py` — set `app.secret_key`, add `POST` method to the existing `/login` route, implement `/logout`, add `login_required` decorator

## Files to create
None.

## New dependencies
No new dependencies. `werkzeug.security` (already installed) provides `check_password_hash`. Flask sessions are built into Flask.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — look up user with `WHERE email = ?`
- Passwords verified with `werkzeug.security.check_password_hash` — never compare plaintext
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- `app.secret_key` must be set **before** any route is registered (place it directly after `app = Flask(__name__)`)
- Store only `session['user_id']` — never store the password or hash in the session
- Follow the Post/Redirect/Get pattern on successful login (redirect, do not re-render)
- `login_required` must redirect to `/login` and not expose the protected content

## Definition of done
- [ ] App starts without errors after `app.secret_key` is added
- [ ] `POST /login` with valid credentials (`demo@spendly.com` / `demo123`) redirects to `/profile`
- [ ] `POST /login` with correct email but wrong password re-renders the login form with a visible error message
- [ ] `POST /login` with an unknown email re-renders the login form with a visible error message (use the same generic message as wrong password to avoid user enumeration)
- [ ] `GET /logout` clears the session and redirects to `/login`
- [ ] After logout, navigating back to `/profile` redirects to `/login` (confirms `login_required` works)
- [ ] Refreshing `/login` after a successful login does not re-submit the form (PRG pattern)
