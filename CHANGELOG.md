# Changelog

Alle nennenswerten Änderungen an diesem Projekt werden in dieser Datei dokumentiert.

### v3.31 – Amtliche Einstufung aus Anhang VI der CLP (Oktober 2026, APP_VERSION 2.5.2)

* **Neu `echa_anhang_vi.json` + `echa_anhang_vi.py`:** die harmonisierte Einstufung nach Anhang VI der CLP-Verordnung, 4.643 Einträge, lokal und ohne Netzzugriff. Erzeugt von `werkzeuge/echa_import.py` aus der ECHA-Tabelle.
* Der Autofill nimmt H-Sätze, Gefahrenkategorien, Piktogramme und Signalwort jetzt von dort, wenn der Stoff harmonisiert eingestuft ist. P-Sätze weiter aus PubChem — die sind nicht harmonisiert, sondern werden vom Hersteller gewählt.
* Das Feld **Gefahrenkategorien** wird damit erstmals automatisch gefüllt.
* Der Knopf sagt, woher die Daten kommen: **„Fertig! (amtlich)"** aus Anhang VI, **„Fertig! (abgeleitet)"** aus den H-Sätzen, wenn der Stoff dort nicht steht.
* **Warum die amtliche Quelle besser ist als die Ableitung:** Das Piktogramm folgt nach CLP aus der **Gefahrenklasse**, nicht aus dem Gefahrenhinweis. Chlorwasserstoff ist „Press. Gas" und trägt deshalb GHS04 — aus H331 und H314 allein lässt sich das nicht herleiten. Die Ableitung bleibt für selbsteingestufte Stoffe.
* ⚠️ **Die ECHA-Datei führt auch noch nicht geltendes Recht** (ATP23 gilt ab 01.02.2027). Der Ausleser wählt je Index-Nummer die letzte Fassung mit Geltungsbeginn ≤ Stichtag; ein Test sichert ab, dass keine künftige Fassung in den Daten landet.
* Mehrstoff-Einträge (166) sind unter jeder ihrer CAS-Nummern auffindbar, 475 Einträge ohne CAS über die EG-Nummer. Über die EG-Nummer erreichbar ist zum Beispiel **„Salzsäure … %" (017-002-01-X)** — die Lösung hat einen eigenen Eintrag ohne CAS, der über 7647-01-0 nicht gefunden würde.
* Fällt Wikidata aus, wird die dann englische Bezeichnung (amtlich oder aus PubChem) nur nach Rückfrage übernommen statt still eingetragen.
* Neu: `test_echa_anhang_vi.py` (13 Tests). Gesamtstand 210.

### v3.30 – Deutsche Bezeichnungen und Piktogramme aus der CLP (Oktober 2026, APP_VERSION 2.5.1)

* Die Autovervollständigung holt den Stoffnamen jetzt deutsch aus Wikidata (CAS-Nummer → P231). PubChem kennt nur englische Namen („formaldehyde", „Isopropanol").
* Bei mehreren Treffern erscheint ein Auswahldialog (Salzsäure: „Chlorwasserstoff" oder „Salzsäure"); der Treffer mit passender PubChem-Kennung steht vorn. Schlägt Wikidata fehl, bleibt der PubChem-Name — die Rückfrage sagt dann, dass er nicht übersetzt ist.
* **Neu `piktogramme.py`:** Zuordnung H-Code → Piktogramm und Signalwort nach Anhang I/V der CLP-VO, alle 91 H-Sätze inklusive der zwölf Kombinationssätze.
* Piktogramme und Signalwort werden daraus **abgeleitet** statt von PubChem übernommen — dort mischen sich zu einer CAS-Nummer EU- und Nicht-EU-Quellen (zu Salzsäure auch japanisches Recht).
* Der SDB-Parser nutzt dieselbe Ableitung; seine frühere `if/elif`-Kette lieferte je H-Satz nur **ein** Piktogramm (H241 trägt GHS01 und GHS02) und kannte 31 Codes nicht.
* **Behoben:** `EUH014` wurde als H-Satz `H014` gelesen — im Autofill und im Parser.
* **Behoben:** `body` behielt über `animation: fadeIn … both` dauerhaft ein `transform`. Das macht ein Element zum Bezugsrahmen für `position: fixed`; beide Dialoge richteten sich am Dokument statt am Fenster aus und öffneten außerhalb des sichtbaren Bereichs.
* Cache-Buster an `autofill.js` und `hp_modal.js` ergänzt (er fehlte).
* Neu: `test_piktogramme.py` (21 Tests), `test_wikidata.py` (8). Gesamtstand 197.

