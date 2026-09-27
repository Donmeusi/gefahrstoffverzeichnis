# 🛡️ Technisch-Organisatorische Maßnahmen (TOM)

**Gefahrstoffverzeichnis — Webanwendung zur Gefahrstoffverwaltung**

**Stand: 27. September 2026**

> **Dokumententyp:** Technisch-Organisatorische Maßnahmen nach Art. 32 DSGVO,
> gegliedert nach dem in der deutschen Datenschutzpraxis üblichen Katalog.
> **Zielgruppe:** Datenschutzbeauftragte, IT-Administration, Informations-
> sicherheitsbeauftragte.
> **Ergänzendes Dokument:** `DATENSCHUTZ_UND_TOM.md` (Zweckbestimmung,
> Datenkategorien, Löschkonzept, Rechtsgrundlagen).

**Wie dieses Dokument zu lesen ist:** Jede Maßnahme steht mit ihrer
**Umsetzung** und ihrem **Status**. Wo eine Angabe geprüft wurde, steht das
dabei. **Abschnitt 9 listet die offenen Punkte** mit Risiko und Aufwand — ein
TOM, das nur Erfülltes nennt, wäre wertlos.

---

## 1. Gegenstand, Geltungsbereich und Systemabgrenzung

**Gegenstand** ist die Anwendung *Gefahrstoffverzeichnis* selbst: der Quelltext,
die von ihr verarbeiteten Daten und die Betriebsartefakte, die das Repository
mitliefert. **Nicht Gegenstand** sind die Infrastruktur des Betreibers
(Serverraum, Netz, Reverse Proxy, Betriebssystem, Virtualisierung) und die
Organisation des Betreibers (Zutrittsregelungen, Schulungen, Verträge). Beides
ist Voraussetzung dafür, dass die hier beschriebenen Maßnahmen greifen, und in
der eigenen TOM-Dokumentation des Betreibers zu ergänzen.

| | |
|---|---|
| **Quelltext** | öffentliches Repository (`github.com/Donmeusi/gefahrstoffverzeichnis`) |
| **Technik** | Python 3.11, Flask, SQLAlchemy, SQLite, Jinja2 |
| **Betriebsart laut Auslieferung** | Container (Docker Compose) oder native Ausführung |
| **Verantwortlicher** | *[vom Betreiber zu ergänzen]* |

**Systemgrenze:** Die Anwendung verarbeitet Daten ausschließlich in einer
SQLite-Datei und einem Upload-Verzeichnis im Datenverzeichnis (`APP_DATA_DIR`).
Es gibt keine Mandantentrennung und keine Schnittstelle zu Fremdsystemen —
mit einer Ausnahme (Abschnitt 5.3).

---

## 2. Verarbeitete Daten und Schutzbedarf

Die vollständige Aufstellung steht in `DATENSCHUTZ_UND_TOM.md`, Abschnitt 2.
Für die Maßnahmebewertung genügt diese Einordnung:

| Datenkategorie | Schutzbedarf | Begründung |
|---|---|---|
| Benutzername, Rollen, Bereichszuweisungen | **normal** | interne Kennungen, kein Außenbezug |
| Passwort-Hashes | **hoch** | Kompromittierung ermöglicht Identitätsübernahme |
| **Unterschriften** (Name oder Bild) | **hoch** | personenbezogen, betrifft auch **Nicht-Systemnutzer**; Verarbeitung ohne Einbeziehung der Betroffenen (DSB-Entscheidung offen, siehe §2.3 des Ergänzungsdokuments) |
| Audit-Log (Handelnder, Aktion, Zeit) | **normal** | personenbezogen, aber pseudonymisierbar |
| Gefahrstoff-, Standort- und Mengendaten | **normal** | Sachdaten; Betriebswissen |
| Sitzungs-Cookie | **hoch** | trägt die Anmeldung; Fälschung = Identitätsübernahme |

**Ergebnis:** Kritisch sind nicht die Fachdaten, sondern **Authentifizierung**
und **Unterschriften**. Die Maßnahmen in Abschnitt 3 und 4 sind entsprechend
priorisiert.

---

## 3. Vertraulichkeit (Art. 32 Abs. 1 lit. b DSGVO)

