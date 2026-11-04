"""Tests für den Excel-/CSV-Import (import_gefahrstoffe.py).

Die Datei prüft die drei Schritte getrennt: Datei lesen (Encoding,
Trennzeichen, Kopfzeilensuche), Spalten erkennen (Aliase, Umlaute) und Zeilen
prüfen (Menge, Datum, Piktogramme aus H-Sätzen, Standort, Duplikate).

Die Regeln sind aus add() übernommen; weicht der Import dort ab, ist ein
Gefahrstoff nach dem Import anders eingestuft als nach dem Anlegen von Hand.

Mit ausführen:
    ~/.venvs/gsv/bin/python -m unittest test_import -v
"""
import datetime as dt
import io
import os
import sys
import unittest

from openpyxl import Workbook, load_workbook

REPO = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, REPO)

import import_gefahrstoffe as imp


def csv_bytes(text, kodierung='utf-8-sig'):
    return text.encode(kodierung)


def xlsx_bytes(zeilen, blattname='Gefahrstoffe'):
    """Baut eine Arbeitsmappe aus einer Liste von Zeilen (Liste von Listen)."""
    arbeitsmappe = Workbook()
    blatt = arbeitsmappe.active
    blatt.title = blattname
    for zeile in zeilen:
        blatt.append(zeile)
    ausgabe = io.BytesIO()
    arbeitsmappe.save(ausgabe)
    return ausgabe.getvalue()


def tabelle_aus(zeilen, dateiname='test.xlsx'):
    daten = xlsx_bytes(zeilen)
    return imp.lies_datei(daten, dateiname)


def pruefe(roh, **kwargs):
    return imp.pruefe_zeile(roh, 2, **kwargs)


class TestSpalten(unittest.TestCase):

    def test_erkennt_deutsche_beschriftungen(self):
        kopf = ['Name', 'CAS-Nummer', 'H-Sätze', 'Menge', 'Einheit',
                'Bereich', 'Unterbereich', 'SDB-Datum',
                'Einstufung & Gefahren']
        zuordnung, unbekannt, doppelt = imp.erkenne_spalten(kopf)

        self.assertEqual(unbekannt, [])
        self.assertEqual(doppelt, [])
        self.assertEqual(zuordnung['name'], 0)
        self.assertEqual(zuordnung['cas_nummer'], 1)
        self.assertEqual(zuordnung['h_saetze'], 2)
        self.assertEqual(zuordnung['menge'], 3)
        self.assertEqual(zuordnung['mengeneinheit'], 4)
        self.assertEqual(zuordnung['bereich'], 5)
        self.assertEqual(zuordnung['unterbereich'], 6)
        self.assertEqual(zuordnung['sdb_datum'], 7)
        self.assertEqual(zuordnung['gefahrenkategorien'], 8)

    def test_umlaute_und_schreibweisen_sind_gleich(self):
        """H-Sätze, H-Saetze und h saetze müssen dasselbe Feld treffen."""
        for beschriftung in ('H-Sätze', 'H-Saetze', 'h saetze', 'H SÄTZE'):
            zuordnung, _, _ = imp.erkenne_spalten(['Name', beschriftung])
            self.assertEqual(zuordnung.get('h_saetze'), 1, beschriftung)

    def test_unbekannte_spalte_wird_gemeldet_nicht_abgelehnt(self):
        zuordnung, unbekannt, _ = imp.erkenne_spalten(
            ['Name', 'Kostenstelle'])
        self.assertEqual(zuordnung['name'], 0)
        self.assertEqual(unbekannt, ['Kostenstelle'])

    def test_doppelte_spalte_erste_gewinnt(self):
        zuordnung, _, doppelt = imp.erkenne_spalten(
            ['Name', 'Stoffname'])
        self.assertEqual(zuordnung['name'], 0)
        self.assertEqual(doppelt, ['Stoffname'])


