#!/usr/bin/env python3
"""Import von Gefahrstoffen aus Excel (.xlsx) oder CSV.

Wozu ein eigenes Modul: Datei lesen, Spalten erkennen und Zeilen prüfen sind
drei Schritte, die sich einzeln prüfen lassen. In den View-Code von main.py
gehören sie nicht - dort bliebe von der Logik nur, was sich über einen
vollständigen Request testen lässt, und die Datenbank stünde im Weg. Diese
Datei kennt deshalb weder Flask noch SQLAlchemy.

Drei Fallen, die den Aufbau bestimmen:

* **Der Excel-Export ist kein Importformat.** export_excel() schreibt "Menge"
  als "4.5 kg" und den Standort als "Bereich > Unterbereich" - lesbar für
  Menschen, aber nicht wieder einlesbar. Deshalb gibt es hier einen eigenen
  Spaltenkatalog (FELDER) mit Aliasen und eine Vorlage zum Herunterladen.
* **Deutsches Excel schreibt CSV mit Semikolon und cp1252.** Ohne
  Encoding-Kette und Trennzeichen-Erkennung scheitert jeder zweite Import.
* **Zellen sind nicht immer Text.** CAS-Nummern, Mengen und Datumsangaben
  kommen je nach Zellformat als Zahl oder als datetime an. Jedes Feld wird
  deshalb einzeln und nachsichtig gelesen; abgelehnt wird eine Zeile nur,
  wenn ein Pflichtfeld fehlt oder ein Wert nicht deutbar ist.

Eine vierte Regel seit 18.11.2026: **Eine fremde Struktur ist kein Fehler.**
Selbst geführte Gebindelisten heißen "Produkt" statt "Name", "Raum" statt
"Lagerort" und führen CMR und aufgebrauchte Behälter in eigenen Spalten.
Deshalb: das beste Blatt statt des ersten, die Kopfzeile auch weiter unten,
Stichwörter in der Beschriftung, und wenn das alles nicht trifft, der
Zellinhalt (CAS-Muster, H-Sätze, GHS-Codes, Textspalte als Name). Abgelehnt
wird nur, was gar keine Tabelle ist.

Aufbau:
  lies_datei()        Bytes -> RohTabelle (Kopfzeile + Zeilen, alles Rohwerte)
  erkenne_spalten()   Kopfzeile -> {feld: Spaltenindex}
  ergaenze_aus_inhalt() fehlende Spalten aus den Zellwerten bestimmen
  spalten_bericht()   unbekannte und doppelte Spalten für die Vorschau
  pruefe_zeile()      Rohwerte einer Zeile -> PrüfZeile (Werte/Fehler/Warnungen)
  markiere_duplikate() gleiche Stoffe am selben Ort zu Gebinden zusammenfassen
  vorlage_xlsx()      Importvorlage als XLSX

Geprüft in test_import.py.
"""
import csv
import datetime as _dt
import io
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from piktogramme import (
    codes_aus_text,
    piktogramme_fuer,
    signalwort_fuer,
    unbekannte_codes,
)

# Grenzen. Sie liegen bewusst unter MAX_CONTENT_LENGTH (16 MB): Ein
# Gefahrstoffverzeichnis hat hunderte, nicht hunderttausende Zeilen. Wer mehr
# hochlädt, hat versehentlich die falsche Datei erwischt - das soll eine
# Meldung geben und keinen mehrere Sekunden blockierten Worker.
MAX_BYTES = 5 * 1024 * 1024
MAX_ZEILEN = 5000

UNTERSTUETZTE_ENDUNGEN = ('xlsx', 'xlsm', 'csv')

# Piktogramme nach CLP, Anhang V. Mehr gibt es nicht; alles andere ist ein
# Tippfehler und soll nicht stillschweigend in der Datenbank landen.
PIKTOGRAMME = ('GHS01', 'GHS02', 'GHS03', 'GHS04', 'GHS05',
               'GHS06', 'GHS07', 'GHS08', 'GHS09')

# Die fünf Einheiten aus dem Formular (templates/add.html). Andere Werte
# werden übernommen, aber als Warnung gemeldet - die Datenbankspalte ist
# Freitext, das Formular bietet jedoch nur diese Auswahl an.
MENGENEINHEITEN = {
    'l': 'L', 'liter': 'L', 'lt': 'L',
    'ml': 'ml', 'milliliter': 'ml',
    'kg': 'kg', 'kilogramm': 'kg', 'kilo': 'kg',
    'g': 'g', 'gramm': 'g',
    'stk': 'Stk', 'st': 'Stk', 'stueck': 'Stk', 'stueckzahl': 'Stk',
}

# Lagerklassen nach TRGS 510, wie sie das Formular anbietet. Die Spalte ist
# Freitext; ein unbekannter Wert wird gemeldet, aber nicht abgelehnt.
LAGERKLASSEN = {
    '1', '2A', '2B', '3', '4.1A', '4.1B', '4.2', '4.3',
    '5.1A', '5.1B', '5.1C', '5.2',
    '6.1A', '6.1B', '6.1C', '6.1D', '6.2', '7',
    '8A', '8B', '10', '11', '12', '13',
}

SIGNALWOERTER = {
    'gefahr': 'Gefahr', 'danger': 'Gefahr',
    'achtung': 'Achtung', 'warning': 'Achtung',
}

_WAHRHEIT = {
    'ja': 'ja', 'j': 'ja', 'jawohl': 'ja', 'yes': 'ja', 'y': 'ja',
    'true': 'ja', 'wahr': 'ja', '1': 'ja', 'x': 'ja',
    'nein': 'nein', 'n': 'nein', 'no': 'nein',
    'false': 'nein', 'falsch': 'nein', '0': 'nein',
}


# ─── Spaltenkatalog ──────────────────────────────────────────────────────────
#
# Eine Stelle für alles, was eine Spalte ausmacht: Beschriftung (auch für die
# Vorlage), Aliase für die Erkennung und die Länge der Datenbankspalte.
# Die Reihenfolge bestimmt die Spaltenfolge in der Vorlage.

