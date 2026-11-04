"""Tests für die Import-Routen in main.py.

Der Import hat zwei Schritte: Erst prüfen (POST /import), dann übernehmen
(POST /import/bestaetigen). Diese Datei sichert ab, dass

* in der Vorschau nichts gespeichert wird,
* nur Zeilen aus zugänglichen Bereichen übernommen werden,
* Duplikate übersprungen oder nur leere Felder gefüllt werden,
* CMR-Stoffe auf Freigabe warten,
* Leser weder importieren noch die Vorlage laden können,
* und ein abgelaufenes Token keinen Fehler auslöst.

Mit ausführen:
    ~/.venvs/gsv/bin/python -m unittest test_import_route -v
"""
import io
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Muss vor dem Import von main stehen (siehe testkonfiguration.py).
import testkonfiguration  # noqa: F401,E402

from main import app, db, User, Bereich, Unterbereich, Gefahrstoff, AuditLog


def csv(daten, dateiname='liste.csv'):
    """Multipart-Upload einer CSV-Datei."""
    return {'datei': (io.BytesIO(daten.encode('utf-8-sig')), dateiname)}


class TestImportRouten(unittest.TestCase):

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

    # ── Umgebung ────────────────────────────────────────────────────────────

    def _umgebung(self):
        """'anna' mit Labor A, dazu ein fremdes Labor B."""
        with app.app_context():
            anna = User(username='anna', role='benutzer')
            anna.set_password('pass123')
            bernd = User(username='bernd', role='benutzer')
            bernd.set_password('pass123')
            db.session.add_all([anna, bernd])
            db.session.commit()

            bereich_a = Bereich(name='Labor A', owner_id=anna.id)
            bereich_b = Bereich(name='Labor B', owner_id=bernd.id)
            db.session.add_all([bereich_a, bereich_b])
            db.session.commit()

            a1 = Unterbereich(name='Schrank A1', bereich_id=bereich_a.id)
            a2 = Unterbereich(name='Schrank A2', bereich_id=bereich_a.id)
            b1 = Unterbereich(name='Schrank B1', bereich_id=bereich_b.id)
            db.session.add_all([a1, a2, b1])
            db.session.commit()

            anna.assigned_bereiche.append(bereich_a)
            db.session.commit()
            return a1.id, a2.id, b1.id

    def _leser(self):
        with app.app_context():
            leser = User(username='leser', role='lesen')
            leser.set_password('pass123')
            db.session.add(leser)
            db.session.commit()

    def _login(self, benutzer='anna'):
        self.client.post('/login', data={'username': benutzer,
                                         'password': 'pass123'},
                         follow_redirects=True)

    def _vorschau(self, inhalt, standort_id=None):
        """Schickt eine Datei zur Vorschau und liefert (Antwort, Token)."""
        daten = csv(inhalt)
        if standort_id is not None:
            daten['unterbereich_id'] = str(standort_id)
        antwort = self.client.post('/import', data=daten,
                                   content_type='multipart/form-data')
        treffer = re.search(r'name="token" value="([^"]+)"',
                            antwort.get_data(as_text=True))
        return antwort, (treffer.group(1) if treffer else None)

    def _bestaetigen(self, token, zeilen=('0',), duplikate='ueberspringen'):
        return self.client.post('/import/bestaetigen', data={
            'token': token, 'duplikate': duplikate, 'zeilen': list(zeilen),
        }, follow_redirects=True)

    # ── Vorschau ────────────────────────────────────────────────────────────

    def test_vorschau_speichert_nichts(self):
        a1_id, _, _ = self._umgebung()
        self._login()

        antwort, token = self._vorschau(
            'Name;CAS-Nummer;H-Sätze\nAceton;67-64-1;H225\n', a1_id)

        self.assertEqual(antwort.status_code, 200)
        self.assertIn('Aceton', antwort.get_data(as_text=True))
        self.assertIsNotNone(token)
        with app.app_context():
            self.assertEqual(Gefahrstoff.query.count(), 0)

    def test_unbekannte_endung_wird_abgelehnt(self):
        self._umgebung()
        self._login()

        antwort = self.client.post(
            '/import',
            data={'datei': (io.BytesIO(b'Name\nAceton\n'), 'liste.txt')},
            content_type='multipart/form-data', follow_redirects=True)

        self.assertIn('Nur .xlsx und .csv', antwort.get_data(as_text=True))

    # ── Bestätigen ──────────────────────────────────────────────────────────

    def test_bestaetigen_legt_stoff_an(self):
        a1_id, _, _ = self._umgebung()
        self._login()
        _, token = self._vorschau(
            'Name;CAS-Nummer;H-Sätze;Menge;Einheit\n'
            'Aceton;67-64-1;"H225, H319";4,5;L\n', a1_id)

        self._bestaetigen(token)

        with app.app_context():
            stoff = Gefahrstoff.query.filter_by(name='Aceton').one()
            self.assertEqual(stoff.cas_nummer, '67-64-1')
            self.assertEqual(stoff.menge, 4.5)
            self.assertEqual(stoff.mengeneinheit, 'L')
            self.assertEqual(stoff.unterbereich_id, a1_id)
            # Piktogramme wurden aus den H-Sätzen abgeleitet.
            self.assertEqual(stoff.piktogramme, 'GHS02,GHS07')
            self.assertEqual(stoff.signalwort, 'Gefahr')
            self.assertEqual(stoff.user_id,
                             User.query.filter_by(username='anna').one().id)
            self.assertEqual(AuditLog.query.filter_by(action='IMPORT').count(), 1)

    def test_standortspalte_schlaegt_ziel(self):
        a1_id, a2_id, _ = self._umgebung()
        self._login()
        _, token = self._vorschau(
            'Name;Standort\nAceton;Labor A › Schrank A2\n', a1_id)

        self._bestaetigen(token)

        with app.app_context():
            stoff = Gefahrstoff.query.filter_by(name='Aceton').one()
            self.assertEqual(stoff.unterbereich_id, a2_id)

    def test_fremder_bereich_wird_abgelehnt(self):
        a1_id, _, b1_id = self._umgebung()
        self._login()
        _, token = self._vorschau(
            'Name;Standort\nAceton;Labor B › Schrank B1\n', a1_id)

        self._bestaetigen(token)

        with app.app_context():
            self.assertEqual(Gefahrstoff.query.count(), 0)

    def test_cmr_stoff_wartet_auf_freigabe(self):
        a1_id, _, _ = self._umgebung()
        self._login()
        _, token = self._vorschau(
            'Name;H-Sätze\nBenzol;H350\n', a1_id)

        self._bestaetigen(token)

        with app.app_context():
            stoff = Gefahrstoff.query.filter_by(name='Benzol').one()
            self.assertFalse(stoff.is_approved)

    # ── Duplikate ───────────────────────────────────────────────────────────

    def _mit_bestand(self):
        a1_id, a2_id, _ = self._umgebung()
        with app.app_context():
            anna = User.query.filter_by(username='anna').one()
            db.session.add(Gefahrstoff(
                name='Aceton', cas_nummer='67-64-1', h_saetze='H225',
                unterbereich_id=a1_id, user_id=anna.id, lagerort=None))
            db.session.commit()
        return a1_id, a2_id

    def test_duplikat_wird_standardmaessig_uebersprungen(self):
        a1_id, _ = self._mit_bestand()
        self._login()
        _, token = self._vorschau(
            'Name;CAS-Nummer;H-Sätze\nAceton;67-64-1;H225\n', a1_id)

        self._bestaetigen(token)

        with app.app_context():
            self.assertEqual(Gefahrstoff.query.count(), 1)

    def test_aktualisieren_fuellt_nur_leere_felder(self):
        a1_id = self._mit_bestand()[0]
        self._login()
        _, token = self._vorschau(
            'Name;CAS-Nummer;H-Sätze;Lagerort;Lagerklasse\n'
            'Aceton;67-64-1;H225;Schrank 3;3\n', a1_id)

        self._bestaetigen(token, duplikate='aktualisieren')

        with app.app_context():
            stoff = Gefahrstoff.query.filter_by(name='Aceton').one()
            # Leer war der Lagerort -> gefüllt. Die Lagerklasse war leer -> 3.
            self.assertEqual(stoff.lagerort, 'Schrank 3')
            self.assertEqual(stoff.lagerklasse, '3')
            # Vorhandene H-Sätze bleiben unangetastet.
            self.assertEqual(stoff.h_saetze, 'H225')

    def test_gleicher_stoff_an_zweitem_standort_wird_angelegt(self):
        """Aceton existiert in Schrank A1 - ein Import nach A2 ist erlaubt."""
        a1_id, a2_id = self._mit_bestand()
        self._login()
        _, token = self._vorschau(
            'Name;CAS-Nummer;Standort\n'
            'Aceton;67-64-1;Labor A › Schrank A2\n', a1_id)

        self._bestaetigen(token)

        with app.app_context():
            self.assertEqual(Gefahrstoff.query.count(), 2)
            standorte = {s.unterbereich_id for s in Gefahrstoff.query.all()}
            self.assertEqual(standorte, {a1_id, a2_id})

    # ── Rechte und Token ────────────────────────────────────────────────────

    def test_leser_darf_nicht_importieren(self):
        self._leser()
        self._login('leser')

        antwort = self.client.get('/import', follow_redirects=True)
        self.assertIn('Keine Schreibberechtigung',
                      antwort.get_data(as_text=True))

    def test_leser_darf_keine_vorlage_laden(self):
        self._leser()
        self._login('leser')

        antwort = self.client.get('/import/vorlage', follow_redirects=True)
        self.assertIn('Keine Schreibberechtigung',
                      antwort.get_data(as_text=True))

    def test_vorlage_wird_als_xlsx_geliefert(self):
        self._umgebung()
        self._login()

        antwort = self.client.get('/import/vorlage')
        self.assertEqual(antwort.status_code, 200)
        self.assertTrue(antwort.data.startswith(b'PK\x03\x04'))
        self.assertIn('gefahrstoffe_import_vorlage.xlsx',
                      antwort.headers.get('Content-Disposition', ''))

    def test_abgelaufenes_token_ist_kein_fehler(self):
        self._umgebung()
        self._login()

        # Ein Token mit gültigem Format, zu dem es keinen Zwischenstand gibt.
        # Bewusst ohne Zufall: gitleaks hielte einen zufällig wirkenden Wert
        # für einen ausgelaufenen Schlüssel.
        antwort = self.client.post(
            '/import/bestaetigen',
            data={'token': '0' * 24, 'zeilen': ['0']},
            follow_redirects=True)

        self.assertEqual(antwort.status_code, 200)
        self.assertIn('abgelaufen', antwort.get_data(as_text=True))

    def test_fremdes_token_wird_abgewiesen(self):
        a1_id, _, _ = self._umgebung()
        self._login()
        _, token = self._vorschau('Name\nAceton\n', a1_id)

        # Ein zweiter Benutzer darf den Zwischenstand nicht übernehmen.
        # Vorher abmelden: /login leitet einen bereits angemeldeten Benutzer
        # um, ohne das Konto zu wechseln.
        self.client.get('/logout')
        self._login('bernd')
        antwort = self.client.post('/import/bestaetigen',
                                   data={'token': token, 'zeilen': ['0']})
        self.assertEqual(antwort.status_code, 403)

    def test_ohne_auswahl_wird_nichts_gespeichert(self):
        a1_id, _, _ = self._umgebung()
        self._login()
        _, token = self._vorschau('Name\nAceton\n', a1_id)

        antwort = self.client.post('/import/bestaetigen',
                                   data={'token': token, 'zeilen': []},
                                   follow_redirects=True)

        self.assertIn('keine Zeile', antwort.get_data(as_text=True))
        with app.app_context():
            self.assertEqual(Gefahrstoff.query.count(), 0)


if __name__ == '__main__':
    unittest.main()
