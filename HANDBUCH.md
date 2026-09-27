# 📘 Vollständiges Benutzerhandbuch: Gefahrstoffverzeichnis

Willkommen im Gefahrstoffverzeichnis! Diese webbasierte Anwendung bietet Ihnen ein umfassendes Set an Funktionen, um Gefahrstoffe in Ihrem Unternehmen, Labor oder Institut sicher, transparent und effizient zu verwalten. 

Dieses Handbuch beschreibt **alle** verfügbaren Funktionen der App und erklärt das zugehörige Rollen- und Berechtigungskonzept im Detail.

---

## 1. 🌟 Übersicht aller Funktionen

### 1.1 Registrierung, Login & Profil
- **Sichere Authentifizierung:** Die App ist durch ein Login-System geschützt.
- **Benutzerprofil (`/profile`):** In Ihrem persönlichen Profil können Sie Ihr Passwort ändern und (je nach Rolle) ausstehende Gefahrstoffe einsehen, die auf eine Freigabe warten.

### 1.2 Das Dashboard (Hauptansicht)
Das Dashboard ist Ihre Zentrale für alle Gefahrstoffe, auf die Sie Zugriff haben.
- **Live-Suche:** Suchen Sie in Echtzeit nach Namen, CAS-Nummern, EG-Nummern oder bestimmten H-Sätzen.
- **Interaktive Filter:** Filtern Sie die Tabelle blitzschnell nach GHS-Piktogrammen oder Signalwörtern.
- **Export (Excel & PDF):** Die aktuell gefilterte Ansicht kann mit einem Klick als strukturierte PDF-Liste oder Excel-Tabelle exportiert werden (inklusive aller Zusatzdaten wie Substitutionsprüfungen und Lagerklassen).

### 1.3 Gefahrstoff-Verwaltung (CRUD)
- **Erfassung (`/add`):** Legen Sie neue Gefahrstoffe an. Erfassen Sie neben Standarddaten auch Lagerklassen, Mengen, GHS-Einstufungen, H/P-Sätze sowie Substitutionsprüfungen.
- **Dateianhänge:** Hängen Sie dem Datensatz Sicherheitsdatenblätter (SDB), Betriebsanweisungen (BA) und Gefährdungsbeurteilungen (GB) als PDF an.
- **Ansicht & Bearbeitung:** Rufen Sie Detailansichten auf oder ändern Sie bestehende Einträge.
- **Kopieren / Duplizieren:** Erstellen Sie exakte Kopien eines bestehenden Gefahrstoffs (z.B. für einen anderen Standort), um sich Tipparbeit zu sparen.
- **Verschieben:** Verschieben Sie einen Gefahrstoff schnell von einem Raum/Bereich in einen anderen.
- **Archivierung (Soft-Delete):** Löschen Sie Datensätze sicher. Sie werden nicht hart aus der Datenbank gelöscht, sondern archiviert, um die Datenintegrität und Historie zu wahren.

### 1.4 ✨ Automatisierte Datenerfassung (SDB & PubChem)
Die App bietet zwei mächtige Funktionen, um Ihnen die manuelle Tipparbeit beim Anlegen von Gefahrstoffen abzunehmen:

**1. SDB Auto-Parsing (PDF-Import):**
Laden Sie beim Anlegen einfach das PDF-Sicherheitsdatenblatt hoch. Die App liest das PDF vollautomatisch aus und befüllt das Formular:
- Extraktion von CAS-Nummer & EG-Nummer
- Erkennung von Signalwort & GHS-Piktogrammen
- Auslesen der H- und P-Sätze

**2. CAS-Nummer Autofill (PubChem):**
Wenn Sie nur die CAS-Nummer zur Hand haben (z.B. `67-64-1`), tippen Sie diese in das Feld ein und klicken auf "🪄 Autofill". Die App holt sich in Sekundenschnelle alle relevanten GHS-Daten aus der offiziellen PubChem-Datenbank und füllt Piktogramme, Signalwort sowie H/P-Sätze automatisch aus.

### 1.5 Dokumenten-Zentralen
Anstatt Gefahrstoffe einzeln anklicken zu müssen, bietet die App globale Sammelstellen für Dokumente:
- **Betriebsanweisungen-Zentrale (`/betriebsanweisungen`):** Eine alphabetische, durchsuchbare Liste aller im System hinterlegten Betriebsanweisungen.
- **Sicherheitsdatenblätter-Zentrale (`/sicherheitsdatenblaetter`):** Schneller Zugriff auf alle hochgeladenen SDBs.

