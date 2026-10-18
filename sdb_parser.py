#!/usr/bin/env python3
"""Sicherheitsdatenblatt auslesen - Abschnitt fuer Abschnitt statt Volltextraten.

Warum dieses Modul: Der fruehere Parser (in `main.py`) suchte Muster im
gesamten Text der ersten 15 Seiten. Das ging an mehreren Stellen schief, die
sich an echten Datenblaettern nachweisen liessen:

* Die CAS-Nummer war der **erste** Treffer von `\\d{2,7}-\\d{2}-\\d`. Im
  Roth-SDB zu Aceton steht davor die Zeile "Index-Nr. in CLP Anhang VI
  606-001-00-8" - gelesen wurde `001-00-8`, also das Ende der Index-Nummer.
* Gefahrenkategorien wurden nur erkannt, wenn sie als CLP-Kuerzel
  ("Flam. Liq. 2") dastanden. Datenblaetter, die die Klasse deutsch
  ausschreiben ("Entzuendbare Fluessigkeiten Kategorie 2"), verloren die
  gesamte Einstufung.
* Das Datum wurde nur als `dd.mm.yyyy` gelesen; "20-Mai-2025" blieb leer.
  Ausserdem galt `Druckdatum` als SDB-Datum - ein altes Datenblatt mit frischem
  Druckdatum haette damit seine 3-/5-Jahres-Frist verloren.

Der Aufbau folgt deshalb drei Regeln:

1. **Erst zerlegen, dann lesen.** `zerlege()` schneidet die 16 Abschnitte
   heraus; jedes Feld wird nur an seiner Stelle gesucht.
2. **Beschriftung vor Muster.** Eine CAS-Nummer gilt nur, wenn sie als solche
   beschriftet ist; ein nacktes Zahlenmuster wird nie als Produkt-CAS
   uebernommen. Zahlen duerfen ausserdem nicht Teil einer laengeren Nummer
   sein (`(?<![\\d-])` verhindert den Index-Nummern-Fehler).
3. **Gegenprobe statt Vertrauen.** `plausibilisiere()` vergleicht die Werte mit
   Anhang VI der CLP-Verordnung (lokal, `echa_anhang_vi.py`) und mit der
   Ableitung aus den H-Saetzen. Widersprueche werden gemeldet, nicht
   stillschweigend ueberschrieben.

Das Modul ist rein: es bekommt Seitentexte (und optional Tabellenzellen) und
gibt ein Dict zurueck. Kein Flask, kein pdfplumber - dadurch ist es ohne
Netz und ohne Datenbank testbar (`test_sdb_parser.py`).
"""
import json
import os
import re
import unicodedata
from datetime import datetime

import echa_anhang_vi
from piktogramme import codes_aus_text, piktogramme_fuer, signalwort_fuer

_REPO = os.path.dirname(os.path.abspath(__file__))

# TRGS 510, Tabelle 1. Dieselbe Liste fuehrt `main.py` fuer den Parser; hier
# steht sie als eigene Konstante, damit das Modul ohne Import von `main`
# testbar bleibt. Ein Test haelt beide Listen zusammen.
LAGERKLASSEN = {
    '1', '2A', '2B', '3', '4.1A', '4.1B', '4.2', '4.3', '5.1A', '5.1B',
    '5.1C', '5.2', '6.1A', '6.1B', '6.1C', '6.1D', '6.2', '7', '8A', '8B',
    '10', '11', '12', '13',
}

# H-Satz -> moegliche Gefahrenkategorien nach Anhang I der CLP-VO.
# Mehrere Eintraege heissen: der H-Satz allein legt die Kategorie nicht fest
# (etwa H228 = Flam. Sol. 1 oder 2). Solche Faelle werden nur zur Gegenprobe
# benutzt, nie geraten.
_H_KATEGORIE = {
    'H200': ['Expl. 1.1'],
    'H201': ['Expl. 1.1'],
    'H202': ['Expl. 1.2'],
    'H203': ['Expl. 1.3'],
    'H204': ['Expl. 1.4'],
    'H205': ['Expl. 1.5'],
    'H206': ['Desens. Expl. 1'],
    'H207': ['Desens. Expl. 2', 'Desens. Expl. 3'],
    'H208': ['Desens. Expl. 4'],
    'H220': ['Flam. Gas 1A'],
    'H221': ['Flam. Gas 1B', 'Flam. Gas 2'],
    'H222': ['Aerosol 1'],
    'H223': ['Aerosol 2'],
    'H229': ['Aerosol 1', 'Aerosol 2', 'Aerosol 3'],
    'H224': ['Flam. Liq. 1'],
    'H225': ['Flam. Liq. 2'],
    'H226': ['Flam. Liq. 3'],
    'H228': ['Flam. Sol. 1', 'Flam. Sol. 2'],
    'H230': ['Flam. Gas 1A'],
    'H231': ['Flam. Gas 1B'],
    'H232': ['Flam. Gas 1A'],
    'H240': ['Self-react. A', 'Org. Perox. A'],
    'H241': ['Self-react. B', 'Org. Perox. B'],
    'H242': ['Self-react. C', 'Self-react. D', 'Self-react. E',
             'Self-react. F', 'Org. Perox. C', 'Org. Perox. D',
             'Org. Perox. E', 'Org. Perox. F'],
    'H250': ['Pyr. Liq. 1'],
    'H251': ['Self-heat. 1'],
    'H252': ['Self-heat. 2'],
    'H260': ['Water-react. 1'],
    'H261': ['Water-react. 2', 'Water-react. 3'],
    'H270': ['Ox. Gas 1'],
    'H271': ['Ox. Liq. 1', 'Ox. Sol. 1'],
    'H272': ['Ox. Liq. 2', 'Ox. Liq. 3', 'Ox. Sol. 2', 'Ox. Sol. 3'],
    'H280': ['Press. Gas'],
    'H281': ['Press. Gas'],
    'H290': ['Met. Corr. 1'],
    'H300': ['Acute Tox. 1', 'Acute Tox. 2'],
    'H301': ['Acute Tox. 3'],
    'H302': ['Acute Tox. 4'],
    'H304': ['Asp. Tox. 1'],
    'H310': ['Acute Tox. 1', 'Acute Tox. 2'],
    'H311': ['Acute Tox. 3'],
    'H312': ['Acute Tox. 4'],
    'H314': ['Skin Corr. 1A', 'Skin Corr. 1B', 'Skin Corr. 1C'],
    'H315': ['Skin Irrit. 2'],
    'H317': ['Skin Sens. 1', 'Skin Sens. 1A', 'Skin Sens. 1B'],
    'H318': ['Eye Dam. 1'],
    'H319': ['Eye Irrit. 2'],
    'H330': ['Acute Tox. 1', 'Acute Tox. 2'],
    'H331': ['Acute Tox. 3'],
    'H332': ['Acute Tox. 4'],
    'H334': ['Resp. Sens. 1', 'Resp. Sens. 1A', 'Resp. Sens. 1B'],
    'H335': ['STOT SE 3'],
    'H336': ['STOT SE 3'],
    'H340': ['Muta. 1A', 'Muta. 1B'],
    'H341': ['Muta. 2'],
    'H350': ['Carc. 1A', 'Carc. 1B'],
    'H350i': ['Carc. 1A', 'Carc. 1B'],
    'H351': ['Carc. 2'],
    'H360': ['Repr. 1A', 'Repr. 1B'],
    'H360F': ['Repr. 1A', 'Repr. 1B'],
    'H360D': ['Repr. 1A', 'Repr. 1B'],
    'H360FD': ['Repr. 1A', 'Repr. 1B'],
    'H360Fd': ['Repr. 1A', 'Repr. 1B'],
    'H360Df': ['Repr. 1A', 'Repr. 1B'],
    'H361': ['Repr. 2'],
    'H361f': ['Repr. 2'],
    'H361d': ['Repr. 2'],
    'H361fd': ['Repr. 2'],
    'H362': ['Lact.'],
    'H370': ['STOT SE 1'],
    'H371': ['STOT SE 2'],
    'H372': ['STOT RE 1'],
    'H373': ['STOT RE 2'],
    'H400': ['Aquatic Acute 1'],
    'H410': ['Aquatic Chronic 1'],
    'H411': ['Aquatic Chronic 2'],
    'H412': ['Aquatic Chronic 3'],
    'H413': ['Aquatic Chronic 4'],
    'H420': ['Ozone 1'],
    # Kombinationsgefahrenhinweise akute Toxizitaet (Anhang I, Tabelle 3.1.2)
    'H300+H310': ['Acute Tox. 1', 'Acute Tox. 2'],
    'H300+H330': ['Acute Tox. 1', 'Acute Tox. 2'],
    'H310+H330': ['Acute Tox. 1', 'Acute Tox. 2'],
    'H300+H310+H330': ['Acute Tox. 1', 'Acute Tox. 2'],
    'H301+H311': ['Acute Tox. 3'],
    'H301+H331': ['Acute Tox. 3'],
    'H311+H331': ['Acute Tox. 3'],
    'H301+H311+H331': ['Acute Tox. 3'],
    'H302+H312': ['Acute Tox. 4'],
    'H302+H332': ['Acute Tox. 4'],
    'H312+H332': ['Acute Tox. 4'],
    'H302+H312+H332': ['Acute Tox. 4'],
}