FELDER = {
    'name': {
        'label': 'Name', 'pflicht': True, 'laenge': 100,
        # "Produkt" ist die gebräuchlichste Beschriftung in selbst geführten
        # Gebindelisten und war der Grund, warum solche Dateien bisher
        # vollständig abgelehnt wurden (Nutzerbeispiel 18.11.2026).
        'aliase': ('Name', 'Stoff', 'Stoffname', 'Stoff-/Produktname',
                   'Stoff/Produkt', 'Stoffname / Produktname',
                   'Bezeichnung', 'Produkt', 'Produktname',
                   'Produktbezeichnung', 'Produktidentifikator',
                   'Handelsname', 'Handelsname (Produkt)', 'Stoffbezeichnung',
                   'Name des Stoffes', 'Substanz', 'Chemikalie',
                   'Chemikalienname', 'Reagenz', 'Präparat', 'Material'),
    },
    'cas_nummer': {
        'label': 'CAS-Nummer', 'laenge': 20,
        'aliase': ('CAS-Nummer', 'CAS', 'CAS-Nr.', 'CAS-Nr', 'CAS-No',
                   'CAS-Nr', 'CAS Registry Number', 'CAS RN', 'CAS Number',
                   'CAS-#', 'CAS ID'),
    },
    'eg_nummer': {
        'label': 'EG-Nummer', 'laenge': 20,
        'aliase': ('EG-Nummer', 'EG-Nr.', 'EG-Nr', 'EG-No', 'EG',
                   'EC-Nummer', 'EC-Nr.', 'EC-No', 'EC', 'EC Number',
                   'EINECS', 'EINECS-Nummer', 'ELINCS'),
    },
    'signalwort': {
        'label': 'Signalwort', 'laenge': 10,
        'aliase': ('Signalwort', 'Signal Word', 'Gefahrensignal'),
    },
    'piktogramme': {
        'label': 'Piktogramme', 'laenge': 100,
        'aliase': ('Piktogramme', 'Piktogramm', 'Piktos',
                   'GHS-Piktogramme', 'Gefahrenpiktogramme', 'GHS-Symbole',
                   'Hazard Pictograms'),
    },
    'gefahrenkategorien': {
        'label': 'Einstufung & Gefahren', 'laenge': 500,
        'aliase': ('Einstufung & Gefahren', 'Einstufung', 'Einstufung GHS',
                   'Einstufung und Gefahren', 'Einstufung (CLP)',
                   'Gefahrenkategorien', 'Gefahrenklassen',
                   'Gefahrenklasse', 'GHS-Klassifizierung',
                   'Classification'),
    },
    'h_saetze': {
        'label': 'H-Sätze', 'laenge': 200,
        'aliase': ('H-Sätze', 'H-Saetze', 'H-Satz', 'H-Saetz',
                   'H-Gefahrenhinweise', 'H-Statements', 'H Statements',
                   'Hazard Statements', 'H-Codes', 'Gefahrenhinweise'),
    },
    'p_saetze': {
        'label': 'P-Sätze', 'laenge': 300,
        'aliase': ('P-Sätze', 'P-Saetze', 'P-Satz', 'P-Saetz',
                   'P-Sicherheitshinweise', 'P-Statements',
                   'P Statements', 'Precautionary Statements', 'P-Codes',
                   'Sicherheitshinweise'),
    },
    'menge': {
        'label': 'Menge', 'laenge': None,
        'aliase': ('Menge', 'Bestand', 'Füllmenge', 'Inhalt',
                   'Quantity', 'Amount', 'Volumen',
                   # Zusatzspalte des Excel-Exports: gleiche Bedeutung, nur
                   # ohne Einheit. Welche der beiden gewinnt, ist egal - die
                   # Einheit kommt in beiden Fällen richtig an.
                   'Menge (Zahl)'),
    },
    'mengeneinheit': {
        'label': 'Einheit', 'laenge': 10,
        'aliase': ('Einheit', 'Mengeneinheit', 'Maßeinheit',
                   'Masseinheit', 'Unit', 'ME'),
    },
    'lagerort': {
        'label': 'Lagerort', 'laenge': 100,
        'aliase': ('Lagerort', 'Lagerplatz', 'Regal', 'Schrank',
                   'Detailstandort', 'Raum', 'Raumnummer', 'Raum-Nr.',
                   'Raumname', 'Lagerraum', 'Fach', 'Aufstellungsort',
                   'Ort im Raum'),
    },
    'lagerklasse': {
        'label': 'Lagerklasse', 'laenge': 10,
        'aliase': ('Lagerklasse', 'LGK', 'LGK-Klasse', 'TRGS 510',
                   'Lagerklasse (TRGS 510)', 'Storage Class'),
    },
    'bereich': {
        'label': 'Bereich', 'laenge': 100,
        'aliase': ('Bereich', 'Bereichsname', 'Abteilung',
                   'Organisationseinheit'),
    },
    'unterbereich': {
        'label': 'Unterbereich', 'laenge': 200,
        'aliase': ('Unterbereich', 'Unterbereichsname',
                   'Unterbereichspfad', 'Arbeitsbereich'),
    },
    'standort': {
        # Kombinierte Angabe "Bereich › Unterbereich". Der Export schreibt
        # genau das in die Spalte "Arbeitsbereich", damit ist der Rundlauf
        # möglich, ohne dass jemand zwei Spalten nachtragen muss.
        'label': 'Standort (Bereich › Unterbereich)', 'laenge': 300,
        'aliase': ('Standort', 'Arbeitsbereich', 'Ort', 'Location',
                   'Aufstellungsort (Bereich)'),
    },
    'sdb_datum': {
        'label': 'SDB-Datum', 'laenge': None,
        'aliase': ('SDB-Datum', 'Datum SDB', 'Datum des SDB',
                   'Sicherheitsdatenblatt-Datum', 'SDB gültig ab'),
    },
    'substitutionspruefung': {
        'label': 'Substitutionsprüfung', 'laenge': 10,
        'aliase': ('Substitutionsprüfung', 'Substitution',
                   'Substitutionsprüfung durchgeführt'),
    },
    'ersatzstoff': {
        'label': 'Ersatzstoff', 'laenge': 200,
        'aliase': ('Ersatzstoff', 'Alternativstoff', 'Substitute'),
    },
    'begruendung': {
        'label': 'Begründung', 'laenge': 500,
        'aliase': ('Begründung', 'Begruendung', 'Grund', 'Reason'),
    },
    'substitution_geprueft_am': {
        'label': 'Substitutionsprüfung geprüft am', 'laenge': None,
        'aliase': ('Substitutionsprüfung geprüft am',
                   'Substitutionspruefung geprueft am',
                   'Geprüft am', 'Datum Substitutionsprüfung'),
    },
    # Drei Spalten, die es in der Datenbank nicht gibt, die aber das Ergebnis
    # des Imports ändern. Sie stehen deshalb im Katalog und nicht bei den
    # ignorierten Spalten.
    'cmr': {
        # Eine Quelle, die CMR selbst führt, darf nicht erst durch die
        # H-Satz-Ableitung als CMR gelten - sonst wäre der Stoff sofort
        # sichtbar, obwohl eine Freigabe nötig ist.
        'label': 'CMR-Stoff', 'laenge': None,
        'aliase': ('CMR', 'CMR-Stoff', 'CMR ja/nein', 'CMR-Einstufung',
                   'Krebserzeugend', 'CMR-Stoff (ja/nein)'),
    },
    'aufgebraucht': {
        # Gebindelisten führen aufgebrauchte Behälter mit. Die Zeile bleibt
        # in der Vorschau sichtbar, wird aber nicht angelegt.
        'label': 'Aufgebraucht', 'laenge': None,
        'aliase': ('Aufgebraucht', 'Verbraucht', 'Entnommen', 'Leer',
                   'Bestand aufgebraucht', 'Aufgebraucht (ja/nein)'),
    },
    'gebinde': {
        # Nur für die Zusammenfassung: Mehrere Zeilen desselben Stoffes am
        # selben Ort sind mehrere Gebinde, kein Duplikat.
        'label': 'Gebinde-Nummer', 'laenge': 50,
        'aliase': ('Gebinde-Nummer', 'Gebindenummer', 'Gebinde-Nr.',
                   'Gebindenr.', 'Gebinde', 'Gebinde-ID'),
    },
}

# Spalten der Importvorlage. "Standort" fehlt bewusst: Die Vorlage bietet
# Bereich und Unterbereich als getrennte Spalten an, das ist beim Ausfüllen
# eindeutiger. Beim Lesen werden beide Formen akzeptiert.
VORLAGE_FELDER = (
    'name', 'cas_nummer', 'eg_nummer', 'signalwort', 'piktogramme',
    'gefahrenkategorien', 'h_saetze', 'p_saetze',
    'menge', 'mengeneinheit', 'lagerort', 'lagerklasse',
    'bereich', 'unterbereich',
    'sdb_datum', 'substitutionspruefung', 'ersatzstoff', 'begruendung',
    'substitution_geprueft_am',
)

# Vorlagen-Hinweise je Spalte (zweites Blatt der Vorlage).
VORLAGE_HINWEISE = (
    ('Name', 'Pflichtfeld. Muss für jede Zeile gefüllt sein.'),
    ('CAS-Nummer', 'Format 123-45-6. Fehlt sie, wird die Zeile trotzdem '
                   'importiert und nur als Warnung gemeldet.'),
    ('Signalwort', 'Gefahr oder Achtung. Leer lassen: wird aus den H-Sätzen '
                   'abgeleitet.'),
    ('Piktogramme', 'GHS01 bis GHS09, kommagetrennt. Leer lassen: wird aus '
                    'den H-Sätzen abgeleitet.'),
    ('Einstufung & Gefahren', 'Freitext aus dem Sicherheitsdatenblatt.'),
    ('H-Sätze', 'z. B. "H225, H319, H336". Grundlage für Piktogramme, '
                'Signalwort und die CMR-Prüfung.'),
    ('Menge', 'Nur die Zahl, Komma oder Punkt als Dezimaltrennzeichen.'),
    ('Einheit', 'L, ml, kg, g oder Stk.'),
    ('Lagerklasse', 'Nach TRGS 510, z. B. 3 oder 8B.'),
    ('Bereich', 'Muss bereits in der App unter Standorte angelegt sein.'),
    ('Unterbereich', 'Name oder Pfad des Unterbereichs, z. B. '
                     '"Labor › Schrank 2".'),
    ('SDB-Datum', 'TT.MM.JJJJ oder JJJJ-MM-TT.'),
    ('Substitutionsprüfung', 'ja oder nein. Bei ja wird der Ersatzstoff '
                             'übernommen, bei nein die Begründung.'),
    ('', ''),
    ('', 'Alternativ zu Bereich und Unterbereich darf eine Spalte "Standort" '
         'die kombinierte Angabe "Bereich › Unterbereich" enthalten.'),
    ('', 'Unbekannte Spalten werden ignoriert und in der Vorschau gemeldet.'),
)


class ImportFehler(ValueError):
    """Ein Fehler, der die ganze Datei betrifft (nicht eine einzelne Zeile).

    Die Meldung ist für die Oberfläche gedacht: keine Ausnahme-Klasse, kein
    Pfad, keine Zeilennummer aus dem Python-Stack.
    """


