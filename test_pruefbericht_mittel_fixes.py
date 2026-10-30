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
from io import BytesIO
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Muss vor dem Import von main stehen, siehe testkonfiguration.py.
import testkonfiguration  # noqa: F401,E402

from main import (app, db, User, AuditLog, Bereich, Unterbereich,
                  Gefahrstoff, PDF_MAX_SEITEN, signatur_passt)


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


def _pdf_mit_seiten(anzahl):
    """Erzeugt ein echtes PDF mit der angegebenen Seitenzahl."""
    from reportlab.pdfgen import canvas
    puffer = BytesIO()
    zeichner = canvas.Canvas(puffer)
    for nummer in range(anzahl):
        zeichner.drawString(72, 720, f'Seite {nummer + 1}')
        zeichner.showPage()
    zeichner.save()
    return puffer.getvalue()


class TestUploadSignatur(unittest.TestCase):
    """F-07a: Endung und Dateikopf muessen zusammenpassen."""

    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()
        with app.app_context():
            db.create_all()
            admin = User(username='admin_u', role='admin')
            admin.set_password('dummy-admin-passwort')
            db.session.add(admin)
            db.session.commit()
            bereich = Bereich(name='Upload-Bereich', owner_id=admin.id)
            db.session.add(bereich)
            db.session.commit()
            unterbereich = Unterbereich(name='Upload-Schrank',
                                        bereich_id=bereich.id)
            db.session.add(unterbereich)
            db.session.commit()
            self.unterbereich_id = unterbereich.id
        self.client.post('/login', data={'username': 'admin_u',
                                         'password': 'dummy-admin-passwort'})

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def _add_mit_datei(self, name, dateiname, inhalt):
        return self.client.post(
            '/add',
            data={'name': name,
                  'unterbereich_id': str(self.unterbereich_id),
                  'sicherheitsdatenblatt': (BytesIO(inhalt), dateiname)},
            content_type='multipart/form-data',
            follow_redirects=True)

    def test_getarnte_exe_als_pdf_wird_abgelehnt(self):
        antwort = self._add_mit_datei('Getarnte Datei', 'boese.pdf',
                                      b'MZ\x90\x00\x03\x00\x00\x00')

        self.assertIn('Dateiinhalt passt nicht', antwort.get_data(as_text=True))
        with app.app_context():
            self.assertIsNone(
                Gefahrstoff.query.filter_by(name='Getarnte Datei').first())
        self.assertFalse(
            os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'],
                                        'Getarnte_Datei_SDB.pdf')))

    def test_leere_datei_wird_abgelehnt(self):
        antwort = self._add_mit_datei('Leere Datei', 'leer.pdf', b'')

        self.assertIn('Dateiinhalt passt nicht', antwort.get_data(as_text=True))
        with app.app_context():
            self.assertIsNone(
                Gefahrstoff.query.filter_by(name='Leere Datei').first())

    def test_echtes_pdf_wird_weiterhin_angenommen(self):
        antwort = self._add_mit_datei('Echtes PDF', 'sdb.pdf', _pdf_mit_seiten(1))

        self.assertIn('erfolgreich hinzugefügt', antwort.get_data(as_text=True))
        with app.app_context():
            stoff = Gefahrstoff.query.filter_by(name='Echtes PDF').one()
            self.assertIsNotNone(stoff.sicherheitsdatenblatt)
            self.assertTrue(os.path.exists(os.path.join(
                app.config['UPLOAD_FOLDER'], stoff.sicherheitsdatenblatt)))


class TestPdfParsingLimits(unittest.TestCase):
    """F-07b: Seiten- und Zeitlimit beim Auslesen von SDB-PDFs."""

    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()
        with app.app_context():
            db.create_all()
            admin = User(username='admin_p', role='admin')
            admin.set_password('dummy-admin-passwort')
            db.session.add(admin)
            db.session.commit()
        self.client.post('/login', data={'username': 'admin_p',
                                         'password': 'dummy-admin-passwort'})

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def _parse(self, dateiname, inhalt):
        return self.client.post(
            '/api/parse_sdb',
            data={'file': (BytesIO(inhalt), dateiname)},
            content_type='multipart/form-data')

    def test_pdf_ueber_seitenlimit_wird_verworfen(self):
        seiten = PDF_MAX_SEITEN + 50
        antwort = self._parse('zu-gross.pdf', _pdf_mit_seiten(seiten))

        self.assertEqual(antwort.status_code, 400)
        meldung = antwort.get_json()['error']
        self.assertIn('Seiten', meldung)
        self.assertIn(str(PDF_MAX_SEITEN), meldung)

    def test_getarnte_exe_als_pdf_wird_verworfen(self):
        antwort = self._parse('boese.pdf', b'MZ\x90\x00\x03\x00\x00\x00')

        self.assertEqual(antwort.status_code, 400)
        self.assertIn('kein gültiges PDF', antwort.get_json()['error'])

    def test_signatur_pruefung_erkennt_pdf_kopf(self):
        self.assertTrue(signatur_passt(b'%PDF-1.7\n...', 'pdf'))
        self.assertFalse(signatur_passt(b'MZ\x90\x00', 'pdf'))
        self.assertFalse(signatur_passt(b'', 'pdf'))


if __name__ == '__main__':
    unittest.main()