_MONATE = {
    'januar': 1, 'jan': 1, 'jänner': 1, 'january': 1,
    'februar': 2, 'feb': 2, 'february': 2,
    'märz': 3, 'maerz': 3, 'mrz': 3, 'mar': 3, 'march': 3,
    'april': 4, 'apr': 4,
    'mai': 5, 'may': 5,
    'juni': 6, 'jun': 6, 'june': 6,
    'juli': 7, 'jul': 7, 'july': 7,
    'august': 8, 'aug': 8,
    'september': 9, 'sep': 9, 'sept': 9,
    'oktober': 10, 'okt': 10, 'october': 10, 'oct': 10,
    'november': 11, 'nov': 11,
    'dezember': 12, 'dez': 12, 'december': 12, 'dec': 12,
}
_MONAT_MUSTER = '|'.join(sorted(_MONATE, key=len, reverse=True))

# Eine CAS-Nummer darf nicht Teil einer laengeren Nummer sein. Genau daran
# scheiterte die alte Volltextsuche: `\b` greift nach dem Bindestrich der
# Index-Nummer 606-001-00-8, also wurde `001-00-8` zur CAS-Nummer.
_CAS = re.compile(r'(?<![\d-])(\d{2,7}-\d{2}-\d)(?![\d-])')
_EG = re.compile(r'(?<![\d-])(\d{3}-\d{3}-\d)(?![\d-])')
_INDEX = re.compile(
    r'(?:Index(?:[-\s]?(?:Nr|No|Nummer|Number))\.?|Index\s+number|EU[-\s]?Index[-\s]?(?:Nr|No)\.?)'
    r'[^\n]{0,20}?(\d{3}-\d{3}-\d{1,2}-\d)', re.IGNORECASE)

# Beschriftete CAS-Nummer. Zwischen Beschriftung und Wert sind hoechstens ein
# Zeilenumbruch und 20 Zeichen erlaubt - damit kann kein Wert aus einer
# benachbarten Zeile eingesammelt werden.
_CAS_BESCHRIFTET = re.compile(
    r'(?:CAS(?:[-\s]?(?:Nr|No|Nummer|Registry[-\s]?Number))?|CAS\s*#)'
    r'[^\n]{0,20}?[:\s]\s*' + _CAS.pattern, re.IGNORECASE)
_EG_BESCHRIFTET = re.compile(
    r'(?:EG|EC)[-\s]?(?:Nr|No|Nummer|Number)\.?'
    r'[^\n]{0,20}?[:\s]\s*' + _EG.pattern, re.IGNORECASE)

_ABSCHNITT = re.compile(
    r'(?im)^[ \t]*(?:(?:ABSCHNITT|SECTION)\s*(\d{1,2})\b'
    r'|(\d{1,2})\.(?=\s*[A-ZÄÖÜ]))')

_LABEL_NAME = re.compile(
    r'^(?:Produktbezeichnung|Produktidentifikator|Handelsname(?:/Bezeichnung)?'
    r'|Produktname|Stoffname'
    r'|Bezeichnung\s+des\s+Stoff(?:e)?s|Bezeichnung\s+des\s+Gemischs'
    r'|Product\s+name|Trade\s+name|Product\s+identifier|Name\s+of\s+the\s+substance'
    r'|Name\s+of\s+the\s+mixture)\s*[:\-]\s*(.+)$', re.IGNORECASE)

# Eine Zeile, die nur aus einer Beschriftung besteht ("Handelsname/Bezeichnung:").
# Der Wert steht dann in der naechsten Zeile.
_NUR_LABEL = re.compile(
    r'^(?:Produktbezeichnung|Produktidentifikator|Handelsname(?:/Bezeichnung)?'
    r'|Produktname|Stoffname|Bezeichnung\s+des\s+Stoff(?:e)?s'
    r'|Bezeichnung\s+des\s+Gemischs|Product\s+name|Trade\s+name'
    r'|Product\s+identifier)\s*:?\s*$', re.IGNORECASE)

