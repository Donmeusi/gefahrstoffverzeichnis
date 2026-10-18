#!/usr/bin/env python3
"""Messt den SDB-Parser an echten Datenblaettern.

Wozu: Die Testtexte in `test_sdb_parser.py` sind nachgebaute Formatierungen.
Ob der Parser mit den Eigenheiten echter Hersteller zurechtkommt, zeigt erst
eine Sammlung echter PDFs. Dieses Werkzeug liest sie mit derselben
Seiten- und Tabellenlogik wie `/api/parse_sdb` und stellt die Felder neben die
Fundstellen und Warnungen.

Aufruf:
    ~/.venvs/gsv/bin/python werkzeuge/sdb_qualitaet.py <pdf|ordner> [...]
    ~/.venvs/gsv/bin/python werkzeuge/sdb_qualitaet.py <ordner> --json
    ~/.venvs/gsv/bin/python werkzeuge/sdb_qualitaet.py <ordner> --erwartet erwartet.json

`--erwartet` prueft gegen eine Soll-Datei:

    {
      "aceton_roth.pdf": {
        "name": "Aceton ROTISOLV® ≥99,9 %, LC-MS Grade",
        "cas": "67-64-1",
        "eg": "200-662-2",
        "signalwort": "Gefahr",
        "sdb_datum": "2024-09-18",
        "lagerklasse": "3",
        "gefahrenkategorien": ["Flam. Liq. 2", "Eye Irrit. 2", "STOT SE 3"]
      }
    }

Verglichen werden nur die genannten Felder; Listen als Menge, Text exakt.
Der Exit-Code ist 1, wenn ein Sollwert nicht getroffen wird.

Die Datenblaetter selbst gehoeren nicht ins Repository (fremde Dokumente,
oeffentliches Repo) - dieses Werkzeug liest sie aus einem beliebigen Ordner.
"""
import argparse
import json
import os
import sys

import pdfplumber

sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
import sdb_parser


def lies_pdf(pfad):
    """Seitentexte und Tabellen wie in `/api/parse_sdb` holen."""
    seiten, tabellen = [], []
    with pdfplumber.open(pfad) as pdf:
        for nummer, page in enumerate(pdf.pages[:15]):
            text = page.extract_text() or ''
            seiten.append(text)
            if (nummer < 6 and len(tabellen) < 12
                    and any(k in text.lower() for k in (
                        'einstufung', 'zusammensetzung', 'classification',
                        'composition'))):
                try:
                    tabellen.extend(page.extract_tables() or [])
                except Exception:
                    pass
    return seiten, tabellen


def pdf_pfade(argumente):
    for argument in argumente:
        if os.path.isdir(argument):
            for name in sorted(os.listdir(argument)):
                if name.lower().endswith('.pdf'):
                    yield os.path.join(argument, name)
        elif argument.lower().endswith('.pdf'):
            yield argument


def vergleiche(ergebnis, soll):
    """Feldweise Vergleich. Gibt (treffer, fehler) zurueck."""
    treffer, fehler = [], []
    for feld, wert in soll.items():
        ist = ergebnis.get(feld)
        if isinstance(wert, list) and isinstance(ist, list):
            ok = {str(x) for x in wert} == {str(x) for x in ist}
        else:
            ok = (ist or '') == (wert or '')
        (treffer if ok else fehler).append(
            feld if ok else f'{feld}: erwartet {wert!r}, gelesen {ist!r}')
    return treffer, fehler


def zeige(pfad, ergebnis):
    print(f'\n=== {os.path.basename(pfad)} ===')
    if not ergebnis.get('success'):
        print('  FEHLER:', ergebnis.get('error'))
        return
    for feld in ('name', 'cas', 'eg', 'signalwort', 'h_saetze', 'p_saetze',
                 'sdb_datum', 'lagerklasse', 'piktogramme',
                 'gefahrenkategorien', 'ist_gemisch'):
        wert = ergebnis.get(feld)
        if isinstance(wert, list):
            wert = '; '.join(wert)
        print(f'  {feld:20} {wert}')

    quellen = ergebnis.get('quellen') or {}
    if quellen:
        print('  Fundstellen:')
        for feld, quelle in quellen.items():
            teile = []
            if quelle.get('abschnitt'):
                teile.append('Abschnitt ' + str(quelle['abschnitt']))
            if quelle.get('seite'):
                teile.append('Seite ' + str(quelle['seite']))
            print(f'    {feld:20} {" · ".join(teile) or "-"}')

    warnungen = ergebnis.get('warnungen') or []
    if warnungen:
        print('  Warnungen:')
        for warnung in warnungen:
            print(f'    [{warnung.get("schwere", "hinweis")}] {warnung.get("text")}')


def main():
    zerleger = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    zerleger.add_argument('pfade', nargs='+', help='PDF-Datei oder Ordner')
    zerleger.add_argument('--json', action='store_true',
                          help='Ergebnis als JSON statt als Text')
    zerleger.add_argument('--erwartet', metavar='DATEI',
                          help='JSON mit Sollwerten je Dateiname')
    args = zerleger.parse_args()

    sollwerte = {}
    if args.erwartet:
        with open(args.erwartet, encoding='utf-8') as f:
            sollwerte = json.load(f)

    alle = {}
    for pfad in pdf_pfade(args.pfade):
        try:
            seiten, tabellen = lies_pdf(pfad)
            alle[os.path.basename(pfad)] = sdb_parser.analysiere(seiten, tabellen)
        except Exception as e:
            alle[os.path.basename(pfad)] = {'success': False,
                                            'error': f'{type(e).__name__}: {e}'}

    if args.json:
        print(json.dumps(alle, ensure_ascii=False, indent=2))
    else:
        for name, ergebnis in alle.items():
            zeige(name, ergebnis)

    if not sollwerte:
        return 0

    print('\n=== Soll-Ist-Vergleich ===')
    gesamt_treffer = gesamt_fehler = 0
    for name, soll in sollwerte.items():
        ergebnis = alle.get(name)
        if ergebnis is None:
            print(f'  {name}: nicht gefunden')
            gesamt_fehler += len(soll)
            continue
        treffer, fehler = vergleiche(ergebnis, soll)
        gesamt_treffer += len(treffer)
        gesamt_fehler += len(fehler)
        print(f'  {name}: {len(treffer)}/{len(treffer) + len(fehler)}')
        for eintrag in fehler:
            print('    -', eintrag)

    gesamt = gesamt_treffer + gesamt_fehler
    quote = (100 * gesamt_treffer / gesamt) if gesamt else 0
    print(f'\n  Gesamt: {gesamt_treffer}/{gesamt} Felder ({quote:.0f} %)')
    return 0 if gesamt_fehler == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
