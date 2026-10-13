"""Tests für die deutsche Namensabfrage bei Wikidata.

Die Abfrage steht in wikidata.py. Sie ist Beiwerk: liefert sie nichts, muss der
Autofill unveraendert weiterarbeiten. Diese Datei sichert ab, dass

* aus einer SPARQL-Antwort die richtigen Kandidaten werden,
* mehrere Zeilen zu einem Stoff nicht mehrfach erscheinen,
* der Treffer mit passender PubChem-Kennung vorn steht,
* und ein Netzfehler eine leere Liste ergibt statt einer Ausnahme.

Kein Test geht ins Netz - die reinen Teile sind von der Abfrage getrennt.

Mit ausführen:
    ~/.venvs/gsv/bin/python -W ignore::ResourceWarning test_wikidata.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import wikidata


def antwort(zeilen):
    """Baut eine SPARQL-Antwort in der Form, die der Endpunkt liefert."""
    return {'results': {'bindings': zeilen}}


def zeile(qid, name, cid=None):
    z = {
        'item': {'value': f'http://www.wikidata.org/entity/{qid}'},
        'name': {'value': name},
    }
    if cid is not None:
        z['cid'] = {'value': str(cid)}
    return z


class TestTrefferAusAntwort(unittest.TestCase):

    def test_ein_treffer(self):
        ergebnis = wikidata.treffer_aus_antwort(antwort([zeile('Q49546', 'Aceton', 180)]))
        self.assertEqual(ergebnis, [{'qid': 'Q49546', 'name': 'Aceton'}])

    def test_mehrere_zeilen_zu_einem_stoff_ergeben_einen_kandidaten(self):
        """Wikidata liefert je P662-Wert eine Zeile - der Stoff bleibt einer."""
        ergebnis = wikidata.treffer_aus_antwort(antwort([
            zeile('Q211086', 'Chlorwasserstoff', 313),
            zeile('Q211086', 'Chlorwasserstoff', 18348331),
        ]))
        self.assertEqual(ergebnis, [{'qid': 'Q211086', 'name': 'Chlorwasserstoff'}])

    def test_passende_pubchem_kennung_steht_vorn(self):
        """Der Salzsaeure-Fall: Gas und Loesung, beide richtig."""
        ergebnis = wikidata.treffer_aus_antwort(antwort([
            zeile('Q2409', 'Salzsäure'),
            zeile('Q211086', 'Chlorwasserstoff', 313),
        ]), cid=313)
        self.assertEqual([e['name'] for e in ergebnis],
                         ['Chlorwasserstoff', 'Salzsäure'])

    def test_ohne_passende_kennung_bleibt_es_alphabetisch(self):
        ergebnis = wikidata.treffer_aus_antwort(antwort([
            zeile('Q2409', 'Salzsäure'),
            zeile('Q211086', 'Chlorwasserstoff'),
        ]), cid=999999)
        self.assertEqual([e['name'] for e in ergebnis],
                         ['Chlorwasserstoff', 'Salzsäure'])

    def test_zeilen_ohne_namen_werden_uebersprungen(self):
        ergebnis = wikidata.treffer_aus_antwort(antwort([
            zeile('Q1', '   ', 5),
            {'item': {'value': 'http://www.wikidata.org/entity/Q2'},
             'name': {'value': 'Ethanol'}},
        ]))
        self.assertEqual(ergebnis, [{'qid': 'Q2', 'name': 'Ethanol'}])

    def test_leere_oder_kaputte_antwort(self):
        for eingabe in (None, {}, {'results': {}}, {'results': {'bindings': []}},
                        {'etwas': 'anderes'}):
            self.assertEqual(wikidata.treffer_aus_antwort(eingabe), [])


class TestNamenZuCas(unittest.TestCase):

    def test_leere_cas_fragt_nicht_ab(self):
        self.assertEqual(wikidata.namen_zu_cas(''), [])
        self.assertEqual(wikidata.namen_zu_cas('   '), [])
        self.assertEqual(wikidata.namen_zu_cas(None), [])

    def test_netzfehler_ergibt_leere_liste(self):
        """Der Autofill darf an der Namensabfrage nicht scheitern.

        Der Endpunkt wird auf eine geschlossene Adresse umgebogen: der
        Verbindungsversuch scheitert sofort, es geht nichts ins Netz.
        """
        original = wikidata.ENDPUNKT
        wikidata.ENDPUNKT = 'http://127.0.0.1:9/sparql'
        try:
            self.assertEqual(wikidata.namen_zu_cas('67-64-1'), [])
        finally:
            wikidata.ENDPUNKT = original


if __name__ == '__main__':
    unittest.main(verbosity=2)
