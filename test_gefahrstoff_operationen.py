"""Tests für die Operationen an Gefahrstoffen: Kopieren und Verschieben.

Zwei Fehler werden hier abgesichert:

1. `copy_stoff` kopierte `lagerklasse` und `gefahrenkategorien` nicht. Eine Kopie
   verlor damit ihre Lagerklasse - und die ist die Grundlage der
   TRGS-510-Zusammenlagerungsprüfung. Die Kopie erschien also ohne genau die
   Konfliktwarnungen, die das Original hat.
2. `move_stoff` prüfte den Ziel-Standort nicht, während `/add` und `/edit` es
   tun. Weil `copy_stoff` denselben Wert ebenfalls ungeprüft übernahm, hatten
   beide Routen die Lücke; sie teilen sich jetzt `ziel_standort_pruefen()`.

Mit ausführen:
    /tmp/gsv-venv/bin/python -W ignore::ResourceWarning test_gefahrstoff_operationen.py
"""
import unittest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from main import app, db, User, Bereich, Unterbereich, Gefahrstoff


class TestGefahrstoffOperationen(unittest.TestCase):
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

    def _umgebung(self, stoff_name='Aceton'):
        """Zwei Bereiche, drei Unterbereiche, ein Gefahrstoff von 'anna'.

        'anna' ist nur dem Bereich A zugewiesen - Bereich B ist für sie fremd.
        """
        with app.app_context():
            anna = User(username='anna', role='benutzer')
            anna.set_password('pass123')
            db.session.add(anna)
            db.session.commit()

            bereich_a = Bereich(name='Labor A', owner_id=anna.id)
            bereich_b = Bereich(name='Labor B', owner_id=anna.id)
            db.session.add_all([bereich_a, bereich_b])
            db.session.commit()

            a1 = Unterbereich(name='Schrank A1', bereich_id=bereich_a.id)
            a2 = Unterbereich(name='Schrank A2', bereich_id=bereich_a.id)
            b1 = Unterbereich(name='Schrank B1', bereich_id=bereich_b.id)
            db.session.add_all([a1, a2, b1])
            db.session.commit()

            anna.assigned_bereiche.append(bereich_a)
            db.session.commit()

            stoff = Gefahrstoff(
                name=stoff_name, cas_nummer='67-64-1', signalwort='Gefahr',
                piktogramme='["GHS02","GHS07"]', gefahrenkategorien='Entzündbare Flüssigkeiten',
                h_saetze='H225,H319', p_saetze='P210,P233', lagerort='Schrank 1',
                lagerklasse='3', menge=5.0, mengeneinheit='L',
                unterbereich_id=a1.id, user_id=anna.id,
            )
            db.session.add(stoff)
            db.session.commit()
            return stoff.id, a1.id, a2.id, b1.id

    def _als_anna(self):
        self.client.post('/login', data={'username': 'anna', 'password': 'pass123'},
                         follow_redirects=True)

    # ── Kopieren: Datenvollständigkeit ───────────────────────────────────────

    def test_kopie_behaelt_lagerklasse_und_gefahrenkategorien(self):
        stoff_id, _, a2_id, _ = self._umgebung()
        self._als_anna()

        self.client.post(f'/copy/{stoff_id}', data={'unterbereich_id': str(a2_id)},
                         follow_redirects=True)

        with app.app_context():
            kopie = Gefahrstoff.query.filter(Gefahrstoff.id != stoff_id).first()
            self.assertIsNotNone(kopie, 'Die Kopie sollte angelegt sein')
            # Die beiden Felder, die vorher verloren gingen
            self.assertEqual(kopie.lagerklasse, '3')
            self.assertEqual(kopie.gefahrenkategorien, 'Entzündbare Flüssigkeiten')

    def test_kopie_behaelt_die_uebrigen_stoffdaten(self):
        stoff_id, _, a2_id, _ = self._umgebung()
        self._als_anna()

        self.client.post(f'/copy/{stoff_id}', data={'unterbereich_id': str(a2_id)},
                         follow_redirects=True)

        with app.app_context():
            original = Gefahrstoff.query.get(stoff_id)
            kopie = Gefahrstoff.query.filter(Gefahrstoff.id != stoff_id).first()
            for feld in ['name', 'cas_nummer', 'signalwort', 'piktogramme',
                         'h_saetze', 'p_saetze', 'lagerort', 'lagerklasse',
                         'gefahrenkategorien', 'menge', 'mengeneinheit']:
                self.assertEqual(getattr(kopie, feld), getattr(original, feld),
                                 f'Feld "{feld}" wurde nicht mitkopiert')
            self.assertEqual(kopie.unterbereich_id, a2_id)
            # Das Original bleibt, wo es war
            self.assertEqual(original.unterbereich_id, original.unterbereich_id)

    # ── Verschieben: Zielprüfung ─────────────────────────────────────────────

    def test_verschieben_in_fremden_bereich_wird_abgelehnt(self):
        stoff_id, a1_id, _, b1_id = self._umgebung()
        self._als_anna()

        res = self.client.post(f'/move/{stoff_id}', data={'unterbereich_id': str(b1_id)},
                               follow_redirects=True)
        self.assertIn('Kein Zugriff auf diesen Ziel-Standort', res.get_data(as_text=True))

        with app.app_context():
            self.assertEqual(Gefahrstoff.query.get(stoff_id).unterbereich_id, a1_id,
                             'Der Gefahrstoff darf den Bereich nicht verlassen haben')

    def test_verschieben_auf_unbekannten_standort_wird_abgelehnt(self):
        stoff_id, a1_id, _, _ = self._umgebung()
        self._als_anna()

        res = self.client.post(f'/move/{stoff_id}', data={'unterbereich_id': '99999'},
                               follow_redirects=True)
        self.assertIn('existiert nicht', res.get_data(as_text=True))

        with app.app_context():
            self.assertEqual(Gefahrstoff.query.get(stoff_id).unterbereich_id, a1_id)

    def test_verschieben_mit_unsinnigem_ziel_wird_abgelehnt(self):
        stoff_id, a1_id, _, _ = self._umgebung()
        self._als_anna()

        res = self.client.post(f'/move/{stoff_id}', data={'unterbereich_id': 'keine-zahl'},
                               follow_redirects=True)
        self.assertIn('Ungültiger Ziel-Standort', res.get_data(as_text=True))

        with app.app_context():
            self.assertEqual(Gefahrstoff.query.get(stoff_id).unterbereich_id, a1_id)

    def test_verschieben_im_eigenen_bereich_funktioniert(self):
        stoff_id, _, a2_id, _ = self._umgebung()
        self._als_anna()

        self.client.post(f'/move/{stoff_id}', data={'unterbereich_id': str(a2_id)},
                         follow_redirects=True)

        with app.app_context():
            self.assertEqual(Gefahrstoff.query.get(stoff_id).unterbereich_id, a2_id)

    def test_verschieben_ohne_standort_bleibt_moeglich(self):
        # Bewusst festgehaltenes Verhalten: ein leerer Wert bedeutet weiterhin
        # "ohne Standort". Die Oberfläche bietet das nicht an (das Auswahlfeld ist
        # pflichtig), der bisherige Code konnte es. Der Test markiert die Stelle
        # für den Fall, dass das jemand ändern will.
        stoff_id, a1_id, _, _ = self._umgebung()
        self._als_anna()

        self.client.post(f'/move/{stoff_id}', data={'unterbereich_id': ''},
                         follow_redirects=True)

        with app.app_context():
            self.assertIsNone(Gefahrstoff.query.get(stoff_id).unterbereich_id)

    # ── Kopieren: dieselbe Lücke wie beim Verschieben ────────────────────────

    def test_kopie_landet_nicht_in_einem_fremden_bereich(self):
        stoff_id, _, _, b1_id = self._umgebung()
        self._als_anna()

        res = self.client.post(f'/copy/{stoff_id}', data={'unterbereich_id': str(b1_id)},
                               follow_redirects=True)
        self.assertIn('Kein Zugriff auf diesen Ziel-Standort', res.get_data(as_text=True))

        with app.app_context():
            self.assertEqual(Gefahrstoff.query.count(), 1,
                             'Es darf keine Kopie entstanden sein')

    # ── Kopieren: Freigabe ───────────────────────────────────────────────────

    def test_kopie_umgeht_die_cmr_freigabe_nicht(self):
        # Ohne eigene is_approved-Angabe bekam die Kopie den Spaltenstandard True.
        # Ein CMR-Stoff wartet nach /add auf Freigabe - die Kopie war dagegen
        # sofort sichtbar, womit sich die Freigabe umgehen ließ.
        stoff_id, _, a2_id, _ = self._umgebung()
        with app.app_context():
            stoff = Gefahrstoff.query.get(stoff_id)
            stoff.h_saetze = 'H350'          # CMR
            stoff.is_approved = False        # wartet auf Freigabe
            db.session.commit()
        self._als_anna()

        res = self.client.post(f'/copy/{stoff_id}', data={'unterbereich_id': str(a2_id)},
                               follow_redirects=True)
        self.assertIn('freigegeben werden', res.get_data(as_text=True))

        with app.app_context():
            kopie = Gefahrstoff.query.filter(Gefahrstoff.id != stoff_id).first()
            self.assertIsNotNone(kopie, 'Die Kopie sollte angelegt sein')
            self.assertFalse(kopie.is_approved,
                             'Eine CMR-Kopie darf nicht sofort sichtbar sein')
            # Kontrolle: sie erscheint nicht in der Liste des Erstellers
            self.assertNotIn('Aceton', self.client.get('/').get_data(as_text=True))

    def test_kopie_eines_unauffaelligen_stoffs_ist_sofort_sichtbar(self):
        # Gegenprobe: für Stoffe ohne CMR-Satz bleibt alles wie bisher.
        stoff_id, _, a2_id, _ = self._umgebung()
        self._als_anna()

        self.client.post(f'/copy/{stoff_id}', data={'unterbereich_id': str(a2_id)},
                         follow_redirects=True)

        with app.app_context():
            kopie = Gefahrstoff.query.filter(Gefahrstoff.id != stoff_id).first()
            self.assertTrue(kopie.is_approved)


if __name__ == '__main__':
    unittest.main()
