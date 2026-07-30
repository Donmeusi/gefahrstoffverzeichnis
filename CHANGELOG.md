# Changelog

Alle nennenswerten Änderungen an diesem Projekt werden in dieser Datei dokumentiert.

### v3.7 – LDAPs, Schreibgeschützte Rolle, Schnell-Inventur & Aushang (Juli 2026)
* **LDAPs-Authentifizierung**: Vollständige Anbindung an Unternehmens-Directories (Active Directory & OpenLDAP) über sichere SSL/TLS-Socket-Verbindungen (`ldaps://` Port 636 / StartTLS). Automatische Anlegung neuer LDAP-Benutzer mit konfigurierbarer Standardrolle (`LDAP_DEFAULT_ROLE`).
* **Schreibgeschützte Rolle „Lesen“**: Neue feingranulare Benutzerrolle `lesen` für Betrachter. Leser sehen zugewiesene Bereiche, dürfen jedoch keine Daten bearbeiten, löschen, exportieren (Excel/PDF) oder Sicherheitsdokumente herunterladen.
* **📱 Schnell-Inventur-Modus**: Neue touch-optimierte Mobile-Checkliste (`/location/<id>/inventur`) zum schnellen Abhaken und Anpassen von Schrank-Lagermengen direkt vor Ort. Automatische Protokollierung im Audit-Log (`INVENTUR`) und Erfassung des Prüfdatums (`last_inventur_datum`).
* **🖨️ Schrank-Aushang & Druckansicht**: Neue A4-optimierte Druckseite (`/location/<id>/print`) für Schrank-Inhaltsverzeichnisse inkl. GHS-Piktogrammen, Mengenangaben, TRGS 510 Lagerklassen, Notfallhinweisen und QR-Code.
* **Selbstheilende Auto-Migration**: Das System prüft und aktualisiert die SQLite-Datenbank beim Anwendungsstart (`migrate_db.py`) vollautomatisch auf fehlende Spalten, um Serverfehler nach Updates zu verhindern.
* **DSB & IT-Dokumentation**: Neue ausführliche technische Systemdokumentation und Technisch-Organisatorische Maßnahmen (`DATENSCHUTZ_UND_TOM.md`) zur Vorlage beim Datenschutzbeauftragten (DSB).

### v3.6 – Clinical & Clean Design Update (Juli 2026)
*   **Neues UI-Theme**: Das gesamte Design wurde auf ein helles, aufgeräumtes "Clinical & Clean" Theme (Labor/Corporate) umgestellt. 
*   **Verbesserte UI**: Reines Weiß für Inhalts-Karten, tiefe Blau-Töne für primäre Aktionen, eine helle Navigationsleiste und weichere Schatten.

### v3.5 – Mobile & Responsive Update (Juli 2026)
*   **Vollständig Responsives Design**: Die Applikation wurde für die Nutzung auf Smartphones und kleineren Monitoren optimiert.
*   **Dynamische Tabellen**: Unwichtige Tabellenspalten (wie Standort, Menge, Dokumente) werden auf mobilen Geräten automatisch ausgeblendet, um horizontales Scrollen zu vermeiden.
*   **Flexible Layouts**: Suchleisten, Filter und Eingabe-Formulare (inkl. Buttons für Autofill & SDB-Upload) stapeln sich nun auf schmalen Bildschirmen sauber untereinander.
*   **Optimierte Modals**: Modal-Fenster für H- und P-Sätze sind nun in der Höhe begrenzt (`max-height`) und intern scrollbar, sodass sie auch auf Handys jederzeit bedienbar bleiben.

### v3.4 – Gefahrenkategorien & PubChem Optimierung (Juli 2026)
*   **Gefahrenkategorien (CLP)**: Neues Feld für CLP-Gefahrenkategorien (wie z.B. "Met. Corr. 1" oder "Skin Corr. 1A"). Diese können beim Auslesen eines Sicherheitsdatenblatts (SDB) komplett automatisch erkannt und über ein übersichtliches Modal bearbeitet werden.
*   **PubChem Autofill Update**: Die Automatik zum Abrufen von Daten anhand der CAS-Nummer aus der PubChem-Datenbank wurde signifikant verbessert. Es werden nun gezielt europäische Quellen (ECHA / Verordnung (EC) No 1272/2008) bevorzugt, um nur noch die tatsächlich in Europa relevanten GHS-Hinweise abzurufen (verhindert Widersprüche durch weltweite Aggregation).
*   **Aktualisierte P-Sätze**: Die Datenbank für die auswählbaren P-Sätze (Sicherheitshinweise) wurde direkt über *gefahrstoffdaten.de* auf den neusten Stand gebracht.

### v3.3 – QR-Codes, PubChem Autofill & Proxy-Support (Juli 2026)
*   **CAS-Nummer Autofill**: Neue Funktion, mit der sich Gefahrstoffe via PubChem-API anhand der CAS-Nummer automatisch ausfüllen lassen (inkl. Piktogramme, Signalwort, H- & P-Sätze).
*   **QR-Code Generierung**: Für jeden Standort (Unterbereich) kann nun lokal ein QR-Code für den Etikettendruck generiert werden. Beim Scannen öffnet sich die App direkt mit der vorgefilterten Inventarliste.
*   **Proxy-Support**: Integration der `ProxyFix` Middleware für den fehlerfreien Betrieb hinter Reverse-Proxies (wie Nginx/Apache) auf Subdomains.
*   **UI/UX KPI-Dashboard**: Neue Statistik-Kacheln auf der Startseite zur besseren Übersicht über Gesamtbestand, Standorte und abgelaufene Sicherheitsdatenblätter.
*   **Excel Export Styling**: Der Excel-Export formatiert nun automatisch die Spaltenbreiten und setzt fettgedruckte Spaltenüberschriften.

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
