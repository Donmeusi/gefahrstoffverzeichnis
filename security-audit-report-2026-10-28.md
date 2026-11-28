# Security Audit — Gefahrstoffverzeichnis

| | |
|---|---|
| **Datum** | 2026-10-28 |
| **Auditierter Stand** | `3b17a46` (Branch `beta`) |
| **Aktueller Stand** | `v3.49` — alle Befunde unten sind behoben, sofern nicht anders vermerkt |
| **Nachprüfung** | 2026-11-28: keine neuen Befunde (Abschnitt 7); DOM-XSS-Prüfung der Skripte in Abschnitt 8, ein latenter Befund entschärft |
| **Methode** | Claude-Code-Skill `security-audit` v1.8.0, Phasen Python/Backend, Container/Deployment, Secrets/Supply-Chain |
| **Umfang** | Statische Analyse plus ein Laufzeit-Test des TLS-Deployments. Kein DAST, keine Penetrationstests. |
| **Nicht geprüft** | `openwiki/`, `static/` (außer Verweisen), `data/`, `handbuch-bilder/`, Binärdateien |
| **Repo-Sichtbarkeit** | `PUBLIC` |
| **Testsuite** | 417 Tests, grün (Stand 28.11.2026; zum Auditzeitpunkt 256) |

Dieser Bericht bewertet die Anwendung als installierbares Open-Source-Produkt. Befunde sind so formuliert, dass sie für jede Installation gelten; wo eine Auswirkung von der Deployment-Entscheidung des Betreibers abhängt, steht das dabei.

---

## 1. Stand

### Behoben

| # | Befund | Schwere | Commit |
|---|---|---|---|
| K1 | IDOR in `/uploads/<datei>` | Hoch | `0e64482` |
| K2 | Standard-Deployment veröffentlicht auf allen Interfaces | Hoch | `11a1030`, `74ff820` |
| K3 | Update-Kette: freie Repo-URL, `git pull` als root | Hoch | `11a1030`, `0e717ac` |
| K4 | `pillow==12.1.1`, 57 Advisories im Upload-Pfad | Hoch | `7f83232` |
| M1 | `ProxyFix` vertraut `X-Forwarded-*` bedingungslos | Mittel | `11a1030` |
| M2 | LDAP-Zertifikatsprüfung standardmäßig aus | Mittel | `0e64482` |
| M3 | Lokaler Passwort-Fallback umgeht AD-Sperren | Mittel | `0e717ac` |
| M4 | Passwort-Policy: 4 Zeichen, keine Prüfung bei Neuanlage | Mittel | `0e64482` |
| M5 | Container läuft als root | Mittel | `11a1030`, `d182176` |
| M6 | Flask 3.1.0 und Werkzeug 3.1.3 veraltet | Mittel | `7f83232` |
| M7 | Quellcode-Mount und Named Volume überlagern sich | Mittel | dokumentiert (`11a1030`) |
| N1 | Inventurliste umgeht das Freigabe-Gate | Niedrig | `0e64482` |
| N2 | Open Redirect in `approve_stoff` | Niedrig | `0e64482` |
| N3 | Markup-Injection im PDF-Export | Niedrig | `0e64482` |
| N4 | LDAP-Filter-/DN-Injection | Niedrig | `0e64482` |
| N5 | SPARQL-Injection über die CAS-Nummer | Niedrig | `0e64482` |
| N6 | Interne Fehlertexte in Responses | Niedrig | `0e64482` |
| N7 | Kein Brute-Force-Schutz | Niedrig | `0e717ac` |
| N8 | Sitzung ohne Ablauf, keine Invalidierung | Niedrig | `0e64482`, `0e717ac` |
| N9 | Sicherheitsheader unvollständig | Niedrig | `0e64482` |
| N10 | `error.log` versioniert | Niedrig | `0e64482`, `7f83232` |
| N11 | `.dockerignore` unvollständig | Niedrig | `7f83232` |
| N12 | Keine Ressourcenlimits, kein Healthcheck | Niedrig | `11a1030` |
| N13 | Base-Image nicht auf Digest gepinnt | Niedrig | `6bb67d1` |
| N14 | `pip install` ohne Prüfsummen | Niedrig | `6bb67d1` |
| N15 | Kein Dependency-Scanning, kein Branch-Schutz | Niedrig | `6bb67d1` |
| N16 | `update.sh`/`update.ps1` ohne Fehlerbehandlung | Niedrig | `7f83232`, `6bb67d1` |
| N17 | `getattr` als Jinja-Global | Info | `0e64482` |
| N18 | TOCTOU bei der Erst-Registrierung | Info | `0e717ac` |