# Zeilen, die in Abschnitt 1.1 stehen, aber nie der Produktname sind.
_KEIN_NAME = re.compile(
    r'(?i)(?:Artikelnummer|Art\.-?Nr|Produktcode|Produktnummer|CAS[-\s]?(?:Nr|No)'
    r'|EG[-\s]?(?:Nr|No)|EC[-\s]?(?:Nr|No)|Index|REACH|Registrierungsnummer'
    r'|Telefon|Telefax|E-Mail|Notruf|Version|Datum|Seite|Sicherheitsdatenblatt'
    r'|gemäß|Verordnung|ABSCHNITT|Abschnitt|Unternehmen|Lieferant|Anschrift'
    r'|Product\s+code|Product\s+number|Telephone|Fax|E-mail|Emergency)')

_KATEGORIEN = []
_KATEGORIE_RE = []


def _lade_kategorien():
    """Die 89 CLP-Kategorien aus `static/hp_data.json` - dieselben, die der
    Auswahldialog anbietet. Eine Kategorie, die dort nicht steht, darf auch
    nicht aus einem SDB ins Feld wandern."""
    global _KATEGORIEN
    if _KATEGORIEN:
        return _KATEGORIEN
    try:
        with open(os.path.join(_REPO, 'static', 'hp_data.json'), encoding='utf-8') as f:
            _KATEGORIEN = [e['code'] for e in json.load(f)['gefahrenkategorien']]
    except Exception:
        _KATEGORIEN = []
    return _KATEGORIEN


def _kategorie_muster(code):
    """Ein CLP-Kuerzel als tolerantes Muster.

    Datenblaetter schreiben "Flam. Liq. 2", "Flam.Liq.2" oder "Flam Liq 2";
    zwischen den Teilen darf deshalb alles aus Punkt, Bindestrich und
    Leerraum stehen. Bindestrich ist noetig fuer "Water-react." und
    "Self-react.".
    """
    teile = re.findall(r'[A-Za-zÄÖÜäöüß]+|\d+(?:\.\d+)?', code)
    return (r'(?<![A-Za-z])' + r'[\s.\-]*'.join(re.escape(t) for t in teile)
            + r'(?![A-Za-z0-9])')


def _kategorie_regexes():
    global _KATEGORIE_RE
    if _KATEGORIE_RE:
        return _KATEGORIE_RE
    codes = _lade_kategorien()
    # Laengere Kuerzel zuerst, damit "Flam. Gas 1A" nicht von einem kuerzeren
    # Muster ueberdeckt wird.
    _KATEGORIE_RE = [(c, re.compile(_kategorie_muster(c), re.IGNORECASE))
                     for c in sorted(codes, key=len, reverse=True)]
    return _KATEGORIE_RE


def normalisiere(text):
    """PDF-Text vereinheitlichen, bevor Muster greifen.

    Die Zeichen, die in echten Datenblaettern regelmaessig Stoerungen
    verursachen: weiche Trennzeichen, geschuetzte Leerzeichen, Ligaturen und
    die vier Bindestrich-Varianten. NFKC loest Ligaturen und Breitzeichen auf,
    die Ersetzungen danach sind bewusst explizit.
    """
    if not text:
        return ''
    text = unicodedata.normalize('NFKC', str(text))
    text = text.replace('­', '').replace('​', '').replace('﻿', '')
    text = text.replace(' ', ' ').replace(' ', ' ').replace(' ', ' ')
    for zeichen in ('‐', '‑', '‒', '–', '—', '−'):
        text = text.replace(zeichen, '-')
    return text.replace('\r\n', '\n').replace('\r', '\n')


def _kopfzeilen_ueberspringen(text, ende):
    """Nach einer Ueberschrift den Rest ihrer Zeile verwerfen.

    "ABSCHNITT 1: Bezeichnung des Stoffs ..." ist eine Ueberschrift, kein
    Inhalt. Blieb der Rest stehen, wurde er als Produktname gelesen - genau so
    entstand der Name ": Bezeichnung des Stoffs beziehungsweise des Gemischs".
    """
    zeilenende = text.find('\n', ende)
    return zeilenende + 1 if zeilenende != -1 else ende


def zerlege(text):
    """Die 16 Abschnitte eines SDB als Dict {Nummer: Text}.

    Erkannt werden "ABSCHNITT 2", "SECTION 2" und die deutsche Zaehlform
    "2. Mögliche Gefahren". Wiederholte Kopfzeilen ("ABSCHNITT 2" auf jeder
    Seite) werden demselben Abschnitt zugeordnet, nicht als neuer Block
    gewertet - sonst ginge der Text der Folgeseiten verloren.

    ⚠️ Die Zaehlform ist nur der Rueckfall. Sie ist nicht eindeutig: Aufzah-
    lungen ("2. Behälter ...") sehen genauso aus. Am Roth-Datenblatt hat ein
    spaeteres "2." den ganzen Abschnitt 2 ueberschrieben. Deshalb gilt: Stehen
    mindestens fuenf "ABSCHNITT/SECTION"-Ueberschriften im Text, werden nur
    diese benutzt; sonst muss die Zaehlform der erwarteten Reihenfolge folgen.
    """
    ausdruecklich = [(m, int(m.group(1))) for m in _ABSCHNITT.finditer(text)
                     if m.group(1)]
    if len(ausdruecklich) >= 5:
        treffer = ausdruecklich
    else:
        treffer = []
        erwartet = 1
        for m in _ABSCHNITT.finditer(text):
            if m.group(1):
                treffer.append((m, int(m.group(1))))
                erwartet = int(m.group(1)) + 1
            elif int(m.group(2)) == erwartet:
                treffer.append((m, erwartet))
                erwartet += 1

    ergebnis = {}
    aktuell = None
    for i, (m, nummer) in enumerate(treffer):
        if not 1 <= nummer <= 16:
            continue
        ende = treffer[i + 1][0].start() if i + 1 < len(treffer) else len(text)
        block = text[_kopfzeilen_ueberspringen(text, m.end()):ende]
        if nummer == aktuell and nummer in ergebnis:
            ergebnis[nummer] += '\n' + block
        else:
            ergebnis[nummer] = block
            aktuell = nummer
    return ergebnis


def _unterabschnitt_22(abschnitt_2):
    """Den Block 2.2 (Kennzeichnungselemente) aus Abschnitt 2 schneiden.

    Die Einstufungstabelle in 2.1 nennt dieselben Codes wie die Kennzeichnung,
    aber mehrfach und in anderer Bedeutung. Wird sie mitgelesen, landen Codes
    im Feld, die nicht zur Kennzeichnung gehoeren - deshalb die harte Grenze.
    """
    m = re.search(
        r'(?im)^[ \t]*2\.2\.?\s*(?:Kennzeichnungselemente|Labelling|Label\s+elements)'
        r'(.*?)(?=^[ \t]*2\.3\.?\s|^[ \t]*(?:ABSCHNITT|SECTION)\s*3\b|\Z)',
        abschnitt_2, re.DOTALL)
    if m:
        return m.group(1)
    m = re.search(
        r'(?i)(?:Kennzeichnungselemente|Labelling|Label\s+elements)'
        r'(.*?)(?=2\.3\.?\s*(?:Sonstige|Other)|ABSCHNITT\s*3\b|SECTION\s*3\b|\Z)',
        abschnitt_2, re.DOTALL)
    return m.group(1) if m else ''


