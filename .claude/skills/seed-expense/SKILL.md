---
name: seed-expenses
description: >
  Seeds realistic dummy expense records for a specific user in a local SQLite
  database. Use this skill whenever the user wants to populate, seed, or generate
  test/demo expense data for a user. Triggers include: "seed expenses", "generate
  dummy expenses", "populate expense data", "add test expenses", "create fake
  expenses for user", or any request involving inserting bulk expense records into
  a database. Even if the user just says "fill in some expenses for user 3" or
  "I need test data for my expenses table", use this skill.
allowed-tools: Read, Bash(python3:*)
---

# Seed Expenses Skill

This skill generates and inserts realistic dummy expense records for a given user
into a local SQLite database. It reads the project's own `database/db.py` to
discover the schema and connection pattern — so it adapts to the project rather
than assuming a fixed structure.

## Usage

The user provides three arguments (in order):

| Argument   | Type    | Meaning                                      |
|------------|---------|----------------------------------------------|
| `user_id`  | integer | The ID of the user to seed expenses for      |
| `count`    | integer | Total number of expense records to create    |
| `months`   | integer | How many past months to spread them across   |

**Example call:** `/seed-expenses 1 50 6`

---

## Step 1 — Read the database module

Before writing any code, read `database/db.py` to understand:
- The **expenses table schema** (column names and types)
- The **database connection pattern** (how to get a connection/cursor)
- The **database filename or path** (never hardcode it — use whatever `db.py` uses)

If `database/db.py` doesn't exist, look for other likely locations such as
`db.py`, `app/db.py`, or `models/db.py`, and read whichever you find.

---

## Step 2 — Parse and validate arguments

Extract from the user's input:
- `user_id` — must be a valid integer
- `count` — must be a valid integer
- `months` — must be a valid integer

If **any argument is missing or not a valid integer**, stop immediately and print:

```
Usage: /seed-expenses <user_id> <count> <months>
Example: /seed-expenses 1 50 6
```

---

## Step 3 — Verify the user exists

Before generating any data, run a quick query to confirm the `user_id` exists in
the `users` table. If it doesn't, stop and print:

```
No user found with id <user_id>.
```

---

## Step 4 — Generate and insert expenses

Write and execute a Python script that:

### Date distribution
Spread expense dates randomly across the past `<months>` calendar months. Use
`random.uniform` or similar — avoid clustering all dates on the same day.

### Categories and realistic Indian amounts (₹)

Use the following categories with Indian-context descriptions. Distribute them
roughly according to the weights shown (Food is most common; Health and
Entertainment are least common):

| Category      | Amount range (₹) | Approximate weight |
|---------------|------------------|--------------------|
| Food          | 50 – 800         | ~30%               |
| Transport     | 20 – 500         | ~20%               |
| Bills         | 200 – 3000       | ~15%               |
| Shopping      | 200 – 5000       | ~15%               |
| Other         | 50 – 1000        | ~10%               |
| Health        | 100 – 2000       | ~5%                |
| Entertainment | 100 – 1500       | ~5%                |

Sample realistic descriptions per category (use these as inspiration, not an
exhaustive list):

- **Food**: "Swiggy order", "Zomato dinner", "chai and samosa", "grocery run –
  BigBasket", "lunch at office canteen", "Domino's pizza"
- **Transport**: "Ola ride to airport", "metro card recharge", "Rapido bike",
  "petrol – HP pump", "Uber to station", "auto to market"
- **Bills**: "Jio recharge", "electricity bill – BESCOM", "broadband – ACT",
  "DTH recharge – Tata Play", "gas cylinder"
- **Shopping**: "Amazon order", "Myntra kurta", "Decathlon shoes",
  "stationery – Nataraj", "Flipkart headphones"
- **Health**: "Apollo pharmacy", "gym membership", "doctor consultation –
  Practo", "vitamins – HealthKart"
- **Entertainment**: "BookMyShow movie", "Spotify premium", "Netflix",
  "cricket match ticket"
- **Other**: "parking fee", "newspaper subscription", "birthday gift",
  "donation", "laundry"

### Database rules

1. **Use the connection pattern from `db.py`** — do not hardcode the DB filename.
2. **Use parameterised queries only** — never build SQL strings with f-strings or
   `%` formatting.
3. **Single transaction** — insert all records in one `BEGIN` / `COMMIT` block.
   If any insert fails, roll back everything so the database stays clean.

---

## Step 5 — Confirm success

After a successful insert, print a summary:

```
✅ Inserted <count> expenses for user <user_id>
📅 Date range: <earliest_date> → <latest_date>
📋 Sample records (5):
  - <date> | <category> | ₹<amount> | <description>
  - ...
```

Pick 5 records at random (or the first 5) from what was just inserted.

---

## Error handling notes

- If the DB file doesn't exist at all, print a clear error and stop — don't
  create a new empty database.
- If the expenses table is missing, print the schema error message from SQLite
  rather than a generic failure.
- Wrap the entire script in a try/except so any unexpected error is surfaced
  cleanly rather than producing a raw traceback.