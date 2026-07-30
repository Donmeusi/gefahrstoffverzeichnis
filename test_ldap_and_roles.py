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

if __name__ == '__main__':
    unittest.main()
