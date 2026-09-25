# Changelog

Alle nennenswerten Änderungen an diesem Projekt werden in dieser Datei dokumentiert.

### v3.8 – Betriebsanweisung speicherbar, korrigierte Gebotszeichen (September 2026)
* **Betriebsanweisung wird dauerhaft gespeichert**: Die individuell angepassten Texte (Tätigkeit, H-Sätze, Schutzmaßnahmen, Verschütten, Brand, Erste Hilfe, Entsorgung) und die gewählten Gebotszeichen bleiben ab jetzt am Gefahrstoff erhalten. Bisher war die gesamte Seite ein Entwurf, der beim Neuladen verfiel — die App speicherte nur den Dateinamen der hochgeladenen BA-PDF, keinen Text. Zwei neue Spalten (`ba_texte`, `ba_gebotszeichen`), neue Route `/gefahrstoff/<id>/betriebsanweisung/speichern`, Knöpfe **Speichern** und **Zurücksetzen** (setzt auf die Standardwerte zurück).
* **Sicherheit**: Die gespeicherten Inhalte stammen aus `contenteditable`-Bereichen und werden mit `|safe` gerendert. Sie laufen deshalb serverseitig durch eine Tag-Whitelist (Attribute werden verworfen), damit kein `<script>`, `onerror=` oder `style=` in die Datenbank und von dort in den Browser eines Administrators gelangen kann. Die Rolle `lesen` kann nicht speichern und sieht die Knöpfe nicht.
* **Arbeitsbereich und Stoffname werden bewusst nicht gespeichert**: Beide kommen live aus der Datenbank. Ein gespeicherter Text würde eine spätere Umbenennung des Stoffs stillschweigend verdecken.
* **Auswahlfenster begrenzt (auf 6)**: Die Icon-Spalte ist 100 px breit. Die Grenze wurde **empirisch** ermittelt, nicht geschätzt: mit sechs Zeichen passt die Betriebsanweisung auch bei 13 langen P-Sätzen noch auf eine A4-Seite. Dazu ein Zähler im Auswahlfenster und die Sperre der noch freien Kästchen. Die Zeichen werden 38 px groß in zwei Spalten umgebrochen.
* **⚠️ Gebotszeichen-Beschriftungen korrigiert**: Fünf der elf Bezeichnungen passten nicht zur tatsächlichen Grafik. `M002` hieß „Gehörschutz benutzen“ (zeigt aber „Anleitung beachten“), `M003` hieß „Augenschutz benutzen“ (zeigt Gehörschutz), `M004` hieß „Schutzhelm benutzen“ (zeigt Augenschutz), `M024` hieß „Hautschutzcreme benutzen“ (zeigt „Diesen Weg benutzen“). „Schutzhelm“ und „Hautschutzcreme“ gehören zu `M014`/`M022`, die hier gar nicht vorhanden sind. Alle Bezeichnungen wurden gegen die Grafik und die offizielle ISO-7010-Liste geprüft. Die Vorbelegung wechselt dadurch von `M003` auf `M004` (Augenschutz) und behält damit die ursprüngliche Absicht bei.
* **Herkunft der Symbole dokumentiert**: `static/symbols/SOURCES.md` hält pro Datei fest, was sich belegen lässt. Die Behauptung des Vorgänger-Commits, es seien durchgehend offizielle Wikimedia-Commons-Dateien, ist für 12 der 13 Dateien nicht belegt: elf M-Dateien und `E003.svg` tragen keinerlei Herkunftsangabe, `F001.svg` hat einen leeren RDF-Block ohne Lizenzfeld. Nur für `F001.svg` ist Commons als Herkunft plausibel. Die Lizenzfrage ist damit **offen** und vor einer Veröffentlichung zu klären.
* **Formular ohne Umbau des Templates**: Die editierbaren Bereiche werden erst beim Absenden per JavaScript in ein leeres `<form>` eingehängt, die Knöpfe hängen über `form="ba-form"` daran. So musste kein Wrapper um das Dokument gelegt und nichts umindentiert werden.
* **Die Betriebsanweisung füllt jetzt die ganze Seite, mit dem roten Rahmen direkt an den Feldern.** Der innere Abstand des Containers ist weg — der Rahmen schließt unmittelbar an Kopftabelle und Abschnitte an (die Zellen behalten ihren eigenen Innenabstand). Außen bleiben 5 mm zur Papierkante, das liegt an der Grenze des bedruckbaren Bereichs und wird von praktisch jedem Drucker vollständig gedruckt. Im Druck ist der Container eine Flex-Spalte über die volle Seitenhöhe, die Abschnitte (`flex: 1 1 auto`) teilen sich den Rest — dadurch bleibt unten kein Weißraum. Die Streckung greift nur im Druck, die Bildschirmansicht bleibt ein normales Fließlayout.
* **Der Ausdruck ist genau eine Seite, ohne Kopf- und Fußzeile.** Drei Ursachen, alle nachgemessen (Seite rendern, mit Chrome nach PDF drucken, Seiten zählen):
  1. `.ba-container { page-break-after: always }` hängte nach jedem Druck eine leere Seite an (mit Regel zwei Seiten, ohne eine).
  2. Das Padding lag auf `body`. Dadurch reichte die body-Box über die Seitenhöhe hinaus und Chrome hängte eine leere zweite Seite an — auch bei 10 mm, obwohl der Inhalt selbst passte. Der äußere Abstand kommt jetzt aus `body { padding: 5mm; height: 100%; box-sizing: border-box }`. Zwei Fallen dabei, beide nachgemessen: das `border-box` ist nötig, sonst rechnet die Prozentangabe gegen die volle Seite und der Rand kommt obendrauf; und das Padding darf **nur auf `body`** stehen, nicht auf `html, body` — sonst wird es zweimal angewendet und der Rand doppelt so breit (5 mm ergab 10 mm).
  3. `line-height` von 1.15 auf 1.05. Ohne Schriftverkleinerung passt damit auch eine Betriebsanweisung mit 13 langen P-Sätzen und sechs Gebotszeichen auf eine Seite.
* **Kopf- und Fußzeile des Browsers**: `@page { margin: 0 }` unterdrückt sie, weil Chrome sie nur zeichnet, wenn ihm ein Seitenrand zur Verfügung steht. Verifiziert: mit `margin: 10mm` druckt Chrome „25.09.26, 15:29 Betriebsanweisung - Aceton“, die `file:///`-URL und „1/1“ mit, mit `margin: 0` nichts davon. Der äußere Rand kommt deshalb aus dem Padding von `html, body`, nicht aus `@page`.
* **Grenze**: Ab etwa 15 langen P-Sätzen braucht die Betriebsanweisung legitim eine zweite Seite. Eine erzwungene Ein-Seiten-Ausgabe würde die Schrift verkleinern — bei einem Sicherheitsdokument bewusst nicht gemacht.
* **Tests**: `test_ba_persistenz.py` deckt Sanitisierung, Zusammenführen bei Teil-Submits, Rechteprüfung, Obergrenze und Zurücksetzen ab (21 Tests).

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
