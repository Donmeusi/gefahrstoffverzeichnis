#!/usr/bin/env python3
"""Baut aus der ECHA-Tabelle die Zuordnung CAS-Nummer -> harmonisierte Einstufung.

Erzeugt `echa_anhang_vi.json` im Projektverzeichnis, das `echa_anhang_vi.py`
zur Laufzeit liest. Dieses Skript laeuft nur beim Aktualisieren, nicht im
Betrieb - die Anwendung braucht kein Netz und kein Excel.

Bezugsquelle: ECHA, "Table of harmonised entries in Annex VI to CLP"
  https://echa.europa.eu/information-on-chemicals/annex-vi-to-clp
Die Datei liegt hinter einer Azure-WAF, die eine JavaScript-Pruefung verlangt;
mit curl kommt man nicht durch (HTTP 403). Im Browser laedt sie sich normal.
Der Dateiname enthaelt die ATP-Version, z. B. annex_vi_clp_table_atp23_en.xlsx.

⚠️ **Die Datei enthaelt auch noch nicht geltendes Recht.** Sie deckt alle
Aenderungsverordnungen bis zur genannten ATP ab, und die Spalte "In application"
nennt je Eintrag das Datum des Geltungsbeginns. ATP23 gilt erst ab 01.02.2027;
wer die rohe Tabelle uebernimmt, stuft Stoffe nach einer Verordnung ein, die
noch nicht in Kraft ist. Dieses Skript waehlt deshalb je Index-Nummer die
**letzte Fassung, deren Geltungsbeginn nicht in der Zukunft liegt** - dafuer
dient das Blatt "History", das alle Vorgaengerfassungen enthaelt.

Aufruf:
    ~/.venvs/gsv/bin/python werkzeuge/echa_import.py <pfad-zur-xlsx> [--stichtag JJJJ-MM-TT]

Ohne Stichtag gilt der heutige Tag. Zum Nachvollziehen laesst sich ein
vergangener oder kuenftiger Stichtag angeben.
"""
import argparse
import datetime
import json
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZIELDATEI = os.path.join(REPO, 'echa_anhang_vi.json')

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'

# Spalten der Datei (Reihenfolge laut Kopfzeile in Zeile 2)
SP_INDEX, SP_ATP, SP_NAME, SP_EG, SP_CAS = 0, 1, 3, 4, 5
SP_KLASSEN, SP_H, SP_KENNZEICHEN, SP_KENNZ_H, SP_KENNZ_EUH = 6, 7, 8, 9, 10
SP_GELTEND = 14          # "In application" - Geltungsbeginn des Eintrags


# ─── XLSX lesen (Standardbibliothek) ────────────────────────────────────────
# Bewusst ohne openpyxl: das ist eine Einmal-Abhaengigkeit fuer ein Werkzeug,
# das selten laeuft. Ein xlsx ist ein ZIP mit XML darin.

def blaetter(pfad):
    """Name -> Pfad im Archiv, fuer jedes Tabellenblatt."""
    with zipfile.ZipFile(pfad) as z:
        rels = {r.get('Id'): r.get('Target')
                for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels')).iter()
                if r.get('Id')}
        aus = {}
        for s in ET.fromstring(z.read('xl/workbook.xml')).iter(NS + 'sheet'):
            kennung = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
            aus[s.get('name')] = 'xl/' + rels[s.get(kennung)].lstrip('/')
        return aus


def gemeinsame_texte(z):
    try:
        wurzel = ET.fromstring(z.read('xl/sharedStrings.xml'))
    except KeyError:
        return []
    return [''.join(t.text or '' for t in si.iter(NS + 't'))
            for si in wurzel.iter(NS + 'si')]