### 1.6 Freigabe-Workflow (Approval System)
Je nach Systemkonfiguration müssen neu angelegte Gefahrstoffe von regulären Benutzern erst geprüft werden.
- **Freigabe / Ablehnung:** Moderatoren und Administratoren sehen in ihrem Profil eine Liste der "ausstehenden" Gefahrstoffe und können diese genehmigen (`Approve`) oder ablehnen (`Reject`).

### 1.7 Standort-Verwaltung & QR-Codes (`/locations`)
Die Lagerorte sind hierarchisch aufgebaut:
- **Bereiche:** Hauptstandorte (z.B. Gebäude, Fakultät, Abteilung). Diesen Bereichen kann ein "Besitzer" (Moderator) zugewiesen werden.
- **Unterbereiche:** Spezifische Lagerorte innerhalb eines Bereichs (z.B. Raum 101, Chemikalienschrank A).

> **⚠️ Was beim Löschen eines Standorts passiert:** Die enthaltenen **Gefahrstoffe werden nicht gelöscht**, sie verlieren nur ihren Standort. Das hat eine Folge, die man kennen sollte: Ohne Standort sieht ein Gefahrstoff nur noch sein **Ersteller** und die Administratoren. Andere Benutzer, die vorher über den Bereich Zugriff hatten, sehen ihn danach nicht mehr. Beim Löschen eines Bereichs verschwinden alle Unterbereiche mit. Die Systemhistorie hält fest, wie viele Unterbereiche und Gefahrstoffe betroffen waren.

**🖨️ QR-Code Generierung:** 
Für jeden Unterbereich lässt sich mit einem Klick auf das QR-Code-Symbol eine druckbare Ansicht erzeugen. Wenn Sie diesen Code ausdrucken und am Schrank anbringen, müssen Mitarbeiter ihn nur noch mit der Smartphone-Kamera abscannen und landen direkt in einer exakt auf diesen Schrank gefilterten Inventarliste. Die QR-Code-Erzeugung geschieht 100% lokal und datenschutzkonform.

### 1.8 Fristen (`/fristen`)
Die Seite listet die offenen Aufgaben, die sich aus Ihren Gefahrstoffen ergeben — dringlichste zuerst, jeweils mit einem Knopf direkt zur erledigenden Aktion. Der Eintrag in der Navigation zeigt die Anzahl.

**Wann etwas als fällig gilt:**

| Prüfung | Frist | Was zu tun ist |
|---|---|---|
| Sicherheitsdatenblatt | Datum älter als 3 Jahre | „SDB-Datum eintragen" öffnet die Bearbeitungsmaske — ein neues Datum setzt die Frist zurück |
| Sicherheitsdatenblatt | Datum älter als 5 Jahre (dringend) | ebenso |
| Kein Sicherheitsdatenblatt hinterlegt | immer fällig | das Dokument am Gefahrstoff hinterlegen |
| Dokument vorhanden, aber ohne Datum | immer fällig | das Datum nachtragen |
| Inventur | jüngste Inventur des Standorts älter als 12 Monate — oder dort wurde noch nie inventarisiert | „Inventur starten" öffnet die Schnell-Inventur; sie setzt das Datum |

- **Sichtbarkeit:** Es erscheinen nur Stoffe und Standorte aus Ihren Bereichen — wie überall in der Anwendung.
- **Die Rolle „Lesen"** sieht die Liste, aber keine Aktionsknöpfe.
- **Die Kachel „Veraltete SDBs"** auf dem Dashboard zählt nur die veralteten Sicherheitsdatenblätter (die Stufen „prüfen" und „dringend") und ist der Einstieg in diese Seite. Oben auf der Seite steht zusätzlich, wie viele Dokumente fehlen und wie viele Inventuren fällig sind — damit die Zahl auf der Kachel und die Liste vergleichbar bleiben.

