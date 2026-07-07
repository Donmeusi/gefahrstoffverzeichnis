from waitress import serve
from main import app
import os
import logging

if __name__ == "__main__":
    # Waitress Logging konfigurieren
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    logger = logging.getLogger('waitress')
    logger.setLevel(logging.INFO)
    
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    
    print(f"Starte Gefahrstoff-App (Production Mode) auf http://{host}:{port}")
    print(f"Waitress WSGI Server läuft...")
    
    # Produktionsserver starten
    serve(app, host=host, port=port, threads=4)