### v3.29 – Layout nutzt große Schirme (Oktober 2026, APP_VERSION 2.5.0)

* Inhaltsrahmen wächst mit dem Fenster bis 1600 px (vorher fest 1280 px).
* Formularkarten 640 → 900 px, Systemansicht 800 → 900 px.
* add.html und edit.html: Breitenbegrenzung ergänzt (hatten bisher gar keine).
* Navigation: verdichtet 1200–1399 px, volle Schrift ab 1400 px.
* Neu: werkzeuge/seitenbreiten.py; navbreiten.py nimmt Fensterbreiten als Argument.
* Unverändert mit Absicht: Login- und Fehlerseiten bleiben schmal, .data-table--dense bleibt.

### v3.28 – Hauptmenü gebündelt (Oktober 2026, APP_VERSION 2.4.0)

* Menü mit elf Einträgen lief über den Rand; die Leiste sitzt im gedeckelten `.container` (1280 px).
* „Verwalten ▾" bündelt Standorte, Benutzer und Historie; Leser bekommen den Auslöser gar nicht.
* Konto-Menü „● benutzername ▾" bündelt Profil und Logout; der Freigabe-Zähler bleibt am Auslöser sichtbar.
* Beide sind `<details>`-Elemente; das Skript liegt in `base.html` und bedient auch die Spaltenauswahl.
* Eine Schwelle statt zwei: 1200 px (vorher 1290 und 1610); die volle Fassung ist entfallen.
* Nebenbei behoben: ungeschützter Menüknopf in `base.html` (TypeError auf Anmeldeseiten).
* Aufgeräumt: `.nav-profile`/`.nav-bubble` entfallen; neues Werkzeug `werkzeuge/navbreiten.py`.

### v3.27 – Mengenschwellen-Prüfung im Formular (Stufe 3, Oktober 2026)

* Nach `/add` und `/edit` meldet die Anwendung überschrittene Kleinmengen oder erreichte Zusatzschwellen als Hinweis; sie blockiert nichts.
* Live-Vorschau im Formular über den neuen Endpunkt `/api/mengenschwellen_vorschau` (prüft ungespeicherte Werte mit dem Bestand).
* Ohne JavaScript bleibt die Box verborgen; verbindliche Prüfung bleibt `/mengenschwellen`.
* Der Endpunkt verlangt Schreibrecht; Prüffehler stören das Speichern nie.
* Für Gase entfällt der LGK-Rückfall (ohne H-Sätze wurden sie doppelt gemeldet).
* Neuer Test (jetzt 167); der Skript-Verweis trägt den `APP_VERSION`-Cache-Buster.
* Bewusst nicht gebaut: eine Admin-Seite zum Bearbeiten der Schwellen (Werte bleiben im Quelltext).

### v3.26 – Mengenschwellen-Prüfung nach TRGS 510 (Oktober 2026)

* Neue Prüfung: ab welcher Menge eine Lagerung außerhalb eines Lagers unzulässig ist (zweite Hälfte der TRGS 510).
* Bezugsebene ist der Lagerabschnitt; Zuordnung primär über H-Sätze, Lagerklasse nur als Ersatz.
* Zahlen an einer Stelle (`mengenschwellen.py`, Tabelle `SCHWELLEN`), jede mit Quelle; gegen Tabelle 1 der TRGS 510 abgeglichen.
* Erfasste Gruppen u. a. (kg): entzündbare Flüssigkeiten 20/100, Feststoffe 200, akut toxische/CMR 50, Gase 0,5–50; Gesamtgrenze 1.500 je Brandabschnitt.
* Ohne Dichte gilt 1 L = 1 kg; „Stück" zählt nicht mit. Arbeitshilfe, kein Ersatz für die Gefährdungsbeurteilung.
* Neue Seite `/mengenschwellen` samt Warnhinweis auf der Stoff-Detailseite und Symbol in der Übersicht; Test (jetzt 158).

