# Gefahrstoffverzeichnis

Eine moderne, webbasierte Applikation (Flask, Python) zur einfachen, sicheren und effizienten Verwaltung von Gefahrstoffen in Unternehmen, Instituten oder im Labor-Umfeld.

Die Anwendung ermöglicht Benutzern das strukturierte Anlegen von Gefahrstoffen, die Verwaltung hierarchischer Standorte (Bereiche und Unterbereiche) sowie den Export der Daten als Excel (`.xlsx`) oder PDF. Eine integrierte Benutzerrollen-Funktion trennt die Sichtbarkeit von Einträgen normaler Nutzer und gewährt Administratoren und Moderatoren erweiterte Rechte inklusive eines speziellen Freigabe-Workflows.

👉 **Für Nutzer:** Eine detaillierte Übersicht aller Funktionen und Rollen finden Sie im ausführlichen [Benutzerhandbuch (HANDBUCH.md)](HANDBUCH.md).  
👉 **Für Datenschutz & IT-Sicherheit:** Die vollständige technische Dokumentation inklusive **Technisch-Organisatorischer Maßnahmen (TOM)** für den Datenschutzbeauftragten (DSB) finden Sie in [DATENSCHUTZ_UND_TOM.md](DATENSCHUTZ_UND_TOM.md).

## ✨ Neue & Wichtige Funktionen (2026 Edition)

*   **LDAPs-Authentifizierung (Active Directory / OpenLDAP)**: Binden Sie Ihr Unternehmens-Verzeichnis via LDAPs/TLS ein. Neue LDAP-Nutzer werden automatisch mit konfigurierbarer Standardrolle angelegt.
*   **Schreibgeschützte Rolle „Lesen“**: Neue Benutzerrolle für reine Betrachter. Leser sehen zugewiesene Bereiche, dürfen jedoch keine Daten bearbeiten, löschen, exportieren (Excel/PDF) oder Dokumente herunterladen.
*   **📱 Schnell-Inventur-Modus**: Touch-optimierte mobile Checkliste zum schnellen Abhaken, Vergleichen und Anpassen von Lagermengen vor Ort am Schrank inklusive automatischer Protokollierung im Audit Log.
*   **🖨️ Schrank-Aushang & Druckansicht**: Generieren Sie A4-optimierte Inhaltsverzeichnisse für Sicherheitsschränke inklusive GHS-Piktogrammen, Notfallhinweisen, Lagerklassen und QR-Code zum Aushang vor Ort.
*   **SDB Auto-Parsing (Automatischer Import)**: Laden Sie ein Sicherheitsdatenblatt (SDB) als PDF hoch. Das System extrahiert vollautomatisch Name, CAS-Nr, EG-Nr, Signalwort, H-/P-Sätze und Piktogramme und füllt das Formular für Sie aus!
*   **Mobile Ready (Responsiv)**: Die gesamte Anwendung wurde mit einem "Mobile First" Ansatz überarbeitet. Auf Smartphones und kleinen Bildschirmen blenden Tabellen unwichtige Spalten aus und Eingabefelder stapeln sich dynamisch, für ein optimales Nutzungserlebnis unterwegs.
*   **CAS-Autofill mit amtlicher Einstufung**: Tippen Sie eine CAS-Nummer ein und laden Sie mit einem Klick alle GHS-Informationen (Piktogramme, Signalwort, H-/P-Sätze, Gefahrenkategorien). Die Einstufung kommt aus **Anhang VI der CLP-Verordnung** — der amtlichen Liste der harmonisierten Einstufungen, die mitgeliefert wird und ohne Netzzugriff arbeitet. Steht ein Stoff dort nicht (selbsteingestufte Stoffe), wird auf PubChem zurückgegriffen. Die deutsche Bezeichnung liefert Wikidata.
*   **QR-Code Generator**: Erzeugen Sie mit einem Klick lokale, datenschutzkonforme QR-Codes für Ihre Lagerorte und Schränke, um per Smartphone-Scan direkt auf den gefilterten Schrank-Inhalt zuzugreifen.
*   **Dokumenten-Zentralen**: Globale Menüpunkte listen alle hochgeladenen Betriebsanweisungen und Sicherheitsdatenblätter aus allen Bereichen alphabetisch sortiert auf. Inklusive Live-Suche – zugänglich für alle Nutzer.
*   **Umfassende Sicherheit (CSRF & Audit)**: Die App ist systemweit gegen Cross-Site Request Forgery (CSRF) geschützt. Administratoren können zudem eine detaillierte **System-Historie (Audit Log)** einsehen, die jeden Datensatz (Erstellen, Ändern, Verschieben, Kopieren, Löschen, Freigeben) protokolliert — einschließlich der Vorgänge der Benutzerverwaltung (Anlegen, Rollenwechsel, Bearbeiten, Bereichszuweisung, Löschen) und der Standortverwaltung. Passwörter werden nur als Ereignis vermerkt, nie im Klartext.
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
*   **Frontend**: HTML5, Vanilla CSS3 ("Clinical & Clean" Design), JavaScript
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