### Bewusst offen

**Restrisiko der Update-Kette (K3).** Die Kette ist entschärft, nicht beseitigt: `git pull` läuft weiter im Container, wenn auch als UID 1000, gegen eine festgelegte URL und mit geprüftem Branch-Namen. Wer den GitHub-Account übernimmt, kann weiterhin Code ausliefern. Eine Signaturprüfung (`git verify-tag`) oder ein Update über ein neu gebautes Image wäre die vollständige Lösung und ist eine Architekturentscheidung.

**M3 für Bestandskonten.** Konten gelten als `lokal`, bis sie sich das erste Mal über LDAP anmelden. Wer vorher ein lokales Passwort gesetzt hat, kommt bis zu diesem Login noch lokal hinein.

**`secret_scanning_non_provider_patterns`.** GitHub ignoriert die Einstellung für dieses Repository (Antwort ohne Änderung, Status bleibt `disabled`). Genau dieser Modus hätte den alten Rückfallschlüssel aus Abschnitt 4 erkannt.

---

## 2. Die Befunde im Einzelnen

### K1 — IDOR: `/uploads/<filename>` lieferte jedes Dokument an jeden angemeldeten Nicht-Leser
**Schwere:** Hoch · **Behoben in** `0e64482`

```python
@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    if current_user.role == 'lesen':
        return redirect(url_for('index'))
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
```

Die Route prüfte nur die Rolle, nicht das Objekt. Jeder `benutzer`, `moderator` oder `admin` rief jedes Sicherheitsdatenblatt, jede Betriebsanweisung und jede Gefährdungsbeurteilung ab — auch aus Bereichen, denen er nicht zugeordnet war. Dateinamen sind aus Stoffname plus Suffix vorhersagbar und damit auch ohne Link enumerierbar.

**Behebung:** Der Dateiname muss zu einem Stoff gehören, den `get_gefahrstoff_query()` liefert; sonst `abort(404)`.

---

### K2 — Standard-Deployment veröffentlichte Port 5000 auf allen Interfaces
**Schwere:** Hoch · **Behoben in** `11a1030`, erweitert in `74ff820`

Die mitgelieferte Compose-Datei band auf `0.0.0.0`. Eine Installation nach Anleitung war damit aus dem gesamten erreichbaren Netz ohne TLS ansprechbar: Anmeldung mit Klartext-Passwort, Sitzungscookie ohne Transportschutz.

**Behebung:** Standard ist `127.0.0.1`. Wer direkten Zugriff braucht, setzt `BIND_ADDR` — die Abwägung bleibt beim Betreiber und ist im README benannt. Ergänzend gibt es jetzt ein optionales TLS-Profil (Abschnitt 3).

---

### K3 — Update-Kette: `git pull` und `pip install` als root mit Schreibzugriff auf den Quellcode
**Schwere:** Hoch · **Entschärft in** `11a1030`, `0e717ac`

Drei Bausteine griffen ineinander:

1. **Freie Remote-URL:** `git remote set-url origin <repo_url>` mit ungeprüftem Formularwert; schon der GET auf `/admin/system` löste `git fetch` gegen diese URL aus. Die Branch-Angabe ging ungeprüft in `git checkout`.
2. **Ausführung als root:** keine `USER`-Zeile im Dockerfile.
3. **Schreibrechter Mount:** `- ./:/app` erlaubte dem Container, Quellcode und `.git/hooks/*` zu überschreiben.

**Behebung:** Container läuft als UID 1000; Repository-URL gegen `UPDATE_REPO_URL` geprüft; Branch-Name gegen ein Muster, das führende `-` ausschließt; alle git-Aufrufe mit `-c protocol.ext.allow=never` und Zeitlimit. Branch Protection auf `main` und `beta`. **Restrisiko siehe Abschnitt 1.**

