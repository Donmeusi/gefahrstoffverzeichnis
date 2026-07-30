import unittest
import os
import sys

# Ensure app directory is on path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from main import app, db, User, Bereich, Unterbereich, Gefahrstoff
from ldap_auth import is_ldap_enabled, get_ldap_config, authenticate_ldap

class TestLdapAndRoles(unittest.TestCase):
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

if __name__ == '__main__':
    unittest.main()
