"""Statische Prüfung der Skripte auf DOM-XSS-Flächen.

Die Prüfung aus Abschnitt 8 des Sicherheitsberichts hat zwölf Stellen gefunden,
die HTML in das Dokument schreiben (innerHTML/outerHTML). Elf davon setzen
konstante Zeichenketten, leeren den Knoten oder schreiben das eigene Markup
eines Knopfes zurück. Eine setzte Werte ein: in `hp_modal.js` wurde der
H-Satz-Katalog per Template in innerHTML gebaut.

Diese Datei hält die Klasse der Lücke zu: Kein innerHTML/outerHTML mit
eingesetzten Werten, und keine der Ausführungsflächen, die man in diesem
Projekt nicht braucht.

Mit ausführen:
    ~/.venvs/gsv/bin/python -m unittest test_dom_xss -v
"""
import os
import re
import unittest

REPO = os.path.dirname(os.path.abspath(__file__))
SKRIPTE = os.path.join(REPO, 'static')

# Zuweisungen an innerHTML/outerHTML, mehrzeilig, bis zum Semikolon.
ZUWEISUNG = re.compile(r'\.(innerHTML|outerHTML)\s*=\s*(.+?);', re.S)

# Flächen, die Code aus Daten ausführen würden. Im Projekt gibt es keine.
AUSFUEHRUNG = [
    (r'\beval\s*\(', 'eval()'),
    (r'\bnew\s+Function\s*\(', 'new Function()'),
    (r'document\.write\s*\(', 'document.write()'),
    (r'\.insertAdjacentHTML\s*\(', 'insertAdjacentHTML()'),
]


def skriptdateien():
    for name in sorted(os.listdir(SKRIPTE)):
        if name.endswith('.js') and not name.endswith('.min.js'):
            yield name, os.path.join(SKRIPTE, name)


class TestDomXss(unittest.TestCase):

    def test_kein_innerhtml_mit_eingesetzten_werten(self):
        """Konstantes Markup ist in Ordnung, interpolierte Werte nicht."""
        treffer = []
        for name, pfad in skriptdateien():
            with open(pfad, encoding='utf-8') as f:
                quelle = f.read()
            for match in ZUWEISUNG.finditer(quelle):
                rumpf = match.group(2)
                if '${' in rumpf:
                    zeile = quelle[:match.start()].count('\n') + 1
                    treffer.append(f'{name}:{zeile}: {rumpf.strip()[:80]}')
        self.assertEqual(treffer, [], 'innerHTML mit eingesetzten Werten:\n'
                         + '\n'.join(treffer))

    def test_keine_dynamische_ausfuehrung(self):
        treffer = []
        for name, pfad in skriptdateien():
            with open(pfad, encoding='utf-8') as f:
                quelle = f.read()
            for muster, beschriftung in AUSFUEHRUNG:
                for match in re.finditer(muster, quelle):
                    zeile = quelle[:match.start()].count('\n') + 1
                    treffer.append(f'{name}:{zeile}: {beschriftung}')
        self.assertEqual(treffer, [], 'Dynamische Ausführung gefunden:\n'
                         + '\n'.join(treffer))

    def test_datenschreibende_skripte_nutzen_textcontent(self):
        """Die drei Stellen, die fremde Daten anzeigen, bleiben bei textContent.

        Das sind die Namen aus Wikidata (`autofill.js`), die Dateinamen aus dem
        PDF-Upload (`sdb_import.js`) und der H-Satz-Katalog (`hp_modal.js`) -
        die einzigen Skripte, die Werte von aussen in das Dokument bringen.
        """
        for name in ('autofill.js', 'sdb_import.js', 'hp_modal.js'):
            with open(os.path.join(SKRIPTE, name), encoding='utf-8') as f:
                quelle = f.read()
            self.assertIn('textContent', quelle,
                          f'{name} sollte fremde Werte über textContent setzen')


if __name__ == '__main__':
    unittest.main()
