"""Regressionstests für die Befunde des Security-Audits vom 2026-10-28.

Jeder Test hält eine konkrete Lücke fest, die im Audit belegt wurde:

- /uploads/<filename> prüfte nur die Rolle, nicht den Bereich des Stoffes
  (IDOR: jedes Dokument an jeden angemeldeten Nicht-Leser).
- Passwort-Policy erlaubte vier Zeichen und prüfte bei der Neuanlage gar nicht.
- approve_stoff folgte einem protokollrelativen Ziel ('//evil.com').

Mit ausführen:
    python -m unittest test_sicherheitsfixes
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Muss vor dem Import von main stehen, siehe testkonfiguration.py.
import testkonfiguration  # noqa: F401,E402

from main import app, db, User, Bereich, Unterbereich, Gefahrstoff


class TestSicherheitsfixes(unittest.TestCase):
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

    # ── Hilfen ───────────────────────────────────────────────────────────────

    def _admin(self):
        """Legt einen Administrator an und meldet ihn an."""
        with app.app_context():
            admin = User(username='admin_s', role='admin')
            admin.set_password('dummy-admin-passwort')
            db.session.add(admin)
            db.session.commit()
            admin_id = admin.id
        self.client.post('/login',
                         data={'username': 'admin_s',
                               'password': 'dummy-admin-passwort'})
        return admin_id

    def _bereich_mit_stoff(self, name, datei, admin_id, freigegeben=True):
        """Bereich mit einem Unterbereich und einem Stoff samt Dokument."""
        with app.app_context():
            bereich = Bereich(name=name, owner_id=admin_id)
            db.session.add(bereich)
            db.session.commit()
            unterbereich = Unterbereich(name=f'{name}-Schrank',
                                        bereich_id=bereich.id)
            db.session.add(unterbereich)
            db.session.commit()
            stoff = Gefahrstoff(name=f'Stoff in {name}',
                                unterbereich_id=unterbereich.id,
                                user_id=admin_id,
                                sicherheitsdatenblatt=datei,
                                is_approved=freigegeben)
            db.session.add(stoff)
            db.session.commit()
            return bereich.id, stoff.id

    def _datei_anlegen(self, name):
        pfad = os.path.join(app.config['UPLOAD_FOLDER'], name)
        os.makedirs(os.path.dirname(pfad), exist_ok=True)
        with open(pfad, 'wb') as fh:
            fh.write(b'%PDF-1.4 Testinhalt')
        return pfad

    # ── IDOR auf /uploads ────────────────────────────────────────────────────

    def test_fremdes_dokument_ist_nicht_abrufbar(self):
        admin_id = self._admin()
        _, stoff_id = self._bereich_mit_stoff('Bereich A', 'A_SDB.pdf', admin_id)
        bereich_b_id, _ = self._bereich_mit_stoff('Bereich B', 'B_SDB.pdf',
                                                   admin_id)
        self._datei_anlegen('A_SDB.pdf')

        with app.app_context():
            benutzer = User(username='nur_b', role='benutzer')
            benutzer.set_password('dummy-benutzer-passwort')
            bereich_b = Bereich.query.get(bereich_b_id)
            benutzer.assigned_bereiche.append(bereich_b)
            db.session.add(benutzer)
            db.session.commit()

        # Erst abmelden: /login leitet um, solange noch eine Sitzung besteht.
        self.client.get('/logout')
        self.client.post('/login', data={'username': 'nur_b',
                                         'password': 'dummy-benutzer-passwort'})

        # Der fremde Stoff selbst ist gesperrt (je nach Route 302 oder 404) ...
        antwort = self.client.get(f'/gefahrstoff/{stoff_id}')
        self.assertIn(antwort.status_code, (302, 404))

        # ... sein Dokument darf es auch sein. Vor dem Fix lieferte diese
        # Anfrage 200 samt Dateiinhalt.
        antwort = self.client.get('/uploads/A_SDB.pdf')
        self.assertEqual(antwort.status_code, 404,
                         'Fremdes Dokument wurde ausgeliefert')

    def test_eigenes_dokument_bleibt_abrufbar(self):
        admin_id = self._admin()
        _, _ = self._bereich_mit_stoff('Bereich C', 'C_SDB.pdf', admin_id)
        self._datei_anlegen('C_SDB.pdf')

        antwort = self.client.get('/uploads/C_SDB.pdf')
        self.assertEqual(antwort.status_code, 200,
                         'Der Administrator muss eigene Dokumente abrufen können')

    def test_unbekannte_datei_bleibt_404(self):
        self._admin()
        self._datei_anlegen('verwaist.pdf')
        antwort = self.client.get('/uploads/verwaist.pdf')
        self.assertEqual(antwort.status_code, 404)

    # ── Passwort-Policy ──────────────────────────────────────────────────────

    def test_registrierung_lehnt_kurzes_passwort_ab(self):
        self.client.post('/register',
                         data={'username': 'erster', 'password': 'kurz'},
                         follow_redirects=True)
        with app.app_context():
            self.assertIsNone(User.query.filter_by(username='erster').first(),
                              'Kurzes Passwort darf kein Konto anlegen')

    def test_registrierung_nimmt_langes_passwort_an(self):
        self.client.post('/register',
                         data={'username': 'erster',
                               'password': 'dummy-langes-passwort'},
                         follow_redirects=True)
        with app.app_context():
            self.assertIsNotNone(User.query.filter_by(username='erster').first())

    def test_benutzeranlage_lehnt_kurzes_passwort_ab(self):
        self._admin()
        self.client.post('/users/create',
                         data={'username': 'neu', 'password': 'kurz',
                               'role': 'benutzer'},
                         follow_redirects=True)
        with app.app_context():
            self.assertIsNone(User.query.filter_by(username='neu').first())

    # ── Open Redirect ───────────────────────────────────────────────────────

    def test_approve_ignoriert_protokollrelatives_ziel(self):
        admin_id = self._admin()
        _, stoff_id = self._bereich_mit_stoff('Bereich D', 'D_SDB.pdf',
                                              admin_id, freigegeben=False)

        antwort = self.client.post(f'/approve/{stoff_id}',
                                   data={'next': '//evil.example'})
        ziel = antwort.headers.get('Location', '')
        self.assertNotIn('evil.example', ziel,
                         'Protokollrelatives Ziel wurde übernommen')
