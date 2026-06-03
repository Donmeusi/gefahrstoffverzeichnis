import sqlite3
import os

db_path = 'gefahrstoffe.db'

if not os.path.exists(db_path):
    print(f"Database {db_path} not found.")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # Add columns to gefahrstoff
    print("Adding is_deleted column to gefahrstoff...")
    cursor.execute('ALTER TABLE gefahrstoff ADD COLUMN is_deleted BOOLEAN DEFAULT 0')
    
    print("Adding deleted_at column to gefahrstoff...")
    cursor.execute('ALTER TABLE gefahrstoff ADD COLUMN deleted_at DATETIME')
except sqlite3.OperationalError as e:
    print(f"Columns might already exist: {e}")

try:
    # Create audit_log table
    print("Creating audit_log table...")
    cursor.execute('''
        CREATE TABLE audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME,
            user_id INTEGER,
            action VARCHAR(50),
            entity_type VARCHAR(50),
            entity_id INTEGER,
            details TEXT,
            FOREIGN KEY(user_id) REFERENCES user(id)
        )
    ''')
except sqlite3.OperationalError as e:
    print(f"Table might already exist: {e}")

conn.commit()
conn.close()
print("Migration completed successfully.")