### 1.9 Administrator-Werkzeuge
- **Audit Log (System-Historie):** Eine Tabelle (`/audit_logs`), die aufzeichnet, wer wann welchen Datensatz erstellt, geändert, verschoben, kopiert, gelöscht oder freigegeben hat — einschließlich der Standortverwaltung. Beim Verschieben stehen alter und neuer Standort im Eintrag, beim Löschen eines Standorts die Zahl der betroffenen Unterbereiche und Gefahrstoffe.
- **Auch die Rechteverwaltung wird protokolliert:** Benutzer anlegen, Rolle ändern, Benutzer bearbeiten, Bereichszuweisung ändern und Benutzer löschen erzeugen jeweils einen Eintrag — beim Rollenwechsel stehen die alte und die neue Rolle darin. Passwörter werden dabei **nie** im Klartext erfasst, sondern nur als Ereignis („Passwort neu gesetzt").
- **Wird ein Benutzerkonto gelöscht**, bleiben seine bisherigen Einträge erhalten, verlieren aber den Namen — sie erscheinen dann als „Benutzer #<ID> (gelöscht)". Die ID bleibt bewusst stehen, damit erkennbar bleibt, dass mehrere Einträge zur selben Person gehören. Der Name bleibt nur im Eintrag über die Löschung selbst stehen, sonst wäre nicht nachvollziehbar, wer gelöscht wurde. Hintergrund: Abschnitt 5 in `DATENSCHUTZ_UND_TOM.md`.
- **System & Updates:** Ein integrierter In-App-Updater (`/admin/system`), mit dem das System per Knopfdruck (`git pull`) auf die neueste Version aktualisiert werden kann.
- **Benutzerverwaltung (`/users`):** Administratoren können neue Benutzer anlegen, bestehende bearbeiten, Rollen ändern, Bereichs-Zugriffe vergeben oder Konten sperren.

---

## 2. 👥 Benutzerrollen und Berechtigungen

Das strikte Berechtigungskonzept stellt sicher, dass Nutzer nur das sehen und bearbeiten können, was für sie relevant ist.

### 👤 1. Der reguläre Benutzer ("Benutzer")
Dies ist die Standardrolle nach der Registrierung.
- **Sichtbarkeit:** Sieht standardmäßig **nur Gefahrstoffe, die er selbst angelegt hat**.
- **Zugewiesene Bereiche:** Administratoren können dem Benutzer bestimmte "Bereiche" zuweisen. Der Benutzer sieht dann auch alle Gefahrstoffe, die in diesem Bereich gelagert werden.
- **Rechte:** Kann eigene Datensätze anlegen, ansehen und Exporte generieren.

### 🛡️ 2. Der Moderator ("Moderator")
Moderatoren fungieren als Bereichs- oder Abteilungsleiter.
- **Sichtbarkeit:** Sieht eigene Gefahrstoffe **sowie alle Gefahrstoffe in Bereichen, denen er als "Besitzer" (Owner) oder zugewiesener Nutzer zugeteilt ist**.
- **Rechte:** 
  - Kann die Bestände in seinen verantworteten Bereichen vollumfänglich verwalten (Verschieben, Bearbeiten, Kopieren, Archivieren).
  - Hat die Befugnis, ausstehende Gefahrstoffe in seinem Bereich **freizugeben (Approve) oder abzulehnen (Reject)**.

### 👑 3. Der Administrator ("Admin")
Administratoren haben die uneingeschränkte Kontrolle über das System. *(Der allererste registrierte Account wird automatisch Administrator).*
- **Sichtbarkeit:** Sieht **alle** Gefahrstoffe im gesamten System, unabhängig vom Standort oder Ersteller.
- **Gefahrstoff-Rechte:** Kann systemweit jeden Datensatz bearbeiten, verschieben, kopieren, archivieren oder freigeben.
- **Standort-Rechte:** Kann neue Bereiche und Unterbereiche erstellen, umbenennen oder löschen.
- **Benutzerverwaltung:** Kann Rollen zuweisen, Benutzer sperren/löschen und Bereichs-Zuweisungen vornehmen.
- **System-Rechte:** Hat exklusiven Zugriff auf das Audit-Log (Systemhistorie) und die In-App-Update-Funktion.

### 👁️ 4. Der Leser ("Lesen")
Die schreibgeschützte Rolle für reine Betrachter, etwa für Prüfer oder Aushilfen.
- **Sichtbarkeit:** Sieht ausschließlich die ihm zugewiesenen Bereiche.
- **Rechte:** Darf Datensätze ansehen und die Übersichten öffnen.
- **Nicht erlaubt:** Anlegen, Bearbeiten, Löschen, Archivieren, Schnell-Inventur, Excel-/PDF-Export, Herunterladen von Dokumenten, Betriebsanweisung bearbeiten, Standortverwaltung und Benutzerverwaltung. Die Navigation blendet diese Punkte aus, zusätzlich prüft der Server jede Route.
- **Bei LDAP:** Ist `LDAP_DEFAULT_ROLE=lesen` gesetzt (die Vorbelegung), erhält jeder neue Verzeichnisbenutzer beim ersten Login diese Rolle.

---
*Ende des Dokuments.*
