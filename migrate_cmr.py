import sqlite3
import os

def migrate():
    db_path = os.path.join(os.path.dirname(__file__), 'gefahrstoffe.db')
    if not os.path.exists(db_path):
        print("Database not found!")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(gefahrstoff)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'is_approved' not in columns:
            cursor.execute("ALTER TABLE gefahrstoff ADD COLUMN is_approved BOOLEAN DEFAULT 1")
            cursor.execute("UPDATE gefahrstoff SET is_approved = 1")
            conn.commit()
            print("Successfully added is_approved column.")
        else:
            print("Column is_approved already exists.")
            
    except Exception as e:
        print(f"Error during migration: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