@dataclass
class RohTabelle:
    """Kopfzeile und Datenzeilen einer gelesenen Datei.

    'kopf' und 'zeilen' enthalten die Rohwerte: Text, Zahl, datetime oder
    None. Erst pruefe_zeile() macht daraus Datenbankfelder. 'zeilennummern'
    hält je Datenzeile die 1-basierte Zeilennummer in der Datei, damit eine
    Fehlermeldung auf die Zeile zeigt, die der Benutzer in Excel sieht -
    auch dann, wenn zwischendurch Leerzeilen übersprungen wurden.
    """
    kopf: list
    zeilen: list
    erste_zeile: int
    zeilennummern: list = field(default_factory=list)
    hinweise: list = field(default_factory=list)
    epoche: _dt.datetime = _dt.datetime(1899, 12, 30)


@dataclass
class PruefZeile:
    """Ergebnis für eine Datenzeile: Werte plus Fehler und Warnungen."""
    zeilennummer: int
    werte: dict
    fehler: list = field(default_factory=list)
    warnungen: list = field(default_factory=list)
    standort_text: str = ''

    @property
    def gueltig(self):
        return not self.fehler

    @property
    def status(self):
        if self.fehler:
            return 'fehler'
        if self.werte.get('aufgebraucht'):
            return 'aufgebraucht'
        if self.werte.get('zusammengefasst_in'):
            return 'zusammengefasst'
        if self.werte.get('vorhanden_id'):
            return 'duplikat'
        if self.warnungen:
            return 'warnung'
        return 'ok'


# ─── Kopfzeile und Spalten ───────────────────────────────────────────────────

def kopf_normalisieren(text):
    """Macht aus einer Spaltenüberschrift einen Vergleichsschlüssel.

    "H-Sätze", "H-Saetze" und "h saetze" ergeben denselben Schlüssel; ebenso
    "Bereich › Unterbereich" und "Bereich > Unterbereich". Umlaute werden
    ausgeschrieben, alles außer a-z und 0-9 fällt weg. Genau das braucht auch
    der Standort-Vergleich in main.py: Dort kommen Pfade mit "›", ">" oder "/"
    an, und alle drei sollen denselben Unterbereich treffen.
    """
    wert = str(text if text is not None else '').strip().casefold()
    for zeichen, ersatz in (('ä', 'ae'), ('ö', 'oe'), ('ü', 'ue'),
                            ('ß', 'ss')):
        wert = wert.replace(zeichen, ersatz)
    return re.sub(r'[^a-z0-9]+', '', wert)


_ALIASE = {}
for _schluessel, _angabe in FELDER.items():
    for _alias in _angabe['aliase']:
        _ALIASE.setdefault(kopf_normalisieren(_alias), _schluessel)
del _schluessel, _angabe, _alias

# Zweite Stufe: einzelne Wörter einer Beschriftung. Sie greift nur, wenn die
# vollständige Beschriftung keinen Alias trifft - "Produktidentifikator nach
# CLP" oder "Raum-Nr." sollen nicht an der Schreibweise scheitern. Ein Wort,
# das auf zwei Felder passt, ordnet nichts zu: Raten wäre hier schlimmer als
# eine gemeldete Spalte.
_STICHWOERTER = {}
for _wort, _feld in (
    ('produkt', 'name'), ('produktname', 'name'),
    ('produktbezeichnung', 'name'), ('produktidentifikator', 'name'),
    ('stoff', 'name'), ('stoffname', 'name'), ('stoffbezeichnung', 'name'),
    ('substanz', 'name'), ('handelsname', 'name'), ('chemikalienname', 'name'),
    ('bezeichnung', 'name'), ('chemikalie', 'name'), ('reagenz', 'name'),
    ('praeparat', 'name'), ('material', 'name'), ('gefahrstoff', 'name'),
    ('cas', 'cas_nummer'), ('casnummer', 'cas_nummer'),
    ('ec', 'eg_nummer'), ('einecs', 'eg_nummer'),
    ('signalwort', 'signalwort'), ('signal', 'signalwort'),
    ('piktogramm', 'piktogramme'), ('piktos', 'piktogramme'),
    ('symbol', 'piktogramme'), ('symbole', 'piktogramme'),
    ('ghs', 'piktogramme'),
    ('hsaetze', 'h_saetze'), ('hsatz', 'h_saetze'),
    ('gefahrenhinweis', 'h_saetze'), ('gefahrenhinweise', 'h_saetze'),
    ('psaetze', 'p_saetze'), ('psatz', 'p_saetze'),
    ('sicherheitshinweis', 'p_saetze'),
    ('sicherheitshinweise', 'p_saetze'),
    ('menge', 'menge'), ('bestand', 'menge'), ('fuellmenge', 'menge'),
    ('inhalt', 'menge'), ('volumen', 'menge'), ('quantity', 'menge'),
    ('amount', 'menge'),
    ('einheit', 'mengeneinheit'), ('mengeneinheit', 'mengeneinheit'),
    ('masseinheit', 'mengeneinheit'), ('unit', 'mengeneinheit'),
    ('raum', 'lagerort'), ('raumnummer', 'lagerort'), ('raumname', 'lagerort'),
    ('lagerort', 'lagerort'), ('lagerplatz', 'lagerort'),
    ('lagerraum', 'lagerort'), ('schrank', 'lagerort'), ('regal', 'lagerort'),
    ('fach', 'lagerort'), ('detailstandort', 'lagerort'),
    ('lagerklasse', 'lagerklasse'), ('lgk', 'lagerklasse'),
    ('bereich', 'bereich'), ('abteilung', 'bereich'),
    ('unterbereich', 'unterbereich'), ('arbeitsbereich', 'unterbereich'),
    ('standort', 'standort'), ('ort', 'standort'),
    ('location', 'standort'),
    ('einstufung', 'gefahrenkategorien'),
    ('gefahrenklasse', 'gefahrenkategorien'),
    ('gefahrenklassen', 'gefahrenkategorien'),
    ('gefahrenkategorien', 'gefahrenkategorien'),
    ('sdb', 'sdb_datum'), ('sicherheitsdatenblatt', 'sdb_datum'),
    ('substitution', 'substitutionspruefung'),
    ('substitutionspruefung', 'substitutionspruefung'),
    ('ersatzstoff', 'ersatzstoff'), ('alternativstoff', 'ersatzstoff'),
    ('substitut', 'ersatzstoff'), ('begruendung', 'begruendung'),
    ('cmr', 'cmr'), ('krebserzeugend', 'cmr'), ('mutagen', 'cmr'),
    ('reproduktionstoxisch', 'cmr'),
    ('aufgebraucht', 'aufgebraucht'), ('verbraucht', 'aufgebraucht'),
    ('entnommen', 'aufgebraucht'),
    ('gebinde', 'gebinde'), ('gebindenummer', 'gebinde'),
):
    _STICHWOERTER.setdefault(kopf_normalisieren(_wort), _feld)
del _wort, _feld


def _woerter(text):
    """Einzelwörter einer Beschriftung, umlautfrei und kleingeschrieben."""
    wert = str(text if text is not None else '').strip().casefold()
    for zeichen, ersatz in (('ä', 'ae'), ('ö', 'oe'), ('ü', 'ue'),
                            ('ß', 'ss')):
        wert = wert.replace(zeichen, ersatz)
    return [wort for wort in re.split(r'[^a-z0-9]+', wert) if wort]


def _stichwort_treffer(zelle):
    """Feld über einzelne Wörter der Beschriftung, None bei Mehrdeutigkeit."""
    treffer = {}
    for wort in _woerter(zelle):
        feld = _STICHWOERTER.get(wort)
        if feld:
            treffer[feld] = treffer.get(feld, 0) + 1
    if len(treffer) == 1:
        return next(iter(treffer))
    return None


