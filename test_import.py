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

    def test_mehrere_blaetter_mit_hinweis(self):
        daten = xlsx_bytes([['Name'], ['Aceton']])
        # Zweites Blatt ergänzen
        wb = load_workbook(io.BytesIO(daten))
        wb.create_sheet('Altlasten')
        puffer = io.BytesIO()
        wb.save(puffer)

        tabelle = imp.lies_datei(puffer.getvalue(), 'test.xlsx')
        self.assertTrue(any('Blatt' in h for h in tabelle.hinweise))

    def test_deckblatt_vor_der_tabelle_wird_uebersprungen(self):
        """Das Datenblatt muss nicht das erste sein (Nutzerbeispiel 18.11.2026)."""
        arbeitsmappe = Workbook()
        deckblatt = arbeitsmappe.active
        deckblatt.title = 'Deckblatt'
        deckblatt.append(['Gefahrstoffverzeichnis'])
        deckblatt.append(['Stand: November 2026'])
        blatt = arbeitsmappe.create_sheet('Verzeichnis')
        blatt.append(['Produkt', 'CAS-Nummer'])
        blatt.append(['Aceton', '67-64-1'])
        puffer = io.BytesIO()
        arbeitsmappe.save(puffer)

        tabelle = imp.lies_datei(puffer.getvalue(), 'test.xlsx')
        self.assertEqual(tabelle.kopf, ['Produkt', 'CAS-Nummer'])
        self.assertEqual(tabelle.zeilen, [['Aceton', '67-64-1']])
        self.assertTrue(any('Verzeichnis' in h for h in tabelle.hinweise))

    def test_fehlende_name_spalte_wird_aus_dem_inhalt_gedeutet(self):
        """Ohne Namen-Spalte wird die Datei gedeutet, nicht abgelehnt."""
        tabelle = tabelle_aus([['Artikelnummer', 'Preis'],
                               ['A-1', '5'],
                               ['A-2', '7']])
        zuordnung, unbekannt, _ = imp.erkenne_spalten(tabelle.kopf)
        zuordnung, hinweise = imp.ergaenze_aus_inhalt(tabelle, zuordnung)
        unbekannt, _ = imp.spalten_bericht(tabelle, zuordnung)

        self.assertEqual(zuordnung.get('name'), 0)
        self.assertTrue(any('Inhalts' in h for h in hinweise))
        self.assertEqual(unbekannt, ['Preis'])

    def test_datei_ohne_kopfzeile_wird_gelesen(self):
        """Eine reine Datenliste ohne Beschriftung ist kein Fehler mehr."""
        tabelle = tabelle_aus([
            ['Aceton', '67-64-1', '5'],
            ['Toluol', '108-88-3', '2'],
        ])
        zuordnung, _, _ = imp.erkenne_spalten(tabelle.kopf)
        zuordnung, _ = imp.ergaenze_aus_inhalt(tabelle, zuordnung)

        self.assertEqual(tabelle.kopf, [])
        self.assertEqual(zuordnung.get('name'), 0)
        self.assertEqual(zuordnung.get('cas_nummer'), 1)
        # Beide Zeilen sind Daten - die erste darf nicht als Kopfzeile gelten.
        self.assertEqual(len(tabelle.zeilen), 2)
        self.assertEqual(tabelle.erste_zeile, 1)

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