def zeilen(pfad, blatt):
    """Gibt je Zeile die Liste der Zellwerte zurueck (leere Zellen als '')."""
    with zipfile.ZipFile(pfad) as z:
        texte = gemeinsame_texte(z)
        wurzel = ET.fromstring(z.read(blaetter(pfad)[blatt]))
        for row in wurzel.iter(NS + 'row'):
            werte = []
            for c in row.iter(NS + 'c'):
                v = c.find(NS + 'v')
                if c.get('t') == 's' and v is not None:
                    werte.append(texte[int(v.text)])
                elif c.get('t') == 'inlineStr':
                    werte.append(''.join(t.text or '' for t in c.iter(NS + 't')))
                else:
                    werte.append(v.text if v is not None else '')
            yield werte


def als_datum(wert):
    """Excel-Zahl oder Text in ein Datum wandeln."""
    if wert is None or wert == '':
        return None
    try:
        return datetime.date(1899, 12, 30) + datetime.timedelta(days=int(float(wert)))
    except (TypeError, ValueError):
        pass
    for muster in ('%Y-%m-%d', '%d.%m.%Y', '%Y/%m/%d'):
        try:
            return datetime.datetime.strptime(str(wert).strip(), muster).date()
        except ValueError:
            continue
    return None


# ─── Inhalt aufbereiten ──────────────────────────────────────────────────────

def liste(mehrzeilig):
    """Zerlegt eine Zelle mit 'H314\\nH331' in eine Liste."""
    if not mehrzeilig:
        return []
    teile = [t.strip() for t in re.split(r'[\n,;]+', mehrzeilig)]
    return [t for t in teile if t]


def signalwort(kennzeichen_zelle):
    """Das Signalwort steckt als 'Dgr'/'Wng' in der Kennzeichnungszelle."""
    for teil in liste(kennzeichen_zelle):
        if teil.lower() in ('dgr', 'danger'):
            return 'Gefahr'
        if teil.lower() in ('wng', 'warning'):
            return 'Achtung'
    return ''


def piktogramme(kennzeichen_zelle):
    """Die Piktogramm-Codes stehen in derselben Zelle wie das Signalwort."""
    return sorted({t.upper() for t in liste(kennzeichen_zelle)
                   if re.fullmatch(r'GHS0[1-9]', t.strip(), re.IGNORECASE)})


def geltungsbeginn_je_atp(pfad, blatt):
    """Welche Aenderungsverordnung gilt ab wann? (Spalte 'In application')"""
    grenzen = {}
    for w in zeilen(pfad, blatt):
        if len(w) <= SP_INDEX or not w[SP_INDEX] or w[SP_INDEX] == 'Index No':
            continue
        if len(w) <= SP_GELTEND:
            continue
        datum = als_datum(w[SP_GELTEND])
        if datum:
            grenzen.setdefault(atp_normalisieren(w[SP_ATP]), set()).add(datum)
    # Je ATP das frueheste genannte Datum; ATP14 nennt zwei (Nachtrag).
    return {atp: min(daten) for atp, daten in grenzen.items() if daten}


def atp_normalisieren(atp):
    """'ATP05upd01' -> 'ATP05'.

    Die Datei kennt neben den ATPs auch Nachträge ("upd"). Sie tragen keinen
    eigenen Geltungsbeginn und gehören zur jeweiligen ATP; ohne diese Zeile
    fielen ihre Einträge still aus der Tabelle.
    """
    return re.sub(r'upd\d*$', '', atp or '', flags=re.IGNORECASE)


