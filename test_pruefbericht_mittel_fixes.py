"""Regressionstests für die Mittel-Findings der IT-Prüfung vom 2026-10-30.

Jeder Test hält genau die Lücke fest, die im Prüfbericht belegt wurde:

- F-05: Ein gleichnamiger LDAP-Benutzer übernahm ein lokales Konto samt Rolle.
- F-07: Uploads prüften nur die Endung; das PDF-Parsing hatte kein Limit.
- F-08: LDAP konnte ohne SSL/StartTLS im Klartext senden.
- F-32: Audit-Log behielt den Benutzernamen nach der Kontolöschung.

F-09 betrifft die Datenschutzdokumentation. Ein Test hält fest, dass die
ausgehenden Verbindungen dort genannt bleiben und PubChem nicht mehr als
einzige Verbindung bezeichnet wird.

Mit ausführen:
    python -m unittest test_pruefbericht_mittel_fixes
"""
import hashlib
import os
import sys
import unittest
from io import BytesIO
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Muss vor dem Import von main stehen, siehe testkonfiguration.py.
import testkonfiguration  # noqa: F401,E402

from main import (app, db, User, AuditLog, Bereich, Unterbereich,
                  Gefahrstoff, PDF_MAX_SEITEN, signatur_passt,
                  log_audit_event)
import ldap_auth


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


class _FakeConnection:
    """Ersetzt ldap3.Connection; zeichnet auto_bind und Bind-Aufrufe auf."""

    aufrufe = []

    def __init__(self, server, user=None, password=None, auto_bind=False,
                 **kwargs):
        self.server = server
        self.user = user
        self.password = password
        self.auto_bind = auto_bind
        self.unbound = False
        _FakeConnection.aufrufe.append(self)

    def unbind(self):
        self.unbound = True


class TestLdapTransport(unittest.TestCase):
    """F-08: LDAP darf nicht im Klartext senden."""

    def setUp(self):
        _FakeConnection.aufrufe.clear()

    def _env(self, **werte):
        basis = {
            'LDAP_ENABLED': 'true',
            'LDAP_HOST': 'ldap.example',
            'LDAP_PORT': '389',
            'LDAP_USE_SSL': 'false',
            'LDAP_START_TLS': 'true',
            'LDAP_USER_DN_TEMPLATE': 'uid={username},dc=example,dc=org',
            'LDAP_REQUIRE_CERT': 'true',
        }
        basis.update(werte)
        return basis

    def test_starttls_wird_vor_dem_bind_angefragt(self):
        with mock.patch.dict(os.environ, self._env(), clear=True), \
                mock.patch.object(ldap_auth, 'Connection', _FakeConnection):
            erfolg, info = ldap_auth.authenticate_ldap('anna', 'geheim')

        self.assertTrue(erfolg)
        self.assertEqual(len(_FakeConnection.aufrufe), 1)
        self.assertEqual(_FakeConnection.aufrufe[0].auto_bind,
                         ldap_auth.AUTO_BIND_TLS_BEFORE_BIND)
        self.assertEqual(info['default_role'], 'lesen')

    def test_ohne_ssl_und_starttls_wird_der_login_verweigert(self):
        env = self._env(LDAP_START_TLS='false')
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(ldap_auth, 'Connection', _FakeConnection):
            erfolg, meldung = ldap_auth.authenticate_ldap('anna', 'geheim')

        self.assertFalse(erfolg)
        self.assertIn('verweigert', meldung)
        self.assertEqual(_FakeConnection.aufrufe, [],
                         'Ohne TLS darf keine Verbindung aufgebaut werden')

    def test_ssl_bleibt_der_standard(self):
        with mock.patch.dict(os.environ, self._env(
                LDAP_PORT='636', LDAP_USE_SSL='true',
                LDAP_START_TLS='false'), clear=True):
            cfg = ldap_auth.get_ldap_config()
        self.assertTrue(cfg['use_ssl'])

    def test_starttls_ist_standard_bei_ldap_auf_port_389(self):
        with mock.patch.dict(os.environ, {'LDAP_USE_SSL': 'false'},
                             clear=True):
            cfg = ldap_auth.get_ldap_config()
        self.assertTrue(cfg['start_tls'])

    def test_startup_warnung_ohne_tls(self):
        env = self._env(LDAP_START_TLS='false')
        with mock.patch.dict(os.environ, env, clear=True), \
                self.assertLogs(ldap_auth.logger, level='WARNING') as protokoll:
            ldap_auth.pruefe_transport_konfiguration()

        self.assertTrue(any('ohne Transportverschluesselung' in zeile
                            for zeile in protokoll.output))