### v3.25 – Neues Erscheinungsbild: „Amt & Akte" (Oktober 2026)

* Neuer eigenständiger Entwurf „Amt & Akte" (drei Richtungen standen zur Wahl).
* Schrift: Source Sans 3 (Fließtext), Source Serif 4 (Überschriften), lokal ausgeliefert über `static/fonts/schriften.css`; Zahlen mit `tabular-nums`.
* Farbe: Papierweiß statt Reinweiß, gedecktes Marine als Akzent, gedämpfte Statusfarben.
* Form: Radien 6–12 → 2–3 px, Schlagschatten und Farbverläufe entfallen, Symbole ohne Kachel, Abzeichen eckig.
* Dunkelmodus auf dunkles Papier umgestellt.
* Unberührt: Druckansichten behalten ihre eigene Gestaltung.
* Navigations-Schwellen mitgezogen (1375/1785 → 1290/1610).

### v3.24 – Nicht freigegebene CMR-Stoffe waren für den Administrator unsichtbar (Oktober 2026)

* Fehler: `get_gefahrstoff_query()` filterte `is_approved` für jeden weg; der Freigabe-Link lief in „Keine Berechtigung, diesen Gefahrstoff anzusehen".
* Administrator und Moderator sehen jetzt nicht freigegebene Stoffe; für reguläre Benutzer bleiben sie bis zur Freigabe unsichtbar.
* Kennzeichnung ergänzt: Abzeichen „Wartet auf Freigabe" in der Detailansicht, Sanduhr-Symbol in der Übersicht.
* Das Abzeichen ist zugleich der Freigabe-Knopf; danach bleibt die Detailseite stehen.
* Neuer Test (jetzt 120).

### v3.23 – Aussehens-Runde: Feinschliff und umschaltbarer Dunkelmodus (Oktober 2026)

* Dunkelmodus per Kopfzeilen-Knopf umschaltbar; Wahl in `localStorage`, sonst Systemvorliebe, vor dem Laden gesetzt.
* Druckansichten (Betriebsanweisung, Standortaushang, QR-Aushang) bleiben in beiden Modi hell — bewusst.
* Eigenes Token für Text und Rahmen des Primär-Blaus; `--bg-subtle` war weiß wie eine Karte.
* Zusammenlagerungshinweis stand als Zeile; Zebra-Tabellen, markierter Menüpunkt, 404/500 gestylt.
* Standortverwaltung: ein Formular mit Umschalter „Bereich/Unterbereich" statt zwei Karten, Liste als Baum.
* Handy bis 600 px: Zusatzspalten aus, Knöpfe nur als Symbol; Schwellen 1375/1785 px.
* Sieben nie benutzte oder doppelte Farbvariablen entfernt (`--info`, `--info-light`, `--gold`).

### v3.22 – Informationsarchitektur der Startseite (Oktober 2026)

* Aus drei Kennzahl-Kacheln wurde eine; die Zahlen stehen jetzt in der Unterzeile des Seitentitels.
* Filter links, Ansichtssteuerung (Tabelle/Kacheln, Spaltenauswahl) rechts — vorher umgekehrt.
* „Neuer Gefahrstoff" ist der einzige kräftige Knopf; Excel und PDF sind neutrale Umrissknöpfe.
* Spaltenauswahl: sechs Spalten der Übersicht ausblendbar, „Name" bleibt immer sichtbar; Wahl im Browser gemerkt.
* Die Fristen-Kachel ist entfallen; die Fristenzahl steht nur noch am Menüpunkt.

### v3.21 – Barrierefreiheit und Kohärenz der Oberfläche (September–Oktober 2026)

