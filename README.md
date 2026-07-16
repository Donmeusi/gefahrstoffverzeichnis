# Gefahrstoffverzeichnis

Eine moderne, webbasierte Applikation (Flask, Python) zur einfachen, sicheren und effizienten Verwaltung von Gefahrstoffen in Unternehmen, Instituten oder im Labor-Umfeld.

Die Anwendung ermöglicht Benutzern das strukturierte Anlegen von Gefahrstoffen, die Verwaltung hierarchischer Standorte (Bereiche und Unterbereiche) sowie den Export der Daten als Excel (`.xlsx`) oder PDF. Eine integrierte Benutzerrollen-Funktion trennt die Sichtbarkeit von Einträgen normaler Nutzer und gewährt Administratoren und Moderatoren erweiterte Rechte inklusive eines speziellen Freigabe-Workflows.

👉 **Für Nutzer:** Eine detaillierte Übersicht aller Funktionen und Rollen finden Sie im ausführlichen [Benutzerhandbuch (HANDBUCH.md)](HANDBUCH.md).

## ✨ Neue & Wichtige Funktionen (2026 Edition)

*   **SDB Auto-Parsing (Automatischer Import)**: Laden Sie ein Sicherheitsdatenblatt (SDB) als PDF hoch. Das System extrahiert vollautomatisch Name, CAS-Nr, EG-Nr, Signalwort, H-/P-Sätze und Piktogramme und füllt das Formular für Sie aus!
*   **Mobile Ready (Responsiv)**: Die gesamte Anwendung wurde mit einem "Mobile First" Ansatz überarbeitet. Auf Smartphones und kleinen Bildschirmen blenden Tabellen unwichtige Spalten aus und Eingabefelder stapeln sich dynamisch, für ein optimales Nutzungserlebnis unterwegs.
*   **PubChem CAS-Autofill**: Tippen Sie eine CAS-Nummer ein und laden Sie mit einem Klick alle GHS-Informationen (Piktogramme, Signalwort, H-/P-Sätze) automatisch aus der offiziellen NIH/PubChem Datenbank herunter.
*   **QR-Code Generator**: Erzeugen Sie mit einem Klick lokale, datenschutzkonforme QR-Codes für Ihre Lagerorte und Schränke, um per Smartphone-Scan direkt auf den gefilterten Schrank-Inhalt zuzugreifen.
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
    *   Durchsuchbare Modal-Auswahlfenster für Gefahrenkategorien (CLP), sowie vollständige H-, EUH- und P-Sätze
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

### 🐳 Vollständige Docker-Installation (Empfohlen für Server & Unraid)

Die App ist durch das integrierte `Dockerfile` und die `docker-compose.yml` voll Docker-kompatibel. Updates (inklusive neuer Dependencies und Datenbank-Migrationen) können bequem über das In-App Update-Feature ohne Neuinstallation geladen werden. Die Pfade für Datenbank und Uploads passen sich im Container automatisch an.

**Voraussetzungen:**
Auf Ihrem Server muss Docker und Docker Compose (bzw. das Compose-Plugin) installiert sein.

**1. Verzeichnis erstellen & Repository klonen:**
Legen Sie einen Ordner für die App an (z.B. in Ihrem Appdata-Verzeichnis) und klonen Sie das Repo dorthin.
```bash
git clone https://github.com/Donmeusi/gefahrstoffverzeichnis.git /pfad/zu/ihrem/appdata/gefahrstoffverzeichnis
cd /pfad/zu/ihrem/appdata/gefahrstoffverzeichnis
```

**2. Container bauen und starten:**
Da im Repository bereits eine fertig konfigurierte `docker-compose.yml` beiliegt, müssen Sie den Container nur noch im Hintergrund starten. Der Parameter `--build` sorgt dafür, dass das Image beim ersten Start frisch erstellt wird:
```bash
docker-compose up -d --build
```
Das System mountet Ihren Code-Ordner als Volume in den Container (`- ./:/app`). Dadurch bleiben alle Ihre zukünftigen Updates (via `git pull`) dauerhaft auf Ihrem Server gespeichert.

**3. Auf die App zugreifen:**
Sobald der Container läuft, erreichen Sie das Gefahrstoffverzeichnis über den Browser unter:
`http://<IP-Ihres-Servers>:5000`

**Hinweis für Unraid-Nutzer:**
Wenn Sie die App auf Unraid betreiben, klonen Sie das Projekt idealerweise nach `/mnt/user/appdata/gefahrstoffverzeichnis`. Sie können die bestehende `docker-compose.yml` dann auch direkt in das "Compose Manager" Plugin von Unraid einbinden und den Stack (Container) über das Webinterface verwalten.
---

## 🔒 Sicherheit & Updates
*   **Daten sicher aktualisieren:** Die `.gitignore`-Datei schützt Ihre produktiven Daten. Führen Sie auf Ihrem Server bei Updates einfach `git pull` aus (oder nutzen Sie den Button im Admin-Menü). Ihre Datenbank (`gefahrstoffe.db`) und hochgeladenen Dokumente (`/uploads`) werden dabei nicht überschrieben.
*   **Produktivbetrieb:** Setzen Sie den `FLASK_SECRET_KEY` als Umgebungsvariable und verwenden Sie einen WSGI-Server (wie *Gunicorn* oder *Waitress*).

## 📅 Changelog

Eine vollständige Liste aller Versionen und Änderungen finden Sie in der [CHANGELOG.md](CHANGELOG.md) Datei.
