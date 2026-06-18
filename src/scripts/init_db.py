"""
init_db.py — One-time setup script for the SQLite MCP database server.
 
Run this ONCE before starting db_server.py:
    uv run python init_db.py
 
It creates database.db (if missing) with 3 related tables and seed data,
so your MCP tools (list_tables, describe_table, query_database) have
something real to return when you test them in the Inspector or Claude.
 
Re-running this script is safe — it drops and recreates the tables
each time, so you always get a clean, known dataset.
"""
 
import sqlite3
 
DB_PATH = "database.db"   # must match DB_PATH in db_server.py
 
 
def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
 
    # ── Drop existing tables so this script is safely re-runnable ──
    cur.execute("DROP TABLE IF EXISTS appointments")
    cur.execute("DROP TABLE IF EXISTS health_logs")
    cur.execute("DROP TABLE IF EXISTS users")
 
    # ── Table 1: users ────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE users (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            email      TEXT NOT NULL UNIQUE,
            age        INTEGER,
            city       TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
 
    # ── Table 2: health_logs (many-to-one with users) ───────────────
    cur.execute("""
        CREATE TABLE health_logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            weight_kg   REAL NOT NULL,
            height_cm   REAL NOT NULL,
            bmi         REAL NOT NULL,
            logged_date TEXT NOT NULL
        )
    """)
 
    # ── Table 3: appointments (many-to-one with users) ──────────────
    cur.execute("""
        CREATE TABLE appointments (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id           INTEGER NOT NULL REFERENCES users(id),
            doctor_name       TEXT NOT NULL,
            specialty         TEXT,
            appointment_date  TEXT NOT NULL,
            status            TEXT DEFAULT 'scheduled'  -- scheduled | completed | cancelled
        )
    """)
 
    # ── Seed data: 5 users ───────────────────────────────────────────
    users = [
        ("Aarav Sharma", "aarav@example.com", 29, "Mumbai"),
        ("Priya Patel",  "priya@example.com", 34, "Delhi"),
        ("Rohan Mehta",  "rohan@example.com", 41, "Pune"),
        ("Sneha Iyer",   "sneha@example.com", 26, "Bengaluru"),
        ("Vikram Nair",  "vikram@example.com", 55, "Chennai"),
    ]
    cur.executemany(
        "INSERT INTO users (name, email, age, city) VALUES (?, ?, ?, ?)",
        users
    )
 
    # ── Seed data: health_logs (a couple of readings per user) ──────
    health_logs = [
        # user_id, weight_kg, height_cm, bmi, logged_date
        (1, 78, 175, 25.5, "2026-01-15"),
        (1, 76, 175, 24.8, "2026-03-15"),
        (2, 62, 162, 23.6, "2026-02-01"),
        (3, 95, 170, 32.9, "2026-01-20"),
        (3, 91, 170, 31.5, "2026-04-20"),
        (4, 55, 158, 22.0, "2026-03-10"),
        (5, 82, 172, 27.7, "2026-02-28"),
    ]
    cur.executemany(
        "INSERT INTO health_logs (user_id, weight_kg, height_cm, bmi, logged_date) "
        "VALUES (?, ?, ?, ?, ?)",
        health_logs
    )
 
    # ── Seed data: appointments ──────────────────────────────────────
    appointments = [
        # user_id, doctor_name, specialty, appointment_date, status
        (1, "Dr. Kapoor", "General Physician", "2026-06-20", "scheduled"),
        (1, "Dr. Verma",  "Cardiologist",       "2026-04-05", "completed"),
        (2, "Dr. Rao",    "Dermatologist",      "2026-06-25", "scheduled"),
        (3, "Dr. Kapoor", "General Physician",  "2026-05-10", "completed"),
        (3, "Dr. Singh",  "Endocrinologist",     "2026-06-30", "scheduled"),
        (4, "Dr. Rao",    "Dermatologist",       "2026-06-22", "scheduled"),
        (5, "Dr. Verma",  "Cardiologist",        "2026-07-02", "scheduled"),
        (5, "Dr. Kapoor", "General Physician",   "2026-03-15", "completed"),
    ]
    cur.executemany(
        "INSERT INTO appointments (user_id, doctor_name, specialty, appointment_date, status) "
        "VALUES (?, ?, ?, ?, ?)",
        appointments
    )
 
    conn.commit()
    conn.close()
 
    print(f"[SUCCESS] {DB_PATH} created with 3 tables:")
    print(f"  - users          ({len(users)} rows)")
    print(f"  - health_logs    ({len(health_logs)} rows)")
    print(f"  - appointments   ({len(appointments)} rows)")
    print("\nTry these in MCP Inspector once db_server.py is running:")
    print('  list_tables()')
    print('  describe_table(table_name="users")')
    print('  query_database(sql="SELECT * FROM users")')
    print('  query_database(sql="SELECT u.name, a.doctor_name, a.status FROM users u '
          'JOIN appointments a ON u.id = a.user_id")')
 
 
if __name__ == "__main__":
    main()