class TestAuditPseudonymisierung(unittest.TestCase):
    """F-32: Nach der Kontolöschung darf kein Klartextname bleiben."""

    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()
        with app.app_context():
            db.create_all()
            admin = User(username='admin_a', role='admin')
            admin.set_password('dummy-admin-passwort')
            ziel = User(username='temp_loesch', role='benutzer')
            ziel.set_password('dummy-benutzer-passwort')
            control = User(username='temp_loesch2', role='benutzer')
            control.set_password('dummy-benutzer-passwort')
            db.session.add_all([admin, ziel, control])
            db.session.commit()
            self.admin_id = admin.id
            self.ziel_id = ziel.id

            log_audit_event(
                'USER_CREATE', 'User', ziel.id,
                'Benutzer "temp_loesch" angelegt (Rolle: benutzer).',
                user_id=admin.id)
            log_audit_event(
                'USER_ROLE', 'User', ziel.id,
                'Rolle von "temp_loesch" von "benutzer" auf "lesen" geändert.',
                user_id=admin.id)
            # Kontrolle: Ein ähnlicher Name eines anderen Kontos bleibt stehen.
            log_audit_event(
                'USER_CREATE', 'User', control.id,
                'Benutzer "temp_loesch2" angelegt (Rolle: benutzer).',
                user_id=admin.id)
            self.zeitstempel = {
                eintrag.id: eintrag.timestamp
                for eintrag in AuditLog.query.all()
            }

        self.client.post('/login', data={'username': 'admin_a',
                                         'password': 'dummy-admin-passwort'})

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def _details(self):
        return ' | '.join(eintrag.details or ''
                          for eintrag in AuditLog.query.all())

    def test_klartextname_verschwindet_aus_dem_audit_log(self):
        # Der Login des Administrators schreibt selbst einen Eintrag. Die
        # Zahl wird deshalb erst unmittelbar vor dem Löschen erhoben.
        with app.app_context():
            anzahl_vorher = AuditLog.query.count()

        antwort = self.client.post(f'/users/delete/{self.ziel_id}')
        self.assertEqual(antwort.status_code, 302)

        with app.app_context():
            details = self._details()
            self.assertNotIn('"temp_loesch"', details,
                             'Der geloeschte Benutzername steht noch im '
                             'Audit-Log')
            pseudonym = ('gelöschter Nutzer '
                         + hashlib.sha256(b'temp_loesch').hexdigest()[:8])
            self.assertIn(pseudonym, details)

            # Der Loescheintrag selbst bleibt erhalten ...
            self.assertIsNotNone(
                AuditLog.query.filter_by(action='USER_DELETE').first())
            # ... und die Anzahl steigt nur um genau diesen einen Eintrag.
            self.assertEqual(AuditLog.query.count(), anzahl_vorher + 1)

    def test_aehnlicher_name_bleibt_erhalten(self):
        self.client.post(f'/users/delete/{self.ziel_id}')

        with app.app_context():
            self.assertIn('"temp_loesch2"', self._details())

    def test_frueherer_name_verschwindet_ebenfalls(self):
        # Wer vor der Löschung umbenannt wurde, trägt den alten Namen in
        # älteren Einträgen und in der Umbenennungszeile selbst. Auch er darf
        # nicht im Klartext zurückbleiben.
        with app.app_context():
            log_audit_event(
                'USER_UPDATE', 'User', self.ziel_id,
                'Benutzername "temp_alt" -> "temp_loesch"',
                user_id=self.admin_id)

        self.client.post(f'/users/delete/{self.ziel_id}')

        with app.app_context():
            details = self._details()
            self.assertNotIn('"temp_alt"', details)
            pseudonym = ('gelöschter Nutzer '
                         + hashlib.sha256(b'temp_alt').hexdigest()[:8])
            self.assertIn(pseudonym, details)

    def test_zeitstempel_bleiben_unveraendert(self):
        self.client.post(f'/users/delete/{self.ziel_id}')

        with app.app_context():
            for eintrag in AuditLog.query.all():
                if eintrag.id in self.zeitstempel:
                    self.assertEqual(eintrag.timestamp,
                                     self.zeitstempel[eintrag.id],
                                     'Die Pseudonymisierung hat den '
                                     'Zeitstempel veraendert')


class TestDatenschutzdoku(unittest.TestCase):
    """F-09: Alle ausgehenden Verbindungen stehen in der Datenschutzdoku."""

    @classmethod
    def setUpClass(cls):
        pfad = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'DATENSCHUTZ_UND_TOM.md')
        with open(pfad, encoding='utf-8') as datei:
            cls.doku = datei.read()
        # Abschnitt 3.3 beschreibt die externen Datenabfragen.
        cls.abschnitt = cls.doku.split('### 3.3', 1)[1].split('### 3.4', 1)[0]

    def test_wikidata_ist_als_verarbeitungstaetigkeit_dokumentiert(self):
        self.assertIn('Wikidata', self.abschnitt)
        self.assertIn('SPARQL', self.abschnitt)
        self.assertIn('CAS', self.abschnitt)

    def test_github_fetch_ist_als_verarbeitungstaetigkeit_dokumentiert(self):
        self.assertIn('GitHub', self.abschnitt)
        self.assertIn('git fetch', self.abschnitt)

    def test_pubchem_ist_nicht_mehr_die_einzige_verbindung(self):
        self.assertNotIn(
            'Die einzige ausgehende Verbindung ist das vom Nutzer '
            'ausgelöste PubChem-Autofill', self.doku)


if __name__ == '__main__':
    unittest.main()