class TestFremdeStrukturen(unittest.TestCase):
    """Dateien, die dem eigenen Spaltenkatalog nicht folgen (18.11.2026).

    Vorlage ist die Gebindeliste des Nutzers: "Produkt" statt "Name", "Raum"
    statt "Lagerort", dazu CMR und "Aufgebraucht". Eine solche Datei wurde
    vorher vollständig abgelehnt.
    """

    KOPF = ['Gebinde-nummer', 'Produkt', 'Summenformel', 'Trivialname',
            'Cas-Nummer', 'Hersteller', 'Art. Nr.', 'Raum', 'Anmerkung',
            'Aufgebraucht', 'CMR']

    ZEILEN = [
        [1, 'Natriumhydroxid', 'NaOH', 'Ätznatron', '1310-73-2', 'EMSURE',
         '1.06498.0500', '205', '≥ 99%, p.a., ACS', 'nein', 'nein'],
        [2, 'Natriumhydroxid', 'NaOH', 'Ätznatron', '1310-73-2', 'Chemapol',
         '501420688', 'Gefahrenlager', 'k.A.', 'nein', 'nein'],
        [3, 'Borsäure', 'H3BO3', 'Borofax', '10043-35-3', 'Roth',
         '281307854', '205', '96%', 'nein', 'ja'],
        [4, 'Borsäure', 'H3BO3', 'Borofax', '10043-35-3', 'Germed DDR',
         'k.A.', '205', '0,1 mol', 'nein', 'ja'],
        [5, 'Aceton', 'C3H6O', 'Propanon', '67-64-1', 'Roth', '1.0001',
         '205', '', 'ja', 'nein'],
    ]

    def tabelle(self):
        return tabelle_aus([self.KOPF] + self.ZEILEN)

    def zeilen(self):
        tabelle = self.tabelle()
        zuordnung, _, _ = imp.erkenne_spalten(tabelle.kopf)
        return [imp.pruefe_zeile(roh, nummer) for nummer, roh
                in imp.zeilen_als_dicts(tabelle, zuordnung)]

    def test_spalten_werden_erkannt(self):
        tabelle = self.tabelle()
        zuordnung, unbekannt, _ = imp.erkenne_spalten(tabelle.kopf)

        self.assertEqual(tabelle.kopf[zuordnung['name']], 'Produkt')
        self.assertEqual(tabelle.kopf[zuordnung['cas_nummer']], 'Cas-Nummer')
        self.assertEqual(tabelle.kopf[zuordnung['lagerort']], 'Raum')
        self.assertEqual(tabelle.kopf[zuordnung['cmr']], 'CMR')
        self.assertEqual(tabelle.kopf[zuordnung['aufgebraucht']],
                         'Aufgebraucht')
        self.assertIn('Summenformel', unbekannt)
        self.assertIn('Hersteller', unbekannt)

    def test_zeilen_werden_gelesen(self):
        zeilen = self.zeilen()

        self.assertTrue(all(zeile.gueltig for zeile in zeilen))
        self.assertEqual(zeilen[0].werte['name'], 'Natriumhydroxid')
        self.assertEqual(zeilen[0].werte['lagerort'], '205')
        self.assertEqual(zeilen[2].werte['cmr'], True)
        self.assertEqual(zeilen[4].status, 'aufgebraucht')

    def test_gebinde_werden_zusammengefasst(self):
        """Borsäure steht zweimal im selben Raum - ein Eintrag, zwei Gebinde."""
        zeilen = self.zeilen()
        imp.markiere_duplikate(zeilen)

        self.assertEqual(zeilen[2].werte['anzahl_gebinde'], 2)
        self.assertEqual(zeilen[3].werte['zusammengefasst_in'], 4)
        # Natriumhydroxid steht in zwei Räumen - bleibt getrennt.
        self.assertNotIn('anzahl_gebinde', zeilen[0].werte)
        self.assertNotIn('anzahl_gebinde', zeilen[1].werte)

    def test_stichwort_im_kopf_genuegt(self):
        """Zusatzwörter in der Beschriftung dürfen den Treffer nicht kippen."""
        zuordnung, unbekannt, _ = imp.erkenne_spalten(
            ['Produktbezeichnung nach CLP', 'Raum-Nr.', 'Kostenstelle'])
        self.assertEqual(zuordnung.get('name'), 0)
        self.assertEqual(zuordnung.get('lagerort'), 1)
        self.assertEqual(unbekannt, ['Kostenstelle'])

    def test_widerspruechliches_stichwort_wird_nicht_geraten(self):
        """Trifft ein Wort zwei Felder, bleibt die Spalte unbestimmt."""
        zuordnung, unbekannt, _ = imp.erkenne_spalten(['Ort Menge'])
        self.assertNotIn('standort', zuordnung)
        self.assertNotIn('menge', zuordnung)
        self.assertIn('Ort Menge', unbekannt)


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

    def test_unlesbare_menge_ist_eine_warnung(self):
        """Seit 18.11.2026: Die Zeile bleibt importierbar, die Menge fehlt."""
        zeile = pruefe({'name': 'Aceton', 'menge': 'viel'})
        self.assertTrue(zeile.gueltig)
        self.assertIsNone(zeile.werte['menge'])
        self.assertTrue(any('keine Zahl' in w for w in zeile.warnungen))

    def test_negative_menge_wird_verworfen(self):
        zeile = pruefe({'name': 'Aceton', 'menge': '-1'})
        self.assertTrue(zeile.gueltig)
        self.assertIsNone(zeile.werte['menge'])
        self.assertTrue(any('negativ' in w for w in zeile.warnungen))

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

    def test_unbekanntes_piktogramm_ist_eine_warnung(self):
        """Es wird nicht übernommen, die Zeile bleibt aber importierbar."""
        zeile = pruefe({'name': 'Aceton', 'piktogramme': 'GHS10'})
        self.assertTrue(zeile.gueltig)
        self.assertIsNone(zeile.werte['piktogramme'])
        self.assertTrue(any('GHS01 bis GHS09' in w for w in zeile.warnungen))

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

    def test_zu_langer_name_wird_gekuerzt(self):
        zeile = pruefe({'name': 'x' * 101})
        self.assertTrue(zeile.gueltig)
        self.assertEqual(len(zeile.werte['name']), 100)
        self.assertTrue(any('gekürzt' in w for w in zeile.warnungen))

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

    def test_unbekannter_standort_ohne_ziel_ist_ein_fehler(self):
        # Ohne Ziel-Standort gibt es kein Auffangnetz: Die Zeile verlöre sonst
        # ihren Standort, ohne dass es jemand merkt.
        zeile = pruefe({'name': 'Aceton', 'standort': 'Keller'},
                       standort_aufloesen=self.aufloeser)
        self.assertFalse(zeile.gueltig)
        self.assertTrue(any('Ziel-Standort wählen' in f for f in zeile.fehler))

    def test_unbekannter_standort_mit_ziel_ist_eine_warnung(self):
        zeile = pruefe({'name': 'Aceton', 'standort': 'Keller'},
                       standort_aufloesen=self.aufloeser,
                       standard_standort_id=3,
                       standard_standort_name='Labor / Schrank 1')
        self.assertTrue(zeile.gueltig)
        self.assertEqual(zeile.werte['unterbereich_id'], 3)
        self.assertTrue(zeile.werte['standort_ersatz'])
        self.assertTrue(any('„Labor / Schrank 1“' in w
                            for w in zeile.warnungen))

    def test_eigener_standort_ist_kein_ersatz(self):
        zeile = pruefe({'name': 'Aceton', 'standort': 'Labor › Schrank 2'},
                       standort_aufloesen=self.aufloeser,
                       standard_standort_id=3,
                       standard_standort_name='Labor / Schrank 1')
        self.assertEqual(zeile.werte['unterbereich_id'], 7)
        self.assertFalse(zeile.werte['standort_ersatz'])

    def test_ersatz_standort_zaehlt_als_gleicher_standort(self):
        # Zwei Zeilen mit unbrauchbaren Standortangaben landen beide im
        # Ziel-Standort - dort sind sie Duplikate, nicht an ihren Wunschorten.
        zeilen = [
            pruefe({'name': 'Aceton', 'cas_nummer': '67-64-1',
                    'standort': 'Keller'},
                   standort_aufloesen=self.aufloeser,
                   standard_standort_id=3,
                   standard_standort_name='Labor / Schrank 1'),
            pruefe({'name': 'Aceton', 'cas_nummer': '67-64-1',
                    'standort': 'Dachboden'},
                   standort_aufloesen=self.aufloeser,
                   standard_standort_id=3,
                   standard_standort_name='Labor / Schrank 1'),
        ]
        self.assertEqual(imp.markiere_duplikate(zeilen), 1)


