"""Tests für das Auslesen von Sicherheitsdatenblättern (`sdb_parser.py`).

Die Testtexte sind **nachgebaute** Datenblätter, keine Hersteller-PDFs: Sie
enthalten genau die Formatierungen, an denen der frühere Parser gescheitert
ist. Das Repo ist öffentlich, deshalb liegen hier keine fremden Dokumente -
echte Datenblätter prüft `werkzeuge/sdb_qualitaet.py` von Hand.

Abgesichert werden die vier Fehler, die an echten Datenblättern nachweisbar
waren:

* die Index-Nummer 606-001-00-8, deren Ende als CAS-Nummer gelesen wurde,
* deutsch ausgeschriebene Gefahrenklassen ohne CLP-Kürzel,
* Datumsangaben mit Monatsnamen ("20-Mai-2025"),
* und der stille Leererfolg bei einem PDF ohne Textebene.

Mit ausführen:
    ~/.venvs/gsv/bin/python -W ignore::ResourceWarning test_sdb_parser.py
"""
import json
import os
import sys
import unittest

REPO = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, REPO)

import sdb_parser


KOPF = """Sicherheitsdatenblatt
gemäß Verordnung (EG) Nr. 1907/2006 (REACH)
{name}
Überarbeitet am: {datum}
"""


def sdb(abschnitte=None, datum='18.09.2024', produkt='Aceton ROTISOLV® ≥99,9 %'):
    """Ein SDB-Text aus Abschnitten bauen. Der Kopf ist immer Seite 1."""
    text = KOPF.format(name=produkt, datum=datum)
    for nummer in sorted(abschnitte or {}):
        text += f'\nABSCHNITT {nummer}: Überschrift\n{abschnitte[nummer]}\n'
    return text


def standard_sdb(datum='18.09.2024'):
    return sdb(datum=datum, abschnitte={
        1: """1.1 Produktidentifikator
Aceton ROTISOLV® ≥99,9 %, LC-MS Grade
Artikelnummer 3153
Index-Nr. in CLP Anhang VI 606-001-00-8
EG-Nummer 200-662-2
CAS-Nummer 67-64-1
1.2 Relevante identifizierte Verwendungen
Laborchemikalie""",
        2: """2.1 Einstufung des Stoffs oder Gemischs
Entzündbare Flüssigkeiten 2 Flam. Liq. 2 H225
Schwere Augenschädigung/Augenreizung 2 Eye Irrit. 2 H319
Spezifische Zielorgan-Toxizität 3 STOT SE 3 H336
2.2 Kennzeichnungselemente
Signalwort Gefahr
Piktogramme
GHS02, GHS07
Gefahrenhinweise
H225 Flüssigkeit und Dampf leicht entzündbar
H319 Verursacht schwere Augenreizung
H336 Kann Schläfrigkeit verursachen
Ergänzende Gefahrenmerkmale
EUH066 Wiederholter Kontakt kann zu spröder Haut führen
Sicherheitshinweise
P210 Von Hitze fernhalten
P305+P351+P338 BEI KONTAKT MIT DEN AUGEN
2.3 Sonstige Gefahren""",
        3: """3.1 Stoffe
Stoffname Aceton
CAS-Nr. 67-64-1
EG-Nr. 200-662-2""",
        7: """7.1 Schutzmaßnahmen
Behälter geschlossen halten.
7.2 Bedingungen zur sicheren Lagerung
Lagerklasse (TRGS 510): 3""",
        8: '8.1 Begrenzung und Überwachung der Exposition',
    })