* Sprungmarke „Zum Inhalt springen", `scope="col"` an allen Tabellenköpfen, Fokusringe (`:focus-visible`), versteckte Beschriftung an jeder Tabelle.
* Piktogramm-Auswahl jetzt mit der Tastatur bedienbar (Kästchen standen auf Größe 0).
* `--text-light` war als Text zu blass (2,96:1) und steht jetzt bei 4,55:1.
* Alle 14 Seiten von Inline-Stilen auf Klassen umgestellt: 445 → 12 (Rest absichtlich); eigene Farbwerte 49 → 0; 13 Schriftgrößen auf drei Stufen vereinheitlicht.
* Vier nie definierte Farbvariablen (`--dark`, `--glass-border`, `--bg-color`, `--text`) und mehrere nie definierte Klassen entfernt; `date` und `url` in die globale Feldregel aufgenommen.

### v3.20 – Produktionsserver in beiden Startwegen, Debugger standardmäßig aus (September 2026)

* Container startete den Entwicklungsserver (`exec flask run` in `docker-entrypoint.sh`); jetzt `exec python run_prod.py`.
* `main.py` startete mit `app.run(debug=True)` den Werkzeug-Debugger; jetzt aus, nur mit `FLASK_DEBUG=1` aktiv.
* `run_prod.py` legt fehlende Tabellen an (`db.create_all()`); neue Spalten ergänzt `migrate_db.py`.
* `FLASK_ENV=production` im nativen Startweg ergänzt (setzt `SESSION_COOKIE_SECURE`); `run_prod.py` liest `PORT`/`HOST`.
* TOM: Risiko „Container startet den Entwicklungsserver" entfallen, zehn Risiken neu nummeriert; `DATENSCHUTZ_UND_TOM.md` nennt wieder Waitress.
* Nicht geändert: Abhängigkeiten werden bei jedem Containerstart installiert (R-6).

### v3.19 – Substitutionsprüfung als Frist (September 2026)

* Neue Spalte `substitution_geprueft_am` am Gefahrstoff: Datumsfeld in Erfassung/Bearbeitung, Datum in der Detailansicht, Eintrag in der Fristenliste.
* Drei getrennte Zustände: `fehlt` (keine Prüfung), `ohne_datum` (Prüfung ohne Datum), `faellig` (älter als das Intervall).
* `SUBSTITUTION_FRIST_MONATE = 24` ist interne Konvention, keine Vorschrift; „nie geprüft" wird immer ausgewiesen.
* `FRISTEN_RANG` jetzt nach `(Kategorie, Stufe)` geschlüsselt; Kopfbereich-Zählung filtert zusätzlich nach Kategorie (zwei Tests).
* „Noch nie geprüft" als Zahl im Kopfbereich, nicht als Zeile; die Kachelzahl bleibt die Zahl der Zeilen.
* Migration: eine Zeile in `migrate_db.py` (31 → 32 Spalten); `test_fristen.py` jetzt 33 Tests, gesamt 119.

### v3.18 – Fristen: aus der toten Kennzahl wird eine Arbeitsliste (September 2026)

* Neue Seite `/fristen` als Arbeitsliste, dringlichste zuerst, Sprung zur Aktion (`/edit/<id>`, `/location/<id>/inventur`); Kachel „Veraltete SDBs" als Einstieg.
* Entscheidung fällt in `sdb_status()` in `main.py`; Template und Kachel lesen nur das Ergebnis; neu: `fehlt` und `ohne_datum`.
* Inventur: Standort fällig, wenn sein jüngstes `last_inventur_datum` älter als 12 Monate ist oder nie inventarisiert wurde; Frist = Maximum.
* Ohne neue Tabelle und Migration; Schwellen als Konstanten (`SDB_FRIST_JAHRE`, `SDB_DRINGEND_JAHRE`, `INVENTUR_FRIST_MONATE`).
* Navigationseintrag „Fristen" mit Zähler-Badge; Schwellen 1340/1750 px; `APP_VERSION` 2.0.3.
* Neue Testdatei `test_fristen.py` (17 Tests), gesamt 103.

### v3.17 – Einträge gelöschter Benutzer bleiben zuordenbar; drei Datenbank-Sicherheitsfehler (September 2026)