### 3.1 Zutrittskontrolle

| Maßnahme | Umsetzung | Status |
|---|---|---|
| Physischer Zugang zum System | Serverraum/Rechenzentrum des Betreibers | **Betreiber** — nicht Teil dieser Anwendung |

Die Anwendung selbst kann keinen Zutrittsschutz leisten. Sie setzt voraus, dass
das System, auf dem sie läuft, physisch geschützt ist. Bei einem Docker-Volume
ist zusätzlich der Zugriff auf die Host-Ebene zu regeln — wer dort Zugriff hat,
hat die Datenbank im Klartext (siehe R-3).

### 3.2 Zugangskontrolle (Authentifizierung)

| Maßnahme | Umsetzung | Status |
|---|---|---|
| Kein Zugang ohne Anmeldung | Jede Route trägt `@login_required`; Ausnahme sind nur `/login` und die Erstanlage | umgesetzt |
| Passwörter nie im Klartext | `werkzeug.security.generate_password_hash`, Verfahren **`scrypt:32768:8:1`** (Werkzeug 3.1.8; geprüft am 27.09.2026) | umgesetzt |
| Keine freie Registrierung | Der erste Account wird Administrator, danach ist `/register` dauerhaft gesperrt (`User.query.count() > 0`) | umgesetzt |
| Konten nur durch Berechtigte | Anlegen/Ändern/Löschen ab Moderator, mit Rollenprüfung serverseitig auf jeder Route | umgesetzt |
| Kein Aussperren durch Fehlbedienung | Der letzte Administrator kann weder degradiert noch gelöscht werden (`is_last_admin()`); Moderatoren können Administratoren nicht verwalten | umgesetzt |
| Verzeichnisanmeldung | LDAPs über TLS; bei aktivem LDAP entfallen lokale Zweitpasswörter. Voreingestellte Rolle neuer Verzeichnisbenutzer: `lesen` | umgesetzt, **Betreiber konfiguriert** |
| **Schutz gegen Passwortraten** | **fehlt** — keine Sperre, keine Verzögerung, kein Zähler | **offen → R-2** |
| **Mindestlänge des Passworts** | **4 Zeichen** (bewusst niedrig, siehe R-2) | **offen → R-2** |

### 3.3 Zugriffskontrolle (Autorisierung)

| Maßnahme | Umsetzung | Status |
|---|---|---|
| Rollenmodell (RBAC) | Vier Rollen: `admin`, `moderator`, `benutzer`, `lesen`; Fähigkeiten zentral über `can_write`, `can_edit_gefahrstoff`, `can_manage_bereich` | umgesetzt |
| Prüfung serverseitig | Jede schreibende Route prüft die Rolle selbst; die Navigation blendet zusätzlich aus, ist aber nicht die Prüfung | umgesetzt |
| Bereichsbezogene Sichtbarkeit | `get_gefahrstoff_query()` filtert jede Liste, jeden Export und die Fristenliste auf die zugewiesenen Bereiche | umgesetzt |
| Schreibgeschützte Rolle | `lesen` darf nicht anlegen, ändern, löschen, inventarisieren, exportieren oder Dokumente herunterladen | umgesetzt |
| Schutz vor Selbstausschluss | Man kann sich nicht selbst löschen | umgesetzt |

Die Rechteprüfung ist durch Regressionstests abgesichert. Sie prüfen unter
anderem, dass die Rolle `lesen` keine Benutzerkonten löschen und keine Standorte
anlegen kann.

### 3.4 Trennungskontrolle

| Maßnahme | Umsetzung | Status |
|---|---|---|
| Datentrennung nach Organisationseinheit | Sichtbarkeit ausschließlich über `user_bereiche`; kein Zugriff außerhalb der Zuweisung | umgesetzt |
| Trennung der Benutzer | Jeder Zugang ist personalisiert; keine geteilten Konten vorgesehen | umgesetzt |
| Mandantenfähigkeit | **nicht vorhanden** — eine Instanz, ein Datenbestand. Für getrennte Organisationen ist je Organisation eine eigene Instanz mit eigenem Schlüssel und eigener Datenbank zu betreiben | by design |

### 3.5 Verschlüsselung

