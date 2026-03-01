# Gefahrstoffverzeichnis

Eine webbasierte Applikation (Flask, Python) zur einfachen und effizienten Verwaltung von Gefahrstoffen in Unternehmen, Instituten oder im Labor-Umfeld. 

Die Anwendung ermöglicht Benutzern das strukturierte Anlegen von Gefahrstoffen, die Verwaltung hierarchischer Standorte (Bereiche und Unterbereiche) sowie den Export der Daten als Excel (`.xlsx`) oder PDF. Eine integrierte Benutzerrollen-Funktion trennt die Sichtbarkeit von Einträgen normaler Nutzer und gewährt nur Administratoren einen Gesamtüberblick.

## Funktionen

*   **Sichere Authentifizierung**: Registrierung und Login. Der zuerst registrierte Nutzer erhält automatisch Administrator-Rechte.
*   **Standort-Verwaltung**: Legen Sie Hauptbereiche und dazugehörige Unterbereiche zur genauen Verortung von Gefahrstoffen an.
*   **Gefahrstoff-Erfassung**: Umfangreiche Erfassungsmaske mit:
    *   Name, CAS-Nummer und EG-Nummer
    *   Menge und Mengeneinheit
    *   GHS-Piktogrammen und Signalwort
    *   Durchsuchbare Modal-Auswahlfenster für vollständige H-, EUH- und P-Sätze
    *   Upload-Möglichkeit für Sicherheitsdatenblätter (SDB) und Betriebsanweisungen (BA) als PDF, DOC oder Bilddateien.
*   **Übersicht und Detailansicht**: Tabellarische Übersicht, filterbar nach Standorten.
*   **Benutzer-Isolation**: Normale Benutzer sehen und verwalten ausschließlich ihre *eigenen* angelegten Datensätze. Administratoren können alle Gefahrstoffe systemweit einsehen, verschieben, kopieren und löschen.
*   **Export-Funktion**: Exportieren Sie angezeigte Datensätze als Excel-Tabelle oder PDF-Dokument (ebenfalls nutzerbasiert gefiltert).
*   **Admin-Dashboard**: Zur Verwaltung, Beförderung oder Sperrung anderer Systembenutzer.

## Technologien

*   **Backend**: Python 3, Flask, Flask-SQLAlchemy, Flask-Login, Werkzeug
*   **Datenbank**: SQLite (`gefahrstoffe.db`)
*   **Frontend**: HTML5, Vanilla CSS3 (Custom Properties, Glassmorphismus, Flexbox/Grid), JavaScript
*   **Exporte**: Pandas (OpenPyXL) für Excel, ReportLab für PDFs

## Installation & Ausführung

### Voraussetzungen
1.  Python 3.8+ ist auf Ihrem System installiert.
2.  Empfohlen: Eine virtuelle Umgebung (Virtual Environment).

### Schritte

1.  **Repository klonen:**
    ```bash
    git clone https://github.com/Donmeusi/gefahrstoffverzeichnis.git
    cd gefahrstoffverzeichnis
    ```

2.  **Virtuelle Umgebung erstellen und aktivieren (Optional aber empfohlen):**
    ```bash
    # Windows
    python -m venv venv
    .\venv\Scripts\Activate.ps1
    
    # macOS/Linux
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Abhängigkeiten installieren:**
    ```bash
    pip install Flask Flask-SQLAlchemy Flask-Login Werkzeug pandas openpyxl reportlab
    ```

4.  **Datenbank & Initialisierung:**
    Beim ersten Start erstellt die Applikation automatisch eine leere SQLite-Datenbankdatei (`gefahrstoffe.db`) sowie einen Ordner `uploads/` für Dokumente. 
    
    *Wichtig:* Der allererste Account, der über `/register` angelegt wird, erhält **dauerhaft** Administrator-Rechte. Starten Sie das System und legen Sie diesen sofort an!

5.  **Anwendung starten:**
    ```bash
    # Für Entwicklungszwecke lokal ausführen:
    python main.py
    ```
    Die Anwendung läuft standardmäßig unter [http://127.0.0.1:5000](http://127.0.0.1:5000).

---

### Verzeichnisstruktur
*   `/main.py` - Zentrale Flask-Routen, Datenbank-Modelle und Logik.
*   `/static/` - Statische Dateien (`style.css`, H/P-Sätze Logik `hp_modal.js`, `hp_data.json` sowie `pictograms/`).
*   `/templates/` - Jinja2 HTML Layouts (Base-Template, Login, Register, Index, Forms).
*   `/uploads/` - Lokaler Speicherort für die durch Nutzer hochgeladenen Dokumente.

## Sicherheitshinweis
Für den absoluten Produktivbetrieb sollte der `FLASK_SECRET_KEY` als Umgebungsvariable gesetzt und ein WSGI-Server (wie *Gunicorn* oder *Waitress*) anstelle des integrierten Flask-Entwicklungsservers verwendet werden.
