"""Tests für das Wiederherstellen gelöschter Gefahrstoffe.

Löschen setzt nur `is_deleted`; der Datensatz bleibt liegen. Bis v3.47 war er
danach über die Oberfläche unerreichbar (TOM, R-8). Seit v3.48 gibt es in der
Systemhistorie einen Knopf, der ihn zurückholt — nur für Administratoren.

Abgesichert wird

* die Rollengrenze: Moderator und Benutzer stellen nichts wieder her,
* dass ein nicht gelöschter Stoff unberührt bleibt,
* dass der DELETE-Eintrag stehen bleibt und ein RESTORE-Eintrag dazukommt,
* dass der Knopf nur dort erscheint, wo es etwas wiederherzustellen gibt.

Mit ausführen:
    ~/.venvs/gsv/bin/python -m unittest test_wiederherstellen -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Muss vor dem Import von main stehen (siehe testkonfiguration.py).
import testkonfiguration  # noqa: F401,E402

from main import (app, db, User, Bereich, Unterbereich, Gefahrstoff,  # noqa: E402
                  AuditLog)


class TestWiederherstellen(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()
        with app.app_context():
            db.create_all()
            chef = User(username='chef', role='admin')
            chef.set_password('pass123')
            mod = User(username='mod', role='moderator')
            mod.set_password('pass123')
            db.session.add_all([chef, mod])
            db.session.commit()

            bereich = Bereich(name='Labor R', owner_id=chef.id)
            db.session.add(bereich)
            db.session.commit()
            unterbereich = Unterbereich(name='Schrank R1', bereich_id=bereich.id)
            db.session.add(unterbereich)
            db.session.commit()

            stoff = Gefahrstoff(name='Aceton', unterbereich_id=unterbereich.id,
                                user_id=chef.id, is_approved=True)
            db.session.add(stoff)
            db.session.commit()

            mod.assigned_bereiche.append(bereich)
            db.session.commit()

            self.stoff_id = stoff.id

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def _login(self, benutzer='chef'):
        self.client.post('/login', data={'username': benutzer,
                                         'password': 'pass123'},
                         follow_redirects=True)

    def _loeschen(self):
        """Über die echte Route löschen - so entsteht der Historie-Eintrag."""
        self.client.post(f'/delete/{self.stoff_id}')

    def _ist_geloescht(self):
        with app.app_context():
            return Gefahrstoff.query.get(self.stoff_id).is_deleted

    def test_wiederherstellen_braucht_anmeldung(self):
        antwort = self.client.post(f'/restore/{self.stoff_id}')
        self.assertEqual(antwort.status_code, 302)
        self.assertIn('/login', antwort.headers['Location'])

    def test_admin_stellt_wieder_her(self):
        self._login()
        self._loeschen()
        self.assertTrue(self._ist_geloescht())

        antwort = self.client.post(f'/restore/{self.stoff_id}')
        self.assertEqual(antwort.status_code, 302)
        self.assertIn('/audit_logs', antwort.headers['Location'])

        with app.app_context():
            stoff = Gefahrstoff.query.get(self.stoff_id)
            self.assertFalse(stoff.is_deleted)
            self.assertIsNone(stoff.deleted_at)
            # Der Vorgang steht in der Historie, der alte Eintrag bleibt.
            aktionen = [e.action for e in
                        AuditLog.query.filter_by(entity_id=self.stoff_id,
                                                 entity_type='Gefahrstoff').all()]
            self.assertIn('DELETE', aktionen)
            self.assertIn('RESTORE', aktionen)

    def test_moderator_stellt_nichts_wieder_her(self):
        self._login('mod')
        self._loeschen()          # als Moderator mit Schreibrecht im Bereich
        self.assertTrue(self._ist_geloescht())

        self.client.post(f'/restore/{self.stoff_id}')
        self.assertTrue(self._ist_geloescht(),
                        'Nur Administratoren dürfen wiederherstellen')

    def test_nicht_geloeschter_stoff_bleibt_unberuehrt(self):
        self._login()
        self.client.post(f'/restore/{self.stoff_id}')

        with app.app_context():
            stoff = Gefahrstoff.query.get(self.stoff_id)
            self.assertFalse(stoff.is_deleted)
            # Kein RESTORE-Eintrag für einen Vorgang, der keiner war.
            self.assertIsNone(AuditLog.query.filter_by(action='RESTORE').first())

    def test_unbekannte_id_ist_404(self):
        self._login()
        antwort = self.client.post('/restore/999999')
        self.assertEqual(antwort.status_code, 404)

    def test_knopf_steht_nur_bei_wiederherstellbaren_stoffen(self):
        self._login()
        self._loeschen()

        html = self.client.get('/audit_logs').get_data(as_text=True)
        self.assertIn(f'/restore/{self.stoff_id}', html)
        self.assertIn('Wiederherstellen', html)

        self.client.post(f'/restore/{self.stoff_id}')
        html = self.client.get('/audit_logs').get_data(as_text=True)
        # Nach der Wiederherstellung gibt es nichts mehr zu holen.
        self.assertNotIn(f'/restore/{self.stoff_id}', html)
        self.assertIn('Wiederhergestellt', html)


if __name__ == '__main__':
    unittest.main()
