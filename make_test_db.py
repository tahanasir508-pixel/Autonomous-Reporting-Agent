"""
make_test_db.py
Creates a small test SQLite database (test_business.db) with sample
sales data — deliberately using DIFFERENT column names than our
dashboard expects, so you can actually try the column-mapping part of
the "Connect Database" feature, not just a trivial matching case.

Run once: python make_test_db.py
"""

import sqlite3

conn = sqlite3.connect("test_business.db")
conn.execute("""
    CREATE TABLE sales_records (
        sale_date TEXT,
        city TEXT,
        item_name TEXT,
        qty INTEGER,
        amount REAL,
        num_transactions INTEGER
    )
""")

rows = [
    ("2026-09-05", "Karachi", "Wireless Earbuds", 40, 1000.0, 25),
    ("2026-09-05", "Lahore", "Smart Watch", 15, 975.0, 10),
    ("2026-09-06", "Karachi", "Wireless Earbuds", 42, 1050.0, 27),
    ("2026-09-06", "Lahore", "Smart Watch", 16, 1040.0, 11),
]
conn.executemany("INSERT INTO sales_records VALUES (?, ?, ?, ?, ?, ?)", rows)
conn.commit()
conn.close()

print("test_business.db created with 4 rows across 2 days.")