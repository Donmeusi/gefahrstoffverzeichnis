"""Tests für die Piktogramm- und Signalwort-Ableitung aus den H-Sätzen.

Die Tabelle steht in piktogramme.py und stammt aus Anhang I/V der CLP-VO. Diese
Datei sichert ab, dass

* die Tabelle jeden H-Satz kennt, den die Anwendung anbietet (hp_data.json) —
  eine Lücke würde sonst stillschweigend zu „kein Piktogramm",
* die Ableitung die Regeln einhält (Piktogramme vereinigt, strengstes
  Signalwort, Code ohne Piktogramm ist ein gültiges Ergebnis),
* Kombinationssätze zusammenbleiben und nicht in Einzelcodes zerfallen,
* die Schreibweise beachtet wird (H360Fd ≠ H360FD, H361fd ≠ H361FD),
* und aus EUH-Sätzen keine Phantom-H-Codes werden.

Mit ausführen:
    ~/.venvs/gsv/bin/python -W ignore::ResourceWarning test_piktogramme.py
"""
import json
import os
import sys
import unittest

REPO = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, REPO)

import piktogramme


def hp_codes():
    with open(os.path.join(REPO, 'static', 'hp_data.json'), encoding='utf-8') as f:
        return {e['code'] for e in json.load(f)['h_saetze']}


class TestTabelle(unittest.TestCase):

    def test_kennt_jeden_angbotenen_h_satz(self):
        """Jeder H-Satz aus hp_data.json muss zugeordnet sein."""
        fehlend = sorted(hp_codes() - set(piktogramme.ZUORDNUNG))
        self.assertEqual(fehlend, [],
                         f'Ohne Zuordnung: {fehlend} - sie laegen still bei '
                         '"kein Piktogramm"')

    def test_hat_keine_ueberzaehligen_codes(self):
        """Und die Tabelle soll nichts enthalten, was die App nicht anbietet."""
        ueberzaehlig = sorted(set(piktogramme.ZUORDNUNG) - hp_codes())
        self.assertEqual(ueberzaehlig, [])

    def test_keine_offenen_faelle(self):
        self.assertEqual(piktogramme.UNSICHER, [])

    def test_werte_sind_plausibel(self):
        for code, eintrag in piktogramme.ZUORDNUNG.items():
            self.assertIn(eintrag['signalwort'], (None, 'Achtung', 'Gefahr'), code)
            for pikto in eintrag['piktogramme']:
                self.assertRegex(pikto, r'^GHS0[1-9]$', code)


class TestAbleitung(unittest.TestCase):

    def test_aceton(self):
        """Entzündbare Flüssigkeit Kat. 2 und Augenschädigung."""
        self.assertEqual(piktogramme.piktogramme_fuer('H225, H319, H336'),
                         ['GHS02', 'GHS07'])
        self.assertEqual(piktogramme.signalwort_fuer('H225, H319, H336'), 'Gefahr')

    def test_natriumhydroxid(self):
        self.assertEqual(piktogramme.piktogramme_fuer('H290, H314'), ['GHS05'])
        self.assertEqual(piktogramme.signalwort_fuer('H290, H314'), 'Gefahr')

    def test_code_ohne_piktogramm_ist_gueltig(self):
        """H412 (Gewässer Chronisch 3) trägt nach CLP kein Piktogramm."""
        self.assertEqual(piktogramme.piktogramme_fuer('H412'), [])
        self.assertEqual(piktogramme.signalwort_fuer('H412'), None)

    def test_piktogramme_werden_vereinigt(self):
        ergebnis = piktogramme.piktogramme_fuer('H225, H314, H400')
        self.assertEqual(ergebnis, ['GHS02', 'GHS05', 'GHS09'])

    def test_strengstes_signalwort_gewinnt(self):
        """Eine Mischung aus Gefahr und Achtung ergibt Gefahr."""
        self.assertEqual(piktogramme.signalwort_fuer('H302'), 'Achtung')
        self.assertEqual(piktogramme.signalwort_fuer('H319'), 'Achtung')
        self.assertEqual(piktogramme.signalwort_fuer('H302, H319'), 'Achtung')
        self.assertEqual(piktogramme.signalwort_fuer('H302, H314'), 'Gefahr')

    def test_ohne_verwertbare_angabe_kommt_nichts(self):
        for eingabe in ('', None, '   ', 'keine Angabe', 'H999'):
            self.assertEqual(piktogramme.piktogramme_fuer(eingabe), [])
            self.assertEqual(piktogramme.signalwort_fuer(eingabe), None)