---

### K4 — `pillow==12.1.1`: 57 Advisories im Upload-Pfad
**Schwere:** Hoch · **Behoben in** `7f83232`

`Image.open(BytesIO(rohdaten))` auf einer hochgeladenen Base64-PNG-Unterschrift, erreichbar für jeden mit Upload-Recht. **Behebung:** `pillow==12.3.0`.

---

### M1 — `ProxyFix` vertraute `X-Forwarded-*` bedingungslos
**Schwere:** Mittel · **Behoben in** `11a1030`

Ohne `TRUSTED_PROXY` blieb `clear_untrusted_proxy_headers = False`; ein Client, der die Anwendung direkt erreichte, setzte `X-Forwarded-Proto` und bestimmte damit das `Secure`-Flag des Sitzungscookies.

**Behebung:** `TRUSTED_PROXY` ist in der Compose-Datei auf die feste Adresse des mitgelieferten Proxys gesetzt, in `.env.example` und README dokumentiert.

---

### M2 — LDAP-Zertifikatsprüfung standardmäßig aus
**Schwere:** Mittel · **Behoben in** `0e64482`

`LDAP_REQUIRE_CERT` stand auf `false` → `ssl.CERT_NONE`. **Behebung:** Default `true`, `LDAP_CA_CERT_FILE` für eigene PKIs, Warnung im Log, wenn die Prüfung abgeschaltet wird.

---

### M3 — Lokaler Passwort-Fallback umging Verzeichnisdienst-Sperrungen
**Schwere:** Mittel · **Behoben in** `0e717ac`

Schlug die LDAP-Anmeldung fehl — falsches Passwort, gesperrtes Konto oder Ausfall —, wurde ohne Unterscheidung lokal weitergeprüft. LDAP-Benutzer konnten über `/profile` ein echtes lokales Passwort setzen; danach war das Verzeichniskonto entbehrlich.

**Behebung:** Spalte `auth_source`; die lokale Prüfung greift nur noch für `lokal`. Passwortänderung im Profil für LDAP-Konten gesperrt.

---

### M4 — Passwort-Policy: 4 Zeichen, bei Neuanlage gar keine Prüfung
**Schwere:** Mittel · **Behoben in** `0e64482`

**Behebung:** 12 Zeichen, geprüft in Registrierung, Benutzeranlage und Profil. Bestehende Konten bleiben unverändert.

---

### M5 — Container lief als root
**Schwere:** Mittel · **Behoben in** `11a1030`, nachgeschärft in `d182176`

`USER app` (UID 1000), `HOME=/app`. Beim ersten echten Start zeigte sich, dass ein frisches Named Volume als `root` angelegt wird — das Datenverzeichnis wird deshalb jetzt im Image erstellt und übergeben, damit das Volume den Besitzer erbt.

---

### M6 — Veraltete Framework-Abhängigkeiten
**Schwere:** Mittel · **Behoben in** `7f83232`

`Flask 3.1.0` → `3.1.3`, `Werkzeug 3.1.3` → `3.1.9`, `cryptography 48.0.0` → `48.0.1`.

---

### M7 — Quellcode-Mount und Named Volume überlagern sich
**Schwere:** Mittel · **Dokumentiert in** `11a1030`

Das Named Volume auf `/app/data` verdeckt das im Bind-Mount enthaltene `./data`. Wer den Quellcode lokal bearbeitet und die Datenbank dort erwartet, arbeitet auf einer anderen Datei als die Anwendung. Betriebsrisiko, kein Sicherheitsdefekt im engeren Sinn; die Trennung ist im README beschrieben.

---

### N1–N18