class TestAbschnitte(unittest.TestCase):

    def test_abschnitte_werden_getrennt(self):
        a = sdb_parser.zerlege(standard_sdb())
        self.assertIn('2.2 Kennzeichnungselemente', a[2])
        self.assertIn('7.2 Bedingungen', a[7])
        self.assertNotIn('Kennzeichnungselemente', a[1])

    def test_spaetere_zahl_ueberschreibt_abschnitt_nicht(self):
        """Ein Aufzählungspunkt "2." in Abschnitt 6 darf Abschnitt 2 nicht ersetzen.

        Am Roth-Datenblatt hat genau das den ganzen Abschnitt 2 mit dem Text
        einer Fußnote überschrieben.
        """
        text = standard_sdb()
        text = text.replace(
            'ABSCHNITT 7:',
            '6.9 Weitere Hinweise\n2. Behälter dicht verschlossen halten.\n'
            'ABSCHNITT 7:')
        a = sdb_parser.zerlege(text)
        self.assertIn('2.2 Kennzeichnungselemente', a[2])
        self.assertNotIn('dicht verschlossen', a[2])


class TestGrunddaten(unittest.TestCase):

    def setUp(self):
        self.ergebnis = sdb_parser.analysiere(standard_sdb().split('\n'))

    def test_index_nummer_wird_nicht_zur_cas(self):
        self.assertEqual(self.ergebnis['cas'], '67-64-1')
        self.assertEqual(self.ergebnis['index_nummer'], '606-001-00-8')

    def test_eg_nummer(self):
        self.assertEqual(self.ergebnis['eg'], '200-662-2')

    def test_name_ohne_beschriftung(self):
        self.assertEqual(self.ergebnis['name'], 'Aceton ROTISOLV® ≥99,9 %, LC-MS Grade')

    def test_name_nach_reiner_beschriftung(self):
        """Oehme schreibt "Handelsname/Bezeichnung:" und den Wert in der Zeile darunter."""
        text = sdb({
            1: '1.1 Produktidentifikator\nHandelsname/Bezeichnung:\n'
               'Allzweckreiniger EU\nArtikel-Nr.:\n228',
            2: '2.2 Kennzeichnungselemente\nSignalwort:Achtung\nH319\nP280',
            3: '3.2 Gemische\nEthanol 64-17-5',
            7: '7.2 Lagerung\nLagerklasse 3',
            8: '8.1 Exposition',
        })
        ergebnis = sdb_parser.analysiere([text])
        self.assertEqual(ergebnis['name'], 'Allzweckreiniger EU')

    def test_nur_index_ohne_cas_bleibt_leer(self):
        text = sdb({
            1: '1.1 Produktidentifikator\nTeststoff\nIndex-Nr. 606-001-00-8',
            2: '2.2 Kennzeichnungselemente\nSignalwort Gefahr',
            3: '3.1 Stoffe',
            7: '7.2 Lagerung\nLagerklasse 3',
            8: '8.1 Exposition',
        })
        ergebnis = sdb_parser.analysiere([text])
        self.assertEqual(ergebnis['cas'], '')

    def test_lagerklasse_nur_aus_der_liste(self):
        text = standard_sdb().replace('Lagerklasse (TRGS 510): 3',
                                      'Lagerklasse (TRGS 510): 99')
        ergebnis = sdb_parser.analysiere([text])
        self.assertEqual(ergebnis['lagerklasse'], '')

    def test_lagerklasse_ohne_klammern(self):
        """Manche Datenblätter schreiben "Lagerklasse TRGS 510: 3"."""
        text = standard_sdb().replace('Lagerklasse (TRGS 510): 3',
                                      'Lagerklasse TRGS 510: 3')
        ergebnis = sdb_parser.analysiere([text])
        self.assertEqual(ergebnis['lagerklasse'], '3')

    def test_lagerklasse_ausserhalb_von_7_2_wird_gemeldet(self):
        text = standard_sdb().replace('Lagerklasse (TRGS 510): 3', '')
        text += ('\nABSCHNITT 15: Rechtsvorschriften\n'
                 'Lagerklasse (TRGS 510): LGK 3 - entzündbare Flüssigkeiten\n')
        ergebnis = sdb_parser.analysiere([text])
        self.assertEqual(ergebnis['lagerklasse'], '3')
        warnungen = ' '.join(w['text'] for w in ergebnis['warnungen'])
        self.assertIn('Abschnitt 15', warnungen)