def erkenne_spalten(kopfzeile):
    """Ordnet Spalten den Feldern zu.

    Rückgabe: (zuordnung, unbekannt, doppelt)
      zuordnung  {feld: spaltenindex}
      unbekannt  Beschriftungen ohne Treffer - werden ignoriert und gemeldet
      doppelt    Beschriftungen, die ein bereits belegtes Feld noch einmal
                 treffen. Die erste Spalte gewinnt.

    Zwei Stufen: erst die vollständigen Aliase, dann einzelne Wörter. Die
    zweite Stufe läuft über alle Spalten, nachdem die erste fertig ist - sonst
    könnte ein Stichwort eine Spalte belegen, die ein anderer Alias exakt
    getroffen hätte.
    """
    zuordnung = {}
    unbekannt = []
    doppelt = []
    offene = []
    for index, zelle in enumerate(kopfzeile or []):
        norm = kopf_normalisieren(zelle)
        if not norm:
            continue
        schluessel = _ALIASE.get(norm)
        if schluessel is None:
            offene.append((index, zelle))
        elif schluessel in zuordnung:
            doppelt.append(str(zelle).strip())
        else:
            zuordnung[schluessel] = index

    for index, zelle in offene:
        schluessel = _stichwort_treffer(zelle)
        if schluessel is None:
            unbekannt.append(str(zelle).strip())
        elif schluessel in zuordnung:
            doppelt.append(str(zelle).strip())
        else:
            zuordnung[schluessel] = index
    return zuordnung, unbekannt, doppelt


def _ist_leer(wert):
    return wert is None or (isinstance(wert, str) and not wert.strip())


# Wie weit unterhalb des Blattanfangs eine Kopfzeile gesucht wird. Manche
# Dateien haben Titel, Anschrift und Datum davor; 100 Zeilen decken das ab,
# ohne bei einer langen Liste jede Zeile zu prüfen.
KOPF_SUCHE_ZEILEN = 100

# So viele Blätter werden bewertet. Mehr ist bei einer Gefahrstoffliste
# unrealistisch und würde nur Laufzeit kosten.
MAX_BLAETTER = 20

_CAS_MUSTER = re.compile(r'\d{2,7}-\d{2}-\d')


def _kopf_zeile_finden(zeilen):
    """Sucht die Kopfzeile unter den ersten nicht leeren Zeilen.

    Viele Dateien haben eine Titelzeile oder eine leere Zeile vor der Tabelle.
    Gewählt wird die Zeile mit den meisten erkannten Feldern. Eine Spalte
    "Name" ist nicht mehr Bedingung: Fehlt sie, wird sie später aus dem
    Zelleninhalt bestimmt (ergaenze_aus_inhalt). Verlangt sind aber zwei
    erkannte Felder - eine einzelne Zelle, die zufällig wie eine Beschriftung
    aussieht, ist noch keine Kopfzeile.
    """
    kandidaten = []
    for index, zeile in enumerate(zeilen[:KOPF_SUCHE_ZEILEN]):
        if all(_ist_leer(z) for z in zeile):
            continue
        zuordnung, _, _ = erkenne_spalten(zeile)
        kandidaten.append((len(zuordnung), index, zuordnung))
    if not kandidaten:
        return None, None

    beste = max(kandidaten, key=lambda k: (k[0], -k[1]))
    if beste[0] < 2:
        return None, None
    return beste[1], beste[2]


def _sieht_wie_daten_aus(zeile):
    """Spricht dafür, dass diese Zeile Daten und keine Beschriftung enthält?"""
    werte = [wert for wert in zeile if not _ist_leer(wert)]
    if not werte:
        return False
    if any(_CAS_MUSTER.fullmatch(_text(wert)) for wert in werte):
        return True
    zahlen = sum(1 for wert in werte
                 if isinstance(wert, (int, float, _dt.datetime, _dt.date)))
    return zahlen >= 2 and zahlen * 2 >= len(werte)


def _tabelle_aus_rohzeilen(rohzeilen, hinweise, epoche=None):
    """Schneidet Kopfzeile und Datenzeilen aus der gelesenen Datei.

    Findet sich keine Kopfzeile, wird die Datei nicht abgelehnt: Sieht die
    erste Zeile wie Daten aus, gelten alle Zeilen als Daten und die Spalten
    werden aus dem Inhalt bestimmt. Sonst gilt die erste Zeile als
    Kopfzeile ohne bekannte Beschriftungen - dasselbe Ergebnis, nur mit
    anderen Zeilennummern.
    """
    # Leerzeilen am Ende entfernen. Leerzeilen in der Mitte bleiben stehen:
    # Ihre Zeilennummer ist die Orientierung, die der Benutzer in Excel hat.
    while rohzeilen and all(_ist_leer(z) for z in rohzeilen[-1]):
        rohzeilen.pop()

    if not rohzeilen:
        raise ImportFehler('Die Datei enthält keine Daten.')

    kopf_index, _ = _kopf_zeile_finden(rohzeilen)
    if kopf_index is None:
        erste = next((index for index, zeile in enumerate(rohzeilen)
                      if not all(_ist_leer(w) for w in zeile)), None)
        if erste is None:
            raise ImportFehler('Die Datei enthält keine Daten.')
        if _sieht_wie_daten_aus(rohzeilen[erste]):
            kopf = []
            daten_start = erste
            hinweise.append(
                'Keine Kopfzeile erkannt - die Spalten wurden aus dem '
                'Zelleninhalt bestimmt.')
        else:
            kopf = [('' if z is None else str(z).strip())
                    for z in rohzeilen[erste]]
            daten_start = erste + 1
            hinweise.append(
                'Die Kopfzeile wurde nicht sicher erkannt - die Spalten '
                'wurden zusätzlich aus dem Zelleninhalt bestimmt.')
    else:
        kopf = [('' if z is None else str(z).strip())
                for z in rohzeilen[kopf_index]]
        daten_start = kopf_index + 1

    daten = []
    for index in range(daten_start, len(rohzeilen)):
        zeile = rohzeilen[index]
        # Ganz leere Zeilen zählen nicht als Fehler. Sie werden übersprungen,
        # ihre Nummer aber nicht weitergegeben: die Nummer der nächsten Zeile
        # bleibt die aus der Datei.
        if all(_ist_leer(w) for w in zeile):
            continue
        daten.append((index + 1, zeile))

    if not daten:
        raise ImportFehler('Die Datei enthält keine Datenzeilen.')
    if len(daten) > MAX_ZEILEN:
        raise ImportFehler(
            f'Die Datei enthält mehr als {MAX_ZEILEN} Zeilen. Bitte in '
            'Teildateien aufteilen.')

    return RohTabelle(
        kopf=kopf,
        zeilen=[zeile for _, zeile in daten],
        zeilennummern=[nummer for nummer, _ in daten],
        erste_zeile=daten[0][0],
        hinweise=hinweise,
        epoche=epoche or _dt.datetime(1899, 12, 30),
    )


# ─── Datei lesen ─────────────────────────────────────────────────────────────

def lies_datei(daten, dateiname):
    """Liest eine .xlsx-, .xlsm- oder .csv-Datei als Bytes in eine RohTabelle.

    Wirft ImportFehler mit einer Meldung, die direkt angezeigt werden kann.
    """
    if not isinstance(daten, (bytes, bytearray)):
        raise ImportFehler('Die Datei konnte nicht gelesen werden.')
    daten = bytes(daten)
    if not daten:
        raise ImportFehler('Die Datei ist leer.')
    if len(daten) > MAX_BYTES:
        raise ImportFehler(
            f'Die Datei ist größer als {MAX_BYTES // (1024 * 1024)} MB.')
    if not dateiname or '.' not in dateiname:
        raise ImportFehler('Der Dateiname enthält keine Endung.')

    endung = dateiname.rsplit('.', 1)[1].lower()
    if endung in ('xlsx', 'xlsm'):
        return _lies_excel(daten)
    if endung == 'csv':
        return _lies_csv(daten)
    if endung == 'xls':
        raise ImportFehler(
            'Das alte Excel-Format .xls wird nicht unterstützt. Bitte die '
            'Datei als .xlsx oder .csv speichern.')
    raise ImportFehler('Nur .xlsx und .csv werden unterstützt.')


