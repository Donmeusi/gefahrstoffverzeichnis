"""Tests für die amtliche Einstufung aus Anhang VI der CLP-Verordnung.

Die Tabelle steht in echa_anhang_vi.json (erzeugt von werkzeuge/echa_import.py).
Diese Datei sichert ab, dass

* die Datei vorhanden, lesbar und plausibel groß ist,
* **kein Eintrag aus einer noch nicht geltenden Änderungsverordnung stammt**
  (die ECHA-Datei deckt auch künftiges Recht ab — ATP23 gilt erst ab 01.02.2027),
* bekannte Stoffe die amtliche Einstufung liefern,
* Stoffe, die nicht in Anhang VI stehen, sauber None ergeben (der Normalfall
  bei selbsteingestuften Stoffen),
* Mehrstoff-Einträge unter jeder ihrer CAS-Nummern auffindbar sind,
* und die Feldwerte die Formate des Formulars treffen.

Mit ausführen:
    ~/.venvs/gsv/bin/python -W ignore::ResourceWarning test_echa_anhang_vi.py
"""
import json
import os
import re
import sys
import unittest

REPO = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, REPO)

import echa_anhang_vi


class TestBestand(unittest.TestCase):

    def test_datei_ist_vorhanden_und_gefuellt(self):
        self.assertTrue(os.path.exists(echa_anhang_vi.DATEI),
                        'echa_anhang_vi.json fehlt — '
                        'werkzeuge/echa_import.py erzeugt sie')
        self.assertGreater(echa_anhang_vi.anzahl(), 3000)

    def test_kein_eintrag_aus_nicht_geltendem_recht(self):
        """⚠️ Der wichtigste Test: nichts aus einer künftigen ATP.

        Die ECHA-Datei führt alle Änderungsverordnungen bis zur genannten ATP
        mit. ATP23 gilt erst ab 01.02.2027; würde sie mitgelesen, stufte die
        Anwendung Stoffe nach einer Verordnung ein, die noch nicht in Kraft ist.
        """
        nicht_in_kraft = {t.split(' ')[0] for t in echa_anhang_vi.stand()['nicht_enthalten']}
        benutzt = {e['a'] for e in echa_anhang_vi.bestand()['eintraege'].values()}
        self.assertEqual(benutzt & nicht_in_kraft, set(),
                         f'Einträge aus nicht geltender Fassung: {benutzt & nicht_in_kraft}')

    def test_stand_ist_dokumentiert(self):
        stand = echa_anhang_vi.stand()
        for feld in ('quelle', 'stichtag', 'geltendes_recht'):
            self.assertTrue(stand[feld], f'{feld} fehlt')


class TestNachschlagen(unittest.TestCase):

    def test_acetone(self):
        e = echa_anhang_vi.eintrag(cas='67-64-1')
        self.assertIsNotNone(e)
        self.assertIn('H225', e['h'])
        self.assertIn('H336', e['h'])
        self.assertNotIn('H350', e['h'])
        # Amtliche Kennzeichnung: entzündbar und Reizwirkung, kein GHS08.
        self.assertEqual(e['g'], ['GHS02', 'GHS07'])
        self.assertEqual(e['s'], 'Gefahr')

    def test_natriumhydroxid(self):
        e = echa_anhang_vi.eintrag(cas='1310-73-2')
        self.assertEqual(e['h'], ['H314'])
        self.assertEqual(e['g'], ['GHS05'])

    def test_chlorwasserstoff_traegt_ghs04(self):
        """Das Piktogramm folgt aus der Gefahrenklasse, nicht aus dem H-Satz.

        Chlorwasserstoff ist "Press. Gas" — daher GHS04, zu dem es in der
        Einstufungszeile gar keinen H-Satz gibt. Aus H331 und H314 allein lässt
        sich GHS04 nicht herleiten; genau darum geht es bei dieser Quelle.
        """
        e = echa_anhang_vi.eintrag(cas='7647-01-0')
        self.assertIn('GHS04', e['g'])
        self.assertIn('Press. Gas', e['k'])

    def test_stoff_ohne_cas_ueber_die_eg_nummer(self):
        """Salzsäure … % hat einen eigenen Eintrag ohne CAS-Nummer."""
        e = echa_anhang_vi.eintrag(eg='231-595-7')
        self.assertIsNotNone(e)
        self.assertIn('acid', e['n'])
        self.assertEqual(e['x'], '017-002-01-X')

    def test_nicht_enthalten_ergibt_none(self):
        """Nicht in Anhang VI heißt: selbsteingestuft — kein Fehler."""
        self.assertIsNone(echa_anhang_vi.eintrag(cas='7732-18-5'))   # Wasser
        self.assertIsNone(echa_anhang_vi.eintrag(cas='0000-00-0'))
        self.assertIsNone(echa_anhang_vi.eintrag())

    def test_leerzeichen_stoeren_nicht(self):
        self.assertIsNotNone(echa_anhang_vi.eintrag(cas='  67-64-1 '))

    def test_mehrstoff_eintrag_unter_jeder_nummer(self):
        """Die CAS-Spalte nennt bei solchen Einträgen mehrere Nummern."""
        for cas in ('131929-60-7', '131929-63-0'):
            e = echa_anhang_vi.eintrag(cas=cas)
            self.assertIsNotNone(e, cas)
            self.assertEqual(e['x'], '603-209-00-0')


class TestFormularwerte(unittest.TestCase):

    def test_formate_treffen_die_des_formulars(self):
        """H-Sätze mit Komma, Gefahrenkategorien mit Semikolon."""
        werte = echa_anhang_vi.formularwerte(echa_anhang_vi.eintrag(cas='67-64-1'))
        self.assertEqual(werte['h_saetze'], 'H225, H336, H319')
        self.assertNotIn(',', werte['gefahrenkategorien'])
        self.assertIn(';', werte['gefahrenkategorien'])
        self.assertEqual(werte['signalwort'], 'Gefahr')
        self.assertIsInstance(werte['piktogramme'], list)

    def test_mehrere_h_saetze_bleiben_getrennt(self):
        werte = echa_anhang_vi.formularwerte(echa_anhang_vi.eintrag(cas='50-00-0'))
        self.assertIn('H350', werte['h_saetze'])
        self.assertIn('H317', werte['h_saetze'])


class TestFehlendeDatei(unittest.TestCase):

    def test_fehlt_die_datei_arbeitet_die_anwendung_weiter(self):
        """Die Tabelle ist Zusatzquelle — ihr Fehlen darf nichts umwerfen."""
        original = echa_anhang_vi.DATEI
        vorher = echa_anhang_vi._bestand
        echa_anhang_vi.DATEI = os.path.join(REPO, 'gibt-es-nicht.json')
        echa_anhang_vi._bestand = None
        try:
            self.assertEqual(echa_anhang_vi.anzahl(), 0)
            self.assertIsNone(echa_anhang_vi.eintrag(cas='67-64-1'))
            self.assertEqual(echa_anhang_vi.stand()['quelle'], '')
        finally:
            echa_anhang_vi.DATEI = original
            echa_anhang_vi._bestand = vorher


if __name__ == '__main__':
    unittest.main(verbosity=2)
