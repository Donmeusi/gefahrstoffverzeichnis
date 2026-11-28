# Spezifikation: Übersicht nach Standort

Stand: 2026-11-28
Bezug: `CHANGELOG.md` v3.43/v3.44, `main.py` (`get_gefahrstoff_query`, `index`, `index_kacheln`), `templates/index.html`

## Ziel

Die Übersicht zeigt den **Standort, in dem gearbeitet wird**, statt des ganzen
Verzeichnisses. Wer über mehrere Standorte sucht, nutzt eine berechtigungsgefilterte
Suche; wer das vollständige Verzeichnis braucht, druckt es.

Damit fällt die teure Ansicht weg: Bei über 3.000 Stoffen insgesamt, verteilt auf
Standorte, rendert der Bildschirm nie mehr als einen Standort. Es gibt **keine
Paginierung und kein Nachladen von Zeilen** — beides wäre Aufwand für eine Ansicht,
die niemand im Alltag braucht.

## Ausgangslage (gemessen)

- `/` zeigt ohne Filter **alles, was der Benutzer sehen darf**. Was das ist, regelt
  `get_gefahrstoff_query()`: reguläre Benutzer nur ihre zugeordneten Bereiche,
  Moderatoren ihre eigenen und zugeordneten, **Administratoren alles**.
- Die Tabelle wird vollständig serverseitig gerendert; jede Zeile trägt zusätzlich
  `data-search` (Name, CAS, EG-Nr., H-Sätze) für die Livesuche, `filterItems()`
  läuft über alle Zeilen im DOM.
- v3.44, 3.000 Stoffe: **9,8 MB** HTML, 365 ms Serverzeit. v3.43 nennt für 671
  Stoffe vor der Kachel-Trennung ~3,3 MB; nach der Trennung entspricht 1.000 Stoffe
  grob **3 MB** (*Schätzung aus dem 3.000er-Messwert, keine Messung*).
- Der Server ist nicht das Problem, der Browser ist es.

## Entscheidungen

### Auslegung: über 3.000 Stoffe insgesamt, 1.000 je Standort

Mehr als 3.000 Stoffe sind nicht ausgeschlossen, verteilen sich aber auf Standorte.
Ein einzelner Standort bleibt bei **bis zu 1.000 Stoffen** — das ist die Zahl, für die
die Ansicht ausgelegt wird.

*Verworfen:* „671 ist der Maßstab, alles darüber ist dokumentierte Grenze." Das hätte
die Gesamtansicht als Start bestehen lassen und genau den Fall offen gelassen, der
kommen kann.

### Startansicht: standortbezogen, Gesamtliste nur als Druck

Der Administrator landet nicht mehr in der Gesamtliste. Die Bildschirmliste zeigt
immer genau einen Standort.

*Verworfen:* Gesamtliste behalten und Zeilen nachladen (wie die Kacheln) — Aufwand
für eine Ansicht ohne Alltagsnutzen. *Verworfen:* Gesamtliste paginieren — ändert die
Suchsemantik und die Bedienung für einen Fall, den der Druck abdeckt.

### Suche: global, serverseitig, berechtigungsgefiltert

Die Suche läuft über **alle Stoffe, die der Nutzer sehen darf**, und zwar auf dem
Server. Ergebnisliste mit Standortspalte.

*Verworfen:* Suche nur im gewählten Standort (heutiges Verhalten) — beantwortet die
eigentliche Frage „wo liegt das Zeug" nicht. *Verworfen:* Treffer clientseitig filtern
— setzt voraus, dass alle Zeilen im DOM liegen, was diese Spec gerade abschafft.

### Druck: berechtigungsgefiltert, Seitenumbruch je Standort

`/verzeichnis/druck` erzeugt ein Dokument mit **allen Standorten, die der Nutzer sehen
darf** — für den Administrator das vollständige Verzeichnis. Je Standort eine
Kopfzeile und ein Seitenumbruch, davor ein Inhaltsverzeichnis der Standorte.

