"""Tests für die Übersicht nach Standort.

Grundlage: docs/specs/SPEC-uebersicht-standort.md. Abgesichert wird

* die Weiterleitung der alten Adressen (Lesezeichen brechen nicht),
* der direkte Einstieg, wenn nur ein Bereich mit einem Standort sichtbar ist,
* die gemerkte Wahl in der Sitzung - und ihr Verfall bei Rechteverlust,
* die Berechtigungsgrenze der Standortansicht,
* die Auswahlseite mit Stoffzahl (inkl. Unter-Standorten) und Warnmarke.

Mit ausführen:
    ~/.venvs/gsv/bin/python -m unittest test_standort_ansicht -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Muss vor dem Import von main stehen (siehe testkonfiguration.py).
import testkonfiguration  # noqa: F401,E402

from main import app, db, User, Bereich, Unterbereich, Gefahrstoff  # noqa: E402


class TestStandortAnsicht(unittest.TestCase):

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
            carla = User(username='carla', role='benutzer')
            carla.set_password('pass123')
            db.session.add_all([anna, bernd, carla])
            db.session.commit()

            labor_a = Bereich(name='Labor A')
            labor_b = Bereich(name='Labor B')
            db.session.add_all([labor_a, labor_b])
            db.session.commit()

            # Raum A hat einen Unter-Standort: die Zahl auf der Auswahlseite
            # muss den ganzen Teilbaum zaehlen.
            raum_a = Unterbereich(name='Raum A', bereich_id=labor_a.id)
            raum_b = Unterbereich(name='Raum B', bereich_id=labor_b.id)
            db.session.add_all([raum_a, raum_b])
            db.session.commit()

            schrank_a1 = Unterbereich(name='Schrank A1', bereich_id=labor_a.id,
                                      parent_id=raum_a.id)
            db.session.add(schrank_a1)
            db.session.commit()

            db.session.add_all([
                Gefahrstoff(name='Aceton', unterbereich_id=schrank_a1.id,
                            user_id=anna.id, is_approved=True),
                Gefahrstoff(name='Toluol', unterbereich_id=raum_b.id,
                            user_id=bernd.id, is_approved=True),
                # Ueber der Kleinmenge fuer Lagerklasse 3 (TRGS 510) - setzt die
                # Warnmarke auf den uebergeordneten Standort.
                Gefahrstoff(name='Testxylol', unterbereich_id=schrank_a1.id,
                            user_id=anna.id, is_approved=True,
                            menge=150.0, mengeneinheit='kg',
                            h_saetze='H226', lagerklasse='3'),
            ])

            # Anna sieht beide Bereiche, Bernd nur B, Carla nur A.
            anna.assigned_bereiche.extend([labor_a, labor_b])
            bernd.assigned_bereiche.append(labor_b)
            carla.assigned_bereiche.append(labor_a)
            db.session.commit()

            self.labor_a_id = labor_a.id
            self.labor_b_id = labor_b.id
            self.raum_a_id = raum_a.id
            self.raum_b_id = raum_b.id

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def _login(self, benutzer='anna'):
        self.client.post('/login', data={'username': benutzer,
                                         'password': 'pass123'},
                         follow_redirects=True)

    def test_alte_adresse_mit_standort_leitet_um(self):
        """Lesezeichen mit ?unterbereich_id= bleiben gueltig."""
        self._login()
        antwort = self.client.get(f'/?unterbereich_id={self.raum_a_id}')
        self.assertEqual(antwort.status_code, 302)
        self.assertTrue(antwort.headers['Location'].endswith(
            f'/standort/{self.raum_a_id}'))

    def test_alte_adresse_mit_bereich_leitet_auf_die_auswahl(self):
        self._login()
        antwort = self.client.get(f'/?bereich_id={self.labor_a_id}')
        self.assertEqual(antwort.status_code, 302)
        self.assertIn('/standorte', antwort.headers['Location'])
        self.assertIn(f'bereich_id={self.labor_a_id}', antwort.headers['Location'])

    def test_ein_bereich_mit_einem_standort_geht_direkt_hinein(self):
        """Carla sieht nur Labor A - also kein Zwischenschritt."""
        self._login('carla')
        antwort = self.client.get('/')
        self.assertEqual(antwort.status_code, 302)
        self.assertTrue(antwort.headers['Location'].endswith(
            f'/standort/{self.raum_a_id}'))

    def test_merkregel_fuehrt_beim_naechsten_aufruf_zurueck(self):
        """Zwei Bereiche: ohne Merkregel Auswahl, danach der Standort."""
        self._login()
        erst = self.client.get('/')
        self.assertEqual(erst.status_code, 302)
        self.assertIn('/standorte', erst.headers['Location'])

        self.client.get(f'/standort/{self.raum_b_id}')
        zweit = self.client.get('/')
        self.assertEqual(zweit.status_code, 302)
        self.assertTrue(zweit.headers['Location'].endswith(
            f'/standort/{self.raum_b_id}'))

    def test_merkregel_verfaellt_bei_rechteverlust(self):
        """Wer den Bereich verliert, landet nicht mehr in seinem Standort."""
        self._login()
        self.client.get(f'/standort/{self.raum_b_id}')

        with app.app_context():
            anna = User.query.filter_by(username='anna').one()
            labor_b = Bereich.query.get(self.labor_b_id)
            anna.assigned_bereiche.remove(labor_b)
            db.session.commit()

        antwort = self.client.get('/')
        self.assertEqual(antwort.status_code, 302)
        self.assertNotIn(f'/standort/{self.raum_b_id}', antwort.headers['Location'])

    def test_fremder_standort_bleibt_gesperrt(self):
        self._login('bernd')
        antwort = self.client.get(f'/standort/{self.raum_a_id}')
        self.assertEqual(antwort.status_code, 302)
        self.assertIn('/standorte', antwort.headers['Location'])

    def test_standortansicht_zeigt_nur_den_standort(self):
        self._login()
        html = self.client.get(
            f'/standort/{self.raum_a_id}').get_data(as_text=True)
        self.assertIn('Aceton', html)
        # Toluol steht in Raum B: dieselbe Pruefung wie die Berechtigungsgrenze.
        self.assertNotIn('Toluol', html)

    def test_auswahlseite_zaehlt_den_teilbaum_und_markiert_die_schwelle(self):
        self._login()
        html = self.client.get('/standorte').get_data(as_text=True)
        self.assertIn('Raum A', html)
        self.assertIn('Raum B', html)
        # Aceton + Testxylol, beide im Unter-Standort Schrank A1.
        self.assertIn('<td>2</td>', html)
        self.assertIn('Mengenschwelle', html)

    def test_auswahlseite_zeigt_fremde_bereiche_nicht(self):
        self._login('carla')
        html = self.client.get('/standorte').get_data(as_text=True)
        self.assertIn('Raum A', html)
        self.assertNotIn('Raum B', html)

    def test_auswahlseite_braucht_anmeldung(self):
        antwort = self.client.get('/standorte')
        self.assertEqual(antwort.status_code, 302)
        self.assertIn('/login', antwort.headers['Location'])


if __name__ == '__main__':
    unittest.main()