### 🔐 LDAPs-Authentifizierung & .env Konfiguration

Zur Anbindung von **Active Directory** oder **OpenLDAP** kopieren Sie die Beispieldatei `.env.example` zu `.env` (oder setzen Sie die Umgebungsvariablen in Ihrem System / Docker Compose):

```bash
cp .env.example .env
```

**Beispiel `.env` Konfiguration:**
```env
# LDAPs Authentifizierung aktivieren
LDAP_ENABLED=true
LDAP_HOST=ldaps://ldap.beispiel.de
LDAP_PORT=636
LDAP_USE_SSL=true
LDAP_BASE_DN=dc=beispiel,dc=de

# Bind DN für Service Account (falls erforderlich)
LDAP_BIND_DN=cn=service_gefahrstoff,ou=services,dc=beispiel,dc=de
LDAP_BIND_PASSWORD=ServiceAccountPasswort

# Benutzer-Suchfilter (Active Directory: sAMAccountName / OpenLDAP: uid)
LDAP_USER_SEARCH_FILTER=(sAMAccountName={username})

# Standardrolle für neue LDAP-Benutzer beim ersten Login (lesen | benutzer | moderator | admin)
LDAP_DEFAULT_ROLE=lesen

# Server-Zertifikat prüfen (Standard: true)
LDAP_REQUIRE_CERT=true

# Für eine eigene/interne PKI das CA-Bundle hinterlegen, statt die Prüfung
# abzuschalten. Sonst gehen die Anmeldedaten ungeprüft an den Verzeichnisdienst.
# LDAP_CA_CERT_FILE=/certs/unternehmens-ca.pem
```

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

**2. Konfiguration anlegen:**
Die Anwendung braucht einen eigenen Sitzungsschlüssel. Ohne ihn startet sie nicht — bewusst, denn ein Standardwert im Repository wäre öffentlich bekannt, und mit ihm ließen sich Anmeldungen fälschen.
```bash
cp .env.example .env
printf 'FLASK_SECRET_KEY=%s\n' "$(openssl rand -base64 32)" > .env
```
Die `.env` ist per `.gitignore` ausgeschlossen. LDAP-Einstellungen (falls benötigt) gehören ebenfalls dorthin, siehe `.env.example`.

**3. Container bauen und starten:**
```bash
docker compose up -d --build
```
Das System mountet Ihren Code-Ordner als Volume in den Container (`- ./:/app`). Dadurch bleiben alle Ihre zukünftigen Updates (via `git pull`) dauerhaft auf Ihrem Server gespeichert. Die Python-Abhängigkeiten werden beim Bauen installiert, nicht bei jedem Start — ein Neustart dauert dadurch rund eine halbe Minute statt mehrerer Minuten.

Der Container läuft **nicht als root**, sondern als Benutzer `app` mit UID/GID 1000. Die eingehängten Verzeichnisse müssen diesem Benutzer gehören, sonst kann die Anwendung die Datenbank nicht schreiben:

```bash
sudo chown -R 1000:1000 /pfad/zu/ihrem/appdata/gefahrstoffverzeichnis
```

**4. Auf die App zugreifen:**
Die mitgelieferte `docker-compose.yml` veröffentlicht Port 5000 nur auf der Loopback-Schnittstelle — gedacht für einen vorgelagerten Reverse Proxy. Direkt aus dem Netz erreichbar ist die App damit nicht, und das ist Absicht: sonst gehen Anmeldungen unverschlüsselt über die Leitung.

Betreiben Sie die App ohne Proxy in einem vertrauenswürdigen LAN, setzen Sie in der `.env`:

```env
BIND_ADDR=0.0.0.0
```

Danach ist sie unter `http://<IP-Ihres-Servers>:5000` erreichbar. Der Zugriff läuft dann unverschlüsselt: Anmeldedaten gehen im Klartext über die Leitung, und das Sitzungscookie trägt kein `Secure`-Flag. In einem vertrauenswürdigen Netz ist das eine bewusste Abwägung; in einem Netz mit fremden Geräten (Gäste-WLAN, gemeinsam genutzte Etage) liest jedes davon mit.

### Betrieb im LAN und im Internet

Die Anwendung ist für beide Wege gleichzeitig gedacht und braucht dafür keine Konfiguration:

| Zugriffsweg | Sitzungscookie |
|---|---|
| `http://<IP>:5000` im LAN | ohne `Secure`-Flag — der Browser nimmt es über HTTP an |
| `https://<domain>` hinter Reverse Proxy | mit `Secure`-Flag — wird nur über HTTPS gesendet |

Grundlage ist `X-Forwarded-Proto`: Senden Sie den Header im Proxy mit, erkennt die Anwendung HTTPS selbst. Nginx-Beispiel:

