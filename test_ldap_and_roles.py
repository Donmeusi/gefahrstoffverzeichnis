import unittest
import os
import sys
from html import unescape

# Ensure app directory is on path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Muss vor dem Import von main stehen: der Datenbank-Engine wird beim Import
# erzeugt. Ohne diese Zeile liefen create_all() und drop_all() gegen die echte
# data/gefahrstoffe.db. Siehe testkonfiguration.py.
import testkonfiguration  # noqa: F401,E402

from main import app, db, User, Bereich, Unterbereich, Gefahrstoff
from ldap_auth import is_ldap_enabled, get_ldap_config, authenticate_ldap

class TestLdapAndRoles(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        # Kein SQLALCHEMY_DATABASE_URI hier: das hätte keine Wirkung, der
        # Engine steht seit dem Import. Die Isolation kommt aus
        # testkonfiguration.py (APP_DATA_DIR -> /tmp).
        self.client = app.test_client()
        with app.app_context():
            db.create_all()

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def test_user_role_properties(self):
        with app.app_context():
            admin = User(username='admin_test', role='admin')
            mod = User(username='mod_test', role='moderator')
            user = User(username='user_test', role='benutzer')
            leser = User(username='leser_test', role='lesen')

            self.assertTrue(admin.is_admin)
            self.assertTrue(admin.can_write)
            self.assertFalse(admin.is_leser)

            self.assertTrue(mod.is_mod_or_admin)
            self.assertTrue(mod.can_write)
            self.assertFalse(mod.is_leser)

            self.assertFalse(user.is_admin)
            self.assertTrue(user.can_write)
            self.assertFalse(user.is_leser)

            self.assertFalse(leser.is_admin)
            self.assertFalse(leser.can_write)
            self.assertTrue(leser.is_leser)

    def test_ldap_module_initialization(self):
        self.assertFalse(is_ldap_enabled())
        cfg = get_ldap_config()
        self.assertEqual(cfg['default_role'], 'lesen')

        # Test LDAP auth disabled
        success, msg = authenticate_ldap('testuser', 'testpass')
        self.assertFalse(success)

    def test_read_only_role_access_restrictions(self):
        with app.app_context():
            leser = User(username='leser_account', role='lesen')
            leser.set_password('pass123')
            db.session.add(leser)
            db.session.commit()

            # Login as leser
            self.client.post('/login', data={'username': 'leser_account', 'password': 'pass123'}, follow_redirects=True)

            # Test write route /add
            res_add = self.client.get('/add', follow_redirects=True)
            self.assertIn('Keine Schreibberechtigung', res_add.get_data(as_text=True))

            # Test export route /export/excel
            res_excel = self.client.get('/export/excel', follow_redirects=True)
            self.assertIn('Keine Berechtigung zum Exportieren', res_excel.get_data(as_text=True))

            # Test export route /export/pdf
            res_pdf = self.client.get('/export/pdf', follow_redirects=True)
            self.assertIn('Keine Berechtigung zum Exportieren', res_pdf.get_data(as_text=True))

    def test_location_print_and_inventur(self):
        with app.app_context():
            admin = User(username='admin_inv', role='admin')
            admin.set_password('pass123')
            db.session.add(admin)
            db.session.commit()

            bereich = Bereich(name='Hauptlabor', owner_id=admin.id)
            db.session.add(bereich)
            db.session.commit()

            unterbereich = Unterbereich(name='Giftschrank A', bereich_id=bereich.id)
            db.session.add(unterbereich)
            db.session.commit()

            stoff = Gefahrstoff(
                name='Ethanol 99%',
                cas_nummer='64-17-5',
                menge=5.0,
                mengeneinheit='L',
                unterbereich_id=unterbereich.id,
                user_id=admin.id
            )
            db.session.add(stoff)
            db.session.commit()

            self.client.post('/login', data={'username': 'admin_inv', 'password': 'pass123'}, follow_redirects=True)

            # Test Print View
            res_print = self.client.get(f'/location/{unterbereich.id}/print')
            self.assertEqual(res_print.status_code, 200)
            self.assertIn('Ethanol 99%', res_print.get_data(as_text=True))

            # Test Inventur GET
            res_inv_get = self.client.get(f'/location/{unterbereich.id}/inventur')
            self.assertEqual(res_inv_get.status_code, 200)
            self.assertIn('Ethanol 99%', res_inv_get.get_data(as_text=True))

            # Test Inventur POST
            res_inv_post = self.client.post(f'/location/{unterbereich.id}/inventur', data={
                f'checked_{stoff.id}': '1',
                f'menge_{stoff.id}': '4.5'
            }, follow_redirects=True)
            self.assertEqual(res_inv_post.status_code, 200)

            updated_stoff = Gefahrstoff.query.get(stoff.id)
            self.assertEqual(updated_stoff.menge, 4.5)
            self.assertIsNotNone(updated_stoff.last_inventur_datum)
            self.assertEqual(updated_stoff.last_inventur_user_id, admin.id)

    # ── Regressionstests zur Rechteprüfung ───────────────────────────────────
    # Hintergrund: delete_user und locations prüften als einzige Stellen
    # `role == 'benutzer'` statt `role in ('benutzer', 'lesen')`. Die Rolle
    # 'lesen' - die niedrigste Stufe, und bei aktivem LDAP die Standardrolle
    # jedes neuen Verzeichnisbenutzers - fiel dadurch durch beide Prüfungen.

    def test_lesen_darf_keine_benutzer_loeschen(self):
        with app.app_context():
            leser = User(username='leser_del', role='lesen')
            leser.set_password('pass123')
            opfer = User(username='opfer_del', role='benutzer')
            opfer.set_password('pass123')
            chef = User(username='chef_del', role='admin')
            chef.set_password('pass123')
            db.session.add_all([leser, opfer, chef])
            db.session.commit()
            opfer_id, chef_id = opfer.id, chef.id

        self.client.post('/login', data={'username': 'leser_del', 'password': 'pass123'},
                         follow_redirects=True)

        res = self.client.post(f'/users/delete/{opfer_id}', follow_redirects=True)
        self.assertIn('Keine Berechtigung', res.get_data(as_text=True))
        # Der Admin wird zusätzlich geprüft: sein Name ist bewusst NICHT 'admin',
        # sonst hätte die reine Namensprüfung den Test bestanden.
        self.client.post(f'/users/delete/{chef_id}', follow_redirects=True)

        with app.app_context():
            self.assertIsNotNone(User.query.get(opfer_id),
                                 'Die Rolle "lesen" darf keinen Benutzer löschen')
            self.assertIsNotNone(User.query.get(chef_id),
                                 'Die Rolle "lesen" darf keinen Administrator löschen')

    def test_lesen_hat_keinen_zugriff_auf_standorte(self):
        with app.app_context():
            leser = User(username='leser_loc', role='lesen')
            leser.set_password('pass123')
            db.session.add(leser)
            db.session.commit()

        self.client.post('/login', data={'username': 'leser_loc', 'password': 'pass123'},
                         follow_redirects=True)

        res = self.client.get('/locations', follow_redirects=True)
        self.assertIn('Keine Berechtigung für die Standortverwaltung',
                      res.get_data(as_text=True))

        # Der Zweig action=add_bereich prüft selbst keine Berechtigung - er war
        # nur durch die (lückenhafte) Prüfung am Routenanfang geschützt.
        self.client.post('/locations',
                         data={'action': 'add_bereich', 'bereich_name': 'VOM_LESER'},
                         follow_redirects=True)
        with app.app_context():
            self.assertIsNone(Bereich.query.filter_by(name='VOM_LESER').first(),
                              'Die Rolle "lesen" darf keine Bereiche anlegen')

    def test_letzter_admin_kann_sich_nicht_degradieren(self):
        # Der erste Administrator entsteht über /register mit frei gewähltem
        # Namen; /register ist danach deaktiviert. Ohne Rollenschutz wäre die
        # Verwaltung nach einer Selbstdegradierung unerreichbar.
        with app.app_context():
            chef = User(username='nur_ein_admin', role='admin')
            chef.set_password('pass123')
            db.session.add(chef)
            db.session.commit()
            chef_id = chef.id

        self.client.post('/login', data={'username': 'nur_ein_admin', 'password': 'pass123'},
                         follow_redirects=True)

        res = self.client.post(f'/users/set_role/{chef_id}', data={'role': 'benutzer'},
                               follow_redirects=True)
        self.assertIn('Der letzte Administrator kann nicht degradiert werden',
                      res.get_data(as_text=True))

        res = self.client.post(f'/users/edit/{chef_id}',
                               data={'username': 'nur_ein_admin', 'role': 'benutzer'},
                               follow_redirects=True)
        self.assertIn('Der letzte Administrator kann nicht degradiert werden',
                      res.get_data(as_text=True))

        with app.app_context():
            self.assertEqual(User.query.get(chef_id).role, 'admin')
            self.assertEqual(User.query.filter_by(role='admin').count(), 1)

    def test_moderator_kann_administrator_nicht_degradieren(self):
        # Ein Administrator kann einen vom Moderator angelegten Benutzer später
        # zum Administrator machen. Über created_by bleibt der Moderator dann
        # "Eigentümer" eines Kontos, das er nicht verwalten dürfen soll.
        with app.app_context():
            mod = User(username='mod_esc', role='moderator')
            mod.set_password('pass123')
            db.session.add(mod)
            db.session.commit()
            befoerdert = User(username='befoerdert', role='admin', created_by=mod.id)
            befoerdert.set_password('pass123')
            # Zweiter Administrator, damit nicht der Last-Admin-Schutz greift,
            # sondern tatsächlich die neue Rollenprüfung geprüft wird.
            zweiter = User(username='zweiter_admin', role='admin')
            zweiter.set_password('pass123')
            db.session.add_all([befoerdert, zweiter])
            db.session.commit()
            befoerdert_id = befoerdert.id

        self.client.post('/login', data={'username': 'mod_esc', 'password': 'pass123'},
                         follow_redirects=True)

        res = self.client.post(f'/users/set_role/{befoerdert_id}', data={'role': 'benutzer'},
                               follow_redirects=True)
        self.assertIn('Administratoren können nur von Administratoren geändert werden',
                      res.get_data(as_text=True))

        with app.app_context():
            self.assertEqual(User.query.get(befoerdert_id).role, 'admin')

    def test_admin_darf_weiterhin_verwalten(self):
        # Gegenprobe: die neuen Prüfungen dürfen die normale Verwaltung nicht
        # blockieren. Zwei Administratoren, einer degradiert den anderen.
        with app.app_context():
            chef1 = User(username='chef_eins', role='admin')
            chef1.set_password('pass123')
            chef2 = User(username='chef_zwei', role='admin')
            chef2.set_password('pass123')
            db.session.add_all([chef1, chef2])
            db.session.commit()
            chef2_id = chef2.id

        self.client.post('/login', data={'username': 'chef_eins', 'password': 'pass123'},
                         follow_redirects=True)

        res = self.client.post(f'/users/set_role/{chef2_id}', data={'role': 'moderator'},
                               follow_redirects=True)
        # unescape: die Flash-Meldung enthält Anführungszeichen, die im HTML als
        # &#34; ankommen.
        self.assertIn('Rolle von "chef_zwei" auf "moderator" gesetzt',
                      unescape(res.get_data(as_text=True)))
        with app.app_context():
            self.assertEqual(User.query.get(chef2_id).role, 'moderator')

if __name__ == '__main__':
    unittest.main()