| Maßnahme | Umsetzung | Status |
|---|---|---|
| Transportverschlüsselung | TLS-Terminierung am Reverse Proxy (Pangolin); `ProxyFix` reicht `X-Forwarded-Proto` weiter, Links werden als `https://` erzeugt | **Betreiber** |
| Cookie nur über HTTPS | `SESSION_COOKIE_SECURE` wird **nur bei `FLASK_ENV=production`** gesetzt — im Docker-Image der Fall, bei Start über `run_prod.py` ohne diese Variable **nicht** | bedingt → R-5 |
| Cookie nicht für Skripte lesbar | `SESSION_COOKIE_HTTPONLY = True` | umgesetzt |
| Cookie nicht bei Fremdseiten | `SESSION_COOKIE_SAMESITE = 'Lax'` | umgesetzt |
| **Verschlüsselung im Ruhezustand** | **nicht vorhanden** — SQLite-Datei und hochgeladene Dokumente liegen im Klartext auf dem Datenträger | **offen → R-3** |

---

## 4. Integrität (Art. 32 Abs. 1 lit. b DSGVO)

### 4.1 Weitergabekontrolle

| Maßnahme | Umsetzung | Status |
|---|---|---|
| Keine Weitergabe an Dritte beim Seitenaufruf | Die Anwendung lädt **keine** externen Ressourcen; Schriften und Symbole liegen in `static/` | umgesetzt |
| Kein Cloud-Bezug | Keine Anbindung an extern betriebene Dienste im Regelbetrieb | umgesetzt |
| Ausgehende Verbindung nur auf Anforderung | PubChem-Autofill (Abschnitt 5.3) — wird ausschließlich durch einen Klick ausgelöst | umgesetzt, zu dokumentieren |
| Export- und Downloadrechte | `lesen` ist gesperrt; alle Exporte folgen der Bereichsfilterung | umgesetzt |
| Nachweis der Herkunft ausgelieferter Dateien | Quell-URL, Lizenz und SHA-256 je Datei in `static/vendor/SOURCES.md` und `static/symbols/SOURCES.md` | umgesetzt |

### 4.2 Eingabekontrolle und Protokollierung

