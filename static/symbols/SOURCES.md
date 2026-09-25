# Herkunft der ISO-7010-Symbole

Diese Dateien werden in der Betriebsanweisung (`templates/ba_print.html`) verwendet.
Der Branch `beta` hat sie mit der Behauptung eingeführt, es seien „exact official
Wikimedia Commons ISO 7010 vector files". Für einen Teil der Dateien trifft das
nachweislich **nicht** zu. Dieses Dokument hält fest, was sich tatsächlich
belegen lässt und was offen ist.

## Bestandsaufnahme

| Datei | Bedeutung (geprüft) | Technische Spuren in der Datei | Herkunft |
|---|---|---|---|
| `M001.svg` | Allgemeines Gebotszeichen | einzeilig minifiziert, kein `sodipodi`/Inkscape-Namespace, keine Metadaten | **unbekannt** |
| `M002.svg` | Anleitung beachten | wie oben | **unbekannt** |
| `M003.svg` | Gehörschutz benutzen | wie oben | **unbekannt** |
| `M004.svg` | Augenschutz benutzen | wie oben | **unbekannt** |
| `M008.svg` | Fußschutz benutzen | wie oben | **unbekannt** |
| `M009.svg` | Schutzhandschuhe benutzen | wie oben | **unbekannt** |
| `M010.svg` | Schutzkleidung benutzen | wie oben | **unbekannt** |
| `M011.svg` | Hände waschen | wie oben | **unbekannt** |
| `M013.svg` | Gesichtsschutzschirm benutzen | wie oben | **unbekannt** |
| `M017.svg` | Atemschutz benutzen | wie oben | **unbekannt** |
| `M024.svg` | Diesen Weg benutzen | wie oben | **unbekannt** |
| `E003.svg` | Erste Hilfe | 543 B, handgezeichnete Geometrie (zwei Rechtecke als Kreuz), keine Metadaten | **unbekannt**, aber triviales Motiv |
| `F001.svg` | Feuerlöscher | Inkscape-Export (`sodipodi:docname="ISO_7010_F001.svg"`, Inkscape 1.0.2); RDF-Block vorhanden, aber `<dc:title />` **leer** und **kein `cc:license`** | vermutlich Wikimedia Commons, Lizenzangabe **entfernt** |

## Wie die Bedeutung der Zeichen geprüft wurde

Die Codes in den Dateinamen wurden nicht übernommen, sondern gegen zwei
unabhängige Quellen geprüft:

1. **Grafik:** Alle 13 Dateien wurden gerendert und angesehen. Ergebnis: die
   Dateien zeigen die offiziellen ISO-7010-Motive.
2. **Offizielle Liste:** Abgleich der Codes gegen die ISO-7010-Übersicht
   (M-Serie, Mandatory action signs).

Beides stimmt überein. Die **Beschriftungen in der Anwendung** waren dagegen in
5 von 11 Fällen falsch und wurden in `main.py` (`BA_GEBOTSZEICHEN`) korrigiert:

| Code | Falsch (vorher) | Richtig (jetzt) |
|---|---|---|
| `M002` | Gehörschutz benutzen | Anleitung beachten |
| `M003` | Augenschutz benutzen | Gehörschutz benutzen |
| `M004` | Schutzhelm benutzen | Augenschutz benutzen |
| `M024` | Hautschutzcreme benutzen | Diesen Weg benutzen |

„Schutzhelm benutzen" und „Hautschutzcreme benutzen" gehören zu **M014** und
**M022**. Diese Zeichen sind hier **nicht vorhanden**; die alten Beschriftungen
hatten also nie eine passende Grafik.

## Lizenzstatus: offen

* Das Repository hat **keine `LICENSE`-Datei**.
* Die ISO-7010-Symbole werden auf Wikimedia Commons überwiegend als
  gemeinfrei eingestuft (`{{PD-self}}` / „PD-simple"). Für `M003` wurde das
  stellvertretend geprüft: die Commons-Seite trägt `{{PD-self}}`, als Autor ist
  ISO genannt, als Quelle „ISO 7010 – M003".
* Für die 11 M-Dateien und `E003.svg` ist die Herkunft in den Dateien selbst
  **nicht** dokumentiert. Ob die Einstufung als gemeinfrei trägt, ist damit
  nicht belegt.
* `E003.svg` ist eine Eigenkonstruktion aus zwei Rechtecken. Ein solches Motiv
  ist nach gängiger Auffassung nicht schutzfähig, die Frage ist hier also
  praktisch bedeutungslos.

**Vor einer Veröffentlichung zu klären:** Für jede Datei die konkrete
Quell-URL und die dort angegebene Lizenz eintragen. Solange das fehlt, ist die
Rechtslage für die gedruckte Arbeitsplatz-Betriebsanweisung unklar.

## Offene Punkte

* `M014` (Schutzhelm) und `M022` (Hautschutzcreme) fehlen. Ein Ergänzen setzt
  Dateien mit **belegter** Herkunft voraus – nicht einfach irgendwoher kopieren.
* Die Bezeichnungen `M013` („Gesichtsschutzschirm") und `M024`
  („Diesen Weg benutzen") sind für eine Gefahrstoff-Betriebsanweisung nur
  eingeschränkt nützlich. Ob sie im Auswahlfenster bleiben, ist eine
  fachliche Entscheidung.
* `F001.svg` sollte aus der Quelle neu geladen werden, damit die
  Lizenzangabe im RDF-Block erhalten bleibt.
