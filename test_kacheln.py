"""Tests für die nachgeladene Kachelansicht der Übersicht.

Die Übersicht liefert nur noch die Tabelle; die Kacheln kommen von
/index/kacheln, wenn der Umschalter sie zum ersten Mal braucht. Das halbiert
bei großen Verzeichnissen das HTML. Diese Datei sichert ab, dass

* die Übersicht keine Kacheln mehr enthält, aber die Adresse dafür mitgibt,
* das Fragment Kacheln und keinen Seitenrahmen liefert,
* es dieselben Bereichsfilter beachtet wie die Übersicht,
* ein fremder Bereich nicht über die Abfrage erreichbar ist.

Mit ausführen:
    ~/.venvs/gsv/bin/python -m unittest test_kacheln -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Muss vor dem Import von main stehen (siehe testkonfiguration.py).
import testkonfiguration  # noqa: F401,E402

from main import app, db, User, Bereich, Unterbereich, Gefahrstoff  # noqa: E402


class TestKacheln(unittest.TestCase):

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

            bereich_a = Bereich(name='Labor A', owner_id=anna.id)
            bereich_b = Bereich(name='Labor B', owner_id=bernd.id)
            db.session.add_all([bereich_a, bereich_b])
            db.session.commit()

            raum_a = Unterbereich(name='Raum A', bereich_id=bereich_a.id)
            raum_b = Unterbereich(name='Raum B', bereich_id=bereich_b.id)
            db.session.add_all([raum_a, raum_b])
            db.session.commit()

            db.session.add_all([
                Gefahrstoff(name='Aceton', unterbereich_id=raum_a.id,
                            user_id=anna.id, is_approved=True),
                Gefahrstoff(name='Toluol', unterbereich_id=raum_b.id,
                            user_id=bernd.id, is_approved=True),
            ])
            anna.assigned_bereiche.append(bereich_a)
            db.session.commit()

            self.bereich_a_id = bereich_a.id
            self.bereich_b_id = bereich_b.id

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def _login(self, benutzer='anna'):
        self.client.post('/login', data={'username': benutzer,
                                         'password': 'pass123'},
                         follow_redirects=True)

    def test_uebersicht_enthaelt_keine_kacheln(self):
        self._login()
        html = self.client.get('/').get_data(as_text=True)

        # Die Tabelle steht, die Kacheln nicht - aber die Adresse ist da.
        self.assertIn('id="gefahrstoffTable"', html)
        self.assertIn('data-kacheln-url="/index/kacheln"', html)
        self.assertNotIn('stoff-card', html)
        self.assertIn('Aceton', html)

    def test_fragment_liefert_nur_kacheln(self):
        self._login()
        antwort = self.client.get('/index/kacheln')
        html = antwort.get_data(as_text=True)

        self.assertEqual(antwort.status_code, 200)
        self.assertIn('stoff-card', html)
        self.assertIn('Aceton', html)
        # Kein Seitenrahmen: nur der Kachelblock.
        self.assertNotIn('<html', html)
        self.assertNotIn('id="gefahrstoffTable"', html)

    def test_fragment_beachtet_den_bereichsfilter(self):
        self._login()
        html = self.client.get(
            f'/index/kacheln?bereich_id={self.bereich_a_id}'
        ).get_data(as_text=True)

        self.assertIn('Aceton', html)
        self.assertNotIn('Toluol', html)

    def test_fremder_bereich_bleibt_gesperrt(self):
        self._login()
        antwort = self.client.get(
            f'/index/kacheln?bereich_id={self.bereich_b_id}')

        self.assertEqual(antwort.status_code, 403)

    def test_fragment_braucht_anmeldung(self):
        antwort = self.client.get('/index/kacheln')
        self.assertEqual(antwort.status_code, 302)
        self.assertIn('/login', antwort.headers['Location'])

    def test_leser_sieht_kacheln_ohne_downloads(self):
        """Die Leser-Rolle bekommt die gesperrten Dokumentknöpfe wie bisher."""
        with app.app_context():
            leser = User(username='leser', role='lesen')
            leser.set_password('pass123')
            leser.assigned_bereiche.append(
                Bereich.query.filter_by(name='Labor A').one())
            db.session.add(leser)
            stoff = Gefahrstoff.query.filter_by(name='Aceton').one()
            stoff.sicherheitsdatenblatt = 'aceton.pdf'
            db.session.commit()

        self._login('leser')
        html = self.client.get('/index/kacheln').get_data(as_text=True)

        self.assertIn('doc-btn-disabled', html)
        self.assertNotIn('href="/uploads/aceton.pdf"', html)


if __name__ == '__main__':
    unittest.main()