class TestGefahren(unittest.TestCase):

    def test_kategorien_aus_abkuerzungen(self):
        ergebnis = sdb_parser.analysiere([standard_sdb()])
        self.assertEqual(
            ergebnis['gefahrenkategorien'],
            ['Flam. Liq. 2', 'Eye Irrit. 2', 'STOT SE 3'])

    def test_kategorien_aus_deutschen_klassennamen(self):
        """Der Fall aus dem D-Tack-Datenblatt: keine CLP-Kürzel in 2.1."""
        text = sdb({
            1: '1.1 Produktidentifikator\nAceton\nCAS-Nr. 67-64-1',
            2: """2.1. Einstufung des Stoffs oder Gemischs
Entzündbare Flüssigkeiten Kategorie 2 - (H225)
Schwere Augenschädigung/Augenreizung Kategorie 2 - (H319)
Spezifische Zielorgan-Toxizität (einmalige Exposition) Kategorie 3 - (H336)
2.2. Kennzeichnungselemente
Signalwort: Gefahr
H225 - Flüssigkeit und Dampf leicht entzündbar.
H319 - Verursacht schwere Augenreizung.
H336 - Kann Schläfrigkeit verursachen.""",
            3: '3.1 Stoffe\nCAS-Nr. 67-64-1',
            7: '7.2 Lagerung\nLagerklasse 3',
            8: '8.1 Exposition',
        })
        ergebnis = sdb_parser.analysiere([text])
        self.assertEqual(
            ergebnis['gefahrenkategorien'],
            ['Flam. Liq. 2', 'Eye Irrit. 2', 'STOT SE 3'])

    def test_h_kombination_bleibt_zusammen(self):
        text = sdb({
            1: '1.1 Produktidentifikator\nTeststoff\nCAS-Nr. 630-08-0',
            2: '2.2 Kennzeichnungselemente\nSignalwort Gefahr\nH300 + H310\nP210',
            3: '3.1 Stoffe',
            7: '7.2 Lagerung\nLagerklasse 3',
            8: '8.1 Exposition',
        })
        ergebnis = sdb_parser.analysiere([text])
        self.assertIn('H300+H310', ergebnis['h_saetze'])

    def test_euh_wird_nicht_als_h_satz_gelesen(self):
        ergebnis = sdb_parser.analysiere([standard_sdb()])
        codes = {c.strip() for c in ergebnis['h_saetze'].split(',')}
        self.assertIn('EUH066', codes)
        self.assertNotIn('H066', codes)
        self.assertNotIn('H014', codes)

    def test_signalwort_nur_aus_abschnitt_2_2(self):
        """Ein "Achtung" irgendwo im Text darf das Signalwort nicht kippen."""
        text = standard_sdb().replace(
            '1.2 Relevante identifizierte Verwendungen',
            'Achtung: Nicht für private Zwecke.\n1.2 Relevante identifizierte Verwendungen')
        ergebnis = sdb_parser.analysiere([text])
        self.assertEqual(ergebnis['signalwort'], 'Gefahr')

    def test_signalwort_mit_clp_zusatz(self):
        """Planol schreibt "Signalwort (CLP) : Achtung"."""
        text = standard_sdb().replace('Signalwort Gefahr', 'Signalwort (CLP) : Gefahr')
        ergebnis = sdb_parser.analysiere([text])
        self.assertEqual(ergebnis['signalwort'], 'Gefahr')

    def test_kategorien_der_bestandteile_bleiben_draussen(self):
        """Die Einstufung in Abschnitt 3 gilt den Bestandteilen, nicht dem Produkt.

        Am Planol-Datenblatt kamen daraus vier Kategorien dazu, obwohl das
        Gemisch nur Eye Irrit. 2 ist.
        """
        text = sdb({
            1: '1.1 Produktidentifikator\nProduktname : Allzweckreiniger\nProduktform : Gemisch',
            2: """2.1. Einstufung des Stoffs oder Gemischs
Schwere Augenschädigung/Augenreizung, Kategorie 2 H319
2.2. Kennzeichnungselemente
Signalwort (CLP) : Achtung
H319 Verursacht schwere Augenreizung.
P280 Schutzhandschuhe tragen.""",
            3: '3.2 Gemische\nNatriumalkylbenzolsulfonat CAS-Nr.: 68411-30-3',
            7: '7.2 Lagerung\nLagerklasse (TRGS 510) : 12',
            8: '8.1 Exposition',
        })
        tabellen = [[['Natriumalkylbenzolsulfonat', 'CAS-Nr.: 68411-30-3',
                      'Acute Tox. 4 (Oral), H302 / Skin Irrit. 2, H315 / '
                      'Eye Dam. 1, H318 / Aquatic Chronic 3, H412']]]
        ergebnis = sdb_parser.analysiere([text], tabellen)
        self.assertEqual(ergebnis['gefahrenkategorien'], ['Eye Irrit. 2'])


