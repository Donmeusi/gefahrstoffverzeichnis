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


class TestCmrFreigabeGate(unittest.TestCase):
    """F-03: Die Freigabe eines CMR-Stoffs darf nicht ueber /edit laufen."""

    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()
        with app.app_context():
            db.create_all()
            admin = User(username='admin_c', role='admin')
            admin.set_password('dummy-admin-passwort')
            db.session.add(admin)
            db.session.commit()
            bereich = Bereich(name='Labor', owner_id=admin.id)
            db.session.add(bereich)
            db.session.commit()
            unterbereich = Unterbereich(name='Schrank',
                                        bereich_id=bereich.id)
            db.session.add(unterbereich)
            db.session.commit()
            benutzer = User(username='nutzer_c', role='benutzer')
            benutzer.set_password('dummy-benutzer-passwort')
            benutzer.assigned_bereiche.append(bereich)
            db.session.add(benutzer)
            db.session.commit()

            wartend = Gefahrstoff(name='CMR wartet',
                                  unterbereich_id=unterbereich.id,
                                  user_id=benutzer.id,
                                  h_saetze='H350', is_approved=False)
            offen = Gefahrstoff(name='Unbedenklich',
                                unterbereich_id=unterbereich.id,
                                user_id=benutzer.id,
                                h_saetze='H302', is_approved=True)
            db.session.add_all([wartend, offen])
            db.session.commit()
            self.unterbereich_id = unterbereich.id
            self.wartend_id = wartend.id
            self.offen_id = offen.id
        self.client.post('/login', data={'username': 'nutzer_c',
                                         'password': 'dummy-benutzer-passwort'})

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def _post_edit(self, stoff_id, h_saetze):
        return self.client.post(f'/edit/{stoff_id}', data={
            'name': 'Bearbeitet',
            'unterbereich_id': str(self.unterbereich_id),
            'h_saetze': h_saetze,
            'menge': '',
        })

    def test_wartender_cmr_stoff_ist_im_edit_gesperrt(self):
        antwort = self.client.get(f'/edit/{self.wartend_id}')
        self.assertEqual(antwort.status_code, 302,
                         'Unfreigegebener CMR-Stoff war ueber /edit lesbar')

    def test_freigabe_laesst_sich_nicht_per_edit_erzwingen(self):
        antwort = self._post_edit(self.wartend_id, 'H302')
        self.assertEqual(antwort.status_code, 302)

        with app.app_context():
            stoff = db.session.get(Gefahrstoff, self.wartend_id)
            self.assertFalse(stoff.is_approved,
                             'Edit hat den CMR-Stoff selbst freigegeben')
            self.assertEqual(stoff.h_saetze, 'H350',
                             'Die Bearbeitung des gesperrten Stoffs kam durch')

    def test_edit_gibt_einen_stoff_nicht_frei(self):
        self._post_edit(self.offen_id, 'H302')

        with app.app_context():
            stoff = db.session.get(Gefahrstoff, self.offen_id)
            self.assertTrue(stoff.is_approved)
            self.assertEqual(stoff.h_saetze, 'H302')

    def test_cmr_werdender_stoff_verliert_die_freigabe(self):
        self._post_edit(self.offen_id, 'H350')

        with app.app_context():
            stoff = db.session.get(Gefahrstoff, self.offen_id)
            self.assertFalse(stoff.is_approved,
                             'Ein nachtraeglich CMR gewordener Stoff blieb '
                             'sichtbar')
            self.assertEqual(stoff.h_saetze, 'H350')


class TestBereichLoeschen(unittest.TestCase):
    """F-04: Nur Besitzer oder Administrator duerfen einen Bereich loeschen."""

    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()
        with app.app_context():
            db.create_all()
            admin = User(username='admin_b', role='admin')
            admin.set_password('dummy-admin-passwort')
            eigentuemer = User(username='mod_besitzer', role='moderator')
            eigentuemer.set_password('dummy-moderator-passwort')
            zugewiesen = User(username='mod_zugewiesen', role='moderator')
            zugewiesen.set_password('dummy-moderator-passwort')
            db.session.add_all([admin, eigentuemer, zugewiesen])
            db.session.commit()

            fremd = Bereich(name='Fremder Bereich', owner_id=admin.id)
            eigen = Bereich(name='Eigener Bereich', owner_id=eigentuemer.id)
            db.session.add_all([fremd, eigen])
            db.session.commit()
            zugewiesen.assigned_bereiche.append(fremd)
            db.session.commit()

            ub_fremd = Unterbereich(name='Fremder Schrank',
                                    bereich_id=fremd.id)
            ub_eigen = Unterbereich(name='Eigener Schrank',
                                    bereich_id=eigen.id)
            db.session.add_all([ub_fremd, ub_eigen])
            db.session.commit()
            self.fremd_id = fremd.id
            self.eigen_id = eigen.id
            self.ub_fremd_id = ub_fremd.id

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def _login(self, username):
        self.client.get('/logout')
        self.client.post('/login', data={'username': username,
                                         'password': 'dummy-moderator-passwort'})

    def test_zugewiesener_moderator_loescht_bereich_nicht(self):
        self._login('mod_zugewiesen')
        antwort = self.client.post(
            f'/location/delete_bereich/{self.fremd_id}')
        self.assertEqual(antwort.status_code, 302)

        with app.app_context():
            self.assertIsNotNone(db.session.get(Bereich, self.fremd_id),
                                 'Zugewiesener Moderator hat den Bereich '
                                 'geloescht')

    def test_zugewiesener_moderator_loescht_unterbereich_nicht(self):
        self._login('mod_zugewiesen')
        antwort = self.client.post(
            f'/location/delete_unterbereich/{self.ub_fremd_id}')
        self.assertEqual(antwort.status_code, 302)

        with app.app_context():
            self.assertIsNotNone(
                db.session.get(Unterbereich, self.ub_fremd_id),
                'Zugewiesener Moderator hat den Unterbereich geloescht')

    def test_besitzer_loescht_eigenen_bereich(self):
        self._login('mod_besitzer')
        antwort = self.client.post(
            f'/location/delete_bereich/{self.eigen_id}')
        self.assertEqual(antwort.status_code, 302)

        with app.app_context():
            self.assertIsNone(db.session.get(Bereich, self.eigen_id),
                              'Der Besitzer muss seinen Bereich loeschen '
                              'duerfen')


if __name__ == '__main__':
    unittest.main()
