# Changelog

Alle nennenswerten Änderungen an diesem Projekt werden in dieser Datei dokumentiert.

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