def bauen(pfad, stichtag):
    alle = blaetter(pfad)
    # Das aktuelle Blatt traegt die ATP-Version im Namen (z. B. "ATP23").
    aktuell = next((b for b in alle if b != 'History'), list(alle)[0])
    grenzen = geltungsbeginn_je_atp(pfad, aktuell)
    rang = {atp: i for i, atp in enumerate(sorted(grenzen, key=lambda a: grenzen[a]))}

    bestand, verworfen = {}, Counter()
    for w in zeilen(pfad, 'History'):
        if len(w) <= SP_CAS or not w[SP_INDEX] or w[SP_INDEX] == 'Index No':
            continue
        atp = atp_normalisieren(w[SP_ATP])
        if atp not in rang:
            verworfen['unbekannte ATP ' + str(atp)] += 1
            continue
        if grenzen[atp] > stichtag:
            verworfen[f'{atp} (ab {grenzen[atp]})'] += 1
            continue
        vorher = bestand.get(w[SP_INDEX])
        if not vorher or rang[atp] > rang[vorher[0]]:
            bestand[w[SP_INDEX]] = (atp, w)

    eintraege, ohne_schluessel, mehrfach = {}, 0, 0
    for index, (atp, w) in bestand.items():
        daten = {
            'h': liste(w[SP_H]),
            'g': piktogramme(w[SP_KENNZEICHEN]),
            's': signalwort(w[SP_KENNZEICHEN]),
            'k': liste(w[SP_KLASSEN]),
            'n': (w[SP_NAME] or '').strip(),
            'x': index,
            'a': atp,
        }
        # ⚠️ Die CAS-Spalte enthaelt bei Mehrstoff-Eintraegen mehrere Nummern
        # ("131929-60-7 [2]\n131929-63-0 [3]") oder gar keine ("- [1]\n- [2]").
        # Wuerde man die Zelle als Ganzes als Schluessel nehmen, waeren 163
        # Eintraege unter einem Kuerzel wie "- [1]" abgelegt und nicht
        # auffindbar. Deshalb jede Nummer einzeln herausziehen.
        cas_liste = re.findall(r'\b\d{2,7}-\d{2}-\d\b', w[SP_CAS] or '')
        eg_liste = re.findall(r'\b\d{3}-\d{3}-\d\b', w[SP_EG] or '')
        schluessel = cas_liste or eg_liste
        if not schluessel:
            ohne_schluessel += 1
            continue
        if len(schluessel) > 1:
            mehrfach += 1
        for s_ in schluessel:
            eintraege.setdefault(s_, daten)
    return eintraege, grenzen, verworfen, ohne_schluessel, mehrfach


def main():
    s = argparse.ArgumentParser(description=__doc__)
    s.add_argument('xlsx', help='Pfad zur ECHA-Exceldatei')
    s.add_argument('--stichtag', help='JJJJ-MM-TT (Vorgabe: heute)')
    a = s.parse_args()

    if not os.path.exists(a.xlsx):
        raise SystemExit(f'Datei nicht gefunden: {a.xlsx}')
    stichtag = (datetime.datetime.strptime(a.stichtag, '%Y-%m-%d').date()
                if a.stichtag else datetime.date.today())

    eintraege, grenzen, verworfen, ohne, mehrfach = bauen(a.xlsx, stichtag)

    inhalte = {
        'quelle': 'ECHA, Table of harmonised entries in Annex VI to CLP',
        'quelldatei': os.path.basename(a.xlsx),
        'erzeugt': datetime.date.today().isoformat(),
        'stichtag': stichtag.isoformat(),
        'geltendes_recht': sorted((a_ for a_ in grenzen if grenzen[a_] <= stichtag),
                                  key=lambda x: grenzen[x])[-1],
        'nicht_enthalten': sorted({f'{a_} ab {d}' for a_, d in grenzen.items() if d > stichtag}),
        'eintraege': eintraege,
    }
    with open(ZIELDATEI, 'w', encoding='utf-8') as f:
        json.dump(inhalte, f, ensure_ascii=False, separators=(',', ':'), sort_keys=True)
        f.write('\n')

    groesse = os.path.getsize(ZIELDATEI)
    print(f'Stichtag {stichtag}, geltendes Recht: {inhalte["geltendes_recht"]}')
    print(f'nicht enthalten (noch nicht in Kraft): {inhalte["nicht_enthalten"]}')
    print(f'Eintraege: {len(eintraege)}  ({groesse / 1024:.0f} KB -> {ZIELDATEI})')
    if ohne:
        print(f'ohne CAS- und EG-Nummer (uebersprungen): {ohne}')
    if mehrfach:
        print(f'Eintraege mit mehreren CAS-Nummern: {mehrfach} (unter jeder Nummer auffindbar)')
    if verworfen:
        print('verworfene Zeilen:')
        for k, n in sorted(verworfen.items()):
            print(f'   {k}: {n}')



if __name__ == '__main__':
    main()