* Benutzerlöschung setzte `user_id` aller Einträge auf NULL — danach nicht mehr zuordenbar.
* Fix: `passive_deletes=True` an der `audit_logs`-Beziehung; ID bleibt, `log.user` ist None. Keine Schemaänderung.
* Keine Namensspalte: `DATENSCHUTZ_UND_TOM.md` Abschnitt 5 sagt pseudonymisierte Aufbewahrung zu.
* Testdateien löschten die echte DB: `:memory:` in `setUp` wirkungslos, `db.drop_all()` traf `data/gefahrstoffe.db`.
* Fix: `testkonfiguration.py` setzt `APP_DATA_DIR` auf `/tmp`, vor `main` importiert.
* `migrate_db.py` ignorierte `APP_DATA_DIR` und migrierte eine fremde Datei; Fix `get_db_path()` mit Vorrang.
* 86 Tests; Dokumentation ergänzt.

### v3.16 – Die letzten drei Lücken in der Systemhistorie (September 2026)

* Passwortänderung im eigenen Profil (`/profile`) erzeugt `USER_PASSWORD` — nur das Ereignis, nie das Passwort.
* Der lokale Login wird protokolliert; bisher nur der LDAP-Login.
* `SYSTEM_UPDATE` für `/admin/system/update_repo` (neue Repository-URL) und `/admin/system/do_update` (Ziel-Branch).
* Der Update-Eintrag entsteht im Request, nicht im Update-Thread (der beendet den Prozess mit `os._exit(0)`).
* Anzeige: kein „System #None" ohne `entity_id`; Beschriftungen „Passwort geändert" und „Systemänderung".
* Bewusst nicht protokolliert: fehlgeschlagene Anmeldungen (keine Sperre gegen Passwortraten) und abgewiesene Rechteprüfungen.
* Fünf neue Tests in `test_audit_log.py` (21); Gesamtstand 84.

### v3.15 – Anlegen von Standorten wird protokolliert (September 2026)

* Beide Zweige von `/locations` (`add_bereich`, `add_unterbereich`) schreiben `CREATE` mit `entity_type` `Bereich` bzw. `Unterbereich`; v3.12 hatte nur das Löschen.
* `standort_text()` nennt jetzt die vollständige Elternkette; verschachtelte Standorte wie `Unterbereich.get_full_path()`.
* Die Schleife über die Eltern ist auf 20 Ebenen begrenzt (Zyklusschutz); `get_full_path()` im Modell hat diesen Schutz nicht.
* Drei neue Tests in `test_audit_log.py` (16): Bereich, Unterbereich mit Pfad, verschachtelter Unterbereich mit Elternkette.
* Gesamtstand: 79 Tests.
* Weiterhin nicht protokolliert: Passwortänderung im Profil, `/admin/system/update_repo`/`do_update`, lokaler Login.

### v3.14 – Anlegen und Bearbeiten prüfen den Ziel-Standort vollständig (September 2026)

* `/add` und `/edit` nutzen jetzt `ziel_standort_pruefen()` wie `/move` und `/copy`; die zuvor inline geschriebene Prüfung war unvollständig.
* Eine ID ohne zugehörigen Unterbereich wurde übernommen und blieb als toter Verweis in der Datenbank; wird jetzt mit „Der gewählte Ziel-Standort existiert nicht." abgelehnt.
* Ein nicht numerischer Wert wurde stillschweigend zu `None` — der Stoff entstand ohne Standort; jetzt Meldung „Ungültiger Ziel-Standort."
* Verhaltensänderung: Ein unsinniger Wert führt zu einer Fehlermeldung statt zu einem Datensatz ohne Standort; reguläre Formulare sind nicht betroffen.
* Sechs neue Tests in `test_gefahrstoff_operationen.py` (16); Gesamtstand 76 Tests.

### v3.13 – Kopieren verliert keine Daten mehr, Verschieben prüft das Ziel (September 2026)