| # | Befund | Behebung |
|---|---|---|
| N1 | Inventurliste zeigte nicht freigegebene CMR-Stoffe | Query über `get_gefahrstoff_query()` |
| N2 | `next=//evil.com` wurde als Ziel übernommen | protokollrelative Ziele abgelehnt |
| N3 | ReportLab-`Paragraph` verarbeitete unescapte Nutzdaten | alle Freitextfelder escaped |
| N4 | LDAP-Filter-/DN-Injection | `escape_filter_chars` / `escape_rdn` |
| N5 | SPARQL-Injection über die CAS-Nummer | CAS-Muster geprüft, zusätzlich escaped |
| N6 | Interne Fehlertexte in Responses | generische Meldung, Details ins Log |
| N7 | Kein Brute-Force-Schutz | 5 Fehlversuche → 15 Minuten Sperre pro Benutzer + Adresse |
| N8 | Sitzung 31 Tage, keine Invalidierung | 12 Stunden, `session_version` bei Passwortwechsel |
| N9 | Keine CSP, keine `Referrer-Policy`, kein `no-store` | ergänzt, `X-XSS-Protection` entfernt, HSTS nur über HTTPS |
| N10 | `error.log` versioniert | enttrackt, `*.log` ignoriert, Log nach `data/logs/` |
| N11 | `.dockerignore` unvollständig | `.env`, `data/`, `*.db`, `openwiki/` ergänzt |
| N12 | Keine Limits, kein Healthcheck | `mem_limit`, `cpus`, `pids_limit`, Healthcheck |
| N13 | Base-Image ohne Digest | auf `sha256:673719e0…` gepinnt |
| N14 | `pip install` ohne Prüfsummen | 864 Hashes, `--require-hashes` |
| N15 | Kein Dependency-Scanning | Dependabot für pip, Docker, Actions; Alerts aktiv |
| N16 | `update.sh` ohne `set -e`, `update.ps1` killt fremde Prozesse | `set -euo pipefail`, Prozesse nur aus eigenem venv |
| N17 | `getattr` als Jinja-Global | entfernt, Templates nutzen `current_user.is_admin` |
| N18 | TOCTOU bei der Erst-Registrierung | `IntegrityError` abgefangen |

---

## 3. Optionales TLS-Profil

`docker compose --profile tls up -d` startet einen Caddy-Container, der TLS terminiert (Port 80/443) und die Anwendung intern weiterleitet. Port 5000 bleibt auf Loopback.

- **Zertifikat:** standardmäßig Caddys lokale CA — der Browser warnt beim ersten Aufruf, bis die CA (`/data/caddy/pki/authorities/local/root.crt`) auf den Geräten eingetragen ist. Mit einer öffentlichen Domain und `CADDYFILE=Caddyfile.acme` übernimmt Let's Encrypt.
- **`SITE_ADDRESS`** ist der Name oder die IP ohne Schema. `default_sni` ist nötig, weil Browser und curl bei IP-Adressen kein SNI senden — ohne ihn bricht der Handshake mit `internal error` ab.
- **`TRUSTED_PROXY`** zeigt auf die feste Adresse des Proxys im eigenen Netz `tlsnet`, das Sitzungscookie bekommt dadurch automatisch `Secure`.

**Geprüft gegen eine laufende Installation** (isolierte Kopie, Host-Ports umgelegt): HTTPS 200, Zertifikat aus der lokalen CA, HTTP → 308, Cookie mit `Secure`, HSTS, CSP, Healthcheck gesund, `Caddyfile.acme` validiert. Nicht geprüft: Let's Encrypt mit einer echten Domain.

---

## 4. Historischer Sitzungsschlüssel — Betreiber müssen handeln

Im **öffentlichen** Repo stand vom 30.07.2026 (`776c0c0`) bis 21.10.2026 (`435ec17`) ein hartkodierter Rückfallwert für `FLASK_SECRET_KEY` in `main.py:34`.

`flask_login` legt die Benutzer-ID in ein mit diesem Schlüssel signiertes Cookie. Wer den Wert kennt, kann für jede Installation, die ohne eigene Variable lief, ein gültiges Sitzungscookie fälschen — ohne Anmeldung. Der Rückfallwert war bis zum 21.10. der Standardweg, weil `docker-compose.yml` die Variable erst mit `74deb34` verpflichtend machte.

