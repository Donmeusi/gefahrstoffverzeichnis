#!/usr/bin/env python3
"""Amtliche harmonisierte Einstufung aus Anhang VI der CLP-Verordnung.

Woher die Daten kommen: aus der ECHA-Tabelle "Table of harmonised entries in
Annex VI to CLP" (https://echa.europa.eu/information-on-chemicals/annex-vi-to-clp),
aufbereitet von `werkzeuge/echa_import.py` in die Datei `echa_anhang_vi.json`.
Die Anwendung liest nur diese Datei - kein Netz, kein Excel im Betrieb.

**Warum das die bessere Quelle ist als die Ableitung aus den H-Saetzen
(`piktogramme.py`):** Das Piktogramm folgt nach CLP aus der **Gefahrenklasse**,
nicht aus dem Gefahrenhinweis. Ein Beispiel, das die Grenze der Ableitung zeigt:
Chlorwasserstoff (7647-01-0) ist als "Press. Gas" eingestuft und traegt deshalb
GHS04 - ein Piktogramm, zu dem es in der Einstufungszeile gar keinen H-Satz
gibt. Aus H331 und H314 allein laesst sich GHS04 nicht herleiten. Die Ableitung
bleibt fuer alles nuetzlich, was **nicht** in Anhang VI steht (selbsteingestufte
Stoffe), ist dort aber eine Annaeherung.

⚠️ **Anhang VI enthaelt nur harmonisierte Stoffe**, keine Gemische und keine
selbsteingestuften Stoffe - das ist der kleinere Teil des Chemikalienrechts.
Fuer ein konkretes Produkt bleibt das Sicherheitsdatenblatt die richtige Quelle.
Von 3819 Eintraegen der Tabelle ist das der Stand; Wasser (7732-18-5) etwa steht
nicht darin, weil es nicht eingestuft ist.

⚠️ **Es gilt immer die Fassung, die gerade in Kraft ist.** Die ECHA-Datei deckt
auch kuenftige Aenderungsverordnungen ab (ATP23 gilt ab 01.02.2027).
`werkzeuge/echa_import.py` waehlt beim Erzeugen je Index-Nummer die letzte
Fassung mit Geltungsbeginn <= Stichtag; die ausgeschlossenen stehen im Feld
`nicht_enthalten` der Datei. Wer die Tabelle neu erzeugt, muss den Stichtag
im Blick behalten.

Bezeichnungen: Die Namen in dieser Tabelle sind **englisch** ("hydrogen
chloride"). Die deutsche Bezeichnung holt `wikidata.py`; die deutschen Texte
der H-Saetze stehen in `static/hp_data.json`.
"""
import json
import os

DATEI = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'echa_anhang_vi.json')

# Einmal gelesen, dann im Speicher gehalten. Die Datei ist gut 1 MB gross und
# aendert sich nur, wenn sie neu erzeugt wird.
_bestand = None


def bestand():
    """Die geladene Tabelle. Fehlt die Datei, kommt ein leerer Bestand zurueck.

    Die Anwendung darf an einer fehlenden oder kaputten Datei nicht scheitern:
    die Tabelle ist eine Zusatzquelle, der Autofill arbeitet ohne sie weiter
    (dann ueber PubChem).
    """
    global _bestand
    if _bestand is None:
        try:
            with open(DATEI, encoding='utf-8') as f:
                _bestand = json.load(f)
        except (OSError, ValueError):
            _bestand = {'eintraege': {}, 'quelle': '', 'stichtag': '',
                        'geltendes_recht': '', 'nicht_enthalten': []}
    return _bestand


def stand():
    """Angaben zur Herkunft: Stichtag, geltende Fassung, nicht enthaltene."""
    b = bestand()
    return {k: b.get(k, '') for k in
            ('quelle', 'quelldatei', 'erzeugt', 'stichtag',
             'geltendes_recht', 'nicht_enthalten')}


def anzahl():
    return len(bestand()['eintraege'])


def eintrag(cas=None, eg=None):
    """Sucht einen Eintrag. Erst ueber die CAS-Nummer, dann ueber die EG-Nummer.

    Die EG-Nummer als zweiter Schluessel ist noetig, weil nicht jeder Eintrag
    eine CAS-Nummer hat (Stoffe ohne CAS, etwa manche UVCB). Gibt None zurueck,
    wenn der Stoff nicht in Anhang VI steht - das ist der Normalfall fuer
    selbsteingestufte Stoffe und kein Fehler.
    """
    eintraege = bestand()['eintraege']
    for schluessel in (cas, eg):
        if schluessel:
            treffer = eintraege.get(str(schluessel).strip())
            if treffer:
                return treffer
    return None


def formularwerte(e):
    """Einen Eintrag in die Feldwerte des Formulars uebersetzen.

    Formate wie in der Anwendung ueblich: H-Saetze mit Komma, Gefahrenkategorien
    mit Semikolon (so zerlegt sie das Formular und so erwartet es auch der
    SDB-Upload).
    """
    return {
        'h_saetze': ', '.join(e.get('h', [])),
        'gefahrenkategorien': '; '.join(e.get('k', [])),
        'piktogramme': list(e.get('g', [])),
        'signalwort': e.get('s', ''),
        'index_nummer': e.get('x', ''),
        'atp': e.get('a', ''),
        # Der amtliche Name ist englisch und dient nur dem Abgleich mit dem,
        # was in der Tabelle steht - nicht als Anzeigename.
        'echa_name': e.get('n', ''),
    }
