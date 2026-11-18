"""Tests für die vorab berechnete Zusammenlagerungsprüfung der Übersicht.

Gefahrstoff.trgs_warnings (Detailseite) und trgs_warnungen_fuer (Liste) müssen
dieselben Stoffe markieren - sonst zeigt die Übersicht ein anderes Bild als
die Detailseite. Die Listenfunktion prüft nur je Lagerabschnitt und
Lagerklasse statt je Stoffpaar, weil die Eigenschaft bei 1000 Stoffen im
selben Raum sonst eine Million Vergleiche und 1000 Abfragen auslöst.

Mit ausführen:
    ~/.venvs/gsv/bin/python -m unittest test_trgs_warnungen -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Muss vor dem Import von main stehen (siehe testkonfiguration.py).
import testkonfiguration  # noqa: F401,E402

from main import (  # noqa: E402
    app, db, User, Bereich, Unterbereich, Gefahrstoff, trgs_warnungen_fuer,
)


class TestTrgsWarnungen(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        with app.app_context():
            db.create_all()
            admin = User(username='admin', role='admin')
            admin.set_password('pass123')
            db.session.add(admin)
            db.session.commit()
            bereich = Bereich(name='Labor', owner_id=admin.id)
            db.session.add(bereich)
            db.session.commit()
            self.raum_a = Unterbereich(name='Raum A', bereich_id=bereich.id)
            self.raum_b = Unterbereich(name='Raum B', bereich_id=bereich.id)
            db.session.add_all([self.raum_a, self.raum_b])
            db.session.commit()
            self.admin_id = admin.id
            self.raum_a_id = self.raum_a.id
            self.raum_b_id = self.raum_b.id

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def _stoff(self, name, lgk, raum, geloescht=False):
        with app.app_context():
            stoff = Gefahrstoff(name=name, lagerklasse=lgk,
                                unterbereich_id=raum, user_id=self.admin_id,
                                is_deleted=geloescht, is_approved=True)
            db.session.add(stoff)
            db.session.commit()
            return stoff.id

    def test_markiert_beide_seiten_eines_verbots(self):
        """LGK 3 und LGK 5.1A dürfen nicht zusammen gelagert werden."""
        aceton = self._stoff('Aceton', '3', self.raum_a_id)
        nitrat = self._stoff('Natriumnitrat', '5.1A', self.raum_a_id)

        with app.app_context():
            warnungen = trgs_warnungen_fuer(
                Gefahrstoff.query.order_by(Gefahrstoff.name).all())

        self.assertEqual(warnungen, {aceton, nitrat})

    def test_getrennte_raeume_bleiben_ruhig(self):
        aceton = self._stoff('Aceton', '3', self.raum_a_id)
        nitrat = self._stoff('Natriumnitrat', '5.1A', self.raum_b_id)

        with app.app_context():
            warnungen = trgs_warnungen_fuer(
                Gefahrstoff.query.order_by(Gefahrstoff.name).all())
            eigen = {s.id for s in Gefahrstoff.query.all() if s.trgs_warnings}

        self.assertEqual(warnungen, set())
        self.assertEqual(eigen, set())
        self.assertNotIn(aceton, warnungen)
        self.assertNotIn(nitrat, warnungen)

    def test_geloeschte_stoffe_zaehlen_nicht(self):
        """Ein gelöschter Explosivstoff darf keinen Konflikt auslösen."""
        aceton = self._stoff('Aceton', '3', self.raum_a_id)
        self._stoff('Altbestand', '1', self.raum_a_id, geloescht=True)

        with app.app_context():
            warnungen = trgs_warnungen_fuer(Gefahrstoff.query.all())

        self.assertEqual(warnungen, set())
        self.assertNotIn(aceton, warnungen)

    def test_ohne_lagerklasse_keine_warnung(self):
        ohne = self._stoff('Wasser', None, self.raum_a_id)
        nitrat = self._stoff('Natriumnitrat', '5.1A', self.raum_a_id)

        with app.app_context():
            warnungen = trgs_warnungen_fuer(Gefahrstoff.query.all())

        self.assertEqual(warnungen, set())
        self.assertNotIn(ohne, warnungen)
        self.assertNotIn(nitrat, warnungen)

    def test_gefilterte_liste_prueft_den_ganzen_abschnitt(self):
        """Auch wenn nur ein Stoff angezeigt wird, gilt der Lagerabschnitt.

        Sonst verschwände die Warnung, sobald man nach einem Stoff sucht.
        """
        aceton = self._stoff('Aceton', '3', self.raum_a_id)
        self._stoff('Natriumnitrat', '5.1A', self.raum_a_id)

        with app.app_context():
            nur_aceton = Gefahrstoff.query.filter_by(name='Aceton').all()
            warnungen = trgs_warnungen_fuer(nur_aceton)

        self.assertEqual(warnungen, {aceton})

    def test_liste_und_eigenschaft_stimmen_ueberein(self):
        """Gegenprobe: die schnelle Liste gegen die Eigenschaft je Stoff."""
        self._stoff('Aceton', '3', self.raum_a_id)
        self._stoff('Natriumnitrat', '5.1A', self.raum_a_id)
        self._stoff('Ethanol', '3', self.raum_a_id)
        self._stoff('Salzsäure', '8A', self.raum_a_id)
        self._stoff('Kalk', '8B', self.raum_b_id)
        self._stoff('Wasserstoffperoxid', '5.1A', self.raum_b_id)

        with app.app_context():
            stoffe = Gefahrstoff.query.order_by(Gefahrstoff.id).all()
            schnell = trgs_warnungen_fuer(stoffe)
            langsam = {s.id for s in stoffe if s.trgs_warnings}

        self.assertEqual(schnell, langsam)


if __name__ == '__main__':
    unittest.main()