class TestDuplikate(unittest.TestCase):

    def test_gleiche_cas_wird_zusammengefasst(self):
        """Gebindelisten führen denselben Stoff mehrfach - kein Datenverlust."""
        zeilen = [
            pruefe({'name': 'Aceton', 'cas_nummer': '67-64-1'}),
            pruefe({'name': 'Aceton technisch', 'cas_nummer': '67-64-1'}),
        ]
        anzahl = imp.markiere_duplikate(zeilen)

        self.assertEqual(anzahl, 1)
        self.assertEqual(zeilen[0].werte['anzahl_gebinde'], 2)
        self.assertEqual(zeilen[0].werte['zusammengefasst_aus'], [2])
        self.assertEqual(zeilen[1].werte['zusammengefasst_in'], 2)
        self.assertEqual(zeilen[1].status, 'zusammengefasst')

    def test_mengen_gleicher_einheit_werden_addiert(self):
        zeilen = [
            pruefe({'name': 'Aceton', 'menge': '2', 'mengeneinheit': 'L'}),
            pruefe({'name': 'Aceton', 'menge': '3', 'mengeneinheit': 'L'}),
        ]
        imp.markiere_duplikate(zeilen)
        self.assertEqual(zeilen[0].werte['menge'], 5.0)
        self.assertEqual(zeilen[0].werte['mengeneinheit'], 'L')

    def test_mengen_verschiedener_einheit_werden_nicht_addiert(self):
        zeilen = [
            pruefe({'name': 'Aceton', 'menge': '2', 'mengeneinheit': 'L'}),
            pruefe({'name': 'Aceton', 'menge': '3', 'mengeneinheit': 'kg'}),
        ]
        imp.markiere_duplikate(zeilen)
        self.assertEqual(zeilen[0].werte['menge'], 2.0)
        self.assertTrue(any('nicht addiert' in w for w in zeilen[0].warnungen))

    def test_verschiedene_lagerorte_werden_nicht_zusammengefasst(self):
        """Raum 205 und Gefahrenlager sind zwei Behälterplätze."""
        zeilen = [
            pruefe({'name': 'Natriumhydroxid', 'cas_nummer': '1310-73-2',
                    'lagerort': '205'}),
            pruefe({'name': 'Natriumhydroxid', 'cas_nummer': '1310-73-2',
                    'lagerort': 'Gefahrenlager'}),
        ]
        self.assertEqual(imp.markiere_duplikate(zeilen), 0)

    def test_aufgebrauchte_zeilen_werden_nicht_zusammengefasst(self):
        zeilen = [
            pruefe({'name': 'Aceton'}),
            pruefe({'name': 'Aceton', 'aufgebraucht': 'ja'}),
        ]
        self.assertEqual(imp.markiere_duplikate(zeilen), 0)
        self.assertEqual(zeilen[1].status, 'aufgebraucht')

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
