"""Tests für die Mengenschwellen-Prüfung nach TRGS 510.

Die Regel steht in mengenschwellen.py (Tabelle SCHWELLEN, Zuordnung über
H-Sätze, ersatzweise Lagerklasse). Diese Datei sichert ab, dass

* die Kleinmengen je Gruppe richtig erkannt und summiert werden,
* die Bezugsebene der Lagerabschnitt ist (Unterbereich) und nicht der Stoff,
* Mengen ohne Massenbezug (Stück, fehlende Menge) die Summe nicht verfälschen,
* und die Seite /mengenschwellen zeigt, was zu tun ist.

Mit ausführen:
    ~/.venvs/gsv/bin/python -W ignore::ResourceWarning test_mengenschwellen.py
"""
import os
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Muss vor dem Import von main stehen: der Datenbank-Engine wird beim Import
# erzeugt. Siehe testkonfiguration.py.
import testkonfiguration  # noqa: F401,E402

import mengenschwellen
from main import app, db, User, Bereich, Unterbereich, Gefahrstoff


def stoff(name, menge, einheit, h_saetze='', lagerklasse=None,
          unterbereich_id=1, is_deleted=False):
    """Attrappe mit genau den Feldern, die mengenschwellen liest."""
    return SimpleNamespace(name=name, menge=menge, mengeneinheit=einheit,
                           h_saetze=h_saetze, lagerklasse=lagerklasse,
                           unterbereich_id=unterbereich_id, is_deleted=is_deleted)


class TestHilfsfunktionen(unittest.TestCase):
    """Reine Funktionen, ohne Datenbank."""

    def test_h_codes_zerlegt_freitext(self):
        self.assertEqual(mengenschwellen.h_codes('H225, H319'),
                         {'H225', 'H319'})
        self.assertEqual(mengenschwellen.h_codes('H300+H310'), {'H300', 'H310'})
        self.assertEqual(mengenschwellen.h_codes(None), set())
        self.assertEqual(mengenschwellen.h_codes(''), set())

    def test_menge_in_kg_rechnet_masseinheiten(self):
        self.assertEqual(mengenschwellen.menge_in_kg(2, 'kg'), (2.0, None))
        self.assertEqual(mengenschwellen.menge_in_kg(500, 'g'), (0.5, None))

    def test_menge_in_kg_behandelt_liter_ohne_dichte_wie_kg(self):
        # Bewusst ohne Dichte: 1 L = 1 kg (siehe Modulkopf). Der Test hält das
        # fest, damit ein späterer Dichte-Einbau nicht unbemerkt die Zahlen
        # ändert.
        self.assertEqual(mengenschwellen.menge_in_kg(3, 'L'), (3.0, None))
        self.assertEqual(mengenschwellen.menge_in_kg(250, 'ml'), (0.25, None))

    def test_menge_in_kg_ohne_massenbezug(self):
        kg, hinweis = mengenschwellen.menge_in_kg(5, 'Stk')
        self.assertIsNone(kg)
        self.assertIn('Stk', hinweis)

    def test_menge_in_kg_ohne_menge(self):
        self.assertIsNone(mengenschwellen.menge_in_kg(None, 'kg')[0])
        self.assertIsNone(mengenschwellen.menge_in_kg('', 'kg')[0])