| Maßnahme | Umsetzung | Status |
|---|---|---|
| Protokollierung aller schreibenden Vorgänge | **vollständig**, geprüft durch einen Quelltextabgleich: jede Funktion, die speichert, protokolliert | umgesetzt |
| Umfang | Gefahrstoffe (anlegen, ändern, verschieben, kopieren, löschen, freigeben, ablehnen, Inventur), Betriebsanweisungen, Benutzer (anlegen, ändern, Rolle, Bereiche, löschen), Standorte (anlegen, löschen), Passwortänderung, lokaler Login, Wartungsaktionen | umgesetzt |
| Nachvollziehbarkeit von Änderungen | Beim Rollenwechsel stehen alte und neue Rolle, beim Verschieben alter und neuer Standort, beim Löschen eines Standorts die Zahl der betroffenen Objekte im Eintrag | umgesetzt |
| Keine Geheimnisse im Protokoll | Passwörter erscheinen nur als Ereignis („Passwort neu gesetzt"), Unterschriften nur als „gesetzt"/„entfernt" — **nie im Inhalt** | umgesetzt |
| Zuordnung nach Kontolöschung | Einträge bleiben einander über die Benutzer-ID zuordenbar; der Name wird nicht aufbewahrt (Pseudonymisierung) | umgesetzt |
| **Manipulationsschutz des Protokolls** | **nicht vorhanden** — gewöhnliche Tabelle in derselben Datenbank, für Administratoren lesbar, Anzeige der letzten 100 Einträge | **offen → R-6** |
| **Fehlgeschlagene Anmeldungen** | **werden nicht protokolliert** — keine Erkennung von Angriffsversuchen | **offen → R-6** |

> Das Protokoll ist damit ein **Nachweis-, kein Beweismittel**-Bestand: Es
> belegt Vorgänge, es beweist sie nicht. Wer Datenbankzugriff hat, kann es
> verändern.

### 4.3 Eingabekontrolle der Fachdaten

| Maßnahme | Umsetzung | Status |
|---|---|---|
| Serverseitige Prüfung von Auswahlfeldern | Ziel-Standorte werden gegen die zugänglichen Bereiche geprüft, unbekannte Ziele abgelehnt (`ziel_standort_pruefen()`) | umgesetzt |
| Schutz vor Auszeichnung in Freitextfeldern | Die bearbeitbaren Texte der Betriebsanweisung laufen durch eine Tag-Whitelist (Attribute werden verworfen) | umgesetzt |
| Schutz der Unterschrift vor eingeschleustem Markup | Strenge Prüfung statt Bereinigung: nur ein PNG-Data-URL mit gültigem Base64 und lesbarem Bild oder ein reiner Name | umgesetzt |
| CSRF-Schutz | Flask-WTF auf allen Formularen; eigener Fehlerpfad mit verständlicher Meldung statt Absturz | umgesetzt |
| Mengen- und Datumsfelder | Werte werden geprüft und gemeldet statt stillschweigend verworfen | umgesetzt |

---

## 5. Verfügbarkeit und Belastbarkeit (Art. 32 Abs. 1 lit. b DSGVO)

### 5.1 Verfügbarkeitskontrolle

| Maßnahme | Umsetzung | Status |
|---|---|---|
| Örtliche Datenhaltung | SQLite-Datei und Uploads im Datenverzeichnis (`APP_DATA_DIR`), kein externer Speicher | umgesetzt |
| Selbststart nach Neustart | `restart: always` in der Compose-Konfiguration | umgesetzt |
| **Produktionsserver** | Der Container startet mit `exec flask run` — dem **Entwicklungsserver**. Waitress liegt mit `run_prod.py` bereit, wird vom Entrypoint aber nicht verwendet | **offen → R-4** |
| Abhängigkeitsinstallation | Der Entrypoint führt bei **jedem** Containerstart `pip install -r requirements.txt` aus: langsam, netzabhängig und nicht reproduzierbar | **offen → R-7** |
| Datenbank-Schema aktuell halten | Automatische Migration beim Start (`migrate_db.py`) plus Alembic-Aufruf; neue Spalten gehören in die Liste in `migrate_db.py` | umgesetzt |

### 5.2 Wiederherstellbarkeit

| Maßnahme | Umsetzung | Status |
|---|---|---|
| Sicherung vor Updates | Vor einem Update wird die Datenbank nach `data/backups/` kopiert (in den Update-Skripten und im Docker-Pfad) | umgesetzt |
| **Zeitgesteuerte Sicherungen** | **nicht vorhanden** — ohne Update entsteht keine Sicherung | **offen → R-8 (mittel)** |
| **Wiederherstellungstest** | **nicht durchgeführt und nicht dokumentiert** | **offen → R-8** |
| Wiederherstellung archivierter Datensätze | Archivierte Gefahrstoffe (`is_deleted`) bleiben in der Datenbank, **lassen sich in der Oberfläche aber nicht zurückholen** | bewusst so, siehe R-9 |

> **Der wichtigste offene Punkt dieses Abschnitts:** Es gibt derzeit **keinen
> belegten Wiederherstellungsweg**. Eine Sicherung, deren Rückspielen nie
> geprobt wurde, ist keine Wiederherstellbarkeit im Sinne des Art. 32. Zu
> sichern sind **beide** Teile — Datenbank **und** Upload-Verzeichnis; ohne die
> Dokumente ist die Datenbank unvollständig.

### 5.3 Auftragskontrolle (Art. 28 DSGVO)

| Maßnahme | Umsetzung | Status |
|---|---|---|
| Auftragsverarbeitung | **nicht anwendbar** — es werden keine Dienstleister mit der Verarbeitung personenbezogener Daten beauftragt | by design |
| Ausnahme mit Klärungsbedarf | **PubChem-Autofill** sendet die CAS-Nummer an die U.S. National Library of Medicine. Enthalten sind ausschließlich anorganische Sachdaten, keine personenbezogenen Daten und keine Bestandsdaten. Die IP-Adresse des **Servers** wird dabei jedoch übertragen — deshalb sollte die Funktion bewusst freigegeben und im Verzeichnis der Verarbeitungstätigkeiten erwähnt werden | **zu dokumentieren → R-10** |

---

## 6. Verfahren zur regelmäßigen Überprüfung (Art. 32 Abs. 1 lit. d DSGVO)

| Maßnahme | Umsetzung | Status |
|---|---|---|
| **Fristenüberwachung in der Anwendung** | Die Seite `/fristen` führt offene Aufgaben als Arbeitsliste: Sicherheitsdatenblätter (3 und 5 Jahre), Substitutionsprüfungen, Inventuren. Jede Zeile führt zur erledigenden Aktion | umgesetzt |
| **Nachweis der Prüffristen** | Intervalle stehen als benannte Konstanten im Quelltext (`SDB_FRIST_JAHRE`, `SDB_DRINGEND_JAHRE`, `INVENTUR_FRIST_MONATE`, `SUBSTITUTION_FRIST_MONATE`) und sind damit prüfbar und änderbar | umgesetzt |
| Hinweis auf Zusammenlagerungsverbote | Die Anwendung prüft bei der Anzeige eines Gefahrstoffs die Lagerklassen desselben Standorts nach TRGS 510 und zeigt Konflikte | umgesetzt |
| **Regelmäßige Überprüfung der Maßnahmen selbst** | **nicht institutionalisiert** — kein Termin, keine verantwortliche Person, keine dokumentierte Prüfung dieses TOM | **offen → R-11** |
| Technische Absicherung durch Tests | 119 automatisierte Tests; die Testumgebung ist von der echten Datenbank getrennt (`testkonfiguration.py`) | umgesetzt |

> Anmerkung zur Abgrenzung: Ein gesetzliches Wiederholungsintervall gibt es nur
> bei der Unterweisung (§14 GefStoffV, mindestens jährlich). Die 3/5 Jahre beim
> Sicherheitsdatenblatt, die 12 Monate bei der Inventur und die 24 Monate bei
> der Substitutionsprüfung sind **betriebliche Konventionen**, keine
> Vorschriften. Das ist im Handbuch so benannt und sollte auch hier nicht anders
> verstanden werden.

---

## 7. Datenschutz durch Technikgestaltung (Art. 25 DSGVO)

| Maßnahme | Umsetzung | Status |
|---|---|---|
| Datenminimierung | Erhoben wird, was die GefStoffV verlangt; kein Profiling, keine Auswertung außerhalb des Zwecks | umgesetzt |
| Datenschutzfreundliche Voreinstellungen | Neue Konten erhalten die **schwächste** Rolle (`lesen`) als Vorbelegung; Sichtbarkeit ist auf das Nötige begrenzt (Default „nichts sehen") | umgesetzt |
| Pseudonymisierung | Audit-Einträge gelöschter Konten bleiben ohne Namen zuordenbar; eine bewusste Entscheidung **gegen** das Mitschreiben des Namens | umgesetzt |
| Löschkonzept | Soft-Delete für Fachdaten, Hartlöschung für Konten, Unterschriften auf `NULL` beim Leeren | siehe Löschkonzept im Ergänzungsdokument |
| Kein Datenabfluss | Keine externen Ressourcen; einzige ausgehende Verbindung ist das angeforderte PubChem-Autofill | umgesetzt |

---

## 8. Verantwortlichkeiten

| Rolle | Verantwortung | Person |
|---|---|---|
| Betreiber / Verantwortlicher | Betrieb, Netz, Zutritt, Sicherungen, Freigabe der PubChem-Funktion | *[zu ergänzen]* |
| IT-Administration | Installation, Updates, Überwachung, Wiederherstellung | *[zu ergänzen]* |
| Datenschutzbeauftragte:r | Beurteilung der offenen Punkte, Freigabe der Unterschriftsverarbeitung | *[zu ergänzen]* |
| Anwendungsentwicklung | Behebung der technischen Punkte R-2, R-4, R-7 | *[zu ergänzen]* |

---

## 9. Offene Punkte, Risiken und Maßnahmen

Nach Dringlichkeit geordnet, das Risiko steht in der Überschrift. **Die
Erreichbarkeit der Installation (R-1) ist vor der Bewertung zu klären**, weil die
Beurteilung der Transport- und Zugangsmaßnahmen davon abhängt.

### R-1 — Erreichbarkeit je Installation festzustellen · **mittel**

* **Was:** Die Maßnahmen zur Transportverschlüsselung und zur Zugangskontrolle
  setzen voraus, dass die Erreichbarkeit der Installation bekannt ist. Sie ist
  hier als Intranetbetrieb beschrieben; für eine einzelne Installation ist das
  aber nachzuweisen, nicht anzunehmen.
* **Wirkung:** Ist eine Installation aus dem Internet erreichbar, greifen die
  offenen Punkte zur Zugangskontrolle (R-2) sofort und mit erhöhtem Risiko, und die Aussage „kein Datenabfluss"
  trägt nicht mehr unverändert.
* **Maßnahme:** Je Installation feststellen und **dokumentieren**, ob sie
  öffentlich, nur über VPN oder nur im Intranet erreichbar ist.
* **Aufwand:** klein (Feststellung und Dokumentation).
* **Status:** offen — Bringschuld des Betreibers, nicht der Anwendung. Sie
  kann ihre eigene Erreichbarkeit nicht kennen, und eine Prüfung von außen
  wurde bewusst nicht durchgeführt.

### R-2 — Kein Schutz gegen Passwortraten, Mindestlänge 4 Zeichen · **mittel**

* **Was:** `/login` kennt keine Sperre, Verzögerung oder Zählung. Das
  Mindestmaß für neue Passwörter ist 4 Zeichen.
* **Wirkung:** Passwörter lassen sich mit vertretbarem Aufwand durchprobieren;
  kurze Passwörter fallen sofort.
* **Maßnahme:** Verzögerung nach Fehlversuchen je Konto und IP, Sperre nach N
  Versuchen, Mindestlänge anheben (12 Zeichen), Fehlversuche protokollieren.
* **Aufwand:** klein bis mittel.
* **Status:** offen.

### R-3 — Keine Verschlüsselung im Ruhezustand · **mittel**

* **Was:** SQLite-Datei und Uploads liegen im Klartext auf dem Datenträger.
* **Wirkung:** Bei Verlust oder unberechtigtem Zugriff auf Datenträger,
  Sicherung oder Docker-Volume sind alle Daten lesbar — einschließlich der
  Unterschriften.
* **Maßnahme:** Verschlüsselung des Datenträgers bzw. Volumes auf
  Infrastrukturebene (Betreiberseite), geschützte Ablage der Sicherungen.
* **Aufwand:** Infrastruktur, kein Anwendungscode.
* **Status:** offen (Betreiber).

### R-4 — Container startet den Entwicklungsserver · **mittel**

* **Was:** Der Entrypoint führt `exec flask run` aus. `run_prod.py` mit Waitress
  ist vorhanden, wird aber nicht verwendet.
* **Wirkung:** Für den Dauerbetrieb ist der Entwicklungsserver nicht gedacht;
  keine definierte Parallelität, keine Betriebsprotokollierung im üblichen
  Umfang.
* **Maßnahme:** Entrypoint auf Waitress umstellen (`run_prod.py`).
* **Aufwand:** klein.
* **Status:** offen.

### R-5 — Cookie-Markierung „nur über HTTPS" nur bedingt gesetzt · **niedrig**

* **Was:** `SESSION_COOKIE_SECURE` hängt an `FLASK_ENV=production`.
* **Wirkung:** Ohne diese Variable wird das Sitzungs-Cookie nicht als
  HTTPS-only markiert; ein Herabstufen auf HTTP würde es mitübertragen.
* **Maßnahme:** Die Markierung unabhängig von `FLASK_ENV` setzen.
* **Aufwand:** klein.
* **Status:** offen.

### R-6 — Protokoll ohne Manipulationsschutz, Fehlversuche unprotokolliert · **niedrig**

* **Was:** Das Audit-Log ist eine gewöhnliche Tabelle in derselben Datenbank,
  Anzeige der letzten 100 Einträge; fehlgeschlagene Anmeldungen werden nicht
  erfasst.
* **Wirkung:** Das Protokoll belegt Vorgänge, es beweist sie nicht. Angriffe
  auf die Anmeldung bleiben unsichtbar.
* **Maßnahme:** Unveränderbarkeit (eigene Datei mit Signatur, externe
  Protokollablage) und Protokollierung von Fehlversuchen — Letzteres sinnvoll
  nur zusammen mit R-2, sonst ist die Historie flutbar.
* **Aufwand:** mittel.
* **Status:** offen.

### R-7 — Abhängigkeiten bei jedem Start installiert · **niedrig**

* **Was:** Der Container führt bei jedem Start `pip install -r
  requirements.txt` aus.
* **Wirkung:** Startzeit, Netzabhängigkeit und die Möglichkeit, dass ein
  Container mit anderen Bibliotheksversionen startet als geprüft.
* **Maßnahme:** Abhängigkeiten beim Bauen des Images installieren.
* **Aufwand:** klein.
* **Status:** offen.

### R-8 — Keine zeitgesteuerten Sicherungen, kein Wiederherstellungstest · **mittel**

* **Was:** Sicherungen entstehen nur vor Updates; ein Rückspielen wurde nie
  geprobt.
* **Wirkung:** Ohne belegten Wiederherstellungsweg ist Art. 32 Abs. 1 lit. b
  (Verfügbarkeit, Belastbarkeit) **nicht** erfüllt.
* **Maßnahme:** Zeitgesteuerte Sicherung von Datenbank **und** Upload-Verzeichnis,
  Aufbewahrung mehrerer Stände, ein dokumentierter und einmal tatsächlich
  durchgeführter Wiederherstellungstest.
* **Aufwand:** mittel (Betreiber).
* **Status:** offen.

### R-9 — Archivierte Datensätze nicht wiederherstellbar · **niedrig**

* **Was:** Gelöschte Gefahrstoffe bleiben in der Datenbank, ein
  Wiederherstellen gibt es in der Oberfläche aber nicht.
* **Wirkung:** Kein Datenschutzproblem — ein Datenintegritätsthema. Ein
  Fehlklick ist nur über einen Eingriff in die Datenbank umkehrbar.
* **Maßnahme:** Papierkorb-Ansicht mit Wiederherstellen.
* **Aufwand:** klein bis mittel.
* **Status:** bewusst offen, im Handbuch benannt.

### R-10 — PubChem-Abruf dokumentieren · **niedrig**

* **Was:** Serverinitiierte Abfrage an einen Dienst außerhalb der EU.
* **Wirkung:** Kein Personenbezug in der Nutzlast, aber die Server-IP wird
  übertragen.
* **Maßnahme:** Im Verzeichnis der Verarbeitungstätigkeiten erwähnen; Funktion
  bewusst freigeben oder abschalten.
* **Aufwand:** klein (Text).
* **Status:** offen.

### R-11 — Überprüfung dieses TOM nicht institutionalisiert · **niedrig**

* **Was:** Kein Termin, keine verantwortliche Person, keine dokumentierte
  Prüfung.
* **Wirkung:** Maßnahmen veralten unbemerkt — eine Angabe, die einmal richtig
  war, bleibt stehen, auch wenn die Anwendung sich geändert hat.
* **Maßnahme:** Jährliche Überprüfung mit Datum und Verantwortlichkeit
  festhalten; Änderungen an der Anwendung lösen eine Nachführung aus.
* **Aufwand:** klein (organisatorisch).
* **Status:** offen.

### Entscheidungen des Datenschutzbeauftragten

Aus `DATENSCHUTZ_UND_TOM.md`, Abschnitt 2.3, weiterhin offen:

1. Ob eine Unterschrift beim Soft-Delete eines Gefahrstoffs mitarchiviert
   werden darf oder zu löschen ist.
2. Ob eine Rechtsgrundlage für das Speichern von Unterschriftsbildern **ohne
   Einbeziehung der betroffenen Beschäftigten** trägt.
3. Rechtsgrundlage der Unterschriftsverarbeitung insgesamt (dort als Platzhalter
   geführt).

---

## 10. Verweise

* `DATENSCHUTZ_UND_TOM.md` — Zweckbestimmung, Datenkategorien, Rechtsgrundlagen, Löschkonzept
* `HANDBUCH.md` — Benutzerhandbuch (Rollen, Fristen, Betriebsanweisung)
* `CHANGELOG.md` — Änderungshistorie der Anwendung
* `static/vendor/SOURCES.md`, `static/symbols/SOURCES.md` — Herkunft und Prüfsummen ausgelieferter Dateien

---

*Ende des Dokuments.*
