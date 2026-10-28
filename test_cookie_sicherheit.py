"""Tests für das Secure-Flag des Sitzungscookies.

Ausgangslage: Die Anwendung setzte SESSION_COOKIE_SECURE in Produktion
immer auf True. Damit war sie im LAN über HTTP nicht benutzbar — der
Browser verwirft ein Secure-Cookie, das über HTTP kommt, und die
Anmeldung scheiterte, obwohl die Zugangsdaten stimmten. Zugleich darf
die Flagge bei HTTPS nicht fehlen.

Die Anwendung entscheidet deshalb pro Request anhand des tatsächlichen
Zugriffswegs (ProxyFix wertet X-Forwarded-Proto aus).

Mit ausführen:
    ~/.venvs/gsv/bin/python -m unittest test_cookie_sicherheit -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Muss vor dem Import von main stehen. Siehe testkonfiguration.py.
import testkonfiguration  # noqa: F401,E402

from main import app, db


def set_cookie_header(response):
    """Der Set-Cookie-Header des Sitzungscookies, oder None."""
    for name, value in response.headers:
        if name.lower() == 'set-cookie' and value.startswith('session='):
            return value
    return None


class TestSessionCookieSecureFlag(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        # Eine explizite Vorgabe aus der Umgebung würde die Erkennung
        # überstimmen; für diese Tests muss sie weg sein.
        self._gespeichert = os.environ.pop('SESSION_COOKIE_SECURE', None)
        self.client = app.test_client()

    def tearDown(self):
        if self._gespeichert is not None:
            os.environ['SESSION_COOKIE_SECURE'] = self._gespeichert

    def test_zugriff_ueber_http_bekommt_kein_secure_flag(self):
        """Im LAN über HTTP muss der Browser das Cookie annehmen."""
        response = self.client.get('/', base_url='http://192.168.188.59:5000')
        cookie = set_cookie_header(response)

        self.assertIsNotNone(cookie, 'Es wurde kein Sitzungscookie gesetzt')
        attribute = [a.strip().lower() for a in cookie.split(';')[1:]]
        self.assertNotIn('secure', attribute,
                         'Secure-Flag darf über HTTP nicht gesetzt sein')

    def test_zugriff_ueber_https_bekommt_secure_flag(self):
        """Hinter einem Proxy mit X-Forwarded-Proto: https muss es da sein."""
        response = self.client.get(
            '/',
            base_url='http://192.168.188.59:5000',
            headers={'X-Forwarded-Proto': 'https'},
        )
        cookie = set_cookie_header(response)

        self.assertIsNotNone(cookie, 'Es wurde kein Sitzungscookie gesetzt')
        self.assertIn('Secure', cookie)

    def test_explizite_vorgabe_gewinnt(self):
        """SESSION_COOKIE_SECURE=true erzwingt die Flagge auch über HTTP."""
        os.environ['SESSION_COOKIE_SECURE'] = 'true'
        try:
            response = self.client.get('/', base_url='http://192.168.188.59:5000')
            cookie = set_cookie_header(response)
            self.assertIsNotNone(cookie)
            self.assertIn('Secure', cookie)
        finally:
            os.environ.pop('SESSION_COOKIE_SECURE', None)