def _datum_lesen(text):
    """Ein Datum aus einem kurzen Textstueck. Gibt `date` oder None."""
    if not text:
        return None

    # 2025-05-20 (ISO)
    m = re.search(r'(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)', text)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date()
        except ValueError:
            pass

    # 20.05.2025 / 20-05-2025 / 20/05/2025
    m = re.search(r'(?<!\d)(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})(?!\d)', text)
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).date()
        except ValueError:
            pass

    # 20-Mai-2025 / 20. Mai 2025 / 20 Mai 2025
    m = re.search(r'(?<!\d)(\d{1,2})\.?[\s\-]+(' + _MONAT_MUSTER + r')\.?[\s\-,]+(\d{4})',
                  text, re.IGNORECASE)
    if m:
        monat = _MONATE.get(m.group(2).lower().rstrip('.'))
        if monat:
            try:
                return datetime(int(m.group(3)), monat, int(m.group(1))).date()
            except ValueError:
                pass

    # May 20, 2025
    m = re.search(r'(' + _MONAT_MUSTER + r')\.?\s+(\d{1,2}),?\s+(\d{4})',
                  text, re.IGNORECASE)
    if m:
        monat = _MONATE.get(m.group(1).lower().rstrip('.'))
        if monat:
            try:
                return datetime(int(m.group(3)), monat, int(m.group(2))).date()
            except ValueError:
                pass
    return None


def _datum_aus_kopf(seiten):
    """Revisionsdatum aus dem Kopfbereich (erste zwei Seiten).

    Reihenfolge: beschriftetes Revisionsdatum, dann beschriftetes Druckdatum
    **nur als Hinweis** - ein Druckdatum ist kein SDB-Datum und darf die
    Fristenrechnung nicht retten. Gibt (datum, fundstelle, nur_druck) zurueck.
    """
    kopf = '\n'.join(seiten[:2])
    for label in (
        r'Überarbeitet\s+am', r'Datum\s+der\s+Überarbeitung', r'Revisionsdatum',
        r'Überarbeitungsdatum', r'Bearbeitungsdatum', r'Ausgabedatum',
        r'Datum\s+der\s+letzten\s+(?:Änderung|Überarbeitung)',
        r'Letzte\s+(?:Änderung|Aktualisierung)',
        r'Revision\s+date', r'Date\s+of\s+revision', r'Version\s+date',
        r'Date\s+of\s+issue',
    ):
        m = re.search(r'(?i)(' + label + r')\s*[:\-]?\s*([^\n]{0,45})', kopf)
        if m:
            datum = _datum_lesen(m.group(2))
            if datum:
                return datum, m.group(0).strip()[:120], False

    m = re.search(r'(?i)(Druckdatum|Print\s+date)\s*[:\-]?\s*([^\n]{0,45})', kopf)
    if m and _datum_lesen(m.group(2)):
        return None, m.group(0).strip()[:120], True
    return None, '', False


def _name_aus_abschnitt_1(abschnitt_1):
    """Produktname aus Abschnitt 1.1 (Fallback: Abschnitt 1 bis 1.2)."""
    block = abschnitt_1
    m = re.search(
        r'(?is)1\.1\.?\s*(?:Produktidentifikator|Product\s+identifier)'
        r'(.*?)(?=1\.2\.?\s|\Z)', abschnitt_1)
    if m:
        block = m.group(1)
    else:
        m = re.search(r'(?is)(.*?)(?=1\.2\.?\s|\Z)', abschnitt_1)
        if m:
            block = m.group(1)

    zeilen = [z.strip() for z in block.split('\n') if z.strip()]

    # 1. Beschriftete Zeile ("Produktbezeichnung: D-Tack Aceton")
    for zeile in zeilen:
        m = _LABEL_NAME.match(zeile)
        if m:
            kandidat = m.group(1).strip()
            if kandidat and not _KEIN_NAME.search(kandidat):
                return kandidat[:100]

    # 2. Erste brauchbare Zeile (Roth: Name steht direkt unter der Ueberschrift,
    #    ohne Doppelpunkt hinter "Bezeichnung des Stoffs").
    for zeile in zeilen:
        if _NUR_LABEL.match(zeile):
            continue
        if _KEIN_NAME.search(zeile):
            continue
        zeile = re.sub(
            r'(?i)^(?:Bezeichnung\s+des\s+Stoff(?:e)?s|Bezeichnung\s+des\s+Gemischs'
            r'|Handelsname|Produktname|Stoffname|Produktbezeichnung)\s+', '', zeile)
        if re.fullmatch(r'[\d\s.,;:/()-]+', zeile):
            continue
        if len(zeile) < 3:
            continue
        # Eine reine Beschriftung ohne Wert ist kein Name.
        if zeile.rstrip(':').strip().lower() in {
            'produktidentifikator', 'produktbezeichnung', 'handelsname',
            'produktname', 'stoffname', 'bezeichnung des stoffs',
            'bezeichnung des stoffes', 'bezeichnung des gemischs',
            'product identifier', 'product name', 'trade name',
        }:
            continue
        return zeile[:100]
    return ''


def _cas_und_eg(abschnitt_1):
    """CAS- und EG-Nummer aus Abschnitt 1 - beschriftet, nie aus Abschnitt 3.

    Die CAS-Nummer eines Gemischs ist die CAS-Nummer **eines Bestandteils**;
    sie darf nicht als Stoff-CAS ins Verzeichnis wandern. Deshalb stammt sie
    ausschliesslich aus Abschnitt 1, wo bei Reinstoffen die Produkt-CAS steht.
    """
    warnungen = []

    m = _CAS_BESCHRIFTET.search(abschnitt_1)
    cas = m.group(1) if m else ''
    if not cas:
        kandidaten = [x.group(1) for x in _CAS.finditer(abschnitt_1)
                      if not re.search(r'(?i)index[^\n]{0,30}$',
                                       abschnitt_1[max(0, x.start() - 40):x.start()])]
        kandidaten = list(dict.fromkeys(kandidaten))
        if len(kandidaten) == 1:
            cas = kandidaten[0]
            warnungen.append({
                'feld': 'cas', 'schwere': 'hinweis',
                'text': f'Die CAS-Nummer {cas} war nicht beschriftet und wurde '
                        'aus Abschnitt 1 übernommen - bitte prüfen.',
            })
        elif len(kandidaten) > 1:
            warnungen.append({
                'feld': 'cas', 'schwere': 'warnung',
                'text': 'Mehrere CAS-Nummern in Abschnitt 1 ohne Beschriftung '
                        f'({", ".join(kandidaten[:3])}); das Feld bleibt leer.',
            })

    m = _EG_BESCHRIFTET.search(abschnitt_1)
    eg = m.group(1) if m else ''
    index = _INDEX.search(abschnitt_1)
    index = index.group(1) if index else ''

    if not eg:
        kandidaten = [x.group(1) for x in _EG.finditer(abschnitt_1)
                      if x.group(1) != cas and x.group(1) != index]
        if len(kandidaten) == 1:
            eg = kandidaten[0]
            warnungen.append({
                'feld': 'eg', 'schwere': 'hinweis',
                'text': f'Die EG-Nummer {eg} war nicht beschriftet und wurde '
                        'aus Abschnitt 1 übernommen - bitte prüfen.',
            })

    return cas, eg, index, warnungen