*Verworfen:* ein PDF je Standort — bei vielen Standorten viele Klicks. *Verworfen:*
durchlaufende Liste mit Standort als Spalte — die Zuordnung geht beim Umblättern
verloren.

### Auswahlseite: flache Liste, nach Bereich gruppiert

Alle sichtbaren Standorte in **einer** Liste, gruppiert nach Bereich, je Eintrag
Stoffzahl und Marke für Mengenschwellen-Überschreitung (TRGS 510). Ein Klick führt
in die Standortansicht.

*Verworfen:* zweistufig (erst Bereich, dann Standort) — bei flacher Hierarchie zwei
Klicks Reibung, und die Warnmarke erscheint erst auf der zweiten Ebene.

### Weg hinein: ein Bereich direkt, sonst letzte Wahl, sonst Auswahl

- Genau **ein** Bereich zugeordnet → direkt in dessen Standortansicht.
- Sonst: die **letzte Wahl aus der Sitzung** (Server-Session, kein Cookie).
- Sonst, oder wenn die Berechtigung für die gemerkte Wahl entfallen ist: Auswahlseite.

### Kennzahlen: standortbezogen

`stats_locations`, `mengen_auffaellig` und `trgs_warnungen` beziehen sich auf den
angezeigten Standort und auf die Standorte, die der Nutzer sehen darf — nie auf das
ganze Verzeichnis. Der Überblick bleibt auf der Auswahlseite erhalten (Stoffzahl und
Warnmarke je Standort).

### Bedienung in der Standortansicht

- **Signalwort- und Piktogrammfilter** bleiben, ebenso die Livesuche **innerhalb** des
  Standorts (für das Durchsuchen der angezeigten Zeilen).
- Der **Bereichs-Dropdown entfällt**; der Standortwechsel steht in der Kopfzeile und
  führt zurück zur Auswahlseite.
- Die **Kachelansicht bleibt** als Umschalter, unverändert (`/index/kacheln`).

### Adressen

| Adresse | Inhalt |
| --- | --- |
| `/` | Auswahlseite (bzw. direkt der einzige Standort) |
| `/standort/<id>` | Standortansicht, inkl. Unter-Standorte (`get_all_child_ids`) |
| `/suche?q=…` | berechtigungsgefilterte Suche |
| `/verzeichnis/druck` | Druck des berechtigten Verzeichnisses |

Alte Links mit `?bereich_id=` oder `?unterbereich_id=` werden auf die passende neue
Adresse **weitergeleitet**, damit Lesezeichen nicht brechen und die
Berechtigungsprüfung erhalten bleibt.

### Messlatten (Abnahme)

Gemessen im echten Browser mit 1.000 Stoffen, dazu 3.000 für die Suche:

- Tabelle nach dem Laden **< 300 ms** filterbar
- Tastendruck im Suchfeld **< 50 ms**
- Suchroute bei 3.000 Stoffen **< 500 ms** serverseitig

Erst diese Messung entscheidet, ob die Standortansicht noch etwas braucht.

## Tests

Die bestehenden 384 bleiben grün. Neu:

- Weiterleitung alter `?bereich_id=`- und `?unterbereich_id=`-Links auf die neue Adresse
- Berechtigungsgrenze der Suche: Treffer nur aus zugeordneten Bereichen
- Berechtigungsgrenze des Drucks: kein fremder Standort im Dokument
- Auswahlseite mit einem Bereich: direkter Einstieg ohne Zwischenseite
- Gemerkte Wahl fällt weg, wenn die Berechtigung entzogen wird

## Nicht Teil dieser Spec

- Paginierung, unendliches Nachladen, Virtualisierung
- Änderungen an der Kachelansicht
- Änderungen am Datenmodell (`Bereich`/`Unterbereich` bleiben, wie sie sind)
- Rechte- und Rollenmodell

## Abweichungen

Noch keine — beim Umsetzen hier nachziehen.
