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

    # Produktionsserver starten.
    #
    # Waitress 3 entfernt X-Forwarded-* standardmaessig, bevor die Anwendung
    # sie sieht. Dann erkennt ProxyFix das HTTPS-Schema nicht, und das
    # Sitzungscookie bekommt hinter einem Reverse Proxy kein Secure-Flag.
    #
    # Standard hier: Header durchreichen (wie bei `flask run`), damit LAN und
    # Internet ohne Zusatzkonfiguration funktionieren. Wer haerten will, setzt
    # TRUSTED_PROXY auf die IP/CIDR des Proxys (nur dieser darf die Header
    # setzen) oder CLEAR_UNTRUSTED_PROXY_HEADERS=true (Header immer verwerfen).
    trusted_proxy = os.environ.get('TRUSTED_PROXY')
    clear_headers = os.environ.get('CLEAR_UNTRUSTED_PROXY_HEADERS', '').strip().lower() in (
        'true', '1', 'yes', 'on'
    )

    options = dict(host=host, port=port, threads=4)
    if trusted_proxy:
        options['trusted_proxy'] = trusted_proxy
        print(f"Vertrauter Proxy: {trusted_proxy}")
    elif clear_headers:
        options['clear_untrusted_proxy_headers'] = True
        print("X-Forwarded-* wird verworfen (CLEAR_UNTRUSTED_PROXY_HEADERS)")
    else:
        options['clear_untrusted_proxy_headers'] = False

    serve(app, **options)
