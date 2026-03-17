import sqlite3

conn = sqlite3.connect("knowledge.db", check_same_thread=False)

cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS knowledge(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word TEXT,
    definition TEXT,
    meaning TEXT,
    example TEXT
)
""")

conn.commit()