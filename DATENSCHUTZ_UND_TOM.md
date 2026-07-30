# Technical Documentation & Data Protection Concept (GDPR / DSGVO)
## Gefahrstoff-Verwaltungsanwendung (Gefahrstoffverzeichnis)

> **Dokumententyp:** Technische Systemdokumentation & Technisch-Organisatorische Maßnahmen (TOM) gemäß Art. 32 DSGVO  
> **Zielgruppe:** Datenschutzbeauftragte (DSB), IT-Administrator:innen, Informationssicherheitsbeauftragte (ISB)  
> **Stand:** 2026 Edition  
> **Betriebsmodus:** Intranet / On-Premises (Self-Hosted)

---

## 1. Systemübersicht & Zweckbestimmung

### 1.1 Zweck der Verarbeitung
Die Anwendung dient der betrieblichen Erfassung, Verwaltung, Dokumentation und Überwachung von Gefahrstoffen gemäß den gesetzlichen Vorgaben der **Gefahrstoffverordnung (GefStoffV § 6)**, den **Technischen Regeln für Gefahrstoffe (TRGS 510 & TRGS 555)** sowie den europäischen Verordnungen **REACH (EG 1907/2006)** und **CLP (EG 1272/2008)**.

### 1.2 Systemarchitektur & Deployment
* **Architektur:** 3-Schichten-Webanwendung (Frontend, Backend, Datenbank).
* **Backend Framework:** Python 3.11, Flask, Flask-SQLAlchemy, Flask-Login, Flask-WTF.
* **Produktions-Webserver (WSGI):** Waitress (Multi-Threaded WSGI HTTP Server).
* **Datenbank:** SQLite 3 (`gefahrstoffe.db`).
* **Deployment:** Native Ausführung auf Linux/Windows-Servern oder containerisiert via Docker (`docker-compose`).
* **Netzwerkeinbindung:** Ausschließlicher Betrieb im internen Firmennetzwerk (Intranet). Keine Anbindung an extern betriebene Cloud-Services.

---

## 2. Verarbeitete Datenkategorien

### 2.1 Personenbezogene Daten (Art. 4 Nr. 1 DSGVO)

| Datenkategorie | Konkrete Datenfelder | Verarbeitungszweck | Speicherort & Schutz |
| :--- | :--- | :--- | :--- |
| **Benutzer-Stammdaten** | Benutzername, Ersteller-ID | Authentifizierung, Zuordnung von Datenbesitz | SQLite DB (`user`-Tabelle) |
| **Authentifizierungsdaten** | Passwort-Hash (PBKDF2:SHA256 via `Werkzeug`) | Autorisierung beim Systemzugang | Verschlüsselt gehasht, Passwörter werden **niemals** im Klartext gespeichert |
| **Rollen & Rechte** | Systemrolle (`admin`, `moderator`, `benutzer`, `lesen`), Bereichszuweisungen | Zugriffsbeschränkung gemäß Minimalprinzip (Need-to-know) | SQLite DB (`user`-Tabelle & `user_bereiche`) |
| **Audit- & Protokolldaten** | User-ID, Aktions-Typ (`CREATE`, `UPDATE`, `DELETE`, `APPROVE`, `REJECT`, `LOGIN`), Datum/Uhrzeit (UTC), Details | Nachvollziehbarkeit & Rechenschaftspflicht (Art. 5 Abs. 2 DSGVO) | SQLite DB (`audit_log`-Tabelle) |
| **Session & Sicherheit** | Session-Cookie (`session`), CSRF-Token | Sitzungssteuerung & Schutz vor Cross-Site Request Forgery | In-Memory Session / Browser-Cookie (`HTTPOnly`, `SameSite=Lax`, `Secure`) |

### 2.2 Sach- & Betriebsdaten
* **Gefahrstoffdaten:** Stoffname, CAS-Nummer, EG-Nummer, GHS-Piktogramme, Signalwort, Gefahrenkategorien, H-Sätze, P-Sätze, Lagerklasse (LGK), Mengen und Mengeneinheiten.
* **Standortdaten:** Hierarchische Bezeichnungen von Standorten, Hauptbereichen und Unterbereichen/Schränken.
* **Dokumente:** Sicherheitsdatenblätter (SDB), Betriebsanweisungen (BA), Gefährdungsbeurteilungen (GB) im PDF- oder DOC-Format.

---

## 3. Netzwerkeinbindung, HTTPS & Sicherheitsarchitektur

### 3.1 HTTPS & Reverse Proxy Architektur
Die Anwendung wird im Intranet hinter einem **TLS/SSL-terminierenden Reverse Proxy** (z. B. Nginx, Apache HTTP Server, Traefik oder Nginx Proxy Manager) betrieben.

