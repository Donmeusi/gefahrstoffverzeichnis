from waitress import serve
from main import app, db
import os
import logging

if __name__ == "__main__":
    # Waitress Logging konfigurieren
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    logger = logging.getLogger('waitress')
    logger.setLevel(logging.INFO)

    # Fehlende Tabellen anlegen. Das erledigte bisher nur der direkte Start von
    # main.py; seit beide Startwege hierher zeigen, muss es hier stehen - sonst
    # laeuft eine frische Installation ohne Datenbankdatei in Tabellenfehler.
    # create_all() legt nur an, was fehlt, und laesst vorhandene Tabellen und
    # Daten unberuehrt. Neue Spalten an bestehenden Tabellen ergaenzt weiterhin
    # migrate_db.py, das beim Import von main laeuft.
    with app.app_context():
        db.create_all()

    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')

    print(f"Starte Gefahrstoff-App (Production Mode) auf http://{host}:{port}")
    print(f"Waitress WSGI Server läuft...")

    # Produktionsserver starten
    serve(app, host=host, port=port, threads=4)
