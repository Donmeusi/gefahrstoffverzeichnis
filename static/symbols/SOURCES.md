# Herkunft der ISO-7010-Symbole

Diese Dateien werden in der Betriebsanweisung (`templates/ba_print.html`) verwendet.
Der Branch `beta` hat sie mit der Behauptung eingeführt, es seien „exact official
Wikimedia Commons ISO 7010 vector files". Diese Behauptung war unbelegt. Am
**25.09.2026** wurde sie überprüft — mit einem eindeutigen Ergebnis.

## Ergebnis: alle Dateien sind belegt und gemeinfrei

Für **jede** Datei in diesem Ordner gilt: sie ist **byte-identisch** mit der
aktuellen Fassung auf Wikimedia Commons. Der SHA-256-Hash stimmt überein. Damit
ist die Herkunft nicht mehr Vermutung, sondern nachprüfbar — auch für
`E003.svg`, das zuvor als Eigenkonstruktion geführt wurde (es ist die offizielle
Commons-Datei, nur sehr einfach gezeichnet).

**Alle hier verbliebenen 14 Dateien sind gemeinfrei.** Es gibt in diesem Ordner
damit **keine Lizenzunsicherheit mehr**. Der einzige Problemfall, `M002.svg`
(CC BY-SA 3.0, Namensnennungspflicht), wurde am 25.09.2026 **entfernt** — die
Begründung und der Nachweis stehen weiter unten, damit der Vorgang
nachvollziehbar bleibt.

## Nachweis pro Datei

Abruf der Fassungen am 25.09.2026. Die Hashes sind die der Dateien **im Repo**;
sie stimmen mit den heruntergeladenen Originalen überein.

| Datei | Bezeichnung | Lizenz laut Commons | SHA-256 |
|---|---|---|---|
| `M001.svg` | Allgemeines Gebotszeichen | Public domain | `74cf07c66b3f4f310b28ec3567261da5d9d2c9c662f34f41f1eab8858b9fd83f` |
| `M003.svg` | Gehörschutz benutzen | Public domain | `95011a231679328752fee3f4244d312e5e8a6370f52b0b113eea80f34c3faa7f` |
| `M004.svg` | Augenschutz benutzen | Public domain | `4f48fc3c89c5cbe968886cae45c448f347f8488db9d4662b7fc3472ffdadf47c` |
| `M008.svg` | Fußschutz benutzen | Public domain | `f8ede9fe797aace32b52002ef4c4f7ddff86f56c5372817f2c81ea9e0b542e87` |
| `M009.svg` | Handschutz benutzen | Public domain | `889059fbb7391d931ae44efa0c0a46d4c065f26729b08875c3a9ddf6f7f709b3` |
| `M010.svg` | Schutzkleidung benutzen | Public domain | `cd778b7164239bb80e24fa678477e632ecdd7b43122eccd945b46145c66a2c9e` |
| `M011.svg` | Hände waschen | Public domain | `4da507ae200c716ae6cad6101a677c5eb0e3df1e673257f9016e10b2d54e5ac9` |
| `M013.svg` | Gesichtsschutz benutzen | Public domain | `da48b12cb73186638ee6836744f343b9f89e6bdb9bb170ee37b7b631be704c10` |
| `M014.svg` | Kopfschutz benutzen | Public domain | `46bdad9a9f23237d0faa48880d85c2af626c497db03d00463e097e9b7bcf0382` |
| `M017.svg` | Atemschutz benutzen | Public domain | `1d5fa609c58f8fc9efe7f6cc5c6ac36e2ca59d70b773cddcd5878a1731ca9d0b` |
| `M022.svg` | Hautschutzmittel benutzen | Public domain | `d05bd1cffd1148cd78e9131ecae19613604061a9c305b83fce935e35175d9e91` |
| `M024.svg` | Fußgängerweg benutzen | Public domain | `feac90fd44b90b186a5c6a77bb3f5e3767a8cd28ac3d310a1039d1f803fd88e3` |
| `F001.svg` | Feuerlöscher | Public domain (Autor: MaxxL) | `8eab9ee3de88fa5a8fe09f22bc3b3f659af44a68e6887799422d3ba817cddd49` |
| `E003.svg` | Erste Hilfe | Public domain | `beb947d67ed4d41cb29ca5104933bea20b7012acfe610702fe3f3486112ac333` |

Quellseiten (Muster `https://commons.wikimedia.org/wiki/File:ISO_7010_<CODE>.svg`):

