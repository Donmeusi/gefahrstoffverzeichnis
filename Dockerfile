# Verwende ein offizielles Python-Image als Basis
FROM python:3.11-slim

# Arbeitsverzeichnis im Container festlegen
WORKDIR /app

# Systempakete aktualisieren und notwendige Bibliotheken installieren
# git wird zwingend für die In-App Update Funktion benötigt
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# WICHTIG für In-App Updates in Docker:
# Anstatt den Code hier per COPY zu kopieren, wird er über docker-compose.yml 
# als Volume gemountet. So bleiben git pull Änderungen erhalten.

# Abhaengigkeiten beim Build installieren, nicht bei jedem Start.
# Der Code wird weiterhin per Bind-Mount nach /app eingehaengt; die Pakete
# liegen in site-packages und werden davon nicht verdeckt. Der Hash der
# requirements.txt wird mitgespeichert, damit der Entrypoint erkennt, ob ein
# git pull die Datei veraendert hat und nachinstalliert werden muss.
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt \
    && sha256sum /app/requirements.txt | cut -d' ' -f1 > /usr/local/share/requirements.sha256

# Entrypoint-Skript kopieren
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Flask-Umgebungsvariablen
ENV FLASK_APP=main.py
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1
ENV RUNNING_IN_DOCKER=true
# Keine .pyc im (schreibgeschuetzt einghaengten) Quellverzeichnis ablegen.
ENV PYTHONDONTWRITEBYTECODE=1

# Nicht als root laufen. Ohne USER-Anweisung hat der Prozess UID 0 und alle
# Default-Capabilities; in Verbindung mit dem schreibbaren Quellcode-Mount
# heisst das: jeder Weg zu Codeausfuehrung trifft den Host mit.
#
# HOME zeigt auf /app, damit `pip install --user` im Entrypoint in das
# einghaengte Verzeichnis schreibt und nicht nach /root.
#
# Bei bestehenden Installationen muessen die einghaengten Verzeichnisse dem
# Benutzer gehoeren (chown -R 1000:1000 <verzeichnis>), sonst kann die
# Anwendung die Datenbank nicht schreiben.
RUN useradd --uid 1000 --shell /usr/sbin/nologin --no-create-home app \
    && chown -R app:app /app /usr/local/share
ENV HOME=/app
USER app

# Port freigeben
EXPOSE 5000

# Startkommando führt das Entrypoint-Skript aus (welches pip & db upgrade macht)
ENTRYPOINT ["docker-entrypoint.sh"]
