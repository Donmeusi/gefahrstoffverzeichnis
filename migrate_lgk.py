import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'gefahrstoffe.db')

def migrate():
    print(f"Migrating database: {db_path}")
    if not os.path.exists(db_path):
        print("Database not found. Nothing to migrate.")
        return
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(gefahrstoff)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'lagerklasse' not in columns:
            print("Adding 'lagerklasse' column to 'gefahrstoff' table...")
            cursor.execute("ALTER TABLE gefahrstoff ADD COLUMN lagerklasse VARCHAR(10)")
            conn.commit()
            print("Migration successful.")
        else:
            print("Column 'lagerklasse' already exists. No migration needed.")
            
    except Exception as e:
        print(f"Error during migration: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