class TestPruefeUnterbereich(unittest.TestCase):
    """Die Prüfung eines Lagerabschnitts."""

    def test_kleinmenge_eingehalten_ergibt_keinen_befund(self):
        self.assertEqual(mengenschwellen.pruefe_unterbereich(
            [stoff('Ethanol', 5, 'L', 'H225', '3')]), [])

    def test_h226_ueber_kleinmenge(self):
        befunde = mengenschwellen.pruefe_unterbereich(
            [stoff('Xylol', 150, 'kg', 'H226', '3')])
        self.assertEqual(len(befunde), 1)
        self.assertEqual(befunde[0]['status'], 'ueberschritten')
        self.assertEqual(befunde[0]['kleinmenge_kg'], 100.0)
        self.assertEqual(befunde[0]['ueberschreitung_kg'], 50.0)

    def test_gleiche_gruppe_wird_summiert(self):
        # Zwei Stoffe unter der Kleinmenge, zusammen darüber - der Kern der
        # Prüfung: nicht der Einzelstoff zählt, sondern der Lagerabschnitt.
        befunde = mengenschwellen.pruefe_unterbereich([
            stoff('Xylol', 60, 'kg', 'H226', '3'),
            stoff('Toluol', 60, 'kg', 'H226', '3'),
        ])
        self.assertEqual(len(befunde), 1)
        self.assertEqual(befunde[0]['summe_kg'], 120.0)
        self.assertEqual(sorted(befunde[0]['stoffnamen']), ['Toluol', 'Xylol'])

    def test_zusatzschwelle_schlaegt_kleinmenge(self):
        befunde = mengenschwellen.pruefe_unterbereich(
            [stoff('Aceton', 250, 'kg', 'H225', '3')])
        self.assertEqual(befunde[0]['status'], 'zusatz')
        self.assertEqual(befunde[0]['zusatz_ab_kg'], 200.0)

    def test_h224_hat_eigene_zehn_kilo_grenze(self):
        # H224 ist allein auf 10 kg begrenzt, auch wenn die Summe H224+H225 die
        # 20-kg-Grenze nicht überschreitet.
        befunde = mengenschwellen.pruefe_unterbereich(
            [stoff('Ether', 12, 'L', 'H224', '3')])
        gruppen = {b['gruppe']: b for b in befunde}
        self.assertIn('entzfluessig_h224', gruppen)
        self.assertEqual(gruppen['entzfluessig_h224']['kleinmenge_kg'], 10.0)

    def test_h_satz_hat_vorrang_vor_lagerklasse(self):
        # Ein Stoff der LGK 3 mit H226 darf nicht zusätzlich an der 20-kg-Regel
        # für H224/H225 gemessen werden.
        befunde = mengenschwellen.pruefe_unterbereich(
            [stoff('Xylol', 150, 'kg', 'H226', '3')])
        self.assertEqual({b['gruppe'] for b in befunde}, {'entzfluessig_kat3'})

    def test_lagerklasse_als_ersatz_ohne_h_satz(self):
        befunde = mengenschwellen.pruefe_unterbereich(
            [stoff('Altöl', 1100, 'kg', '', '10')])
        self.assertEqual(befunde[0]['gruppe'], 'brennbar_fluessig_lgk10')
        self.assertEqual(befunde[0]['kleinmenge_kg'], 1000.0)

    def test_stueck_und_fehlende_menge_gehen_nicht_in_die_summe(self):
        befunde = mengenschwellen.pruefe_unterbereich([
            stoff('Druckgasflasche', 5, 'Stk', 'H280', '2A'),
            stoff('Pulver', None, 'kg', 'H228', '4.1B'),
        ])
        self.assertEqual(befunde, [])

    def test_stoff_ohne_massenbezug_wird_als_hinweis_gefuehrt(self):
        befunde = mengenschwellen.pruefe_unterbereich([
            stoff('Xylol', 150, 'kg', 'H226', '3'),
            stoff('Druckgasflasche', 5, 'Stk', 'H280', '2A'),
        ])
        self.assertIn('Druckgasflasche', befunde[0]['ohne_menge'])

    def test_gesamtgrenze_1500_kg(self):
        befunde = mengenschwellen.pruefe_unterbereich(
            [stoff('Wasser', 1600, 'L', '', '12')])
        gesamt = [b for b in befunde if b['status'] == 'gesamt']
        self.assertEqual(len(gesamt), 1)
        self.assertEqual(gesamt[0]['kleinmenge_kg'], 1500.0)

    def test_geloeschte_stoffe_zaehlen_nicht(self):
        befunde = mengenschwellen.pruefe_unterbereich([
            stoff('Xylol', 150, 'kg', 'H226', '3'),
            stoff('Geloescht', 500, 'kg', 'H226', '3', is_deleted=True),
        ])
        self.assertEqual(befunde[0]['summe_kg'], 150.0)

    def test_stoffe_ohne_menge_zaehlt(self):
        stoffe = [
            stoff('Druckgasflasche', 5, 'Stk', 'H280', '2A'),
            stoff('Pulver', None, 'kg', 'H228', '4.1B'),
            stoff('Xylol', 10, 'kg', 'H226', '3'),
        ]
        self.assertEqual(mengenschwellen.stoffe_ohne_menge(stoffe), 2)