def _lies_excel(daten):
    # OOXML ist ein ZIP-Container. Ein beliebiger ZIP (oder ein umbenanntes
    # PDF) scheitert sonst erst tief in openpyxl mit einer unverständlichen
    # Meldung. Die Prüfung des Dateikopfs entspricht der in main.py für
    # Uploads (DATEI_SIGNATUREN).
    if not daten.startswith(b'PK\x03\x04'):
        raise ImportFehler(
            'Die Datei ist keine gültige Excel-Arbeitsmappe. Bei .xls hilft '
            'das Speichern als .xlsx.')
    try:
        arbeitsmappe = load_workbook(io.BytesIO(daten), read_only=True,
                                     data_only=True)
    except Exception:
        raise ImportFehler(
            'Die Excel-Datei konnte nicht geöffnet werden. Ist sie '
            'beschädigt oder passwortgeschützt?') from None

    try:
        hinweise = []
        blaetter = arbeitsmappe.worksheets
        if not blaetter:
            raise ImportFehler('Die Arbeitsmappe enthält kein Blatt.')

        # Jedes Blatt bekommt eine Punktzahl; gelesen wird das beste. Eine
        # Arbeitsmappe mit einem Deckblatt, einer Hinweistabelle und dem
        # eigentlichen Verzeichnis war bisher ein Fehlschlag, sobald das
        # Deckblatt vorn lag.
        beste = None
        for blatt in blaetter[:MAX_BLAETTER]:
            rohzeilen = []
            zu_viele = False
            for zeile in blatt.iter_rows(values_only=True):
                # Ein paar Zeilen Puffer, damit die Grenze erst nach der
                # Kopfzeilensuche greift; die eigentliche Prüfung steht in
                # _tabelle_aus_rohzeilen().
                if len(rohzeilen) > MAX_ZEILEN + 20:
                    zu_viele = True
                    break
                rohzeilen.append(list(zeile))

            kopf_index, zuordnung = _kopf_zeile_finden(rohzeilen)
            zeilen_mit_inhalt = sum(
                1 for zeile in rohzeilen
                if not all(_ist_leer(w) for w in zeile))
            erste = next((zeile for zeile in rohzeilen
                          if not all(_ist_leer(w) for w in zeile)), [])
            datenartig = 1 if (kopf_index is not None
                               or _sieht_wie_daten_aus(erste)) else 0
            punkte = (1 if kopf_index is not None else 0,
                      datenartig, len(zuordnung or {}), zeilen_mit_inhalt)
            if beste is None or punkte > beste[0]:
                beste = (punkte, blatt.title, rohzeilen, zu_viele)

        _, titel, rohzeilen, zu_viele = beste
        if zu_viele:
            raise ImportFehler(
                f'Das Blatt „{titel}“ enthält mehr als {MAX_ZEILEN} Zeilen. '
                'Bitte in Teildateien aufteilen.')
        if len(blaetter) > 1:
            hinweise.append(
                f'Blatt „{titel}“ gelesen; die übrigen Blätter enthielten '
                'keine passendere Tabelle.')

        return _tabelle_aus_rohzeilen(rohzeilen, hinweise,
                                      epoche=getattr(arbeitsmappe, 'epoch', None))
    finally:
        arbeitsmappe.close()


def _dekodiere(daten):
    """Text einer CSV-Datei und die verwendete Kodierung.

    Deutsches Excel schreibt cp1252, neuere Versionen UTF-8 mit BOM. Die
    Reihenfolge ist wichtig: utf-8-sig scheitert bei cp1252 sauber, cp1252
    scheitert an den wenigen Bytes, die dort undefiniert sind, latin-1
    scheitert nie und ist deshalb der letzte Ausweg.
    """
    for kodierung in ('utf-8-sig', 'cp1252', 'latin-1'):
        try:
            return daten.decode(kodierung), kodierung
        except UnicodeDecodeError:
            continue
    return daten.decode('latin-1', errors='replace'), 'latin-1'


def _trennzeichen(text):
    """Trennzeichen einer CSV-Datei: Sniffer, sonst Auszählung."""
    probe = text[:8192]
    try:
        dialekt = csv.Sniffer().sniff(probe, delimiters=';,\t|')
        if dialekt.delimiter:
            return dialekt.delimiter
    except csv.Error:
        pass

    # Rückfall: In den ersten Zeilen zählen. Deutsches Excel nutzt ";",
    # englische Exporte ",". Steht beides gleich oft da, gewinnt ";".
    zeilen = text.splitlines()[:5]
    zaehler = {zeichen: sum(z.count(zeichen) for z in zeilen)
               for zeichen in ';,\t|'}
    bester = max(zaehler, key=lambda z: (zaehler[z], z == ';'))
    return bester if zaehler[bester] else ';'


def _lies_csv(daten):
    text, kodierung = _dekodiere(daten)
    hinweise = []
    if kodierung not in ('utf-8-sig',):
        hinweise.append(f'Die Datei wurde als {kodierung.upper()} gelesen.')

    trenner = _trennzeichen(text)
    try:
        leser = csv.reader(io.StringIO(text, newline=''), delimiter=trenner)
        rohzeilen = []
        for zeile in leser:
            if len(rohzeilen) > MAX_ZEILEN + 20:
                raise ImportFehler(
                    f'Die Datei enthält mehr als {MAX_ZEILEN} Zeilen.')
            rohzeilen.append(list(zeile))
    except csv.Error as fehler:
        raise ImportFehler(
            f'Die CSV-Datei konnte nicht gelesen werden: {fehler}') from None

    # Ein einspaltiges Ergebnis ist fast immer ein falsch erkanntes
    # Trennzeichen. Das soll in der Vorschau stehen und nicht in einer
    # Fehlermeldung enden, weil die Datei sonst korrekt ist.
    if rohzeilen and all(len(z) <= 1 for z in rohzeilen) and ';' in text:
        hinweise.append(
            'Die Datei wirkt einspaltig - möglicherweise wurde das '
            'Trennzeichen nicht erkannt.')

    return _tabelle_aus_rohzeilen(rohzeilen, hinweise)


def zeilen_als_dicts(tabelle, zuordnung):
    """Paart jede Datenzeile mit ihrer Dateizeilennummer und den Rohwerten.

    Rückgabe: [(zeilennummer, {feld: rohwert}), ...]. Die Zeilennummer ist
    die, die der Benutzer in Excel sieht - die Fehlermeldung muss dorthin
    zeigen, nicht auf einen Listenindex.
    """
    ergebnis = []
    for versatz, zeile in enumerate(tabelle.zeilen):
        nummer = (tabelle.zeilennummern[versatz]
                  if versatz < len(tabelle.zeilennummern)
                  else tabelle.erste_zeile + versatz)
        roh = {}
        for schluessel, index in zuordnung.items():
            roh[schluessel] = zeile[index] if index < len(zeile) else None
        ergebnis.append((nummer, roh))
    return ergebnis


def _spaltenwerte(tabelle):
    """Die nicht leeren Zellwerte je Spalte, als Text und auf 200 gekürzt."""
    breite = max((len(zeile) for zeile in tabelle.zeilen), default=0)
    spalten = []
    for index in range(breite):
        werte = [_text(zeile[index]) for zeile in tabelle.zeilen
                 if index < len(zeile) and not _ist_leer(zeile[index])]
        spalten.append(werte[:200])
    return spalten


def _anteil(werte, test, minimum=0.6):
    """Anteil der Werte, die den Test bestehen, mindestens 'minimum'."""
    if not werte:
        return False
    return sum(1 for wert in werte if test(wert)) / len(werte) >= minimum


def _ist_zahl_text(text):
    return bool(re.fullmatch(r'[+-]?\d+([.,]\d+)?', text.strip()))


def _ist_janein(text):
    return re.sub(r'[^a-z0-9]', '', text.casefold()) in _WAHRHEIT


def ergaenze_aus_inhalt(tabelle, zuordnung):
    """Ergänzt fehlende Spalten anhand der Zellwerte.

    Rückgabe: (zuordnung, hinweise). Die Kopfzeile hat Vorrang; hier werden
    nur Felder belegt, die sie nicht geliefert hat, und jede Spalte höchstens
    einmal. Der Rückfall ist nötig für Dateien mit fremden Beschriftungen
    ("Produkt", "Raum") und für solche ganz ohne Kopfzeile - bisher wurden
    beide abgelehnt.

    Erkannt werden nur Felder, die sich am Inhalt sicher unterscheiden
    lassen: CAS-Nummer, H-/P-Sätze, Piktogramme, Signalwort und - als
    letzter Ausweg - der Stoffname. Mengen werden bewusst nicht geraten:
    Eine Artikelnummer ist auch eine Zahl.
    """
    zuordnung = dict(zuordnung)
    hinweise = []
    spalten = _spaltenwerte(tabelle)

    regeln = (
        ('cas_nummer', lambda wert: bool(_CAS_MUSTER.fullmatch(wert)), 0.6),
        ('h_saetze', lambda wert: bool(re.search(r'\bH\s?\d{3}', wert)), 0.6),
        ('p_saetze', lambda wert: bool(re.search(r'\bP\s?\d{3}', wert)), 0.6),
        ('piktogramme',
         lambda wert: bool(re.search(r'GHS\s?-?\s?\d', wert, re.IGNORECASE)),
         0.5),
        ('signalwort',
         lambda wert: (re.sub(r'[^a-z]', '', wert.casefold())
                       in SIGNALWOERTER), 0.6),
    )
    for feld, test, minimum in regeln:
        if feld in zuordnung:
            continue
        for index, werte in enumerate(spalten):
            if index in zuordnung.values():
                continue
            if _anteil(werte, test, minimum):
                zuordnung[feld] = index
                hinweise.append(
                    f'Spalte „{spaltenname(tabelle, index)}“ wurde anhand '
                    f'des Inhalts als {FELDER[feld]["label"]} erkannt.')
                break

    if 'name' not in zuordnung:
        index = _name_spalte_raten(tabelle, spalten, zuordnung)
        if index is not None:
            zuordnung['name'] = index
            hinweise.append(
                f'Spalte „{spaltenname(tabelle, index)}“ wurde anhand des '
                'Inhalts als Stoffname verwendet - bitte in der Vorschau '
                'prüfen.')
    return zuordnung, hinweise