**Für Betreiber älterer Installationen:** `FLASK_SECRET_KEY` neu erzeugen (`openssl rand -base64 32`), setzen, Container neu starten — das invalidiert alle bestehenden Sitzungen, was hier gewollt ist. Das Löschen aus dem HEAD genügt nicht, die Historie bleibt öffentlich. Zusätzlich empfiehlt sich ein Blick in das Audit-Log auf Anmeldungen zwischen Ende Juli und dem Rotationsdatum.

**Für das Projekt:** Der aktuelle Stand ist korrekt — `main.py` liest `os.environ["FLASK_SECRET_KEY"]` ohne Rückfallwert und bricht bei Fehlen ab; `docker-compose.yml` erzwingt den Wert. Diese Entscheidung sollte im CHANGELOG als Sicherheitsfix mit Rotationshinweis stehen; dort steht sie seit `v3.33`.

---

## 5. Geprüft, ohne Befund

- **SQL-Injection:** alle Abfragen über SQLAlchemy-ORM; `text()` nur mit konstanten Statements in `migrate_database()`; kein `raw()`, kein `extra()`.
- **Command-Injection:** kein `shell=True`, kein `os.system`/`eval`/`exec`; alle `subprocess`-Aufrufe in Listenform.
- **Insecure Deserialization:** kein `pickle`, `marshal`, `yaml.load`; nur `json.loads` mit Typ-Prüfung.
- **XXE:** Die Anwendung parst keine vom Nutzer hochgeladenen XML-Dateien; `lxml` wird im Laufzeitcode nicht importiert. Die im Auftrag vermuteten `pdftotext`-Aufrufe existieren nicht.
- **SSTI/XSS:** kein `render_template_string`, keine dynamischen Templates, Autoescape aktiv. Die neun `|safe` in `ba_print.html` laufen durch einen Whitelist-Sanitizer, der Attribute verwirft und Text escaped — eigene Umgehungsprüfung ohne Durchlass.
- **CSRF:** global aktiv, keine Ausnahme, alle POST-Formulare mit Token; POST ohne Token führt die Aktion nicht aus.
- **AuthZ:** alle 34 Routen einzeln geprüft (Stand 28.11.2026: 50 Routen, siehe Abschnitt 7). Jede außer `/login` und `/register` mit `@login_required`, Rollenprüfungen auf allen Verwaltungsrouten. Die einzige Lücke war `/uploads` (K1).
- **Path Traversal:** `send_from_directory` + `safe_join`; `../../etc/passwd` → 404. Dateinamen serverseitig aus `secure_filename` und Whitelist erzeugt.
- **Datei-Upload:** 16-MB-Limit, Endungs-Whitelist vor jedem Speichern, Ablage außerhalb `static/`, Auslieferung mit `nosniff`. Inhaltliche Prüfung fehlt (offene Härtung: Magic-Bytes).
- **Secrets im Repo:** `.env` nie getrackt, `data/` nie getrackt, keine Zertifikate oder Keys, keine Provider-Token, keine DB-Connection-Strings. `gitleaks dir` ohne Treffer; `gitleaks git` nur die zwei historischen `SECRET_KEY`-Funde (Abschnitt 4).
- **Compose:** kein `privileged`, kein `network_mode: host`, kein Docker-Socket-Mount.
- **Debug-Modus:** aus; Produktion über Waitress.

---

## 6. Offene Punkte außerhalb des Audits

- `static/*.js` wurde nicht geprüft (Client-Logik für `parse_sdb`, `autofill`, Mengenschwellen-Vorschau). **Nachgeholt am 28.11.2026, siehe Abschnitt 8.**
- Keine Laufzeitmessung des PDF-Parsings auf große Dateien (DoS-Fläche für Benutzer mit Schreibrecht).
- Die Branch-Protection erzwingt kein Review — bei einem Ein-Personen-Projekt wäre eine Required-Approval-Regel nicht erfüllbar. Force-Push und Löschen sind gesperrt.

---

## 7. Nachprüfung am 28.11.2026

**Anlass:** Seit dem Audit sind drei Funktionsversionen dazugekommen (v3.45 bis v3.47):
die Übersicht zeigt einen Standort statt des ganzen Verzeichnisses, es gibt eine Suche über
alle Standorte und ein gedrucktes Gesamtverzeichnis. Geprüft wurde, ob die neuen Wege die im
Audit festgelegten Grenzen einhalten und ob die früheren Behebungen unverändert gelten.