def _bestandteile(abschnitt_3, tabellen):
    """Bestandteile aus Abschnitt 3 - CAS, EG und Konzentration, soweit lesbar.

    Die Liste dient zwei Zwecken: sie erkennt ein Gemisch (mehr als ein
    Bestandteil) und sie zeigt dem Nutzer, was im Datenblatt steht. Gespeichert
    wird sie nicht.
    """
    gesehen = {}

    def ergaenze(cas, eg='', konzentration='', naehe=''):
        if not cas or cas in gesehen:
            return
        if not eg:
            m = _EG.search(naehe)
            if m and m.group(1) != cas:
                eg = m.group(1)
        if not konzentration:
            m = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:[-–]\s*(\d+(?:[.,]\d+)?))?\s*%',
                          naehe)
            if m:
                konzentration = m.group(0).replace(' ', '')
        gesehen[cas] = {'cas': cas, 'eg': eg, 'konzentration': konzentration}

    for m in _CAS.finditer(abschnitt_3):
        umfeld = abschnitt_3[max(0, m.start() - 120):m.end() + 120]
        # Ein Index-Ende ist keine CAS-Nummer; die Lookarounds verhindern das
        # bereits, zusaetzlich wird "Index" im Umfeld ausgeschlossen.
        if re.search(r'(?i)index[^\n]{0,30}$', abschnitt_3[max(0, m.start() - 40):m.start()]):
            continue
        ergaenze(m.group(1), naehe=umfeld)

    for tabelle in tabellen or []:
        for zeile in tabelle or []:
            zellen = [str(z or '').strip() for z in zeile or []]
            zeilentext = ' | '.join(zellen)
            m = _CAS.search(zeilentext)
            if m:
                ergaenze(m.group(1), naehe=zeilentext)
            elif any('gemisch' in z.lower() for z in zellen):
                continue

    return list(gesehen.values())[:20]


def _kategorien_aus_abkuerzungen(text):
    """CLP-Kuerzel in der Reihenfolge ihres Auftretens.

    Die Reihenfolge ist nicht kosmetisch: Sie zeigt dem Nutzer die Klassen so,
    wie sie im Datenblatt stehen. Deshalb werden Treffer nach Position
    sortiert, nicht nach der Laenge des Kuerzels.
    """
    treffer = []
    for code, muster in _kategorie_regexes():
        for m in muster.finditer(text):
            treffer.append((m.start(), code))
    treffer.sort(key=lambda x: x[0])
    return _eindeutig([code for _, code in treffer])


def _deutsch_zu_kategorien(klasse, kategorie):
    """Deutsche Gefahrenklasse + Kategorie -> CLP-Kuerzel.

    Datenblaetter schreiben die Klasse haeufig aus ("Entzuendbare
    Fluessigkeiten Kategorie 2"). Ohne diese Zuordnung verliert der Parser die
    gesamte Einstufung - der Fall, der am D-Tack-Datenblatt nachweisbar war.
    """
    k = klasse.lower()
    kats = [x.strip() for x in kategorie.replace(' ', '').split('/') if x.strip()]
    ergebnis = []

    def nimm(familie):
        for kat in kats:
            code = f'{familie} {kat}'
            if code in _lade_kategorien():
                ergebnis.append(code)

    if 'wasser' in k and 'entzündbare gase' in k:
        nimm('Water-react.')
    elif 'entzündbare flüssigkeit' in k:
        nimm('Flam. Liq.')
    elif 'entzündbare gase' in k or 'entzündbares gas' in k:
        nimm('Flam. Gas')
    elif 'entzündbarer feststoff' in k or 'entzündbare feststoffe' in k:
        nimm('Flam. Sol.')
    elif 'aerosol' in k:
        nimm('Aerosol')
    elif 'oxidierende gase' in k or 'oxidierendes gas' in k:
        nimm('Ox. Gas')
    elif 'gase unter druck' in k:
        ergebnis.append('Press. Gas')
    elif 'oxidierende flüssigkeit' in k:
        nimm('Ox. Liq.')
    elif 'oxidierender feststoff' in k or 'oxidierende feststoffe' in k:
        nimm('Ox. Sol.')
    elif 'selbstzersetzlich' in k:
        nimm('Self-react.')
    elif 'organische peroxide' in k:
        nimm('Org. Perox.')
    elif 'pyrophore flüssigkeit' in k:
        nimm('Pyr. Liq.')
    elif 'pyrophorer feststoff' in k:
        nimm('Pyr. Sol.')
    elif 'selbsterhitzungsfähig' in k:
        nimm('Self-heat.')
    elif 'auf metalle korrosiv' in k:
        nimm('Met. Corr.')
    elif 'desensibilisierte explosive' in k:
        nimm('Desens. Expl.')
    elif 'akute toxizität' in k:
        nimm('Acute Tox.')
    elif 'ätz' in k or 'hautätz' in k:
        nimm('Skin Corr.')
    elif 'hautreiz' in k or ('reiz' in k and 'haut' in k):
        nimm('Skin Irrit.')
    elif 'augenschädigung' in k and 'augenreizung' in k:
        # "Schwere Augenschädigung/Augenreizung Kategorie 1" = Eye Dam.,
        # Kategorie 2 = Eye Irrit. - die Kategorie entscheidet.
        if '1' in kats:
            nimm('Eye Dam.')
        if '2' in kats:
            nimm('Eye Irrit.')
    elif 'augenschädigung' in k:
        nimm('Eye Dam.')
    elif 'augenreizung' in k:
        nimm('Eye Irrit.')
    elif 'sensibilisierung der atemwege' in k:
        nimm('Resp. Sens.')
    elif 'sensibilisierung der haut' in k:
        nimm('Skin Sens.')
    elif 'keimzellmutagenität' in k:
        nimm('Muta.')
    elif 'karzinogenität' in k:
        nimm('Carc.')
    elif 'reproduktionstoxizität' in k:
        nimm('Repr.')
    elif 'laktation' in k:
        ergebnis.append('Lact.')
    elif 'zielorgan' in k and 'wiederholte' in k:
        nimm('STOT RE')
    elif 'zielorgan' in k:
        nimm('STOT SE')
    elif 'aspirationsgefahr' in k:
        nimm('Asp. Tox.')
    elif 'gewässergefährdend' in k and 'akut' in k:
        nimm('Aquatic Acute')
    elif 'gewässergefährdend' in k:
        nimm('Aquatic Chronic')
    elif 'ozonschicht' in k:
        nimm('Ozone')
    return ergebnis


