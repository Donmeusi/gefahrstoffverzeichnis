"""Tests für die Systemhistorie (Audit Log).

Hintergrund: Bis v3.10 schrieb die Benutzerverwaltung überhaupt keine Einträge -
weder Anlegen noch Rollenwechsel, Bearbeitung, Löschen oder Bereichszuweisung.
Damit war im Nachhinein nicht feststellbar, wer wann Rechte geändert oder ein
Konto entfernt hatte. Diese Datei hält fest, dass jede dieser Aktionen einen
Eintrag erzeugt und was darin stehen muss.

Mit ausführen:
    /tmp/gsv-venv/bin/python -W ignore::ResourceWarning test_audit_log.py
"""
import unittest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from main import app, db, User, Bereich, AuditLog


class TestAuditLog(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.client = app.test_client()
        with app.app_context():
            db.create_all()

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def _login_admin(self, username='chef_audit'):
        """Legt einen Administrator an, meldet ihn an und gibt seine ID zurück."""
        with app.app_context():
            admin = User(username=username, role='admin')
            admin.set_password('pass123')
            db.session.add(admin)
            db.session.commit()
            admin_id = admin.id
        self.client.post('/login', data={'username': username, 'password': 'pass123'},
                         follow_redirects=True)
        return admin_id

    def _benutzer_anlegen(self, username, role='benutzer'):
        with app.app_context():
            user = User(username=username, role=role)
            user.set_password('pass123')
            db.session.add(user)
            db.session.commit()
            return user.id

    # ── Anlegen ──────────────────────────────────────────────────────────────

    def test_create_user_schreibt_audit_eintrag(self):
        self._login_admin()
        self.client.post('/users/create',
                         data={'username': 'neu_audit', 'password': 'geheim123',
                               'role': 'benutzer'},
                         follow_redirects=True)

        with app.app_context():
            ziel = User.query.filter_by(username='neu_audit').first()
            self.assertIsNotNone(ziel, 'Der Benutzer sollte angelegt sein')
            eintrag = AuditLog.query.filter_by(action='USER_CREATE').first()
            self.assertIsNotNone(eintrag, 'Das Anlegen muss in der Historie stehen')
            self.assertEqual(eintrag.entity_type, 'User')
            self.assertEqual(eintrag.entity_id, ziel.id)
            self.assertIn('neu_audit', eintrag.details)
            self.assertIn('benutzer', eintrag.details)
            # Wer gehandelt hat, muss erkennbar sein
            self.assertEqual(eintrag.user.username, 'chef_audit')

    def test_erster_admin_wird_korrekt_protokolliert(self):
        # Regression: der Aufruf lautete log_audit_event(user.id, "USER_CREATE",
        # "<Satz>") - eine Zahl stand als Aktion, der Satz in der Integer-Spalte
        # entity_id. Der Eintrag war damit unbrauchbar.
        self.client.post('/register',
                         data={'username': 'erster_admin', 'password': 'geheim123'},
                         follow_redirects=True)

        with app.app_context():
            eintrag = AuditLog.query.filter_by(action='USER_CREATE').first()
            self.assertIsNotNone(eintrag, 'Die Registrierung muss in der Historie stehen')
            self.assertEqual(eintrag.entity_type, 'User')
            admin = User.query.filter_by(username='erster_admin').first()
            self.assertEqual(eintrag.entity_id, admin.id)
            # current_user ist beim Registrieren noch anonym; der Eintrag muss
            # trotzdem dem neuen Administrator zugeordnet sein.
            self.assertEqual(eintrag.user_id, admin.id)

    # ── Rolle ────────────────────────────────────────────────────────────────

    def test_rollenwechsel_haelt_alte_und_neue_rolle_fest(self):
        self._login_admin()
        zid = self._benutzer_anlegen('rollen_ziel', role='benutzer')

        self.client.post(f'/users/set_role/{zid}', data={'role': 'lesen'},
                         follow_redirects=True)

        with app.app_context():
            eintrag = AuditLog.query.filter_by(action='USER_ROLE').first()
            self.assertIsNotNone(eintrag, 'Der Rollenwechsel muss protokolliert werden')
            self.assertEqual(eintrag.entity_id, zid)
            # Beide Rollen: ohne die alte ist nicht nachvollziehbar, was vorher galt
            self.assertIn('benutzer', eintrag.details)
            self.assertIn('lesen', eintrag.details)

    # ── Bearbeiten ───────────────────────────────────────────────────────────

    def test_edit_haelt_die_geaenderten_felder_fest(self):
        self._login_admin()
        zid = self._benutzer_anlegen('edit_ziel', role='benutzer')

        self.client.post(f'/users/edit/{zid}',
                         data={'username': 'edit_ziel_neu', 'role': 'moderator'},
                         follow_redirects=True)

        with app.app_context():
            eintrag = AuditLog.query.filter_by(action='USER_UPDATE').first()
            self.assertIsNotNone(eintrag, 'Die Bearbeitung muss protokolliert werden')
            self.assertIn('edit_ziel', eintrag.details)
            self.assertIn('edit_ziel_neu', eintrag.details)
            self.assertIn('moderator', eintrag.details)

    def test_edit_ohne_aenderung_wird_als_solche_vermerkt(self):
        self._login_admin()
        zid = self._benutzer_anlegen('unveraendert', role='benutzer')

        self.client.post(f'/users/edit/{zid}',
                         data={'username': 'unveraendert', 'role': 'benutzer'},
                         follow_redirects=True)

        with app.app_context():
            eintrag = AuditLog.query.filter_by(action='USER_UPDATE').first()
            self.assertIsNotNone(eintrag)
            self.assertIn('Ohne inhaltliche', eintrag.details)

    # ── Löschen ──────────────────────────────────────────────────────────────

    def test_benutzer_loeschen_haelt_den_namen_fest(self):
        self._login_admin()
        zid = self._benutzer_anlegen('weg_damit', role='benutzer')

        self.client.post(f'/users/delete/{zid}', follow_redirects=True)

        with app.app_context():
            self.assertIsNone(User.query.filter_by(username='weg_damit').first(),
                              'Der Benutzer sollte gelöscht sein')
            eintrag = AuditLog.query.filter_by(action='USER_DELETE').first()
            self.assertIsNotNone(eintrag, 'Das Löschen muss protokolliert werden')
            self.assertEqual(eintrag.entity_id, zid)
            # Die Zeile ist weg - der Name kann nur aus dem Eintrag selbst kommen
            self.assertIn('weg_damit', eintrag.details)
            self.assertIn('benutzer', eintrag.details)

    # ── Bereichszuweisung ────────────────────────────────────────────────────

    def test_bereichszuweisung_wird_protokolliert(self):
        admin_id = self._login_admin()
        with app.app_context():
            bereich = Bereich(name='Audit-Labor', owner_id=admin_id)
            ziel = User(username='bereich_ziel', role='benutzer')
            ziel.set_password('pass123')
            db.session.add_all([bereich, ziel])
            db.session.commit()
            zid, bid = ziel.id, bereich.id

        self.client.post(f'/users/assign_bereiche/{zid}',
                         data={'bereich_ids': [str(bid)]}, follow_redirects=True)

        with app.app_context():
            eintrag = AuditLog.query.filter_by(action='USER_BEREICHE').first()
            self.assertIsNotNone(eintrag, 'Die Bereichszuweisung muss protokolliert werden')
            self.assertEqual(eintrag.entity_id, zid)
            self.assertIn('Audit-Labor', eintrag.details)
            # vorher -> nachher
            self.assertIn('keine', eintrag.details)

    # ── Anzeige ──────────────────────────────────────────────────────────────

    def test_historie_rendert_und_uebersetzt_die_aktionen(self):
        # Prüft zugleich, dass das Template fehlerfrei rendert - ein Jinja-Fehler
        # in audit_logs.html würde sonst erst im Betrieb auffallen.
        self._login_admin()
        zid = self._benutzer_anlegen('beschriftung', role='benutzer')
        self.client.post(f'/users/set_role/{zid}', data={'role': 'lesen'},
                         follow_redirects=True)
        self.client.post(f'/users/delete/{zid}', follow_redirects=True)

        res = self.client.get('/audit_logs')
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        # Die Aktionen erscheinen auf Deutsch, nicht als roher Code
        self.assertIn('Rolle geändert', html)
        self.assertIn('Benutzer gelöscht', html)
        self.assertNotIn('USER_ROLE', html)
        self.assertNotIn('USER_DELETE', html)

    # ── Keine Geheimnisse in der Historie ────────────────────────────────────

    def test_passwort_steht_nicht_in_der_historie(self):
        # Gegenstück zur Unterschrift: das Passwort ist personenbezogen und wird
        # als Ereignis vermerkt, nie im Klartext.
        self._login_admin()
        self.client.post('/users/create',
                         data={'username': 'pw_test', 'password': 'SuperGeheim123',
                               'role': 'benutzer'},
                         follow_redirects=True)

        zid = self._benutzer_anlegen('pw_ziel', role='benutzer')
        self.client.post(f'/users/edit/{zid}',
                         data={'username': 'pw_ziel', 'role': 'benutzer',
                               'password': 'NochGeheimer456'},
                         follow_redirects=True)

        with app.app_context():
            eintraege = AuditLog.query.all()
            self.assertTrue(eintraege, 'Es sollten Einträge existieren')
            for eintrag in eintraege:
                self.assertNotIn('SuperGeheim123', eintrag.details or '')
                self.assertNotIn('NochGeheimer456', eintrag.details or '')
            # Das Ereignis selbst muss aber vermerkt sein
            self.assertTrue(any('Passwort' in (e.details or '') for e in eintraege),
                            'Der Passwortwechsel sollte als Ereignis vermerkt sein')


if __name__ == '__main__':
    unittest.main()