class TestAlleBefunde(unittest.TestCase):
    """Aufteilung auf Lagerabschnitte und Sortierung."""

    def test_abschnitte_werden_getrennt(self):
        befunde = mengenschwellen.alle_befunde([
            stoff('Xylol', 150, 'kg', 'H226', '3', unterbereich_id=1),
            stoff('Aceton', 250, 'kg', 'H225', '3', unterbereich_id=2),
        ])
        self.assertEqual({b['unterbereich_id'] for b in befunde}, {1, 2})

    def test_stoffe_ohne_standort_werden_uebersprungen(self):
        befunde = mengenschwellen.alle_befunde([
            stoff('Xylol', 150, 'kg', 'H226', '3', unterbereich_id=None),
        ])
        self.assertEqual(befunde, [])

    def test_zusatzschwelle_steht_vorn(self):
        befunde = mengenschwellen.alle_befunde([
            stoff('Xylol', 150, 'kg', 'H226', '3', unterbereich_id=1),
            stoff('Aceton', 250, 'kg', 'H225', '3', unterbereich_id=1),
        ])
        self.assertEqual(befunde[0]['status'], 'zusatz')


class TestMengenschwellenSeite(unittest.TestCase):
    """Liste und Seiten — mit Datenbank."""

    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()
        with app.app_context():
            db.create_all()

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def _umgebung(self, ueber_schwelle=True):
        """Admin mit einem Lagerabschnitt und einem entzündbaren Stoff."""
        with app.app_context():
            admin = User(username='chef_mengen', role='admin')
            admin.set_password('pass123')
            db.session.add(admin)
            db.session.commit()

            bereich = Bereich(name='Labor M', owner_id=admin.id)
            db.session.add(bereich)
            db.session.commit()

            unterbereich = Unterbereich(name='Schrank M1', bereich_id=bereich.id)
            db.session.add(unterbereich)
            db.session.commit()

            db.session.add(Gefahrstoff(
                name='Testxylol',
                unterbereich_id=unterbereich.id,
                user_id=admin.id,
                menge=150.0 if ueber_schwelle else 5.0,
                mengeneinheit='kg',
                h_saetze='H226',
                lagerklasse='3',
                is_approved=True,
            ))
            db.session.commit()

        self.client.post('/login',
                         data={'username': 'chef_mengen', 'password': 'pass123'},
                         follow_redirects=True)

    def _seite(self, pfad='/mengenschwellen'):
        res = self.client.get(pfad)
        self.assertEqual(res.status_code, 200, pfad)
        return res.get_data(as_text=True)

    def test_seite_verlangt_anmeldung(self):
        res = self.client.get('/mengenschwellen')
        self.assertEqual(res.status_code, 302)

    def test_ueberschreitung_erscheint_in_der_liste(self):
        self._umgebung(ueber_schwelle=True)
        html = self._seite()
        # Auf Zeilenmerkmale prüfen, nicht auf den Kacheltext: "Kleinmenge
        # überschritten" steht auch als Beschriftung der Kennzahl oben.
        self.assertIn('Testxylol', html)
        self.assertIn('Entzündbare Flüssigkeiten Kat. 3', html)
        self.assertIn('Schrank M1', html)

    def test_eingehaltene_kleinmenge_ergibt_leerzustand(self):
        self._umgebung(ueber_schwelle=False)
        html = self._seite()
        self.assertIn('Keine überschrittenen Mengenschwellen', html)
        self.assertNotIn('Testxylol', html)

    def test_detailseite_zeigt_den_hinweis(self):
        self._umgebung(ueber_schwelle=True)
        with app.app_context():
            stoff_id = Gefahrstoff.query.filter_by(name='Testxylol').first().id
        html = self._seite(f'/view/{stoff_id}')
        self.assertIn('Mengenschwellen im Lagerabschnitt (TRGS 510)', html)
        self.assertIn('150.0', html)

    def test_uebersicht_zeigt_das_symbol(self):
        self._umgebung(ueber_schwelle=True)
        html = self._seite('/')
        self.assertIn('Mengenschwelle im Lagerabschnitt überschritten', html)

    def test_navigationszähler_vorhanden(self):
        self._umgebung(ueber_schwelle=True)
        html = self._seite('/')
        self.assertIn('Mengenschwellen', html)
        self.assertIn('nav-count', html)


if __name__ == '__main__':
    unittest.main(verbosity=2)