def spalten_bericht(tabelle, zuordnung):
    """(unbekannt, doppelt) für die Vorschau, aus der endgültigen Zuordnung.

    Nötig, weil ergaenze_aus_inhalt() Spalten nachträglich belegt: Eine solche
    Spalte ist nicht mehr "ignoriert" und darf nicht mehr in der Meldung
    stehen. "Doppelt" heißt: Die Beschriftung würde ein bereits belegtes Feld
    noch einmal treffen - die erste Spalte gilt.
    """
    belegt = set(zuordnung.values())
    unbekannt = []
    doppelt = []
    for index, label in enumerate(tabelle.kopf):
        label = (label or '').strip()
        if not label or index in belegt:
            continue
        schluessel = (_ALIASE.get(kopf_normalisieren(label))
                      or _stichwort_treffer(label))
        if schluessel is not None and schluessel in zuordnung:
            doppelt.append(label)
        else:
            unbekannt.append(label)
    return unbekannt, doppelt


def spaltenname(tabelle, index):
    if index < len(tabelle.kopf) and tabelle.kopf[index]:
        return tabelle.kopf[index]
    return f'Spalte {index + 1}'


def _name_spalte_raten(tabelle, spalten, zuordnung):
    """Die überzeugendste Textspalte, die noch keinem Feld zugeordnet ist."""
    belegt = set(zuordnung.values())
    bester = None
    beste_punkte = (0, 0)
    for index, werte in enumerate(spalten):
        if index in belegt or not werte:
            continue
        if _anteil(werte, _ist_zahl_text, 0.5):
            continue
        if _anteil(werte, _ist_janein, 0.8):
            continue
        if _anteil(werte, lambda wert: bool(_CAS_MUSTER.fullmatch(wert))):
            continue
        if _anteil(werte, lambda wert: bool(re.search(r'\b[HP]\s?\d{3}', wert))):
            continue
        # Vorzug: viele gefüllte Zeilen, dann viele verschiedene Werte. Bei
        # Gleichstand gewinnt die linke Spalte (strenge Größer-Prüfung).
        punkte = (len(werte), len(set(wert.casefold() for wert in werte)))
        if punkte > beste_punkte:
            beste_punkte = punkte
            bester = index
    return bester


# ─── Werte lesen ─────────────────────────────────────────────────────────────

def _text(wert):
    """Zellwert als getrimmter Text, '' für leer.

    Excel liefert je nach Zellformat int, float, datetime oder str. Eine
    Mengenangabe 5.0 soll "5" heißen und nicht "5.0"; ein Datum in einer
    Textspalte wird als ISO-Datum gelesen.
    """
    if wert is None:
        return ''
    if isinstance(wert, _dt.datetime):
        return wert.date().isoformat()
    if isinstance(wert, _dt.date):
        return wert.isoformat()
    if isinstance(wert, bool):
        return 'ja' if wert else 'nein'
    if isinstance(wert, float) and wert.is_integer():
        return str(int(wert))
    return str(wert).strip()


def _zahl(wert):
    """Zahl aus einer Zelle oder einem Text, None wenn nicht lesbar.

    "4,5", "4.5" und "1.234,5" werden verstanden. Bei "1.234" ist die
    Bedeutung ohne Kontext nicht entscheidbar; die Regel lautet deshalb
    bewusst: nur der Punkt ohne Komma bleibt Dezimalpunkt. Wer Tausenderpunkte
    schreibt, hat damit 1,234 statt 1234 - das fällt in der Vorschau auf.
    """
    if isinstance(wert, bool):
        return None
    if isinstance(wert, (int, float)):
        return float(wert)

    text = _text(wert)
    if not text:
        return None
    text = text.replace(' ', '').replace(' ', '')
    if ',' in text and '.' in text:
        if text.rfind(',') > text.rfind('.'):
            text = text.replace('.', '').replace(',', '.')
        else:
            text = text.replace(',', '')
    elif ',' in text:
        text = text.replace(',', '.')
    try:
        return float(text)
    except ValueError:
        return None


def _menge_und_einheit(wert):
    """Trennt "4,5 kg" in (4.5, 'kg'). Ohne Einheit ist der zweite Wert ''."""
    text = _text(wert)
    if not text:
        return None, ''
    treffer = re.match(r'^\s*([0-9.,\s ]+?)\s*([A-Za-zÄÖÜäöüß%³/]*)\s*$',
                       text)
    if not treffer:
        return _zahl(text), ''
    zahl = _zahl(treffer.group(1))
    return zahl, treffer.group(2).strip()


def _einheit(wert):
    """(Einheit, Problemtext). Unbekannte Einheiten werden übernommen."""
    text = _text(wert)
    if not text:
        return None, None
    schluessel = kopf_normalisieren(text)
    if schluessel in MENGENEINHEITEN:
        return MENGENEINHEITEN[schluessel], None
    return text[:10], (f'Unbekannte Mengeneinheit „{text}“ - übernommen, das '
                       'Formular bietet sie nicht an.')


def _datum(wert, epoche):
    """(date, Problemtext) aus einer Zelle. Problemtext nur bei unlesbar.

    Akzeptiert datetime (so liefert openpyxl formatierte Datumszellen), die
    Excel-Serienzahl und Text in den Formaten, die in Deutschland üblich sind.
    Die Epoche kommt aus der Arbeitsmappe: Excel kennt neben 1899-12-30 auch
    den 1904-Kalender, und eine Serienzahl wäre damit um vier Jahre verschoben.
    """
    if _ist_leer(wert):
        return None, None
    if isinstance(wert, _dt.datetime):
        return wert.date(), None
    if isinstance(wert, _dt.date):
        return wert, None
    if isinstance(wert, bool):
        return None, f'„{wert}“ ist kein lesbares Datum.'
    if isinstance(wert, (int, float)):
        if 1 <= wert <= 80000:
            try:
                return (epoche + _dt.timedelta(days=int(wert))).date(), None
            except (OverflowError, ValueError):
                pass
        return None, f'„{_text(wert)}“ ist kein lesbares Datum.'

    text = _text(wert)
    # Zeitanteil abschneiden: "2024-01-31 00:00:00", "2024-01-31T00:00:00".
    text = re.split(r'[ T]', text, maxsplit=1)[0]
    for format_ in ('%d.%m.%Y', '%d.%m.%y', '%Y-%m-%d', '%Y.%m.%d',
                    '%d-%m-%Y'):
        try:
            return _dt.datetime.strptime(text, format_).date(), None
        except ValueError:
            continue
    # ISO mit Zeitanteil, der kein Leerzeichen hatte (2024-01-31T08:15)
    try:
        return _dt.date.fromisoformat(text), None
    except ValueError:
        return None, f'„{text}“ ist kein lesbares Datum (erwartet TT.MM.JJJJ).'


def _piktogramme(wert, fehler):
    """Piktogramm-Codes aus einer Zelle, als geordnete Liste.

    Unbekannte Angaben sind ein Fehler und keine Warnung: Ein "GHS10" würde
    sonst als Piktogramm gespeichert, das keine Vorlage anzeigen kann.
    """
    text = _text(wert)
    if not text:
        return []
    # "GHS 08" und "GHS-08" sind gebräuchliche Schreibweisen. Erst zusammen-
    # ziehen, dann trennen - sonst zerfällt "GHS 08" in "GHS" und "08" und
    # beide Teile gelten als unbekannt.
    text = re.sub(r'GHS\s*-?\s*(\d)', r'GHS\1', text, flags=re.IGNORECASE)
    gefunden = []
    for teil in re.split(r'[,;/\s|]+', text):
        if not teil:
            continue
        norm = re.sub(r'[^A-Za-z0-9]', '', teil).upper()
        if norm in PIKTOGRAMME:
            gefunden.append(norm)
        else:
            fehler.append(
                f'Unbekanntes Piktogramm „{teil}“ (erwartet GHS01 bis GHS09).')
    return sorted(set(gefunden))