class TestLesen(unittest.TestCase):

    def test_csv_semikolon_cp1252(self):
        """So schreibt deutsches Excel: Semikolon, cp1252, Umlaute."""
        text = ('Name;CAS-Nummer;H-Sätze;Menge\n'
                'Salzsäure;7647-01-0;"H314, H335";1,5\n')
        tabelle = imp.lies_datei(csv_bytes(text, 'cp1252'), 'liste.csv')

        self.assertEqual(tabelle.kopf[0], 'Name')
        self.assertEqual(tabelle.zeilen[0][0], 'Salzsäure')
        self.assertTrue(any('CP1252' in h for h in tabelle.hinweise))

    def test_csv_komma_utf8_mit_bom(self):
        text = 'Name,CAS-Nummer\nAceton,67-64-1\n'
        tabelle = imp.lies_datei(csv_bytes(text), 'liste.csv')

        self.assertEqual(tabelle.zeilen[0], ['Aceton', '67-64-1'])
        self.assertFalse(any('CP1252' in h for h in tabelle.hinweise))

    def test_csv_mit_tab(self):
        text = 'Name\tCAS-Nummer\nAceton\t67-64-1\n'
        tabelle = imp.lies_datei(csv_bytes(text), 'liste.csv')
        self.assertEqual(tabelle.zeilen[0], ['Aceton', '67-64-1'])

    def test_excel_mit_titelzeile(self):
        """Eine Titelzeile vor der Tabelle darf den Import nicht stören."""
        tabelle = tabelle_aus([
            ['Gefahrstoffverzeichnis 2026'],
            [],
            ['Name', 'CAS-Nummer'],
            ['Aceton', '67-64-1'],
        ])
        self.assertEqual(tabelle.kopf, ['Name', 'CAS-Nummer'])
        self.assertEqual(tabelle.zeilen, [['Aceton', '67-64-1']])
        # Titel (1), Leerzeile (2), Kopf (3) -> erste Datenzeile ist 4.
        self.assertEqual(tabelle.erste_zeile, 4)

    def test_leerzeilen_in_der_mitte_zaehlen_als_zeile(self):
        tabelle = tabelle_aus([
            ['Name'],
            ['Aceton'],
            [],
            ['Toluol'],
        ])
        paare = imp.zeilen_als_dicts(tabelle, {'name': 0})
        self.assertEqual([nummer for nummer, _ in paare], [2, 4])

    def test_nur_erstes_blatt_mit_hinweis(self):
        daten = xlsx_bytes([['Name'], ['Aceton']])
        # Zweites Blatt ergänzen
        wb = load_workbook(io.BytesIO(daten))
        wb.create_sheet('Altlasten')
        puffer = io.BytesIO()
        wb.save(puffer)

        tabelle = imp.lies_datei(puffer.getvalue(), 'test.xlsx')
        self.assertTrue(any('Blatt' in h for h in tabelle.hinweise))

    def test_fehlende_name_spalte_ist_ein_fehler(self):
        with self.assertRaises(imp.ImportFehler) as kontext:
            tabelle_aus([['Artikelnummer', 'Preis'], ['A-1', '5']])
        self.assertIn('Kopfzeile', str(kontext.exception))

    def test_alte_xls_datei_wird_abgelehnt(self):
        with self.assertRaises(imp.ImportFehler) as kontext:
            imp.lies_datei(b'\xd0\xcf\x11\xe0' + b'0' * 100, 'alt.xls')
        self.assertIn('.xlsx', str(kontext.exception))

    def test_umbenanntes_pdf_ist_keine_arbeitsmappe(self):
        with self.assertRaises(imp.ImportFehler):
            imp.lies_datei(b'%PDF-1.7\n', 'liste.xlsx')

    def test_leere_datei(self):
        with self.assertRaises(imp.ImportFehler):
            imp.lies_datei(b'', 'liste.csv')

    def test_zu_grosse_datei(self):
        with self.assertRaises(imp.ImportFehler) as kontext:
            imp.lies_datei(b'x' * (imp.MAX_BYTES + 1), 'liste.csv')
        self.assertIn('MB', str(kontext.exception))


