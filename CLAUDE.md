# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the dev server (port 5001)
python app.py

# Run all tests
pytest

# Run a single test file
pytest tests/test_auth.py -v

# Install dependencies into the venv
pip install -r requirements.txt
```

## Architecture

**Spendly** is a Flask expense-tracking web app backed by SQLite. The project is a step-by-step student exercise; many routes are stubs, and `database/db.py` is intentionally empty for students to implement.

### Request flow

```
app.py (routes) → templates/*.html (Jinja2) → static/css + static/js
                        ↓
              database/db.py (SQLite helpers)
```

### Key files

- `app.py` — all routes live here; no blueprints. `app.secret_key` must be set before Flask sessions work (needed for auth in Step 3).
- `database/db.py` — must expose `get_db()`, `init_db()`, and `seed_db()`. **Not yet implemented** (Step 1). `get_db()` should return a SQLite connection (not a cursor) with `row_factory = sqlite3.Row` and `PRAGMA foreign_keys = ON`.
- `database/__init__.py` — empty; makes `database/` a Python package.
- `templates/base.html` — shared layout. All page templates extend it via Jinja2 blocks: `title`, `head`, `content`, `scripts`.
- `static/js/main.js` — global JS; **no frameworks**, vanilla JS only.

### Template conventions

- `static/css/style.css` — global styles, loaded by `base.html`.
- `static/css/landing.css` — landing-page-only styles, loaded via `{% block head %}` in `landing.html`. Do not load it in `base.html`.
- `login.html` and `register.html` already have `<form method="POST">` pointing at `/login` and `/register` — the POST route handlers don't exist yet (Step 3).

### Exercise step sequence

| Step | Route / Feature |
|------|----------------|
| 1 | `database/db.py` — `get_db()`, `init_db()`, `seed_db()` |
| 2 | DB schema: `users` and `expenses` tables |
| 3 | `/login` POST, `/logout`, session management |
| 4 | `/profile` |
| 7 | `/expenses/add` POST |
| 8 | `/expenses/<id>/edit` POST |
| 9 | `/expenses/<id>/delete` POST |

### Typography

Google Fonts: **DM Serif Display** (headings) and **DM Sans** (body). Both are loaded in `base.html`; do not add other font imports.