class TestDatum(unittest.TestCase):

    def test_monatsname_mit_bindestrichen(self):
        ergebnis = sdb_parser.analysiere([standard_sdb(datum='20-Mai-2025')])
        self.assertEqual(ergebnis['sdb_datum'], '2025-05-20')

    def test_monatsname_mit_punkten(self):
        ergebnis = sdb_parser.analysiere([standard_sdb(datum='20. Mai 2025')])
        self.assertEqual(ergebnis['sdb_datum'], '2025-05-20')

    def test_englische_schreibweise(self):
        ergebnis = sdb_parser.analysiere([standard_sdb(datum='May 20, 2025')])
        self.assertEqual(ergebnis['sdb_datum'], '2025-05-20')

    def test_bearbeitungsdatum(self):
        """Oehme schreibt "Bearbeitungsdatum:20.01.2023" (ohne Leerzeichen)."""
        text = standard_sdb(datum='20.01.2023').replace(
            'Überarbeitet am: 20.01.2023', 'Bearbeitungsdatum:20.01.2023')
        ergebnis = sdb_parser.analysiere([text])
        self.assertEqual(ergebnis['sdb_datum'], '2023-01-20')

    def test_ausgabedatum(self):
        text = standard_sdb(datum='16.09.2025').replace(
            'Überarbeitet am: 16.09.2025', 'Ausgabedatum: 16.09.2025')
        ergebnis = sdb_parser.analysiere([text])
        self.assertEqual(ergebnis['sdb_datum'], '2025-09-16')

    def test_druckdatum_ist_kein_sdb_datum(self):
        """Ein Druckdatum darf ein altes Datenblatt nicht aktuell wirken lassen."""
        text = standard_sdb().replace('Überarbeitet am: 18.09.2024',
                                      'Druckdatum: 17.10.2026')
        ergebnis = sdb_parser.analysiere([text])
        self.assertEqual(ergebnis['sdb_datum'], '')
        self.assertIn('Druckdatum',
                      ' '.join(w['text'] for w in ergebnis['warnungen']))


