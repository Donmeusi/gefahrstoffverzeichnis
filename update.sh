#!/bin/bash
# -e: bei einem fehlgeschlagenen Schritt nicht weiterlaufen. Vorher startete
# das Skript die Anwendung auch dann, wenn `pip install` oder die Migration
# abgebrochen war - in einem inkonsistenten Abhaengigkeitsstand.
# -u: undefinierte Variablen als Fehler statt als leeren String.
# -o pipefail: Fehler in einer Pipe werden sichtbar.
set -euo pipefail

sleep 2

mkdir -p data/backups
timestamp=$(date +"%Y%m%d_%H%M%S")
if [ -f "data/gefahrstoffe.db" ]; then
    cp data/gefahrstoffe.db "data/backups/gefahrstoffe_${timestamp}.db"
elif [ -f "gefahrstoffe.db" ]; then
    cp gefahrstoffe.db "data/backups/gefahrstoffe_${timestamp}.db"
fi

# Branch wechseln falls angegeben (via Umgebungsvariable TARGET_BRANCH)
if [ -n "${TARGET_BRANCH:-}" ]; then
    # Nur Zeichen, die in einem Branch-Namen vorkommen koennen. Ohne diese
    # Pruefung wuerde ein Wert wie "-f" von git als Option gelesen.
    case "$TARGET_BRANCH" in
        -*) echo "Ungueltiger Branch-Name: $TARGET_BRANCH" >&2; exit 1 ;;
        *[!A-Za-z0-9._/-]*|"") echo "Ungueltiger Branch-Name: $TARGET_BRANCH" >&2; exit 1 ;;
    esac
    git -c protocol.ext.allow=never fetch
    git -c protocol.ext.allow=never checkout "$TARGET_BRANCH"
fi

git -c protocol.ext.allow=never pull

source venv/bin/activate
pip install -r requirements.txt
export FLASK_APP=main.py
# FLASK_ENV wirkt sich nicht mehr auf das Secure-Flag aus; das entscheidet
# SchemeAwareSessionInterface anhand des Zugriffswegs (main.py).
export FLASK_ENV=production
flask db upgrade

# Logdatei ausserhalb des Repos ablegen: error.log lag frueher im Wurzel-
# verzeichnis und war versioniert, jeder Lauf haette ihn in den naechsten
# Commit geschrieben.
mkdir -p data/logs
nohup python run_prod.py > data/logs/error.log 2>&1 &
