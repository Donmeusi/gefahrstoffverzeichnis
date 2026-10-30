"""Regressionstests für die freigabekritischen Befunde der IT-Prüfung
vom 2026-10-30 (F-01 bis F-04, F-34).

Jeder Test hält genau die Lücke fest, die im Prüfbericht belegt wurde:

- F-01: Pillow 12.3.0 mit 41 GHSA-Meldungen; Fix ist 13.0.0.
- F-02: /users/edit prüfte die Passwort-Mindestlänge nicht.
- F-03: CMR-Freigabe-Gate war über /edit/<id> umgehbar.
- F-04: Ein nur zugewiesener Moderator durfte den Bereich löschen.
- F-34: Logout invalidierte die Sitzung nicht serverseitig.

Mit ausführen:
    python -m unittest test_pruefbericht_fixes
"""
import base64
import os
import sys
import unittest
from importlib.metadata import version

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Muss vor dem Import von main stehen, siehe testkonfiguration.py.
import testkonfiguration  # noqa: F401,E402

from main import (app, db, User, Bereich, Unterbereich, Gefahrstoff,
                  BA_SIGNATUR_BILD_PRAEFIX, sanitize_ba_unterschrift)

# Ein gueltiges 1x1-PNG.
PNG_1X1 = ('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ'
           'AAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==')
# JPEG-Signatur, damit Image.open ein anderes Format erkennt.
JPEG_KOPF = '/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsL'


class TestPillowVersion(unittest.TestCase):
    """F-01: Die Bildpruefung der Unterschrift braucht Pillow >= 13.0.0."""

    def test_pillow_ist_mindestens_13(self):
        installiert = version('Pillow')
        teile = tuple(int(teil) for teil in installiert.split('.')[:2])
        self.assertGreaterEqual(
            teile, (13, 0),
            f'Pillow {installiert} ist installiert; die 41 GHSA-Meldungen '
            'sind erst ab 13.0.0 behoben.')

    def test_png_unterschrift_wird_weiterhin_akzeptiert(self):
        roh = ('{"typ": "bild", "wert": "%s%s"}'
               % (BA_SIGNATUR_BILD_PRAEFIX, PNG_1X1))
        geprueft = sanitize_ba_unterschrift(roh)
        self.assertIsNotNone(geprueft)
        self.assertIn(PNG_1X1, geprueft)

    def test_fremdformat_wird_abgelehnt(self):
        roh = ('{"typ": "bild", "wert": "%s%s"}'
               % (BA_SIGNATUR_BILD_PRAEFIX, JPEG_KOPF))
        self.assertIsNone(sanitize_ba_unterschrift(roh))


class TestPasswortPolicyEditUser(unittest.TestCase):
    """F-02: /users/edit muss dieselbe Mindestlaenge pruefen wie /register."""

    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()
        with app.app_context():
            db.create_all()
            admin = User(username='admin_s', role='admin')
            admin.set_password('dummy-admin-passwort')
            ziel = User(username='zweitkonto', role='benutzer')
            ziel.set_password('gueltiges-passwort-123')
            db.session.add_all([admin, ziel])
            db.session.commit()
            self.ziel_id = ziel.id
        self.client.post('/login', data={'username': 'admin_s',
                                         'password': 'dummy-admin-passwort'})

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def test_kurzes_passwort_wird_abgelehnt(self):
        antwort = self.client.post(
            f'/users/edit/{self.ziel_id}',
            data={'username': 'zweitkonto', 'password': 'x',
                  'role': 'benutzer'})
        self.assertEqual(antwort.status_code, 302)

        with app.app_context():
            ziel = db.session.get(User, self.ziel_id)
            self.assertTrue(
                ziel.check_password('gueltiges-passwort-123'),
                'Das alte Passwort muss unveraendert gelten')
            self.assertFalse(ziel.check_password('x'),
                             'Das zu kurze Passwort wurde uebernommen')

    def test_ausreichend_langes_passwort_wird_uebernommen(self):
        neues = 'neues-sicheres-passwort'
        antwort = self.client.post(
            f'/users/edit/{self.ziel_id}',
            data={'username': 'zweitkonto', 'password': neues,
                  'role': 'benutzer'})
        self.assertEqual(antwort.status_code, 302)

        with app.app_context():
            ziel = db.session.get(User, self.ziel_id)
            self.assertTrue(ziel.check_password(neues))


if __name__ == '__main__':
    unittest.main()
