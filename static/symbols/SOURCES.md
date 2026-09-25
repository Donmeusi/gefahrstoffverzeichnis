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
| `M014.svg` | Kopfschutz benutzen | einzeilig minifiziert, kein Inkscape-Namespace, `width`/`height` = 265 | **belegt**, siehe unten |
| `M017.svg` | Atemschutz benutzen | wie oben | **unbekannt** |
| `M022.svg` | Hautschutzmittel benutzen | wie oben | **belegt**, siehe unten |
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
**M022**. Diese Zeichen waren hier ursprünglich **nicht vorhanden**; die alten
Beschriftungen hatten also nie eine passende Grafik. Seit dem 25.09.2026 sind
beide ergänzt und tragen ihre offiziellen Bezeichnungen.

## Lizenzstatus: offen

* Das Repository hat **keine `LICENSE`-Datei**.
* Die ISO-7010-Symbole werden auf Wikimedia Commons überwiegend als
  gemeinfrei eingestuft (`{{PD-self}}` / „PD-simple"). Für `M003` wurde das
  stellvertretend geprüft: die Commons-Seite trägt `{{PD-self}}`, als Autor ist
  ISO genannt, als Quelle „ISO 7010 – M003".
* Für die 11 weiterhin undokumentierten M-Dateien und `E003.svg` ist die
  Herkunft in den Dateien selbst **nicht** dokumentiert. Ob die Einstufung als
  gemeinfrei trägt, ist damit nicht belegt. `M014.svg` und `M022.svg` sind
  davon **nicht** betroffen, ihre Herkunft ist unten belegt.
* `E003.svg` ist eine Eigenkonstruktion aus zwei Rechtecken. Ein solches Motiv
  ist nach gängiger Auffassung nicht schutzfähig, die Frage ist hier also
  praktisch bedeutungslos.

**Vor einer Veröffentlichung zu klären:** Für jede Datei die konkrete
Quell-URL und die dort angegebene Lizenz eintragen. Solange das fehlt, ist die
Rechtslage für die gedruckte Arbeitsplatz-Betriebsanweisung unklar.

## Belegte Herkunft: `M014.svg` und `M022.svg`

Diese beiden Dateien wurden am 25.09.2026 ergänzt. Sie sind **unverändert** von
Wikimedia Commons übernommen (byte-identisch), damit die Herkunft über den
Hash nachprüfbar bleibt:

| Datei | Quell-URL | Lizenz | SHA-256 |
|---|---|---|---|
| `M014.svg` | https://upload.wikimedia.org/wikipedia/commons/0/0c/ISO_7010_M014.svg | `{{PD-self}}` | `46bdad9a9f23237d0faa48880d85c2af626c497db03d00463e097e9b7bcf0382` |
| `M022.svg` | https://upload.wikimedia.org/wikipedia/commons/4/44/ISO_7010_M022.svg | `{{PD-self}}` | `d05bd1cffd1148cd78e9131ecae19613604061a9c305b83fce935e35175d9e91` |

Beide Commons-Seiten nennen als Autor „ISO", als Quelle „ISO 7010 – M014"
bzw. „ISO 7010 – M022" und tragen die Freigabeerklärung „I, the copyright
holder of this work, release this work into the public domain". Das ist
dieselbe Einstufung, die für `M003` bereits geprüft wurde.

**Grafik geprüft:** Beide Dateien wurden gerendert und angesehen. `M014` zeigt
einen Kopf mit Helm, `M022` eine Hand mit einer Salbentube. Beides passt zu den
offiziellen Bezeichnungen.

## Bezeichnungen

Die Bezeichnungen wurden gegen zwei unabhängige Quellen geprüft: die amtliche
Liste in **ASR A1.3, Anhang 1** (Gebotszeichen) und die Übersicht in
**DGUV Information 211-041**, Anhang 3. Beide führen:

* `M014` → „Kopfschutz benutzen" (nicht „Schutzhelm benutzen")
* `M022` → „Hautschutzmittel benutzen" (nicht „Hautschutzcreme benutzen")

## Ein Nebenbefund zur Herkunft der übrigen Dateien

Die beiden Commons-Originale sind **stilistisch nicht von den vorhandenen
M-Dateien zu unterscheiden**: 265 × 265, einzeilig minifiziert, `fill="#005387"`,
`fill-rule="evenodd"`, kein `sodipodi`/Inkscape-Namespace, keine Metadaten.
Verglichen mit `M009.svg` und `M017.svg` ergibt sich kein sichtbarer oder
technischer Unterschied.

Das ist **kein Beleg**, aber ein weiteres Indiz dafür, dass die 11 vorhandenen
M-Dateien aus derselben Commons-Serie stammen und ihre Herkunft nur nicht
dokumentiert wurde. Wer die offenen Herkunftsfragen klären will, sollte dort
ansetzen.

## Offene Punkte

* ~~`M014` (Schutzhelm) und `M022` (Hautschutzcreme) fehlen.~~ **Erledigt am
  25.09.2026** – beide sind mit belegter Herkunft ergänzt, siehe oben.
* Für die **11 übrigen M-Dateien** fehlt weiterhin die belegte Herkunft. Der
  Nebenbefund oben zeigt, wo die Spur ansetzt: dieselbe Commons-Serie. Der
  saubere Weg ist dort, jede Datei von der Commons-Seite neu zu laden und
  Quell-URL, Lizenz und Hash hier einzutragen — nach demselben Muster wie bei
  `M014`/`M022`.
* Die Bezeichnungen `M013` („Gesichtsschutzschirm") und `M024`
  („Diesen Weg benutzen") sind für eine Gefahrstoff-Betriebsanweisung nur
  eingeschränkt nützlich. Ob sie im Auswahlfenster bleiben, ist eine
  fachliche Entscheidung.
* `F001.svg` sollte aus der Quelle neu geladen werden, damit die
  Lizenzangabe im RDF-Block erhalten bleibt.