def _kategorien_aus_deutsch(text):
    gefunden = []
    for zeile in text.split('\n'):
        # Explosivstoffe tragen "Unterklasse 1.1" statt "Kategorie 1".
        for m in re.finditer(
                r'(?i)(explosive\s+stoffe[^\n]{0,100}?unterklasse\s+(\d\.\d))', zeile):
            code = f'Expl. {m.group(2)}'
            if code in _lade_kategorien():
                gefunden.append(code)

        for m in re.finditer(
                r'(?i)([A-ZÄÖÜ][^\n]{2,120}?)\s*(?:Kategorie|Kat\.?)\s*'
                r'([0-9][A-Za-z]?(?:\s*/\s*[0-9A-Za-z]+)?)', zeile):
            gefunden.extend(_deutsch_zu_kategorien(m.group(1), m.group(2)))
    return gefunden


def _eindeutig(liste):
    ergebnis, gesehen = [], set()
    for eintrag in liste:
        schluessel = eintrag.lower()
        if schluessel not in gesehen:
            gesehen.add(schluessel)
            ergebnis.append(eintrag)
    return ergebnis


def _kategorien_aus_h(h_saetze):
    sicher, unsicher = [], []
    for code in h_saetze:
        kandidaten = _H_KATEGORIE.get(code)
        if not kandidaten:
            continue
        if len(set(kandidaten)) == 1:
            sicher.append(kandidaten[0])
        else:
            unsicher.append((code, kandidaten))
    return _eindeutig(sicher), unsicher


def _seite_von(fundstelle, seiten):
    """Erste Seite, auf der die Fundstelle vorkommt (1-basiert)."""
    if not fundstelle:
        return None
    kuerzel = fundstelle.strip()[:60]
    for i, seite in enumerate(seiten, 1):
        if kuerzel and kuerzel in seite:
            return i
    return None


def _seite_abschnitt(seiten, nummer, titel):
    """Seite, auf der ein Unterabschnitt beginnt ("2.1 Einstufung").

    Genauer als `_seite_von`, weil ein Kuerzel wie "Eye Irrit. 2" auch in
    Abschnitt 16 (Wortlaut der H-Saetze) steht - die Fundstelle waere dann
    Seite 10 statt Seite 1.
    """
    muster = re.compile(r'(?i)' + re.escape(nummer) + r'\.?\s*' + titel)
    for i, seite in enumerate(seiten, 1):
        if muster.search(seite):
            return i
    return None


def _abschnitt_von(fundstelle, abschnitte):
    """Abschnittsnummer, in der die Fundstelle steht - oder None."""
    if not fundstelle:
        return None
    kuerzel = fundstelle.strip()[:60]
    for nummer, text in abschnitte.items():
        if kuerzel and kuerzel in text:
            return nummer
    return None


def _warnung(feld, text, schwere='warnung'):
    return {'feld': feld, 'schwere': schwere, 'text': text}


