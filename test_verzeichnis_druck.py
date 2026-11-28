"""Tests für das gedruckte Gesamtverzeichnis.

Grundlage: docs/specs/SPEC-uebersicht-standort.md (Q6 und Q12). Abgesichert wird

* die Berechtigungsgrenze: gedruckt wird nur, was der Benutzer sehen darf,
* das Inhaltsverzeichnis und ein Seitenumbruch je Standort,
* Sortierung (Standorte nach Name, Stoffe nach Name, Unter-Standorte gemischt),
* der Unter-Standort steht je Zeile dabei, wenn er nicht die Gruppe ist.

Mit ausführen:
    ~/.venvs/gsv/bin/python -m unittest test_verzeichnis_druck -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Muss vor dem Import von main stehen (siehe testkonfiguration.py).
import testkonfiguration  # noqa: F401,E402

from main import app, db, User, Bereich, Unterbereich, Gefahrstoff  # noqa: E402


class TestVerzeichnisDruck(unittest.TestCase):

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

            raum_z = Unterbereich(name='Zebra-Raum', bereich_id=labor_a.id)
            raum_a = Unterbereich(name='Alpha-Raum', bereich_id=labor_a.id)
            raum_b = Unterbereich(name='Raum B', bereich_id=labor_b.id)
            db.session.add_all([raum_z, raum_a, raum_b])
            db.session.commit()

            schrank = Unterbereich(name='Schrank A1', bereich_id=labor_a.id,
                                   parent_id=raum_a.id)
            db.session.add(schrank)
            db.session.commit()

            db.session.add_all([
                # Absichtlich in falscher Reihenfolge angelegt.
                Gefahrstoff(name='Zinkstaub', unterbereich_id=raum_a.id,
                            user_id=anna.id, is_approved=True),
                Gefahrstoff(name='Aceton', unterbereich_id=schrank.id,
                            user_id=anna.id, is_approved=True,
                            cas_nummer='67-64-1'),
                Gefahrstoff(name='Toluol', unterbereich_id=raum_b.id,
                            user_id=bernd.id, is_approved=True),
                # Ein leerer Standort muss als solcher im Verzeichnis stehen.
            ])
            anna.assigned_bereiche.append(labor_a)
            bernd.assigned_bereiche.append(labor_b)
            db.session.commit()

            # IDs im Kontext lesen: ausserhalb sind die Objekte detached und
            # ihre Attribute abgelaufen (DetachedInstanceError).
            self.raum_z_id = raum_z.id
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

    def _druck(self):
        antwort = self.client.get('/verzeichnis/druck')
        self.assertEqual(antwort.status_code, 200)
        return antwort.get_data(as_text=True)

    def test_druck_braucht_anmeldung(self):
        antwort = self.client.get('/verzeichnis/druck')
        self.assertEqual(antwort.status_code, 302)
        self.assertIn('/login', antwort.headers['Location'])

    def test_druck_zeigt_nur_eigene_bereiche(self):
        self._login()
        html = self._druck()
        self.assertIn('Alpha-Raum', html)
        self.assertIn('Zebra-Raum', html)
        self.assertNotIn('Raum B', html)
        self.assertNotIn('Toluol', html)

    def test_leerer_standort_steht_im_verzeichnis(self):
        """Ein Standort ohne Stoffe fehlt nicht stillschweigend."""
        self._login()
        html = self._druck()
        self.assertIn('keine Gefahrstoffe eingetragen', html)

    def test_inhaltsverzeichnis_und_seitenumbruch_je_standort(self):
        self._login()
        html = self._druck()
        self.assertIn('Inhalt', html)
        # Eine Sektion je Standort, jede mit eigenem Umbruch.
        self.assertEqual(html.count('class="standort"'), 2)
        self.assertIn('page-break-before: always', html)
        # Inhaltsverzeichnis nennt beide Standorte in Seitenreihenfolge.
        self.assertLess(html.index('Alpha-Raum'), html.index('Zebra-Raum'))

    def test_stoffe_sortiert_und_unterstandort_genannt(self):
        self._login()
        html = self._druck()
        # Aceton steht im Unter-Standort Schrank A1, Zinkstaub direkt im Raum.
        self.assertLess(html.index('Aceton'), html.index('Zinkstaub'))
        self.assertIn('Schrank A1', html)

    def test_admin_sieht_das_vollstaendige_verzeichnis(self):
        with app.app_context():
            admin = User(username='chef', role='admin')
            admin.set_password('pass123')
            db.session.add(admin)
            db.session.commit()

        self._login('chef')
        html = self._druck()
        self.assertIn('Aceton', html)
        self.assertIn('Toluol', html)
        self.assertEqual(html.count('class="standort"'), 3)


if __name__ == '__main__':
    unittest.main()