* Die Kopie umging die CMR-Freigabe: `copy_stoff` setzte `is_approved` nicht, sie war sofort sichtbar; jetzt `is_approved = not is_cmr_stoff(h_saetze)` wie `/add`.
* Die Kopie verlor `lagerklasse` und `gefahrenkategorien` (Grundlage der TRGS-510-Warnungen); beide werden jetzt mitkopiert.
* `/move` und `/copy` prüften den Ziel-Standort nicht (fremder Bereich per Request möglich); beide nutzen jetzt `ziel_standort_pruefen()`.
* Die Prüfung lehnt ein Ziel ohne existierenden Unterbereich ab; leer bleibt „ohne Standort".
* Testdatei `test_gefahrstoff_operationen.py` (10 Tests); Gesamtstand 70.
* Nicht mitkopiert mit Absicht: `ba_texte`/`ba_gebotszeichen` (doppelte `ba_nummer`) und `ba_unterschrift`.

### v3.12 – Verschieben, Kopieren und Standort-Löschungen protokolliert (September 2026)

* `move_stoff`, `copy_stoff`, `delete_bereich` und `delete_unterbereich` schreiben jetzt Audit-Einträge (vier Lücken geschlossen).
* Neue Aktionen `MOVE` und `COPY`, dazu `DELETE` mit `entity_type` `Bereich`/`Unterbereich`.
* Verschieben protokolliert alten und neuen Standort, Kopieren die Quelle; Löschen nennt Folgen (Unterbereiche, standortlose Gefahrstoffe).
* Namen werden vor dem Löschen gesichert (Bereich/Unterbereich/Benutzer).
* Neue Hilfsfunktion `standort_text()` für Klartext-Standorte statt `get_full_path()`; verträgt `None`.
* `MOVE`/`COPY` erhalten Beschriftungen und Symbole in `audit_logs.html`; vier neue Tests (`test_audit_log.py`, jetzt 13).
* Bewusst weiterhin nicht protokolliert: Anlegen von Bereichen, Passwortänderung, `/admin/system`-Updates, lokaler Login.

### v3.11 – Benutzerverwaltung wird protokolliert (September 2026)

* Benutzerverwaltung schrieb bis hierher keine Einträge; jetzt fünf Ereignisse `USER_CREATE`, `USER_UPDATE`, `USER_ROLE`, `USER_BEREICHE`, `USER_DELETE`.
* Rollenwechsel mit alter und neuer Rolle, Bearbeiten nur mit geänderten Feldern, Löschen mit Name und Rolle; ohne Änderung steht „Ohne inhaltliche Änderung".
* Passwörter nie im Klartext, nur „Passwort neu gesetzt" (ein Test hält das fest).
* Fehler behoben: `register` rief `log_audit_event` mit falschen Argumenten auf; die Funktion nimmt jetzt ein optionales `user_id` entgegen.
* `audit_logs.html`: neue Aktionen sowie `LOGIN`, `APPROVE`, `REJECT`, `INVENTUR` mit deutschen Beschriftungen und Symbolen.
* Neue Testdatei `test_audit_log.py` (9 Tests); Gesamtstand 56 Tests.
* Wort „manipulationssicher" in `HANDBUCH.md` und `README.md` entfernt.

### v3.10 – Rechteprüfung korrigiert, Administrator-Schutz an die Rolle gebunden (September 2026)

* `delete_user` und `locations` prüften als einzige Stellen `role == 'benutzer'` statt `role in ('benutzer','lesen')`: die Rolle „Lesen" konnte Benutzer und Administratoren löschen.
* Der Zweig `action=add_bereich` prüfte keine Berechtigung und ist jetzt von der Prüfung am Routenanfang erfasst.
* Neue Prüfung `is_last_admin()` schützt den letzten Administrator anhand der **Rolle** statt am Namen `admin` (in `set_role`, `edit_user`, `delete_user`).
* Moderatoren können Administratoren nicht mehr verwalten (Zusatzprüfung `not current_user.is_admin and user.role == 'admin'`).
* Fünf Regressionstests in `test_ldap_and_roles.py` (jetzt 9 Tests).
* Nicht Teil dieser Änderung: `FLASK_SECRET_KEY` fällt weiterhin auf einen Standardwert im Quelltext zurück; `docker-compose.yml` setzt sie nicht.

### v3.9 – Keine externen CDNs mehr, responsiv auf allen Breiten (September 2026)

