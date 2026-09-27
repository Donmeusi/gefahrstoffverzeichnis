import sqlite3
import os


def get_db_path():
    """Pfad zur Datenbank, die die Anwendung tatsächlich benutzt.

    APP_DATA_DIR hat Vorrang - main.py liest denselben Wert. Vorher suchte diese
    Datei ausschließlich an zwei festen relativen Pfaden ('data/gefahrstoffe.db'
    und 'gefahrstoffe.db') und migrierte damit eine andere Datei als die
    Anwendung benutzte, sobald APP_DATA_DIR gesetzt war. Die Migration meldete
    trotzdem Erfolg, das Protokoll nannte nur den festen Pfad.

    Existiert die Datei unter APP_DATA_DIR nicht, wird None zurückgegeben und
    nicht auf die festen Pfade ausgewichen: das wäre eine fremde Datenbank.
    """
    data_dir = os.environ.get('APP_DATA_DIR')
    if data_dir:
        pfad = os.path.join(data_dir, 'gefahrstoffe.db')
        return pfad if os.path.exists(pfad) else None

    for p in ('data/gefahrstoffe.db', 'gefahrstoffe.db'):
        if os.path.exists(p):
            return p
    return None


def run_migrations():
    db_path = get_db_path()

    if not db_path:
        print("Keine Datenbankdatei gefunden. Es sind keine Migrationen erforderlich.")
        return

    print(f"Führe automatische Datenbank-Migrationen für '{db_path}' aus...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    def get_columns(table):
        try:
            cursor.execute(f"PRAGMA table_info({table});")
            return [row[1] for row in cursor.fetchall()]
        except Exception:
            return []

    tables = [t[0] for t in cursor.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]

    if 'gefahrstoff' in tables:
        existing = get_columns('gefahrstoff')
        columns_to_add = {
            'gefahrenkategorien': 'VARCHAR(500)',
            'is_deleted': 'BOOLEAN DEFAULT 0',
            'is_approved': 'BOOLEAN DEFAULT 1',
            'deleted_at': 'DATETIME',
            'last_inventur_datum': 'DATETIME',
            'last_inventur_user_id': 'INTEGER',
            'gefaehrdungsbeurteilung': 'VARCHAR(200)',
            'ba_texte': 'TEXT',
            'ba_gebotszeichen': 'VARCHAR(100)',
            'ba_unterschrift': 'TEXT'
        }
        for col, col_type in columns_to_add.items():
            if col not in existing:
                try:
                    print(f"  + Füge Spalte 'gefahrstoff.{col}' ({col_type}) hinzu...")
                    cursor.execute(f"ALTER TABLE gefahrstoff ADD COLUMN {col} {col_type};")
                except Exception as e:
                    print(f"  Warning bei Spalte '{col}': {e}")

    if 'user' in tables:
        existing = get_columns('user')
        if 'created_by' not in existing:
            try:
                print("  + Füge Spalte 'user.created_by' (INTEGER) hinzu...")
                cursor.execute("ALTER TABLE user ADD COLUMN created_by INTEGER;")
            except Exception as e:
                print(f"  Warning bei Spalte 'user.created_by': {e}")

    if 'bereich' in tables:
        existing = get_columns('bereich')
        if 'owner_id' not in existing:
            try:
                print("  + Füge Spalte 'bereich.owner_id' (INTEGER) hinzu...")
                cursor.execute("ALTER TABLE bereich ADD COLUMN owner_id INTEGER;")
            except Exception as e:
                print(f"  Warning bei Spalte 'bereich.owner_id': {e}")

    conn.commit()
    conn.close()
    print("[OK] Datenbank-Migrationen erfolgreich abgeschlossen!")

if __name__ == '__main__':
    run_migrations()