**Was neu ist**

| Neu | Seit | Was daran sicherheitsrelevant ist |
|---|---|---|
| `/standort/<id>` | v3.45 | Sichtbarkeit genau eines Standorts statt aller |
| `/standorte` | v3.45 | Auswahlseite mit Stoffzahlen je Standort |
| `/suche` | v3.46 | Abfrage über alle sichtbaren Bereiche, serverseitig |
| `/verzeichnis/druck` | v3.47 | Ausgabe des gesamten sichtbaren Bestands |
| `/` | v3.45 | leitet nur noch weiter, keine eigene Datenansicht |
| `/restore/<id>` | v3.48 | holt einen gelöschten Gefahrstoff zurück, nur Administratoren |

Die Zahl der Routen ist von 34 auf 51 gestiegen (einschließlich der `/api/*`-Endpunkte).

**Ergebnis: keine neuen Befunde.**

| Prüfung | Befund |
|---|---|
| Routen ohne `@login_required` | weiterhin genau `/login` und `/register`; `register` ist ab dem ersten Konto durch die Zählprüfung gesperrt — unverändert |
| Autorisierung der neuen Routen | `/standort` prüft zusätzlich `darf_unterbereich()`; `/suche` und `/verzeichnis/druck` verwenden `get_gefahrstoff_query()`, `/standorte` `get_accessible_bereiche()`. Es gibt kein zweites Rechtemodell |
| Regressionstests für die Grenzen | 24 neue Tests, davon fünf ausdrücklich zur Grenze: Treffer aus fremdem Bereich, fremder Standort im Druck, gemerkter Standort verfällt bei Rechteverlust, fremder Standort gesperrt, fremder Bereich nicht auf der Auswahlseite |
| SQL-Injection | Die Suche filtert in Python über `casefold()` statt per SQL-`LIKE`; im Anwendungspfad weiterhin keine `text()`-, `raw()`- oder `extra()`-Aufrufe |
| XSS in den neuen Vorlagen | `get_full_path()` liefert Klartext statt HTML-Entities, die neuen Vorlagen kommen deshalb ohne `|safe` aus; Autoescape ist aktiv. Die neun `|safe` in `ba_print.html` sind unverändert und laufen weiter durch den Whitelist-Sanitizer |
| CSRF | `CSRFProtect(app)` global, unverändert; die Suche ist ein GET ohne Zustandsänderung |
| Umfang der Suche | Treffer auf `SUCHERGEBNISSE_MAX` (200) gedeckelt, die Gesamtzahl wird nur gezählt. Eine breite Suche rendert damit nicht wieder tausende Zeilen — dieselbe Überlegung, die v3.45 für die Übersicht durchgesetzt hat |
| Abhängigkeiten | `pillow` 12.3.0 → **13.0.0**, `werkzeug` 3.1.3 → **3.1.9**, `flask` 3.1.0 → **3.1.3**; Installation weiterhin nur mit `--require-hashes`. Die Befunde K4 und M6 sind damit weiter überholt, nicht zurückgefallen |
| Testsuite | 417 Tests grün, davon 24 für die neuen Wege (zum Auditzeitpunkt 256) |

**Nicht geprüft:** kein DAST, keine Penetrationstests, keine Lastmessung. Die Bewertung der neuen
Routen stützt sich auf Quellcodeprüfung und die Regressionstests. `static/*.js` ist weiterhin
ungeprüft (Abschnitt 6).

**Empfehlung:** keine Änderung erforderlich. Der Bestand trägt, weil die Bereichsgrenze an einer
einzigen Stelle liegt (`get_gefahrstoff_query()`) und alle neuen Wege daran hängen. Wer künftig
eine Route ergänzt, sollte sie an dieselbe Query hängen — nicht an eine eigene Prüfung.

---

## 8. DOM-XSS-Prüfung der Skripte (28.11.2026)

Abschnitt 6 führte als offenen Punkt: „`static/*.js` wurde nicht geprüft." Das ist nachgeholt.

