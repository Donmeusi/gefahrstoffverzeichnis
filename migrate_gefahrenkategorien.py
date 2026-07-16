import sqlite3
import os

db_path = 'data/gefahrstoffe.db'

if not os.path.exists(db_path):
    print(f"Database {db_path} not found.")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    print("Adding gefahrenkategorien column to gefahrstoff...")
    cursor.execute('ALTER TABLE gefahrstoff ADD COLUMN gefahrenkategorien VARCHAR(500)')
    conn.commit()
    print("Migration successful!")
except sqlite3.OperationalError as e:
    print(f"Column might already exist: {e}")
finally:
    conn.close()
