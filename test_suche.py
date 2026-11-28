"""Tests für die Stoffsuche über alle Standorte.

Grundlage: docs/specs/SPEC-uebersicht-standort.md (Q5). Abgesichert wird

* die Berechtigungsgrenze: gesucht wird nur in sichtbaren Bereichen,
* Feldabdeckung (Name, CAS, EG, H-Satz) und Groß-/Kleinschreibung mit Umlaut,
* dass ein Treffer den Standort nennt und auf die Standortansicht verlinkt,
* die Obergrenze der Trefferliste.

Mit ausführen:
    ~/.venvs/gsv/bin/python -m unittest test_suche -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Muss vor dem Import von main stehen (siehe testkonfiguration.py).
import testkonfiguration  # noqa: F401,E402

import main  # noqa: E402
from main import app, db, User, Bereich, Unterbereich, Gefahrstoff  # noqa: E402


class TestSuche(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()
        with app.app_context():
            db.create_all()
            anna = User(username='anna', role='benutzer')
            anna.set_password('pass123')
            bernd = User(username='bernd', role='benutzer')
            bernd.set_password('pass123')
            db.session.add_all([anna, bernd])
            db.session.commit()

            labor_a = Bereich(name='Labor A')
            labor_b = Bereich(name='Labor B')
            db.session.add_all([labor_a, labor_b])
            db.session.commit()

            raum_a = Unterbereich(name='Raum A', bereich_id=labor_a.id)
            raum_b = Unterbereich(name='Raum B', bereich_id=labor_b.id)
            db.session.add_all([raum_a, raum_b])
            db.session.commit()

            db.session.add_all([
                Gefahrstoff(name='Aceton', unterbereich_id=raum_a.id,
                            user_id=anna.id, is_approved=True,
                            cas_nummer='67-64-1', h_saetze='H225, H319'),
                Gefahrstoff(name='Äthanol', unterbereich_id=raum_a.id,
                            user_id=anna.id, is_approved=True,
                            cas_nummer='64-17-5'),
                Gefahrstoff(name='Toluol', unterbereich_id=raum_b.id,
                            user_id=bernd.id, is_approved=True,
                            cas_nummer='108-88-3'),
            ])
            anna.assigned_bereiche.append(labor_a)
            bernd.assigned_bereiche.append(labor_b)
            db.session.commit()

            self.raum_a_id = raum_a.id

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def _login(self, benutzer='anna'):
        self.client.post('/login', data={'username': benutzer,
                                         'password': 'pass123'},
                         follow_redirects=True)

    def _suche(self, begriff):
        return self.client.get(f'/suche?q={begriff}').get_data(as_text=True)

    def test_suche_braucht_anmeldung(self):
        antwort = self.client.get('/suche?q=Aceton')
        self.assertEqual(antwort.status_code, 302)
        self.assertIn('/login', antwort.headers['Location'])

    def test_findet_ueber_den_eigenen_bereich_hinaus(self):
        """Anna sieht nur Labor A - dort liegt Aceton, und der Standort steht dabei."""
        self._login()
        html = self._suche('Aceton')
        self.assertIn('Aceton', html)
        self.assertIn('Labor A / Raum A', html)
        self.assertIn(f'/standort/{self.raum_a_id}', html)

    def test_findet_nichts_aus_fremden_bereichen(self):
        self._login()
        html = self._suche('Toluol')
        # "Toluol" steht als Suchbegriff im Feld und in der Meldung - der Beweis
        # ist, dass kein Treffer verlinkt wird.
        self.assertIn('Kein Stoff gefunden', html)
        self.assertNotIn('href="/view/', html)

    def test_findet_ueber_die_cas_nummer(self):
        self._login()
        html = self._suche('67-64-1')
        self.assertIn('Aceton', html)

    def test_findet_ueber_den_h_satz(self):
        self._login()
        html = self._suche('H319')
        self.assertIn('Aceton', html)
        self.assertNotIn('Äthanol', html)

    def test_gross_klein_mit_umlaut(self):
        """SQLite-LIKE vergleicht nur ASCII; die Suche muss "äth" trotzdem finden."""
        self._login()
        html = self._suche('äth')
        self.assertIn('Äthanol', html)

    def test_leere_suche_zeigt_hinweis(self):
        self._login()
        html = self._suche('')
        self.assertIn('Gib einen Suchbegriff ein', html)

    def test_trefferliste_ist_begrenzt(self):
        """Eine breite Suche darf nicht wieder tausende Zeilen rendern."""
        with app.app_context():
            anna = User.query.filter_by(username='anna').one()
            for i in range(5):
                db.session.add(Gefahrstoff(
                    name=f'Teststoff-{i}', unterbereich_id=self.raum_a_id,
                    user_id=anna.id, is_approved=True))
            db.session.commit()

        alt = main.SUCHERGEBNISSE_MAX
        main.SUCHERGEBNISSE_MAX = 2
        try:
            self._login()
            html = self._suche('Teststoff')
            self.assertIn('die ersten 2 werden gezeigt', html)
            self.assertIn('5 Treffer', html)
            # Nur zwei Zeilen verlinkt, nicht alle fünf.
            self.assertEqual(html.count('/view/'), 2)
        finally:
            main.SUCHERGEBNISSE_MAX = alt


if __name__ == '__main__':
    unittest.main()