* Keine externen Ressourcen mehr (base/ba_print/location_print/print_qr): Google Fonts und Font Awesome kamen zuvor von Dritten.
* Inter und Font Awesome 6.4.0 liegen unter `static/fonts/` und `static/vendor/font-awesome/`; Lizenzen/SHA-256 in `static/vendor/SOURCES.md`.
* Der tote Arial-Aufruf in `ba_print.html` entfällt; `APP_VERSION` auf 2.0.2 (Cache-Buster für `style.css`).
* Navigation überlief 901–1465 px: Zwischenbereich 1240–1500 px verdichtet, unter 1240 px Hamburger-Menü.
* Überläufe behoben via `min-width: 0`, `flex-wrap: wrap`, `overflow-wrap`; `.table-responsive` auch in `audit_logs.html`, `betriebsanweisungen.html`, `sicherheitsdatenblaetter.html`.
* `ba_print.html` erhält `viewport`-Meta und Scrollbereich; `print_qr.html`/`location_print.html` korrigiert; Ausdruck unverändert.

### v3.8 – Betriebsanweisung speicherbar, korrigierte Gebotszeichen (September 2026)

* Betriebsanweisung dauerhaft gespeichert: angepasste Texte (Tätigkeit, H-Sätze, Schutzmaßnahmen, Verschütten, Brand, Erste Hilfe, Entsorgung) und gewählte Gebotszeichen bleiben am Gefahrstoff. Drei neue Spalten `ba_texte`, `ba_gebotszeichen`, `ba_unterschrift`; neue Route `/gefahrstoff/<id>/betriebsanweisung/speichern`; Knöpfe **Speichern** und **Zurücksetzen**.
* Gespeicherte `contenteditable`-Inhalte laufen serverseitig durch eine Tag-Whitelist (Attribute verworfen); die Rolle `lesen` kann nicht speichern.
* Bewusst nicht gespeichert: Arbeitsbereich und Stoffname — beide kommen live aus der Datenbank.
* Unterschrift: zeichnen (PNG) oder Name eintragen („gez. M. Mustermann"); streng geprüft, nur `data:image/png;base64,` (geprüft, Länge begrenzt) oder reiner Name (normalisiert, 80 Zeichen), `svg+xml` verworfen. Inhalt **nicht** im Audit-Log, dort nur „Unterschrift gesetzt"/„entfernt".
* Unterschriftsbild echt geprüft (muss sich als PNG lesen lassen, PIL); eigener Meldungsblock auf der BA-Seite (nur am Bildschirm).
* Fehler behoben — Nummernfeld nicht bearbeitbar (leeres `<span>` hat Breite 0): leere inline-Eingabefelder bekommen Mindestgröße; „Nummer" wird über die bestehende Feldliste gespeichert (kein neues Datenbankfeld).
* Gebotszeichen-Beschriftungen korrigiert: fünf von elf passten nicht zur Grafik (`M002`, `M003`, `M004`, `M024`); Vorbelegung wechselt von `M003` auf `M004`. `M009` und `M013` bleiben bewusst vom amtlichen Wortlaut abweichend.
* `M014` (Kopfschutz) und `M022` (Hautschutzmittel) ergänzt; `M002.svg` entfernt (CC BY-SA 3.0, einzige nicht gemeinfreie Datei); `M024.svg` nur aus der Auswahl entfernt (gemeinfrei). Auswahl umfasst 11 Zeichen.
* Herkunft der Symbole: `static/symbols/SOURCES.md` mit SHA-256 und Quell-URLs; alle Dateien byte-identisch mit den Commons-Originalen.
* Auswahlfenster auf 6 Zeichen begrenzt, mit Zähler und Sperre freier Kästchen; Zeichen 38 px groß in zwei Spalten.
* Druck auf genau eine Seite: `page-break-after` entfernt, Padding auf `body` (5 mm, `border-box`), `line-height` 1.05, `@page { margin: 0 }` unterdrückt Kopf-/Fußzeile; Abschnitte wachsen proportional zum Inhalt.
* Formular ohne Template-Umbau (JS hängt editierbare Bereiche beim Absenden in ein `<form>`, Knöpfe via `form="ba-form"`); Tests: `test_ba_persistenz.py` (21 Tests).

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