* `M001` https://upload.wikimedia.org/wikipedia/commons/e/ee/ISO_7010_M001.svg
* `M002` https://upload.wikimedia.org/wikipedia/commons/b/b1/ISO_7010_M002.svg
* `M003` https://upload.wikimedia.org/wikipedia/commons/7/75/ISO_7010_M003.svg
* `M004` https://upload.wikimedia.org/wikipedia/commons/0/01/ISO_7010_M004.svg
* `M008` https://upload.wikimedia.org/wikipedia/commons/3/3c/ISO_7010_M008.svg
* `M009` https://upload.wikimedia.org/wikipedia/commons/7/7c/ISO_7010_M009.svg
* `M010` https://upload.wikimedia.org/wikipedia/commons/1/10/ISO_7010_M010.svg
* `M011` https://upload.wikimedia.org/wikipedia/commons/d/de/ISO_7010_M011.svg
* `M013` https://upload.wikimedia.org/wikipedia/commons/1/19/ISO_7010_M013.svg
* `M014` https://upload.wikimedia.org/wikipedia/commons/0/0c/ISO_7010_M014.svg
* `M017` https://upload.wikimedia.org/wikipedia/commons/d/d6/ISO_7010_M017.svg
* `M022` https://upload.wikimedia.org/wikipedia/commons/4/44/ISO_7010_M022.svg
* `M024` https://upload.wikimedia.org/wikipedia/commons/4/4f/ISO_7010_M024.svg
* `F001` https://upload.wikimedia.org/wikipedia/commons/3/3e/ISO_7010_F001.svg
* `E003` https://upload.wikimedia.org/wikipedia/commons/0/0e/ISO_7010_E003_-_First_aid_sign.svg

## Wie geprüft wurde

Drei voneinander unabhängige Prüfungen, alle am 25.09.2026:

1. **Hash-Vergleich.** Jede Datei wurde von Wikimedia geladen und per SHA-256
   gegen die Repo-Fassung verglichen. Ergebnis: bei allen 15 Dateien identisch.
2. **Grafik angesehen.** Alle Zeichen wurden gerendert (`rsvg-convert`) und
   betrachtet. Jedes zeigt das Motiv, das seine Bezeichnung behauptet.
3. **Bezeichnung gegen offizielle Listen.** Abgleich mit der amtlichen Liste in
   **ASR A1.3, Anhang 1** und mit **DGUV Information 211-041**, Anhang 3.

## `M002.svg` — entfernt am 25.09.2026 (CC BY-SA 3.0)