class TestGemisch(unittest.TestCase):

    def test_bestandteile_werden_nicht_zur_stoff_cas(self):
        text = sdb({
            1: '1.1 Produktidentifikator\nReinigungsmittel XY\n1.2 Verwendungen',
            2: '2.2 Kennzeichnungselemente\nSignalwort Achtung\nH315\nP210',
            3: """3.2 Gemische
Ethanol 64-17-5 30-40 %
Wasser 7732-18-5 60-70 %""",
            7: '7.2 Lagerung\nLagerklasse 3',
            8: '8.1 Exposition',
        })
        ergebnis = sdb_parser.analysiere([text])
        self.assertEqual(ergebnis['cas'], '')
        self.assertTrue(ergebnis['ist_gemisch'])
        self.assertEqual({b['cas'] for b in ergebnis['bestandteile']},
                         {'64-17-5', '7732-18-5'})

    def test_ein_bestandteil_ohne_cas_in_abschnitt_1_ist_gemisch(self):
        text = sdb({
            1: '1.1 Produktidentifikator\nLösung XY\n1.2 Verwendungen',
            2: '2.2 Kennzeichnungselemente\nSignalwort Achtung\nH315\nP210',
            3: '3.2 Gemische\nEthanol 64-17-5 30-40 %',
            7: '7.2 Lagerung\nLagerklasse 3',
            8: '8.1 Exposition',
        })
        ergebnis = sdb_parser.analysiere([text])
        self.assertEqual(ergebnis['cas'], '')
        self.assertTrue(ergebnis['ist_gemisch'])


class TestScan(unittest.TestCase):

    def test_pdf_ohne_textebene_ist_ein_fehler(self):
        ergebnis = sdb_parser.analysiere(['', '   ', ''])
        self.assertFalse(ergebnis['success'])
        self.assertIn('Scan', ergebnis['error'])


class TestPlausibilisierung(unittest.TestCase):

    def test_leere_kategorien_werden_aus_anhang_vi_gefuellt(self):
        werte = {
            'cas': '67-64-1', 'h_saetze': 'H225, H319, H336',
            'gefahrenkategorien': [], 'signalwort': '', 'warnungen': [],
            'quellen': {}, 'ist_gemisch': False,
        }
        ergebnis = sdb_parser.plausibilisiere(werte)
        self.assertEqual(set(ergebnis['gefahrenkategorien']),
                         {'Flam. Liq. 2', 'Eye Irrit. 2', 'STOT SE 3'})
        self.assertEqual(ergebnis['signalwort'], 'Gefahr')

    def test_unbekannte_cas_wird_gemeldet(self):
        werte = {
            'cas': '001-00-8', 'h_saetze': '', 'gefahrenkategorien': [],
            'signalwort': '', 'warnungen': [], 'quellen': {},
            'ist_gemisch': False,
        }
        ergebnis = sdb_parser.plausibilisiere(werte)
        self.assertIn('nicht in Anhang VI',
                      ' '.join(w['text'] for w in ergebnis['warnungen']))

    def test_abweichende_h_saetze_werden_als_hinweis_gemeldet(self):
        werte = {
            'cas': '67-64-1', 'h_saetze': 'H225, H319, H336, H400',
            'gefahrenkategorien': ['Flam. Liq. 2'], 'signalwort': 'Gefahr',
            'warnungen': [], 'quellen': {}, 'ist_gemisch': False,
        }
        ergebnis = sdb_parser.plausibilisiere(werte)
        self.assertIn('H400',
                      ' '.join(w['text'] for w in ergebnis['warnungen']))


class TestTabellen(unittest.TestCase):

    def test_jeder_h_satz_hat_eine_kategorie(self):
        """Sonst bliebe ein H-Satz still ohne Kategorie - wie H360Fd vor dem Fix."""
        with open(os.path.join(REPO, 'static', 'hp_data.json'), encoding='utf-8') as f:
            codes = {e['code'] for e in json.load(f)['h_saetze']}
        fehlend = sorted(codes - set(sdb_parser._H_KATEGORIE))
        self.assertEqual(fehlend, [], f'Ohne Kategorie: {fehlend}')

    def test_alle_kategorien_sind_im_formular_bekannt(self):
        sdb_parser._lade_kategorien()
        bekannt = set(sdb_parser._KATEGORIEN)
        unbekannt = sorted({k for werte in sdb_parser._H_KATEGORIE.values()
                            for k in werte if k not in bekannt})
        self.assertEqual(unbekannt, [], f'Nicht in hp_data.json: {unbekannt}')


if __name__ == '__main__':
    unittest.main(verbosity=2)