class TestWerte(unittest.TestCase):

    def test_menge_mit_einheit_in_einer_zelle(self):
        zeile = pruefe({'name': 'Aceton', 'menge': '4,5 kg'})
        self.assertEqual(zeile.werte['menge'], 4.5)
        self.assertEqual(zeile.werte['mengeneinheit'], 'kg')

    def test_menge_mit_tausenderpunkt(self):
        zeile = pruefe({'name': 'Aceton', 'menge': '1.234,5 l'})
        self.assertEqual(zeile.werte['menge'], 1234.5)
        self.assertEqual(zeile.werte['mengeneinheit'], 'L')

    def test_menge_ohne_einheit_warnt(self):
        zeile = pruefe({'name': 'Aceton', 'menge': '5'})
        self.assertEqual(zeile.werte['menge'], 5.0)
        self.assertTrue(any('ohne Einheit' in w for w in zeile.warnungen))

    def test_unlesbare_menge_ist_ein_fehler(self):
        zeile = pruefe({'name': 'Aceton', 'menge': 'viel'})
        self.assertFalse(zeile.gueltig)
        self.assertTrue(any('keine Zahl' in f for f in zeile.fehler))

    def test_negative_menge_ist_ein_fehler(self):
        zeile = pruefe({'name': 'Aceton', 'menge': '-1'})
        self.assertFalse(zeile.gueltig)

    def test_einheit_aus_spalte_gewinnt(self):
        zeile = pruefe({'name': 'Aceton', 'menge': '4,5 kg',
                        'mengeneinheit': 'L'})
        self.assertEqual(zeile.werte['mengeneinheit'], 'L')
        self.assertTrue(any('weicht' in w for w in zeile.warnungen))

    def test_unbekannte_einheit_wird_uebernommen(self):
        zeile = pruefe({'name': 'Aceton', 'menge': '5', 'mengeneinheit': 'm³'})
        self.assertEqual(zeile.werte['mengeneinheit'], 'm³')
        self.assertTrue(any('Unbekannte Mengeneinheit' in w
                            for w in zeile.warnungen))

    def test_datum_deutsch_und_iso(self):
        for wert in ('31.01.2024', '2024-01-31', dt.date(2024, 1, 31),
                     dt.datetime(2024, 1, 31, 8, 15)):
            zeile = pruefe({'name': 'Aceton', 'sdb_datum': wert})
            self.assertEqual(zeile.werte['sdb_datum'], dt.date(2024, 1, 31),
                             f'{wert!r}')

    def test_excel_serienzahl_wird_zum_datum(self):
        # 45321 ist der 30.01.2024 im 1899-Kalender.
        zeile = pruefe({'name': 'Aceton', 'sdb_datum': 45321})
        self.assertEqual(zeile.werte['sdb_datum'], dt.date(2024, 1, 30))

    def test_unlesbares_datum_ist_nur_eine_warnung(self):
        zeile = pruefe({'name': 'Aceton', 'sdb_datum': 'irgendwann'})
        self.assertTrue(zeile.gueltig)
        self.assertIsNone(zeile.werte['sdb_datum'])
        self.assertTrue(any('kein lesbares Datum' in w
                            for w in zeile.warnungen))

    def test_piktogramme_und_signalwort_aus_h_saetzen(self):
        zeile = pruefe({'name': 'Aceton', 'h_saetze': 'H225, H319, H336'})
        self.assertEqual(zeile.werte['piktogramme'], 'GHS02,GHS07')
        self.assertEqual(zeile.werte['signalwort'], 'Gefahr')
        self.assertTrue(any('abgeleitet' in w for w in zeile.warnungen))

    def test_h_satz_ohne_piktogramm_bleibt_leer(self):
        # H362 (Laktation) trägt nach CLP weder Piktogramm noch Signalwort.
        zeile = pruefe({'name': 'Stoff', 'h_saetze': 'H362'})
        self.assertIsNone(zeile.werte['piktogramme'])
        self.assertIsNone(zeile.werte['signalwort'])

    def test_explizite_piktogramme_werden_normalisiert(self):
        zeile = pruefe({'name': 'Aceton',
                        'piktogramme': 'GHS 08; ghs-07'})
        self.assertEqual(zeile.werte['piktogramme'], 'GHS07,GHS08')

    def test_unbekanntes_piktogramm_ist_ein_fehler(self):
        zeile = pruefe({'name': 'Aceton', 'piktogramme': 'GHS10'})
        self.assertFalse(zeile.gueltig)
        self.assertTrue(any('GHS01 bis GHS09' in f for f in zeile.fehler))

    def test_signalwort_wird_normalisiert(self):
        zeile = pruefe({'name': 'Aceton', 'signalwort': 'achtung!'})
        self.assertEqual(zeile.werte['signalwort'], 'Achtung')

    def test_unbekannter_h_satz_warnt(self):
        zeile = pruefe({'name': 'Stoff', 'h_saetze': 'H999'})
        self.assertTrue(zeile.gueltig)
        self.assertTrue(any('H999' in w for w in zeile.warnungen))

    def test_substitution_ja_nimmt_ersatzstoff(self):
        zeile = pruefe({'name': 'Aceton', 'substitutionspruefung': 'Ja',
                        'ersatzstoff': 'Ethanol', 'begruendung': 'zu teuer'})
        self.assertEqual(zeile.werte['ersatzstoff'], 'Ethanol')
        self.assertIsNone(zeile.werte['begruendung'])

    def test_substitution_nein_nimmt_begruendung(self):
        zeile = pruefe({'name': 'Aceton', 'substitutionspruefung': 'nein',
                        'ersatzstoff': 'Ethanol', 'begruendung': 'kein Ersatz'})
        self.assertIsNone(zeile.werte['ersatzstoff'])
        self.assertEqual(zeile.werte['begruendung'], 'kein Ersatz')

    def test_ja_ohne_ersatzstoff_warnt(self):
        zeile = pruefe({'name': 'Aceton', 'substitutionspruefung': 'ja'})
        self.assertTrue(any('kein Ersatzstoff' in w for w in zeile.warnungen))

    def test_lange_werte_werden_gekuerzt(self):
        zeile = pruefe({'name': 'Aceton', 'gefahrenkategorien': 'x' * 600})
        self.assertEqual(len(zeile.werte['gefahrenkategorien']), 500)
        self.assertTrue(any('gekürzt' in w for w in zeile.warnungen))

    def test_zu_langer_name_ist_ein_fehler(self):
        zeile = pruefe({'name': 'x' * 101})
        self.assertFalse(zeile.gueltig)

    def test_cas_format_warnt(self):
        zeile = pruefe({'name': 'Aceton', 'cas_nummer': '67641'})
        self.assertTrue(any('Format' in w for w in zeile.warnungen))

    def test_unbekannte_lagerklasse_warnt(self):
        zeile = pruefe({'name': 'Aceton', 'lagerklasse': '99'})
        self.assertTrue(any('TRGS-510' in w for w in zeile.warnungen))