```text
┌──────────────────────────────────────────────────────────────────────────┐
│                             FIRMEN-INTRANET                              │
│                                                                          │
│  ┌──────────────┐     HTTPS (TLS 1.3, Port 443)     ┌─────────────────┐  │
│  │ User-Client  │ ─────────────────────────────────►│  Reverse Proxy  │  │
│  └──────────────┘                                   └────────┬────────┘  │
│                                                              │           │
│                                        HTTP (Port 5000)      │ ProxyFix  │
│                                                              ▼           │
│                                                     ┌─────────────────┐  │
│                                                     │ Gefahrstoff-App │  │
│                                                     │ (Waitress WSGI) │  │
│                                                     └────────┬────────┘  │
│                                                              │           │
│                                                              ▼           │
│                                                     ┌─────────────────┐  │
│                                                     │ SQLite & Uploads│  │
│                                                     └─────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
```

* **ProxyFix-Integration:** In `main.py` ist `werkzeug.middleware.proxy_fix.ProxyFix` konfiguriert. Der Proxy reicht die ursprünglichen Header (`X-Forwarded-Proto: https`, `X-Forwarded-For`) an Flask weiter. Links und Weiterleitungen werden serverseitig als `https://` generiert.
* **SSL-Zertifikate:** Die Verwaltung der SSL-Zertifikate (z. B. interne Unternehmens-CA oder Let's Encrypt / ACME) erfolgt zentral auf dem Reverse Proxy.

### 3.2 Session- & Transport-Sicherheit
* `SESSION_COOKIE_HTTPONLY = True`: Verhindert das Auslesen von Session-Cookies über Client-seitige Skripte (Schutz vor XSS).
* `SESSION_COOKIE_SAMESITE = 'Lax'`: Schützt vor Cross-Site-Request-Forgery-Angriffen.
* `SESSION_COOKIE_SECURE = True`: Wird bei `FLASK_ENV=production` automatisch aktiviert und stellt sicher, dass Cookies nur verschlüsselt übertragen werden.
* `CSRF-Schutz (Flask-WTF)`: Jedes HTML-Formular sowie AJAX-Anfragen verwenden ein eindeutiges `csrf_token`. Ungültige oder fehlende Tokens werden durch einen dedizierten Error-Handler abgefangen.

### 3.3 Externe Datenabfragen (PubChem / GESTIS)
* **PubChem / NIH API:** Beim Aufruf des optionalen *PubChem-Autofills* werden ausschließlich CAS-Nummern (rein anonyme Sachdaten) per verschlüsselter HTTPS-Anfrage an die offizielle Datenbank der U.S. National Library of Medicine geschickt. Es werden **keine** personenbezogenen Daten oder Firmen-IPs übermittelt.

---

## 4. Technisch-Organisatorische Maßnahmen (TOM) gemäß Art. 32 DSGVO

### 4.1 Vertraulichkeit (Art. 32 Abs. 1 lit. b DSGVO)

#### Zutrittskontrolle
* Der Anwendungsserver steht im gesicherten Rechenzentrum / Serverraum des Unternehmens mit physikalischer Zutrittsbeschränkung (Schließsystem / Chipkarten).

#### Zugangskontrolle (Authentifizierung)
* **Passwort-Policy:** Passwort-Speicherung erfolgt ausschließlich mit starken Einweg-Hashfunktionen (`werkzeug.security.generate_password_hash` mit PBKDF2:SHA256).
* **LDAPs-Integration (LDAP over SSL/TLS):** Optionale Anbindung an das zentrale Unternehmens-Directory (Active Directory / OpenLDAP) über Port 636 oder StartTLS. Dadurch entfallen lokale Zweit-Passwörter.
* **Registrierungssperre:** Die freie Benutzerregistrierung ist nach der Erstanlegung des ersten Administrators deaktiviert. Neue Konten können nur durch Berechtigte angelegt werden.

#### Zugriffskontrolle (Autorisierung / Rollenkonzept)
Die Anwendung erzwingt ein striktes **Rollen- und Rechte-Modell (RBAC)** auf Datenbank- und Routenebene:

| Rolle | Lesen | SDB/BA/GB Download | Exporte (Excel/PDF) | Erfassen / Bearbeiten | Löschen | Benutzerverwaltung | Audit-Log |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **👑 Administrator** | Alle |  Ja |  Ja |  Ja |  Ja |  Ja |  Ja |
| **🛡️ Moderator** | Ausgewählte Bereiche |  Ja |  Ja |  Ja (in Bereichen) |  Ja |  Eigene User | ❌ |
| **👤 Benutzer** | Zugewiesene Bereiche |  Ja |  Ja |  Ja (eigene/Bereiche) |  Eigene | ❌ | ❌ |
| **👁️ Lesen** *(Neu)* | Zugewiesene Bereiche | ❌ Gesperrt | ❌ Gesperrt | ❌ Schreibschutz | ❌ Gesperrt | ❌ | ❌ |

#### Trennungskontrolle
* Benutzer sehen ausschließlich Daten der ihnen über `user_bereiche` zugewiesenen Unternehmensbereiche.

---

### 4.2 Integrität (Art. 32 Abs. 1 lit. b DSGVO)

#### Weitergabekontrolle
* Vollständige Transportverschlüsselung im Netz via HTTPS/TLS.
* Verbot von Daten-Downloads & Exporten für die eingeschränkte Rolle `Lesen`.

#### Eingabekontrolle & Protokollierung
* **Audit-System (`AuditLog`):** Sämtliche Änderungen an Gefahrstoffen, Erstellungen von Benutzern sowie Freigabe- und Ablehnungsvorgänge werden protokolliert.
* **Archivierung (Soft-Delete):** Gelöschte Gefahrstoffe verbleiben mit `is_deleted=True` und Lösch-Zeitstempel in der Datenbank und werden vor normalen Benutzern verborgen. Eine unwiderrufliche Löschung ist nur durch den Administrator möglich.

---

### 4.3 Verfügbarkeit & Belastbarkeit (Art. 32 Abs. 1 lit. b DSGVO)

#### Verfügbarkeitskontrolle & Disaster Recovery
* **Self-Contained Data:** Alle Anwendungsdaten (SQLite-Datenbank & hochgeladene PDF/DOC-Dateien) befinden sich lokal im Verzeichnis `./data/`.
* **Automatische Datenbank-Sicherungen:** Bei Updates und Migrationen erstellt das System automatische Sicherheitskopien unter `./data/backups/`.
* **Automatischer Fallback-Schutz:** Die Anwendung prüft beim Start das Vorhandensein der Datenbank und verhindert ein Überschreiben bestehender Daten durch automatische Pfad-Prüfungen.
* **Docker Restart Policy:** Bei Container-Deployments sorgt `restart: always` für den automatischen Neustart nach Server-Reboots.

---

### 4.4 Verfahren zur regelmäßigen Überprüfung (Art. 32 Abs. 1 lit. d DSGVO)

* **TRGS 510 Zusammenlagerungs-Prüfer:** Die Anwendung prüft automatisch Zusammenlagerungsverbote zwischen Gefahrstoffen am selben Standort.
* **SDB-Fristenüberwachung:** Das System berechnet das Alter von Sicherheitsdatenblättern und hebt Dokumente, die älter als 3 bzw. 5 Jahre sind, visuell zur Aktualisierungsprüfung hervor.
* **Regelmäßige Audits:** Der Administrator kann das System über die integrierte Historie und Validierungsskripte auditieren.

---

## 5. Lösch- & Aufbewahrungskonzept

* **Betriebsdaten / Gefahrstoffe:** Aufbewahrung während des aktiven Betriebs der Betriebsstätte gemäß GefStoffV. Nach Außerdienststellung eines Stoffes erfolgt die Soft-Delete Archivierung zur Einhaltung von Nachweispflichten bei Gewerbeaufsichts- und Berufsgenossenschaftsprüfungen.
* **Benutzerkonten:** Beim Ausscheiden von Mitarbeiter:innen können deren Konten durch den Administrator gelöscht werden. Bereits getätigte Audit-Log-Einträge bleiben zur Einhaltung der Rechenschaftspflicht pseudonymisiert erhalten.

---

## 6. Fazit für den Datenschutzbeauftragten (DSB)

Die Gefahrstoff-App erfüllt alle Anforderungen an den **Datenschutz durch Technikgestaltung (Privacy by Design)** und **datenschutzfreundliche Voreinstellungen (Privacy by Default)** gemäß Art. 25 DSGVO:

1. **Kein Datenabfluss:** Alle Daten verbleiben zu 100 % lokal auf der Intranet-Infrastruktur Ihres Unternehmens.
2. **Minimalprinzip:** Es werden nur technisch und gesetzlich zwingend erforderliche Daten erhoben.
3. **Schutz der Integrität:** Passwörter werden nie im Klartext gespeichert; Schreib- und Export-Rechte sind durch das neue Rollenmodell `Lesen` feingranular steuerbar.
4. **Vollständige Transparenz:** Ein integriertes Audit-Log garantiert die lückenlose Revisionsfähigkeit aller Aktionen.
