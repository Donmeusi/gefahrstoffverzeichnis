# Gefahrstoffverzeichnis

Eine moderne, webbasierte Applikation (Flask, Python) zur einfachen, sicheren und effizienten Verwaltung von Gefahrstoffen in Unternehmen, Instituten oder im Labor-Umfeld.

Die Anwendung ermöglicht Benutzern das strukturierte Anlegen von Gefahrstoffen, die Verwaltung hierarchischer Standorte (Bereiche und Unterbereiche) sowie den Export der Daten als Excel (`.xlsx`) oder PDF. Eine integrierte Benutzerrollen-Funktion trennt die Sichtbarkeit von Einträgen normaler Nutzer und gewährt Administratoren und Moderatoren erweiterte Rechte inklusive eines speziellen Freigabe-Workflows.

👉 **Für Nutzer:** Eine detaillierte Übersicht aller Funktionen und Rollen finden Sie im ausführlichen [Benutzerhandbuch (HANDBUCH.md)](HANDBUCH.md).

## ✨ Neue & Wichtige Funktionen (2026 Edition)

*   **SDB Auto-Parsing (Automatischer Import)**: Laden Sie ein Sicherheitsdatenblatt (SDB) als PDF hoch. Das System extrahiert vollautomatisch Name, CAS-Nr, EG-Nr, Signalwort, H-/P-Sätze und Piktogramme und füllt das Formular für Sie aus!
*   **Dokumenten-Zentralen**: Globale Menüpunkte listen alle hochgeladenen Betriebsanweisungen und Sicherheitsdatenblätter aus allen Bereichen alphabetisch sortiert auf. Inklusive Live-Suche – zugänglich für alle Nutzer.
*   **Umfassende Sicherheit (CSRF & Audit)**: Die App ist systemweit gegen Cross-Site Request Forgery (CSRF) geschützt. Administratoren können zudem eine detaillierte **System-Historie (Audit Log)** einsehen, die jeden Datensatz (Erstellen, Ändern, Löschen, Freigeben) manipulationssicher protokolliert.
*   **Archivierung (Soft-Delete)**: Gefahrstoffe werden beim "Löschen" nicht mehr unwiderruflich aus der Datenbank entfernt, sondern sicher archiviert (`is_deleted=True`), um versehentlichen Datenverlust zu verhindern.

## ⚙️ Kernfunktionen

*   **Sichere Authentifizierung**: Registrierung und Login. Der zuerst registrierte Nutzer erhält automatisch Administrator-Rechte.
*   **Standort-Verwaltung**: Legen Sie Hauptbereiche und dazugehörige Unterbereiche zur genauen Verortung von Gefahrstoffen an. Moderatoren können einzelnen Bereichen als Besitzer zugewiesen werden.
*   **Gefahrstoff-Erfassung**: Umfangreiche Erfassungsmaske mit:
    *   Name, CAS-Nummer und EG-Nummer
    *   Menge und Mengeneinheit, sowie Lagerklasse (LGK)
    *   GHS-Piktogrammen und Signalwort
    *   Durchsuchbare Modal-Auswahlfenster für vollständige H-, EUH- und P-Sätze
    *   Sektion für Substitutionsprüfungen
*   **Live-Suche & Filter**: Echtzeit-Suche (nach Name, CAS, H-Sätzen) und Filter (nach Piktogrammen und Signalwort) der Gefahrstofftabelle direkt im Browser.
*   **Benutzer-Isolation & Freigabe-Workflow**: Normale Benutzer sehen ausschließlich ihre eigenen Datensätze. Administratoren und Moderatoren haben zudem die Möglichkeit, neu erstellte Stoffe anderer User via "Approve/Reject" zu prüfen.
*   **Export-Funktionen**: Exportieren Sie die aktuell angezeigten, gefilterten Datensätze detailliert als Excel-Tabelle oder PDF-Dokument.
*   **In-App Updates**: Administratoren können das System direkt über die Benutzeroberfläche auf die neueste Version aktualisieren (GitHub Pull).

## 🛠️ Technologien

*   **Backend**: Python 3.11, Flask, Flask-WTF (CSRF), Flask-SQLAlchemy, Flask-Login, pdfplumber
*   **Datenbank**: SQLite (`gefahrstoffe.db`)
*   **Frontend**: HTML5, Vanilla CSS3 ("Clinical Glassmorphism" Design), JavaScript
*   **Exporte**: Pandas (OpenPyXL) für Excel, ReportLab für PDFs

## 🚀 Installation & Ausführung