class TestStandort(unittest.TestCase):

    def aufloeser(self, text):
        if text == 'Labor › Schrank 2':
            return 7, None
        return None, f'Standort „{text}“ wurde nicht gefunden.'

    def test_standortspalte_hat_vorrang(self):
        zeile = pruefe({'name': 'Aceton', 'standort': 'Labor › Schrank 2'},
                       standort_aufloesen=self.aufloeser,
                       standard_standort_id=3)
        self.assertEqual(zeile.werte['unterbereich_id'], 7)

    def test_bereich_und_unterbereich_werden_zusammengesetzt(self):
        gesehen = {}

        def aufloeser(text):
            gesehen['text'] = text
            return 7, None

        zeile = pruefe({'name': 'Aceton', 'bereich': 'Labor',
                        'unterbereich': 'Schrank 2'},
                       standort_aufloesen=aufloeser)
        self.assertEqual(gesehen['text'], 'Labor › Schrank 2')
        self.assertEqual(zeile.werte['unterbereich_id'], 7)

    def test_ohne_angabe_gilt_der_standard(self):
        zeile = pruefe({'name': 'Aceton'},
                       standort_aufloesen=self.aufloeser,
                       standard_standort_id=3)
        self.assertEqual(zeile.werte['unterbereich_id'], 3)
        self.assertEqual(zeile.standort_text, '')

    def test_unbekannter_standort_ist_ein_fehler(self):
        zeile = pruefe({'name': 'Aceton', 'standort': 'Keller'},
                       standort_aufloesen=self.aufloeser)
        self.assertFalse(zeile.gueltig)


