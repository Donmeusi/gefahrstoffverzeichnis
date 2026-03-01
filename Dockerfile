# Verwende ein offizielles Python-Image als Basis
FROM python:3.11-slim

# Arbeitsverzeichnis im Container festlegen
WORKDIR /app

# Systempakete aktualisieren und notwendige Bibliotheken installieren (z.B. für ReportLab/Fonts)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Abhängigkeiten kopieren
COPY requirements.txt .

# Python-Abhängigkeiten installieren
RUN pip install --no-cache-dir -r requirements.txt

# Restlichen Sourcecode kopieren
COPY . .

# Flask-Umgebungsvariablen
ENV FLASK_APP=main.py
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

# Ordner für Uploads erstellen (wird per Volume eingebunden)
RUN mkdir -p /app/uploads

# Port freigeben
EXPOSE 5000

# Startkommando (alternativ mit Gunicorn für Produktion)
CMD ["flask", "run", "--host=0.0.0.0"]