**Umfang:** `static/autofill.js`, `static/hp_modal.js`, `static/mengenschwellen_vorschau.js`,
`static/sdb_import.js` sowie die Inline-Skripte in `base.html`, `index.html`, `add.html`,
`inventur.html`, `ba_print.html` und `admin_system.html`.

**Vorgehen:** Quellen und Senken. Gesucht wurde jede Stelle, an der ein Wert in das Dokument
gelangt (`innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write`, `setAttribute` auf
`href`/`src`, `eval`/`new Function`), und für jede Fundstelle die Herkunft des Wertes bestimmt.

**Zwölf Senken.** Elf davon setzen konstante Zeichenketten, leeren einen Knoten oder schreiben
das eigene Markup eines Knopfes zurück — unbedenklich. Eine setzte Werte ein:

### F1 — `hp_modal.js` baute den Satzkatalog per Template in `innerHTML` · **niedrig (latent)**, behoben

```js
textSpan.innerHTML = `<strong>${item.code}</strong>: ${item.text}`;
```

* **Herkunft:** `/static/hp_data.json`, eine mitgelieferte statische Datei (37 KB).
* **Ausnutzbarkeit heute:** nicht. Kein Nutzereingang führt in diese Datei; sie zu ändern
  setzt Schreibzugriff auf das Repository voraus, und dann ist jede Annahme dieses Berichts
  ohnehin hinfällig.
* **Warum es trotzdem behoben ist:** Es ist die einzige Stelle, an der ein fremder Wert
  ungeprüft als Markup interpretiert wird. Sobald der Katalog einmal aus der Anwendung kommt
  (eigene Sätze, Import, je Organisation verschiedene Kataloge), wird daraus eine echte
  DOM-XSS-Lücke — und niemand würde sich an diese Zeile erinnern.
* **Behebung:** Der Code wird ein `<strong>`-Element mit `textContent`, der Text ein
  Textknoten. `test_dom_xss.py` hält die Klasse zu: kein `innerHTML` mit `${…}` in
  `static/*.js`, keine der Ausführungsflächen, und die drei Skripte, die fremde Werte
  anzeigen, müssen `textContent` verwenden. Die Prüfung wurde gegen die alte Zeile
  gegengeprüft — sie schlägt dort an.

**Ohne Befund:**

| Weg | Befund |
|---|---|
| Namen aus Wikidata/PubChem (`autofill.js`) | `createElement` + `textContent`; die Auswahl im Dialog ist bewusst als DOM-Knoten gebaut |
| Dateinamen aus dem PDF-Upload (`sdb_import.js`) | ausschließlich `textContent` — der klassische XSS-Vektor für Uploads ist damit sauber |
| Kachel-Fragment (`index.html`: `grid.innerHTML = await antwort.text()`) | serverseitig mit Jinja-Autoescape gerendert, eigener Endpunkt mit Anmeldepflicht |
| Suchfeld und Filter | Werte werden nur verglichen, nie in das Dokument geschrieben |
| Mengenschwellen-Vorschau (`mengenschwellen_vorschau.js`) | Zeichen `<`, `>` und `&` werden vor dem Einsetzen ersetzt — Textkontext, damit ausreichend |
| Dynamische Ausführung | kein `eval`, kein `new Function`, kein `document.write`, kein `insertAdjacentHTML`, kein `setTimeout` mit Zeichenkette |
| `setAttribute` | ausschließlich feste Werte (`data-theme`, `aria-*`, `data-code`, `data-ba-generated`) |

**Nicht geprüft:** keine Laufzeitprüfung mit einem Angriffsvektor (kein DAST), keine
Bewertung der Browser-Abhängigkeiten, keine Prüfung, ob die gesetzte CSP die Skripte
tatsächlich in jedem Browser blockt. Die Aussage stützt sich auf Quellcodeprüfung und die
statischen Regressionstests.

---

*Bericht erzeugt mit dem Claude-Code-Skill `security-audit` v1.8.0. Befunde wurden stichprobenartig am Quellcode gegengeprüft; das TLS-Deployment zusätzlich gegen eine laufende Installation getestet.*