class TestDuplikate(unittest.TestCase):

    def test_gleiche_cas_wird_markiert(self):
        zeilen = [
            pruefe({'name': 'Aceton', 'cas_nummer': '67-64-1'}),
            pruefe({'name': 'Aceton technisch', 'cas_nummer': '67-64-1'}),
        ]
        anzahl = imp.markiere_duplikate(zeilen)

        self.assertEqual(anzahl, 1)
        self.assertNotIn('duplikat_von', zeilen[0].werte)
        self.assertEqual(zeilen[1].werte['duplikat_von'], 2)
        self.assertEqual(zeilen[1].status, 'duplikat')

    def test_gleicher_stoff_an_zwei_standorten_ist_kein_duplikat(self):
        """Derselbe Stoff in zwei Bereichen ist im Verzeichnis zulässig."""
        zeilen = [
            pruefe({'name': 'Aceton', 'cas_nummer': '67-64-1'},
                   standard_standort_id=1),
            pruefe({'name': 'Aceton', 'cas_nummer': '67-64-1'},
                   standard_standort_id=2),
        ]
        anzahl = imp.markiere_duplikate(zeilen)

        self.assertEqual(anzahl, 0)

    def test_ohne_cas_zaehlt_name_und_standort(self):
        zeilen = [
            pruefe({'name': 'Aceton'}, standard_standort_id=1),
            pruefe({'name': 'aceton'}, standard_standort_id=2),
        ]
        anzahl = imp.markiere_duplikate(zeilen)

        self.assertEqual(anzahl, 0)

    def test_fehlzeilen_zaehlen_nicht_als_duplikat(self):
        zeilen = [pruefe({'name': ''}), pruefe({'name': ''})]
        self.assertEqual(imp.markiere_duplikate(zeilen), 0)


class TestVorlage(unittest.TestCase):

    def test_vorlage_laesst_sich_wieder_lesen(self):
        daten = imp.vorlage_xlsx()
        arbeitsmappe = load_workbook(io.BytesIO(daten))
        blatt = arbeitsmappe['Gefahrstoffe']
        kopf = [zelle.value for zelle in blatt[1]]

        self.assertEqual(kopf[0], 'Name')
        self.assertIn('CAS-Nummer', kopf)
        self.assertIn('H-Sätze', kopf)
        self.assertIn('Unterbereich', kopf)
        self.assertNotIn('Standort (Bereich › Unterbereich)', kopf)
        self.assertIn('Hinweise', arbeitsmappe.sheetnames)

        # Die Kopfzeile der Vorlage muss der eigene Import erkennen.
        zuordnung, unbekannt, _ = imp.erkenne_spalten(kopf)
        self.assertEqual(unbekannt, [])
        self.assertIn('name', zuordnung)
        self.assertIn('sdb_datum', zuordnung)
        self.assertIn('unterbereich', zuordnung)


if __name__ == '__main__':
    unittest.main()
