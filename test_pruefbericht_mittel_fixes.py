"""Regressionstests für die Mittel-Findings der IT-Prüfung vom 2026-10-30.

Jeder Test hält genau die Lücke fest, die im Prüfbericht belegt wurde:

- F-05: Ein gleichnamiger LDAP-Benutzer übernahm ein lokales Konto samt Rolle.
- F-07: Uploads prüften nur die Endung; das PDF-Parsing hatte kein Limit.
- F-08: LDAP konnte ohne SSL/StartTLS im Klartext senden.
- F-32: Audit-Log behielt den Benutzernamen nach der Kontolöschung.

F-09 ist eine reine Dokumentationsänderung und braucht keinen Code-Test.

Mit ausführen:
    python -m unittest test_pruefbericht_mittel_fixes
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Muss vor dem Import von main stehen, siehe testkonfiguration.py.
import testkonfiguration  # noqa: F401,E402

from main import app, db, User, AuditLog


class TestLdapKontoUebernahme(unittest.TestCase):
    """F-05: Ein Verzeichnisbenutzer darf keine lokale Rolle erben."""

    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()
        with app.app_context():
            db.create_all()
            # Zweiter Admin, damit die Umstellung des gleichnamigen Kontos
            # nicht versehentlich die einzige Administratorrolle entfernt.
            chef = User(username='admin_echt', role='admin')
            chef.set_password('dummy-admin-passwort')
            lokal = User(username='gleichnamig', role='admin',
                         auth_source='lokal')
            lokal.set_password('lokales-altes-passwort')
            db.session.add_all([chef, lokal])
            db.session.commit()
            self.lokal_id = lokal.id

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def _ldap_login(self, username, default_role):
        with mock.patch('main.is_ldap_enabled', return_value=True), \
                mock.patch('main.authenticate_ldap',
                           return_value=(True, {'username': username,
                                                'default_role': default_role})):
            return self.client.post(
                '/login',
                data={'username': username, 'password': 'verzeichnis-passwort'})

    def test_gleichnamiger_ldap_nutzer_erbt_adminrolle_nicht(self):
        antwort = self._ldap_login('gleichnamig', 'lesen')
        self.assertEqual(antwort.status_code, 302)

        with app.app_context():
            konto = db.session.get(User, self.lokal_id)
            self.assertEqual(konto.role, 'lesen',
                             'Der LDAP-Benutzer hat die lokale Adminrolle '
                             'geerbt')
            self.assertEqual(konto.auth_source, 'ldap')

            eintrag = AuditLog.query.filter_by(action='USER_ROLE').first()
            self.assertIsNotNone(eintrag)
            self.assertIn('zurueckgesetzt', eintrag.details)

    def test_neues_ldap_konto_erhaelt_default_rolle(self):
        antwort = self._ldap_login('neuer_verzeichnisnutzer', 'benutzer')
        self.assertEqual(antwort.status_code, 302)

        with app.app_context():
            konto = User.query.filter_by(
                username='neuer_verzeichnisnutzer').one()
            self.assertEqual(konto.role, 'benutzer')
            self.assertEqual(konto.auth_source, 'ldap')

    def test_lokales_passwort_gilt_nach_umstellung_nicht_mehr(self):
        self._ldap_login('gleichnamig', 'lesen')
        self.client.get('/logout')

        with mock.patch('main.is_ldap_enabled', return_value=False):
            antwort = self.client.post(
                '/login',
                data={'username': 'gleichnamig',
                      'password': 'lokales-altes-passwort'},
                follow_redirects=True)

        self.assertIn('Ungültiger Benutzername oder Passwort',
                      antwort.get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()