### Voraussetzungen
1.  Python 3.8+ ist auf Ihrem System installiert.
2.  Empfohlen: Eine virtuelle Umgebung (Virtual Environment).

### Schritte

1.  **Repository klonen:**
    ```bash
    git clone https://github.com/Donmeusi/gefahrstoffverzeichnis.git
    cd gefahrstoffverzeichnis
    ```

2.  **Virtuelle Umgebung erstellen und aktivieren:**
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
    pip install -r requirements.txt
    ```

4.  **Datenbank & Initialisierung:**
    Beim ersten Start erstellt die Applikation automatisch eine leere SQLite-Datenbankdatei (`gefahrstoffe.db`) sowie den Ordner `uploads/` für Dokumente.
    *Wichtig:* Der allererste Account, der über `/register` angelegt wird, erhält **dauerhaft** Administrator-Rechte. 

5.  **Anwendung starten:**
    ```bash
    python main.py
    ```
    Die Anwendung läuft standardmäßig unter [http://127.0.0.1:5000](http://127.0.0.1:5000).

6.  **Mit Docker / Unraid ausführen (Empfohlen für Server):**
    Die App ist voll Docker-kompatibel. Die Pfade für Datenbank und Uploads stellen sich automatisch um, wenn der Container läuft (`RUNNING_IN_DOCKER=true`).
    ```bash
    docker-compose up -d
    ```

---

## 🔒 Sicherheit & Updates
*   **Daten sicher aktualisieren:** Die `.gitignore`-Datei schützt Ihre produktiven Daten. Führen Sie auf Ihrem Server bei Updates einfach `git pull` aus (oder nutzen Sie den Button im Admin-Menü). Ihre Datenbank (`gefahrstoffe.db`) und hochgeladenen Dokumente (`/uploads`) werden dabei nicht überschrieben.
*   **Produktivbetrieb:** Setzen Sie den `FLASK_SECRET_KEY` als Umgebungsvariable und verwenden Sie einen WSGI-Server (wie *Gunicorn* oder *Waitress*).

## 📅 Changelog

### v3.2 – Docker Fixes, Excel Update & Dokumentation (Juli 2026)
*   **Docker & Unraid Kompatibilität**: Automatischer Switch auf absolute Pfade (`/app/gefahrstoffe.db` und `/app/uploads`) via `RUNNING_IN_DOCKER` Variable. Verhindert Rechteprobleme in Containern, ohne die lokale Ausführung zu beeinträchtigen.
*   **Erweiterter Excel-Export**: Der Excel-Export (`.xlsx`) wurde an den PDF-Export angeglichen und beinhaltet nun Piktogramme (als Textliste), Lagerklassen (LGK), Datum der SDBs sowie Details der Substitutionsprüfungen.
*   **Handbuch**: Ein vollständiges `HANDBUCH.md` mit detaillierter Beschreibung aller Funktionen, Dokumentenzentralen, Freigabe-Workflows (Approve/Reject) und Rollensystem (Admin, Moderator, Benutzer) hinzugefügt.

### v3.1 – Erweiterte Such- & Filterfunktionen (Juni 2026)
*   **Live-Filter**: Neue Dropdowns zum gezielten Filtern nach GHS-Piktogrammen und Signalwörtern in der Gefahrstoff-Übersicht.
*   **Erweiterte Suchleiste**: Die Freitext-Suche bezieht nun auch H-Sätze in die Suche mit ein, parallel zu Name und CAS-Nummer.
*   **UI-Fixes**: Optimiertes Padding für die Suchleiste.

### v3.0 – Security, Auto-Parsing & Glassmorphism UI (Juni 2026)
*   **Sicherheit & Architektur**: Systemweite CSRF-Protection per Flask-WTF, Audit Logs (System-Historie für Admins), und Soft-Delete-Mechanismus für Gefahrstoffe.
*   **SDB Auto-Parsing**: PDF-Inhalte (CAS, EG, Signalwort, H/P-Sätze) werden beim Dateiupload vollautomatisch ausgelesen und in das HTML-Formular injiziert. Intelligente Umbenennung beim Speichern.
*   **Betriebsanweisungen**: Neue globale Übersicht (`/betriebsanweisungen`) für alle hochgeladenen Betriebsanweisungen.
*   **UI/UX (Clinical Glassmorphism)**: Komplettes Redesign in "Clinical/Medical Glassmorphism" mit sanften Blauschattierungen, durchsichtigen Flächen, abgerundeten Karten und modernsten Micro-Animationen.