def analysiere(seiten, tabellen=None):
    """SDB-Seitentexte -> Formularwerte, Quellen und Warnungen.

    `seiten` ist eine Liste von Seitentexten (pdfplumber `extract_text`),
    `tabellen` optional eine Liste von Tabellen (`extract_tables`). Reine
    Funktion: kein Dateizugriff ausser der mitgelieferten Kategorienliste und
    dem Anhang-VI-Bestand.
    """
    seiten = [normalisiere(s or '') for s in (seiten or [])]
    volltext = '\n'.join(seiten)
    if len(volltext.strip()) < 200:
        return {
            'success': False,
            'error': 'Das PDF enthält keinen auslesbaren Text. Vermutlich ist es '
                     'ein Scan ohne Textebene - bitte das Original-PDF des '
                     'Herstellers verwenden oder die Werte von Hand eintragen.',
        }

    abschnitte = zerlege(volltext)
    sec1 = abschnitte.get(1, '')
    sec2 = abschnitte.get(2, '')
    sec3 = abschnitte.get(3, '')
    sec7 = abschnitte.get(7, '')

    warnungen = []
    quellen = {}

    # --- Name ---------------------------------------------------------------
    name = _name_aus_abschnitt_1(sec1)
    if name:
        quellen['name'] = {'abschnitt': '1.1', 'seite': _seite_von(name, seiten),
                           'fundstelle': name}
    else:
        warnungen.append(_warnung('name',
            'Der Produktname konnte in Abschnitt 1.1 nicht gefunden werden.'))

    # --- CAS / EG -----------------------------------------------------------
    cas, eg, index, cas_warnungen = _cas_und_eg(sec1)
    warnungen.extend(cas_warnungen)
    if cas:
        quellen['cas'] = {'abschnitt': '1.1 bzw. 1.2', 'seite': _seite_von(cas, seiten),
                          'fundstelle': f'CAS-Nummer {cas}'}
    if eg:
        quellen['eg'] = {'abschnitt': '1.1 bzw. 1.2', 'seite': _seite_von(eg, seiten),
                         'fundstelle': f'EG-Nummer {eg}'}

    # --- Kennzeichnung (2.2) -------------------------------------------------
    sec22 = _unterabschnitt_22(sec2)
    if not sec22:
        sec22 = sec2
        if sec2:
            warnungen.append(_warnung('h_saetze',
                'Der Block 2.2 (Kennzeichnungselemente) wurde nicht gefunden; '
                'H- und P-Sätze stammen aus dem gesamten Abschnitt 2.', 'hinweis'))

    h_saetze = codes_aus_text(sec22)
    euh_saetze = [re.sub(r'\s+', '', x).upper() for x in
                  re.findall(r'(?<![A-Za-z])(EUH\s?\d{3}[A-Za-z]?)', sec22, re.IGNORECASE)]
    h_saetze = _eindeutig(h_saetze + euh_saetze)
    if not h_saetze and sec2:
        h_saetze = _eindeutig(codes_aus_text(sec2))
        if h_saetze:
            warnungen.append(_warnung('h_saetze',
                'In Abschnitt 2.2 standen keine H-Sätze; sie wurden aus '
                'Abschnitt 2 übernommen.', 'hinweis'))
    if not h_saetze:
        warnungen.append(_warnung('h_saetze',
            'Es wurden keine H-Sätze gefunden. Bitte von Hand prüfen.'))

    p_saetze = _eindeutig([
        re.sub(r'\s+', '', x).upper()
        for x in re.findall(r'(?<![A-Za-z])(P\s?\d{3}(?:\s*\+\s*P\s?\d{3})*)',
                            sec22, re.IGNORECASE)
    ])
    if not p_saetze:
        warnungen.append(_warnung('p_saetze',
            'Es wurden keine P-Sätze gefunden. Bitte von Hand prüfen.', 'hinweis'))

    muster_signalwort = re.search(
        r'Signalwort\s*(?:\([^)]{0,20}\))?\s*[:\-]?\s*(Gefahr|Achtung)\b',
        sec22 or sec2, re.IGNORECASE)
    signalwort = muster_signalwort.group(1).capitalize() if muster_signalwort else ''
    abgeleitet = signalwort_fuer(h_saetze) or ''
    if signalwort and abgeleitet and signalwort.lower() != abgeleitet.lower():
        warnungen.append(_warnung('signalwort',
            f'Das SDB nennt „{signalwort}", die H-Sätze ergeben „{abgeleitet}". '
            'Bitte prüfen.', 'hinweis'))
    if not signalwort and abgeleitet:
        signalwort = abgeleitet
        warnungen.append(_warnung('signalwort',
            f'Kein Signalwort im SDB gefunden; aus den H-Sätzen abgeleitet: '
            f'„{abgeleitet}".', 'hinweis'))

    piktogramme = sorted({x.upper() for x in
                          re.findall(r'\b(GHS0[1-9])\b', sec22, re.IGNORECASE)}
                         | set(piktogramme_fuer(h_saetze)))

    if h_saetze:
        quellen['h_saetze'] = {
            'abschnitt': '2.2',
            'seite': (_seite_abschnitt(seiten, '2.2', 'Kennzeichnungselemente')
                      or _seite_von(h_saetze[0], seiten)),
            'fundstelle': ', '.join(sorted(h_saetze)),
        }
    if p_saetze:
        quellen['p_saetze'] = {
            'abschnitt': '2.2',
            'seite': (_seite_abschnitt(seiten, '2.2', 'Kennzeichnungselemente')
                      or _seite_von(p_saetze[0], seiten)),
            'fundstelle': ', '.join(sorted(p_saetze)),
        }
    if signalwort:
        quellen['signalwort'] = {
            'abschnitt': '2.2',
            'seite': (_seite_abschnitt(seiten, '2.2', 'Kennzeichnungselemente')
                      or _seite_von('Signalwort', seiten)),
            'fundstelle': f'Signalwort {signalwort}',
        }

    # --- Gefahrenkategorien --------------------------------------------------
    # Die Tabellen aus Abschnitt 3 nennen die Einstufung der **Bestandteile**,
    # nicht die des Gemischs. Sie duerfen deshalb nicht in die Kategorien
    # fliessen - am Planol-Datenblatt kamen so Acute Tox. 4, Skin Irrit. 2,
    # Eye Dam. 1 und Aquatic Chronic 3 dazu, obwohl das Produkt nur Eye Irrit. 2
    # ist. Abschnitt 2.1 steht im Text; Tabellen werden nur fuer die
    # Bestandteile (Abschnitt 3) gelesen.
    sec21 = sec2
    kategorien = _eindeutig(
        _kategorien_aus_abkuerzungen(sec21)
        + _kategorien_aus_deutsch(sec21))

    sicher, unsicher = _kategorien_aus_h(h_saetze)

    if kategorien:
        # Jeder H-Satz muss durch eine Kategorie gedeckt sein. Fehlt die
        # Deckung, ist entweder die Klasse nicht erkannt oder der H-Satz
        # gehoert nicht zur Kennzeichnung.
        for code, kandidaten in unsicher:
            if not set(kandidaten) & set(kategorien):
                warnungen.append(_warnung('gefahrenkategorien',
                    f'Für {code} wurde keine passende Kategorie in Abschnitt 2.1 '
                    f'gefunden ({", ".join(kandidaten)}).', 'hinweis'))
        # Eindeutige Kategorien aus den H-Sätzen ergaenzen - aber nur, wenn
        # sie in Abschnitt 2.1 fehlen. So bleibt die Tabelle fuehrend, und
        # eine unvollstaendige Erkennung fuellt sich nicht mit Raten.
        for code in sicher:
            if code not in kategorien:
                kategorien.append(code)
        alle_moeglichen = {c for code in h_saetze
                           for c in _H_KATEGORIE.get(code, [])}
        for code in kategorien:
            if h_saetze and code not in alle_moeglichen:
                warnungen.append(_warnung('gefahrenkategorien',
                    f'Die Kategorie „{code}" wird durch keinen der gefundenen '
                    'H-Sätze gestützt.', 'hinweis'))
    else:
        kategorien = sicher
        if kategorien:
            warnungen.append(_warnung('gefahrenkategorien',
                'Abschnitt 2.1 nannte keine auswertbare Klasse; die Kategorien '
                'wurden aus den H-Sätzen abgeleitet.', 'hinweis'))
        if unsicher:
            warnungen.append(_warnung('gefahrenkategorien',
                'Einige H-Sätze legen die Kategorie nicht eindeutig fest: '
                + ', '.join(code for code, _ in unsicher) + '.'))

    if kategorien:
        quellen['gefahrenkategorien'] = {
            'abschnitt': '2.1',
            'seite': (_seite_abschnitt(seiten, '2.1', 'Einstufung')
                      or _seite_von(kategorien[0], seiten)),
            'fundstelle': '; '.join(kategorien),
        }

    # --- Datum ---------------------------------------------------------------
    datum, datum_fund, nur_druck = _datum_aus_kopf(seiten)
    if datum:
        quellen['sdb_datum'] = {'abschnitt': 'Kopfbereich', 'seite': 1,
                                'fundstelle': datum_fund}
    elif nur_druck:
        warnungen.append(_warnung('sdb_datum',
            'Im Dokument steht nur ein Druckdatum, kein Revisionsdatum. Das '
            'Feld bleibt leer, damit ein altes Datenblatt nicht aktuell wirkt.'))
    else:
        warnungen.append(_warnung('sdb_datum',
            'Kein Revisionsdatum gefunden. Bitte das Datum von Hand eintragen.'))

    # --- Lagerklasse ---------------------------------------------------------
    lagerklasse, lgk_fund, ausserhalb = '', '', False
    for quelle, bereich in (('7.2', sec7), ('Volltext', volltext)):
        if not bereich:
            continue
        for m in re.finditer(r'(?i)(?:Lagerklasse|LGK)'
                             r'(?:\s*\([^)]{0,40}\))?'
                             r'(?:\s*TRGS\s*510)?'
                             r'[^\n]{0,40}?\b(\d{1,2}(?:\.\d)?\s?[A-Za-z]?)\b', bereich):
            kandidat = m.group(1).replace(' ', '').upper()
            if kandidat in LAGERKLASSEN:
                lagerklasse, lgk_fund = kandidat, m.group(0).strip()[:120]
                ausserhalb = quelle == 'Volltext'
                break
        if lagerklasse:
            break
    if lagerklasse:
        gefunden_in = _abschnitt_von(lgk_fund, abschnitte)
        quellen['lagerklasse'] = {
            'abschnitt': (f'{gefunden_in}' if ausserhalb and gefunden_in else '7.2'),
            'seite': _seite_von(lgk_fund, seiten),
            'fundstelle': lgk_fund,
        }
        if ausserhalb:
            warnungen.append(_warnung('lagerklasse',
                'Die Lagerklasse steht nicht in Abschnitt 7.2'
                + (f', sondern in Abschnitt {gefunden_in}' if gefunden_in else '')
                + ' - bitte prüfen.', 'hinweis'))

    # --- Gemisch / Bestandteile ---------------------------------------------
    bestandteile = _bestandteile(sec3, tabellen)
    ist_gemisch = (len(bestandteile) >= 2
                   or (not cas and len(bestandteile) >= 1))
    if ist_gemisch:
        if not cas:
            anzahl = len(bestandteile)
            warnungen.append(_warnung('cas',
                f'Gemisch mit {anzahl} '
                + ('Bestandteil' if anzahl == 1 else 'Bestandteilen')
                + '. Die CAS-Nummer eines Bestandteils wurde nicht als '
                'Stoff-CAS übernommen.', 'hinweis'))
        quellen['bestandteile'] = {'abschnitt': '3', 'seite': _seite_von(
            bestandteile[0]['cas'], seiten), 'fundstelle': ', '.join(
            b['cas'] for b in bestandteile)}
    elif not bestandteile and not cas:
        warnungen.append(_warnung('cas',
            'Weder in Abschnitt 1 noch in Abschnitt 3 wurde eine CAS-Nummer '
            'gefunden.', 'hinweis'))

    werte = {
        'success': True,
        'name': name,
        'cas': cas,
        'eg': eg,
        'index_nummer': index,
        'gefahrenkategorien': kategorien,
        'signalwort': signalwort,
        'h_saetze': ', '.join(sorted(h_saetze)),
        'p_saetze': ', '.join(sorted(p_saetze)),
        'piktogramme': piktogramme,
        'sdb_datum': datum.strftime('%Y-%m-%d') if datum else '',
        'lagerklasse': lagerklasse,
        'ist_gemisch': ist_gemisch,
        'bestandteile': bestandteile,
        'warnungen': warnungen,
        'quellen': quellen,
    }
    return plausibilisiere(werte)


