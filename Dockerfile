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

# Entrypoint-Skript kopieren
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Flask-Umgebungsvariablen
ENV FLASK_APP=main.py
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1
ENV RUNNING_IN_DOCKER=true

# Port freigeben
EXPOSE 5000

# Startkommando führt das Entrypoint-Skript aus (welches pip & db upgrade macht)
ENTRYPOINT ["docker-entrypoint.sh"]