def _signalwort(wert, warnungen):
    text = _text(wert)
    if not text:
        return None
    norm = re.sub(r'[^a-z]', '', text.casefold())
    if norm in SIGNALWOERTER:
        return SIGNALWOERTER[norm]
    warnungen.append(f'Unbekanntes Signalwort „{text}“ (erwartet Gefahr oder '
                     'Achtung).')
    return None


def _wahrheit(wert):
    """ja/nein aus einer Zelle, None wenn unklar."""
    text = re.sub(r'[^a-z0-9]', '', _text(wert).casefold())
    return _WAHRHEIT.get(text)


def _begrenzt(schluessel, wert, warnungen):
    """Kürzt einen Wert auf die Länge der Datenbankspalte.

    SQLite prüft String-Längen nicht, PostgreSQL und andere Ziele schon. Ein
    stillschweigend abgeschnittener Wert wäre ärgerlich, deshalb steht die
    Kürzung als Warnung in der Vorschau.
    """
    grenze = FELDER[schluessel]['laenge']
    if grenze and wert and len(wert) > grenze:
        warnungen.append(
            f'„{FELDER[schluessel]["label"]}“ ist länger als {grenze} Zeichen '
            'und wird gekürzt.')
        return wert[:grenze]
    return wert


# ─── Zeile prüfen ────────────────────────────────────────────────────────────

def pruefe_zeile(roh, zeilennummer, standort_aufloesen=None,
                 standard_standort_id=None, standard_standort_name=None,
                 epoche=None):
    """Prüft eine Datenzeile und übersetzt sie in Datenbankfelder.

    standort_aufloesen: Callable(text) -> (unterbereich_id, fehlermeldung).
    Ohne Callable bleibt der Standort unaufgelöst (für Tests der reinen
    Logik).

    Ein Standort, den die App nicht kennt, ist eine Warnung und die Zeile
    landet im Ziel-Standort - vorausgesetzt, beim Hochladen wurde einer
    gewählt (Nutzerentscheidung 04.11.2026). Ohne Ziel-Standort bleibt es ein
    Fehler: Sonst verlöre die Zeile ihren Standort, ohne dass es jemand
    merkt.

    Die Regeln folgen add(): Die Substitutionsprüfung entscheidet, ob
    Ersatzstoff oder Begründung übernommen wird, Piktogramme und Signalwort
    werden aus den H-Sätzen abgeleitet, wenn sie fehlen. is_approved bleibt
    Sache des Aufrufers - die CMR-Regel steht in main.py und soll dort die
    einzige bleiben.
    """
    fehler = []
    warnungen = []
    werte = {}

    # -- Name: einziges Pflichtfeld -----------------------------------------
    # Ein zu langer Name wird gekürzt und gemeldet, nicht abgelehnt: Der
    # Eintrag ist sonst vollständig und die Kürzung in der Vorschau sichtbar.
    name = _text(roh.get('name'))
    if not name:
        fehler.append('Name fehlt.')
    else:
        name = _begrenzt('name', name, warnungen)
    werte['name'] = name or None

    # -- Nummern und Freitexte ---------------------------------------------
    for schluessel in ('cas_nummer', 'eg_nummer', 'gefahrenkategorien',
                       'p_saetze', 'lagerort', 'ersatzstoff', 'begruendung'):
        wert = _begrenzt(schluessel, _text(roh.get(schluessel)), warnungen)
        werte[schluessel] = wert or None

    if werte['cas_nummer'] and not re.fullmatch(
            r'\d{2,7}-\d{2}-\d', werte['cas_nummer']):
        warnungen.append(
            f'CAS-Nummer „{werte["cas_nummer"]}“ hat nicht das Format '
            '123-45-6.')

    # -- H-Sätze ------------------------------------------------------------
    h_saetze = _begrenzt('h_saetze', _text(roh.get('h_saetze')), warnungen)
    werte['h_saetze'] = h_saetze or None
    if h_saetze:
        ohne_zuordnung = unbekannte_codes(h_saetze)
        if ohne_zuordnung:
            warnungen.append(
                'H-Sätze ohne Zuordnung in der CLP-Tabelle: '
                + ', '.join(ohne_zuordnung))
    h_codes = codes_aus_text(h_saetze) if h_saetze else []

    # -- Piktogramme: explizit oder aus den H-Sätzen ------------------------
    # Ein unbekanntes Piktogramm ist eine Warnung, kein Zeilenfehler: Es wird
    # nicht übernommen, die übrigen Angaben der Zeile sind aber brauchbar.
    piktogramme = _piktogramme(roh.get('piktogramme'), warnungen)
    if not piktogramme and h_codes:
        piktogramme = piktogramme_fuer(h_saetze)
        if piktogramme:
            warnungen.append(
                'Piktogramme aus den H-Sätzen abgeleitet: '
                + ', '.join(piktogramme) + '.')
    werte['piktogramme'] = ','.join(piktogramme) if piktogramme else None

    # -- Signalwort: explizit oder aus den H-Sätzen -------------------------
    signalwort = _signalwort(roh.get('signalwort'), warnungen)
    if not signalwort and h_codes:
        signalwort = signalwort_fuer(h_saetze)
    werte['signalwort'] = signalwort

    # -- Menge und Einheit --------------------------------------------------
    menge, einheit_in_zelle = _menge_und_einheit(roh.get('menge'))
    if _text(roh.get('menge')) and menge is None:
        warnungen.append(
            f'Menge „{_text(roh.get("menge"))}“ ist keine Zahl - die Menge '
            'bleibt leer.')
    if menge is not None and menge < 0:
        warnungen.append('Menge ist negativ - sie wird nicht übernommen.')
        menge = None
    werte['menge'] = menge

    einheit, problem = _einheit(roh.get('mengeneinheit'))
    if problem:
        warnungen.append(problem)
    elif not einheit and einheit_in_zelle:
        einheit, problem = _einheit(einheit_in_zelle)
        if problem:
            warnungen.append(problem)
    elif einheit and einheit_in_zelle:
        aus_zelle, _ = _einheit(einheit_in_zelle)
        if aus_zelle and aus_zelle != einheit:
            warnungen.append(
                f'Einheit in der Menge („{einheit_in_zelle}“) weicht von der '
                f'Spalte Einheit („{einheit}“) ab - es gilt die Spalte Einheit.')
    if menge is not None and not einheit:
        warnungen.append('Menge ohne Einheit.')
    werte['mengeneinheit'] = einheit

    # -- Lagerklasse --------------------------------------------------------
    lagerklasse = _text(roh.get('lagerklasse')).upper().replace(' ', '')
    werte['lagerklasse'] = lagerklasse or None
    if lagerklasse and lagerklasse not in LAGERKLASSEN:
        warnungen.append(
            f'Lagerklasse „{lagerklasse}“ steht nicht in der TRGS-510-Liste '
            'des Formulars - übernommen.')

    # -- Daten --------------------------------------------------------------
    epoche = epoche or _dt.datetime(1899, 12, 30)
    for schluessel in ('sdb_datum', 'substitution_geprueft_am'):
        datum, problem = _datum(roh.get(schluessel), epoche)
        if problem:
            warnungen.append(
                f'{FELDER[schluessel]["label"]}: {problem} Feld bleibt leer.')
        werte[schluessel] = datum

    # -- Substitutionsprüfung ----------------------------------------------
    # Wie in add(): "ja" übernimmt den Ersatzstoff, "nein" die Begründung.
    # Das jeweils andere Feld wird nicht stillschweigend mitgespeichert.
    entscheidung = _wahrheit(roh.get('substitutionspruefung'))
    if _text(roh.get('substitutionspruefung')) and entscheidung is None:
        warnungen.append(
            f'Substitutionsprüfung „{_text(roh.get("substitutionspruefung"))}“ '
            'nicht verstanden (erwartet ja oder nein).')
    werte['substitutionspruefung'] = entscheidung
    if entscheidung != 'ja':
        werte['ersatzstoff'] = None
    if entscheidung != 'nein':
        werte['begruendung'] = None
    if entscheidung == 'ja' and not werte['ersatzstoff']:
        warnungen.append(
            'Substitutionsprüfung "ja", aber kein Ersatzstoff angegeben.')
    if entscheidung == 'nein' and not werte['begruendung']:
        warnungen.append(
            'Substitutionsprüfung "nein", aber keine Begründung angegeben.')

    # -- CMR-Kennzeichnung aus der Quelle ----------------------------------
    # Führt die Datei CMR selbst, gilt sie zusätzlich zu den H-Sätzen. Sonst
    # wäre ein Stoff, dessen SDB keine H-Sätze nennt, sofort sichtbar.
    cmr = _wahrheit(roh.get('cmr'))
    if _text(roh.get('cmr')) and cmr is None:
        warnungen.append(
            f'CMR-Angabe „{_text(roh.get("cmr"))}“ nicht verstanden '
            '(erwartet ja oder nein).')
    werte['cmr'] = (cmr == 'ja') if cmr else None
    if werte['cmr']:
        warnungen.append(
            'Als CMR-Stoff gekennzeichnet - der Stoff wartet nach dem Import '
            'auf die Freigabe.')

    # -- Aufgebrauchte Gebinde --------------------------------------------
    # Sie bleiben in der Vorschau stehen, werden aber nicht angelegt.
    aufgebraucht = _wahrheit(roh.get('aufgebraucht'))
    if _text(roh.get('aufgebraucht')) and aufgebraucht is None:
        warnungen.append(
            f'Angabe „Aufgebraucht“ („{_text(roh.get("aufgebraucht"))}“) '
            'nicht verstanden (erwartet ja oder nein).')
    werte['aufgebraucht'] = (aufgebraucht == 'ja') if aufgebraucht else None

    # Nur für die Zusammenfassung mehrerer Zeilen, keine Datenbankspalte.
    werte['gebinde'] = _text(roh.get('gebinde')) or None

    # -- Standort -----------------------------------------------------------
    standort_text = _text(roh.get('standort'))
    bereich = _text(roh.get('bereich'))
    unterbereich = _text(roh.get('unterbereich'))
    if not standort_text and (bereich or unterbereich):
        standort_text = ' › '.join(t for t in (bereich, unterbereich) if t)
    if len(standort_text) > FELDER['standort']['laenge']:
        warnungen.append('Standortangabe ist zu lang und wird gekürzt.')
        standort_text = standort_text[:FELDER['standort']['laenge']]

    standort_id = standard_standort_id
    # Gesetzt, wenn die Angabe aus der Zeile nicht aufgelöst werden konnte und
    # deshalb der Ziel-Standort gilt. Die Vorschau zeigt das an.
    standort_ersatz = False
    if standort_text:
        if standort_aufloesen is None:
            standort_id = None
        else:
            standort_id, standort_fehler = standort_aufloesen(standort_text)
            if standort_fehler:
                if standard_standort_id is not None:
                    ziel = (f'„{standard_standort_name}“'
                            if standard_standort_name else 'den Ziel-Standort')
                    warnungen.append(
                        f'{standort_fehler} Die Zeile landet in '
                        f'{ziel}.')
                    standort_id = standard_standort_id
                    standort_ersatz = True
                else:
                    fehler.append(
                        f'{standort_fehler} Bitte beim Hochladen einen '
                        'Ziel-Standort wählen oder die Standortangabe '
                        'korrigieren.')
    werte['unterbereich_id'] = standort_id
    werte['standort_ersatz'] = standort_ersatz

    return PruefZeile(zeilennummer=zeilennummer, werte=werte,
                      fehler=fehler, warnungen=warnungen,
                      standort_text=standort_text)