`M002` („Gebrauchsanweisung beachten") war die **einzige** Datei hier, die nicht
gemeinfrei ist: die Commons-Seite trägt als einzigen Lizenzbaustein
`{{self|cc-by-sa-3.0}}`. Nachgeprüft im Wikitext der Seite, nicht nur über die
API — es gibt dort **keinen** zusätzlichen Public-Domain-Baustein. Damit gilt
**Namensnennungspflicht** (`AttributionRequired: true`, Urheber laut Seite
„ISO", Quelle „ISO 7010 – M002 / Own work").

Auch der deutsche Wikipedia-Artikel bindet nur diese Commons-Datei ein — die
Seite `de.wikipedia.org/wiki/Datei:ISO_7010_M002.svg` existiert dort **nicht
lokal** und zeigt deshalb dieselbe Lizenz. Über Wikipedia gibt es also keine
freiere Fassung.

Die Datei wurde deshalb **aus dem Repo und aus `BA_GEBOTSZEICHEN` entfernt**
(Entscheidung des Betreibers). Gründe, die dabei mitgespielt haben:

* Auf Commons existiert **keine** gemeinfreie oder CC0-Fassung dieses Motivs.
  Der einzige weitere Treffer, `Unofficial additional ISO 7010 sign M002 Keep
  door closed.svg`, zeigt ein **anderes** Motiv und ist ausdrücklich inoffiziell.
* `M002` **fehlt in ASR A1.3, Anhang 1** — die Liste springt von M001 auf M003.
  Es gehört damit nicht zum amtlichen deutschen Zeichensatz, den ASR A1.3
  auflistet.
* Eine Namensnennung im Ausdruck hätte das sorgfältig ausgemessene
  Ein-Seiten-Layout der Betriebsanweisung gefährdet.

**Nachweis der entfernten Datei** (für die Nachvollziehbarkeit, SHA-256 der
Fassung vom 25.09.2026, byte-identisch mit Commons):

| Datei | Quell-URL | Lizenz | SHA-256 |
|---|---|---|---|
| `M002.svg` (entfernt) | https://upload.wikimedia.org/wikipedia/commons/b/b1/ISO_7010_M002.svg | CC BY-SA 3.0 | `b4e456e4f10b72703e4fe39bbc05ce6efde22077beb2d500bf070bf55facd790` |

Bereits gespeicherte Betriebsanweisungen mit `M002` sind unkritisch:
`load_ba_gebotszeichen` in `main.py` filtert unbekannte Codes heraus, das Zeichen
verschwindet also einfach aus dem Ausdruck. In der Datenbank war ohnehin kein
einziger Datensatz mit Gebotszeichen belegt (geprüft am 25.09.2026).

## Bezeichnungen

Die Grafik jedes Zeichens passt zur Beschriftung — der Fehler der Vorfassung
(fünf falsche Beschriftungen, u. a. „Schutzhelm" an einem Augenschutz-Zeichen)
ist behoben.

**Zwei Beschriftungen weichen bewusst vom amtlichen Wortlaut ab.** Sie sind
inhaltlich nicht falsch, treffen aber nicht die Normformulierung. Das ist eine
**getroffene Entscheidung**, kein offener Punkt: der Betreiber hat am 25.09.2026
entschieden, sie zugunsten der Verständlichkeit für die Anwender so zu lassen.

| Code | Amtlich (ASR A1.3) | Im Repo (bewusst) | Anmerkung |
|---|---|---|---|
| `M009` | Handschutz benutzen | Schutzhandschuhe benutzen | ASR A1.3 |
| `M013` | Gesichtsschutz benutzen | Gesichtsschutzschirm benutzen | ASR A1.3 |

Geprüft gegen **drei** Quellen, die sich in diesen Fällen einig sind: ASR A1.3
Anhang 1, DGUV Information 211-041 Anhang 3 und der Wikipedia-Artikel
„ISO 7010".

`M001`, `M003`, `M004`, `M008`, `M010`, `M011`, `M014`, `M017`, `M022` stimmen
wörtlich mit der amtlichen Liste überein.

## Zwei Zeichen sind nicht mehr in der Auswahl

| Code | Bezeichnung | Grund | Datei |
|---|---|---|---|
| `M002` | Gebrauchsanweisung beachten | CC BY-SA 3.0, Namensnennungspflicht | **gelöscht** |
| `M024` | Fußgängerweg benutzen / „Diesen Weg benutzen" | fachlich ohne Nutzen für eine Gefahrstoff-BA | liegt weiter im Ordner |

`M024` wurde am 25.09.2026 aus `BA_GEBOTSZEICHEN` entfernt. Anders als bei `M002`
ist die Datei **gemeinfrei** — es gab also keinen Lizenzgrund, sie zu löschen. Sie
liegt weiterhin hier; sie wird nur nicht mehr angeboten. Ein Wiederaufnehmen wäre
eine Zeile in `main.py`. Wird sie wieder angeboten, ist die Beschriftung wieder
die Abweichung „Diesen Weg benutzen" (amtlich: „Fußgängerweg benutzen").

`load_ba_gebotszeichen` in `main.py` filtert beide Codes heraus. Bereits
gespeicherte Betriebsanweisungen verlieren das Zeichen dadurch einfach; in der
Datenbank war ohnehin kein Datensatz mit Gebotszeichen belegt (geprüft am
25.09.2026).

## `E003.svg` — doch keine Eigenkonstruktion

Die frühere Notiz hier lautete, `E003` sei eine Eigenkonstruktion aus zwei
Rechtecken. **Das war falsch.** Ein Hash-Vergleich am 25.09.2026 zeigt: die Datei
ist byte-identisch mit `File:ISO 7010 E003.svg` auf Commons (Public domain).
Sie *sieht* nur sehr einfach aus, weil die Commons-Datei so gezeichnet ist —
weißes Quadrat, grünes Quadrat (`#237F52`), zwei weiße Rechtecke als Kreuz,
400 × 400 px.

Der einzige Unterschied zu den übrigen Dateien ist der Zeichenstil: diese Datei
ist mehrzeilig und mit `style`-Attributen geschrieben, die M-Zeichen sind
einzeilig minifiziert. Optisch passt sie (grünes Erste-Hilfe-Zeichen). Es besteht
**kein Handlungsbedarf** — die Lizenzfrage ist geklärt, und das Motiv ist das
offizielle.

## Offene Punkte

* ~~**`M002` lizenzieren oder ersetzen.**~~ **Erledigt am 25.09.2026** — Zeichen
  entfernt, siehe oben. Alle verbliebenen Dateien sind gemeinfrei.
* ~~**Beschriftungen** auf den amtlichen Wortlaut umstellen.~~
  **Entschieden am 25.09.2026:** `M009` und `M013` bleiben wie sie sind,
  `M002` und `M024` werden nicht mehr angeboten. Siehe Tabellen oben.
* **Nachkontrolle.** Die Hashes oben sind der Stand vom 25.09.2026. Wenn Commons
  eine Datei überarbeitet, laufen Repo und Quelle auseinander. Bei Zweifel
  erneut laden und vergleichen.