```nginx
location / {
    proxy_pass http://127.0.0.1:5000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

Reicht Ihr Proxy den Header nicht durch, setzen Sie in der `.env` `SESSION_COOKIE_SECURE=true` (erzwingt das Flag) oder `false` (schaltet es ab). Beides ist ein Notbehelf — der saubere Weg ist der Header.

**Wichtig beim Betrieb hinter einem Proxy:** Der Produktionsserver (Waitress) reicht `X-Forwarded-*` durch, damit die Anwendung HTTPS erkennt. Ohne weitere Konfiguration darf **jeder** Client diese Header setzen — auch einer, der den Proxy umgeht. Tragen Sie deshalb die Adresse Ihres Proxys ein:

```env
# Nur dieser Proxy darf die Header setzen (IP oder CIDR)
TRUSTED_PROXY=172.17.0.1

# Oder: Header immer verwerfen (dann kein automatisches Secure-Flag,
# SESSION_COOKIE_SECURE=true setzen)
# CLEAR_UNTRUSTED_PROXY_HEADERS=true
```

Die Anwendung selbst sollte **nicht** direkt aus dem Internet erreichbar sein: Port 5000 gehört hinter den Proxy, nicht in die Firewall-Freigabe. Deshalb veröffentlicht die mitgelieferte Compose-Datei den Port nur auf `127.0.0.1`.

**Hinweis für Unraid-Nutzer:**
Wenn Sie die App auf Unraid betreiben, klonen Sie das Projekt idealerweise nach `/mnt/user/appdata/gefahrstoffverzeichnis`. Sie können die bestehende `docker-compose.yml` dann auch direkt in das "Compose Manager" Plugin von Unraid einbinden und den Stack (Container) über das Webinterface verwalten.
---

## 🔒 Sicherheit & Updates
*   **Daten sicher aktualisieren:** Die `.gitignore`-Datei schützt Ihre produktiven Daten. Führen Sie auf Ihrem Server bei Updates einfach `git pull` aus (oder nutzen Sie den Button im Admin-Menü). Ihre Datenbank (`gefahrstoffe.db`) und hochgeladenen Dokumente (`/uploads`) werden dabei nicht überschrieben.
*   **WICHTIG - Datenbank Migration nach Updates:** Nach größeren Versionsupdates kann es vorkommen, dass neue Tabellenspalten (wie z.B. für Gefahrenkategorien) zur App hinzugefügt wurden. Um "Internal Server Errors" nach dem Aktualisieren zu vermeiden, führen Sie das Migrationsskript aus:
    *   **Standard-Installation:** Führen Sie `python migrate_gefahrenkategorien.py` in Ihrem App-Verzeichnis aus.
    *   **Docker-Installation:** Führen Sie den Befehl innerhalb des laufenden Containers aus: `docker exec -it gefahrstoffe_app python /app/migrate_gefahrenkategorien.py`
*   **Produktivbetrieb:** `FLASK_SECRET_KEY` ist Pflicht — ohne ihn startet die Anwendung nicht. Die Docker-Installation startet bereits den WSGI-Server *Waitress*; bei einer Installation ohne Docker starten Sie `python run_prod.py` statt `flask run`.
*   **Sitzungsschlüssel rotieren, wenn er bekannt geworden ist.** Bis Oktober 2026 gab es im Quelltext einen Rückfallwert für `FLASK_SECRET_KEY`. Wer eine Installation aus dieser Zeit ohne eigene Variable betrieben hat, sollte den Schlüssel neu erzeugen (`openssl rand -base64 32`) und den Container neu starten — das beendet alle bestehenden Sitzungen. Das Löschen aus dem Code genügt nicht, weil der alte Wert in der Git-Historie öffentlich bleibt.
*   **Passwörter:** lokal gesetzte Passwörter brauchen mindestens 12 Zeichen (Registrierung, Benutzeranlage, Profil). Bestehende Konten sind davon nicht betroffen. Nach fünf Fehlversuchen ist die Anmeldung für 15 Minuten gesperrt.
*   **Verzeichnisdienst-Konten:** Wer sich über LDAP anmeldet, kann in der Anwendung kein lokales Passwort setzen — sonst liefe eine Sperre im AD ins Leere. Das Passwort wird ausschließlich dort geändert.
*   **Abhängigkeiten:** `requirements.txt` enthält Prüfsummen und wird mit `--require-hashes` installiert. Nach einer Änderung neu erzeugen:
    ```bash
    pip-compile --generate-hashes --no-annotate --output-file requirements.txt requirements.txt
    ```
*   **Basis-Image:** Das `Dockerfile` pinnt `python:3.11-slim` auf einen Digest. Sicherheitsupdates des Basis-Images kommen nur über einen neuen Digest herein — deshalb regelmäßig aktualisieren (Dependabot schlägt es vor).

## 📅 Changelog

Eine vollständige Liste aller Versionen und Änderungen finden Sie in der [CHANGELOG.md](CHANGELOG.md) Datei.