def _duplikat_schluessel(zeile):
    """Schlüssel, unter dem zwei Zeilen denselben Eintrag beschreiben.

    CAS-Nummer (sonst Name), Standort und Lagerort. Der Lagerort gehört dazu,
    weil "Raum 205" und "Gefahrenlager" zwei verschiedene Behälterplätze sind
    - auch wenn derselbe Stoff dort steht.
    """
    cas = (zeile.werte.get('cas_nummer') or '').strip().casefold()
    name = (zeile.werte.get('name') or '').strip().casefold()
    if not cas and not name:
        return None
    lagerort = (zeile.werte.get('lagerort') or '').strip().casefold()
    return (cas or name, bool(cas), zeile.werte.get('unterbereich_id'),
            lagerort)


def _fasse_zusammen(erste, weitere):
    """Übernimmt eine Zeile in die erste desselben Stoffes am selben Ort.

    Gebindelisten führen denselben Stoff mehrfach - je Behälter eine Zeile.
    Bisher galt das als Duplikat und die Zeilen wurden verworfen. Jetzt wird
    daraus ein Verzeichniseintrag: Mengen werden addiert, leere Felder aus den
    weiteren Zeilen gefüllt. Nichts verschwindet stillschweigend - beide
    Zeilen bleiben in der Vorschau sichtbar.
    """
    weitere.werte['zusammengefasst_in'] = erste.zeilennummer
    erfasst = erste.werte.setdefault('zusammengefasst_aus', [])
    erfasst.append(weitere.zeilennummer)
    erste.werte['anzahl_gebinde'] = len(erfasst) + 1
    erste.warnungen.append(
        f'Zeile {weitere.zeilennummer} als weiteres Gebinde übernommen.')

    for feld in ('cas_nummer', 'eg_nummer', 'signalwort', 'piktogramme',
                 'gefahrenkategorien', 'h_saetze', 'p_saetze', 'lagerklasse',
                 'sdb_datum', 'cmr', 'gebinde'):
        if not erste.werte.get(feld) and weitere.werte.get(feld):
            erste.werte[feld] = weitere.werte[feld]

    menge = weitere.werte.get('menge')
    if menge is None:
        return
    eigene = erste.werte.get('menge')
    eigene_einheit = (erste.werte.get('mengeneinheit') or '').casefold()
    fremde_einheit = (weitere.werte.get('mengeneinheit') or '').casefold()
    if eigene is None:
        erste.werte['menge'] = menge
        if not erste.werte.get('mengeneinheit'):
            erste.werte['mengeneinheit'] = weitere.werte.get('mengeneinheit')
    elif eigene_einheit == fremde_einheit:
        erste.werte['menge'] = eigene + menge
    else:
        # Nicht addieren: "2 L" und "3 kg" ergeben keine Menge. Die erste
        # Menge bleibt stehen, der Hinweis steht in der Vorschau.
        erste.warnungen.append(
            f'Menge aus Zeile {weitere.zeilennummer} ('
            f'{weitere.werte.get("mengeneinheit") or "ohne Einheit"}) wurde '
            'nicht addiert - sie hat eine andere Einheit.')


def markiere_duplikate(zeilen):
    """Fasst Zeilen desselben Stoffes am selben Ort zusammen.

    Gebindelisten führen jeden Behälter als eigene Zeile. Das ist kein
    Duplikat im Sinne des Verzeichnisses, sondern derselbe Eintrag mehrfach -
    die erste Zeile nimmt die weiteren auf (Mengen werden addiert). Die
    weiteren Zeilen bekommen werte['zusammengefasst_in'] = Zeilennummer des
    ersten Vorkommens, damit die Vorschau sie nicht als eigenen Stoff anlegt.

    Derselbe Stoff an zwei Standorten bleibt getrennt - das entspricht /copy.
    Aufgebrauchte Zeilen und Fehlzeilen nehmen an der Zusammenfassung nicht
    teil.

    Rückgabe: Anzahl der zusammengefassten Zeilen.
    """
    gesehen = {}
    anzahl = 0
    for zeile in zeilen:
        if not zeile.gueltig or zeile.werte.get('aufgebraucht'):
            continue
        schluessel = _duplikat_schluessel(zeile)
        if schluessel is None:
            continue

        if schluessel in gesehen:
            _fasse_zusammen(gesehen[schluessel], zeile)
            anzahl += 1
        else:
            gesehen[schluessel] = zeile
    return anzahl


# ─── Vorlage ─────────────────────────────────────────────────────────────────

def vorlage_xlsx():
    """Importvorlage als XLSX-Bytes: Kopfzeile plus Blatt "Hinweise"."""
    arbeitsmappe = Workbook()
    blatt = arbeitsmappe.active
    blatt.title = 'Gefahrstoffe'
    blatt.append([FELDER[schluessel]['label'] for schluessel in VORLAGE_FELDER])

    for zelle in blatt[1]:
        zelle.font = Font(bold=True)
    blatt.freeze_panes = 'A2'

    # Spaltenbreite nach Beschriftung, aber nicht schmaler als sinnvoll.
    for index, schluessel in enumerate(VORLAGE_FELDER, start=1):
        blatt.column_dimensions[get_column_letter(index)].width = min(
            max(len(FELDER[schluessel]['label']) + 4, 16), 40)

    hinweise = arbeitsmappe.create_sheet('Hinweise')
    hinweise.append(['Spalte', 'Hinweis'])
    for zelle in hinweise[1]:
        zelle.font = Font(bold=True)
    for spalte, text in VORLAGE_HINWEISE:
        hinweise.append([spalte, text])
    hinweise.column_dimensions['A'].width = 30
    hinweise.column_dimensions['B'].width = 90

    ausgabe = io.BytesIO()
    arbeitsmappe.save(ausgabe)
    return ausgabe.getvalue()