def _ohne_marker(code):
    """Anhang-VI-Codes tragen Fussnoten wie "H373 **" oder "Acute Tox. 3 *"."""
    return re.sub(r'\s*\*+\s*$', '', str(code)).strip()


def plausibilisiere(werte):
    """Die gelesenen Werte gegen Anhang VI der CLP pruefen.

    Die Gegenprobe ueberschreibt nichts stillschweigend: Sie ergaenzt nur, was
    leer ist, und meldet jeden Widerspruch. Fuer Reinstoffe ist Anhang VI die
    amtliche Einstufung; fuer Gemische gibt es dort keinen Eintrag, und das
    Fehlen ist kein Fehler.
    """
    warnungen = list(werte.get('warnungen') or [])
    quellen = dict(werte.get('quellen') or {})
    cas = werte.get('cas') or ''

    if not cas:
        werte['warnungen'] = warnungen
        werte['quellen'] = quellen
        return werte

    eintrag = echa_anhang_vi.eintrag(cas=cas)
    if not eintrag:
        if not werte.get('ist_gemisch'):
            werte['warnungen'] = warnungen
            werte['quellen'] = quellen
            warnungen.append(_warnung('cas',
                f'Die CAS-Nummer {cas} steht nicht in Anhang VI der CLP-Verordnung. '
                'Das ist bei selbsteingestuften Stoffen normal - die Einstufung '
                'stammt dann vom Hersteller. Bitte den Wert gegen das Original '
                'prüfen.', 'hinweis'))
        return werte

    soll_h = {_ohne_marker(h) for h in eintrag.get('h', [])}
    ist_h = {_ohne_marker(h) for h in
             (werte.get('h_saetze') or '').split(',') if h.strip()}
    ist_h = {h for h in ist_h if h.startswith('H') and not h.startswith('EUH')}
    fehlend = sorted(soll_h - ist_h)
    zusaetzlich = sorted(ist_h - soll_h)
    if fehlend:
        warnungen.append(_warnung('h_saetze',
            'Anhang VI nennt zusätzlich: ' + ', '.join(fehlend)
            + '. Bitte H-Sätze gegen das Original prüfen.', 'hinweis'))
    if zusaetzlich:
        warnungen.append(_warnung('h_saetze',
            'Im SDB stehen H-Sätze, die Anhang VI nicht nennt: '
            + ', '.join(zusaetzlich) + '.', 'hinweis'))

    soll_k = [_ohne_marker(k) for k in eintrag.get('k', [])]
    ist_k = list(werte.get('gefahrenkategorien') or [])
    if not ist_k and soll_k:
        werte['gefahrenkategorien'] = _eindeutig(soll_k)
        quellen['gefahrenkategorien'] = {
            'abschnitt': 'Anhang VI (CLP)', 'seite': None,
            'fundstelle': 'harmonisierte Einstufung zu ' + cas,
        }
        warnungen.append(_warnung('gefahrenkategorien',
            'Das SDB nannte keine Kategorie; eingesetzt aus Anhang VI: '
            + ', '.join(_eindeutig(soll_k)) + '.', 'hinweis'))
    elif ist_k and soll_k:
        fehlend_k = [k for k in _eindeutig(soll_k) if k not in ist_k]
        if fehlend_k:
            warnungen.append(_warnung('gefahrenkategorien',
                'Anhang VI nennt zusätzlich: ' + ', '.join(fehlend_k)
                + '. Bitte prüfen.', 'hinweis'))

    soll_s = eintrag.get('s') or ''
    if not werte.get('signalwort') and soll_s:
        werte['signalwort'] = soll_s

    werte['warnungen'] = warnungen
    werte['quellen'] = quellen
    return werte
