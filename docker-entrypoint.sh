#!/bin/bash
set -e

echo "Starting Docker Entrypoint..."

# Abhaengigkeiten sind im Image installiert. Nachinstalliert wird nur, wenn
# ein git pull die requirements.txt veraendert hat. Verglichen wird mit dem
# Hash aus dem Image bzw. mit dem zuletzt installierten Stand in /app/data
# (bleibt ueber Neustarts erhalten).
if [ -f "requirements.txt" ]; then
    STAMP=/app/data/.requirements.sha256
    IMAGE_HASH_FILE=/usr/local/share/requirements.sha256
    WANT=$(sha256sum requirements.txt | cut -d' ' -f1)
    HAVE=$(cat "$STAMP" 2>/dev/null || cat "$IMAGE_HASH_FILE" 2>/dev/null || echo "none")
    if [ "$WANT" != "$HAVE" ]; then
        echo "requirements.txt geaendert - installiere Abhaengigkeiten..."
        # --user, weil der Container als nicht-root laeuft. Die Pakete landen
        # unter $HOME/.local (= /app/.local) und stehen trotzdem auf sys.path.
        pip install --no-cache-dir --user -r requirements.txt
        echo "$WANT" > "$STAMP" 2>/dev/null || true
    else
        echo "Abhaengigkeiten unveraendert - ueberspringe pip install."
    fi
fi

# Ensure database is up to date
if [ -f "migrate_db.py" ]; then
    echo "Running database auto-migrations..."
    python migrate_db.py
fi
if [ -d "migrations" ]; then
    echo "Running database migrations..."
    flask db upgrade
fi

echo "Starting WSGI Server (Waitress)..."
exec python run_prod.py
