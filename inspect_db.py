"""Quick database inspector to view tables and stored data in terminal."""

import sqlite3
from pathlib import Path


def inspect():
    db_path = Path("apex.db")
    if not db_path.exists():
        # Check if located inside apex-gateway/
        db_path = Path("apex-gateway/apex.db")

    if not db_path.exists():
        print("Database 'apex.db' not found. Run quickstart.py or the gateway first.")
        return

    print(f"Reading from database: {db_path.resolve()}\n")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Get list of tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = [r[0] for r in cur.fetchall()]

    for table in tables:
        print("=" * 60)
        print(f"TABLE: {table}")
        print("=" * 60)

        cur.execute(f"PRAGMA table_info({table});")
        columns = [col[1] for col in cur.fetchall()]
        print("Columns:", " | ".join(columns))
        print("-" * 60)

        cur.execute(f"SELECT * FROM {table} LIMIT 10;")
        rows = cur.fetchall()

        if not rows:
            print("(No records found)")
        else:
            for row in rows:
                print(row)
        print("\n")

    conn.close()


if __name__ == "__main__":
    inspect()