class TestCodesAusText(unittest.TestCase):

    def test_kombinationssatz_bleibt_zusammen(self):
        """H300+H310 ist ein eigener Code, keine zwei."""
        self.assertEqual(piktogramme.codes_aus_text('H300+H310'), ['H300+H310'])
        self.assertEqual(piktogramme.piktogramme_fuer('H300+H310'), ['GHS06'])

    def test_kombinationssatz_mit_leerzeichen(self):
        self.assertEqual(piktogramme.codes_aus_text('H300 + H310 + H330'),
                         ['H300+H310+H330'])

    def test_schreibweise_ist_bedeutungstragend(self):
        """H360Fd und H360FD sind verschiedene Codes - nicht zusammenwerfen."""
        self.assertIn('H360Fd', piktogramme.ZUORDNUNG)
        self.assertIn('H360FD', piktogramme.ZUORDNUNG)
        self.assertEqual(piktogramme.codes_aus_text('H360Fd'), ['H360Fd'])
        self.assertEqual(piktogramme.codes_aus_text('H360FD'), ['H360FD'])
        # H361fd ist die amtliche Schreibweise, H361FD gibt es nicht.
        self.assertEqual(piktogramme.codes_aus_text('H361fd'), ['H361fd'])
        self.assertEqual(piktogramme.unbekannte_codes('H361FD'), ['H361FD'])

    def test_euh_saetze_erzeugen_keine_phantom_codes(self):
        """Aus EUH014 darf kein H014 werden."""
        self.assertEqual(piktogramme.codes_aus_text('EUH014'), [])
        self.assertEqual(piktogramme.codes_aus_text('EUH014, H314'), ['H314'])
        self.assertEqual(piktogramme.unbekannte_codes('EUH208, EUH066'), [])

    def test_trenner_werden_vertragen(self):
        for text in ('H225, H319', 'H225,H319', 'H225; H319', 'H225 H319',
                     'H225 / H319'):
            self.assertEqual(piktogramme.codes_aus_text(text), ['H225', 'H319'], text)

    def test_kleinbuchstabiges_h_wird_erkannt(self):
        self.assertEqual(piktogramme.codes_aus_text('h314'), ['H314'])

    def test_kleinbuchstabiges_h_auch_im_kombinationssatz(self):
        """Ein Kombinationssatz hat mehrere führende H - jedes muss passen."""
        self.assertEqual(piktogramme.codes_aus_text('h300+H310'), ['H300+H310'])
        self.assertEqual(piktogramme.codes_aus_text('H300+h310'), ['H300+H310'])
        self.assertEqual(piktogramme.piktogramme_fuer('h300+h310'), ['GHS06'])

    def test_doppelte_werden_zusammengefasst(self):
        self.assertEqual(piktogramme.codes_aus_text('H314, H314'), ['H314'])

    def test_unbekannte_werden_gemeldet_nicht_verschluckt(self):
        self.assertEqual(piktogramme.unbekannte_codes('H314, H999'), ['H999'])

    def test_liste_wird_wie_text_behandelt(self):
        """Der SDB-Parser sammelt die Codes als Liste."""
        self.assertEqual(piktogramme.codes_aus_text(['H225', 'H319']),
                         ['H225', 'H319'])
        self.assertEqual(piktogramme.piktogramme_fuer(['H225', 'H319']),
                         ['GHS02', 'GHS07'])
        self.assertEqual(piktogramme.signalwort_fuer(['H302', 'H314']), 'Gefahr')

    def test_h241_traegt_zwei_piktogramme(self):
        """Der alte if/elif im SDB-Parser lieferte je Code nur eines."""
        self.assertEqual(piktogramme.piktogramme_fuer('H241'), ['GHS01', 'GHS02'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
