"""Tests für die Systemhistorie (Audit Log).

Hintergrund: Bis v3.10 schrieb die Benutzerverwaltung überhaupt keine Einträge -
weder Anlegen noch Rollenwechsel, Bearbeitung, Löschen oder Bereichszuweisung.
Damit war im Nachhinein nicht feststellbar, wer wann Rechte geändert oder ein
Konto entfernt hatte. Diese Datei hält fest, dass jede dieser Aktionen einen
Eintrag erzeugt und was darin stehen muss.

Mit ausführen:
    /tmp/gsv-venv/bin/python -W ignore::ResourceWarning test_audit_log.py
"""
import unittest
import os
import sys
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Muss vor dem Import von main stehen: der Datenbank-Engine wird beim Import
# erzeugt. Siehe testkonfiguration.py.
import testkonfiguration  # noqa: F401,E402

from main import app, db, User, Bereich, Unterbereich, Gefahrstoff, AuditLog


class TestAuditLog(unittest.TestCase):
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

    def _login_admin(self, username='chef_audit'):
        """Legt einen Administrator an, meldet ihn an und gibt seine ID zurück."""
        with app.app_context():
            admin = User(username=username, role='admin')
            admin.set_password('pass123')
            db.session.add(admin)
            db.session.commit()
            admin_id = admin.id
        self.client.post('/login', data={'username': username, 'password': 'pass123'},
                         follow_redirects=True)
        return admin_id

    def _benutzer_anlegen(self, username, role='benutzer'):
        with app.app_context():
            user = User(username=username, role=role)
            user.set_password('pass123')
            db.session.add(user)
            db.session.commit()
            return user.id

    def _standort_und_stoff(self, admin_id, stoff_name='Teststoff'):
        """Bereich mit zwei Unterbereichen und einem Gefahrstoff darin."""
        with app.app_context():
            bereich = Bereich(name='Audit-Labor', owner_id=admin_id)
            db.session.add(bereich)
            db.session.commit()
            schrank1 = Unterbereich(name='Schrank 1', bereich_id=bereich.id)
            schrank2 = Unterbereich(name='Schrank 2', bereich_id=bereich.id)
            db.session.add_all([schrank1, schrank2])
            db.session.commit()
            stoff = Gefahrstoff(name=stoff_name, unterbereich_id=schrank1.id,
                                user_id=admin_id, lagerklasse='3',
                                menge=1.0, mengeneinheit='L')
            db.session.add(stoff)
            db.session.commit()
            return stoff.id, schrank1.id, schrank2.id, bereich.id

    # ── Anlegen ──────────────────────────────────────────────────────────────

    def test_create_user_schreibt_audit_eintrag(self):
        self._login_admin()
        self.client.post('/users/create',
                         data={'username': 'neu_audit', 'password': 'geheim123',
                               'role': 'benutzer'},
                         follow_redirects=True)

        with app.app_context():
            ziel = User.query.filter_by(username='neu_audit').first()
            self.assertIsNotNone(ziel, 'Der Benutzer sollte angelegt sein')
            eintrag = AuditLog.query.filter_by(action='USER_CREATE').first()
            self.assertIsNotNone(eintrag, 'Das Anlegen muss in der Historie stehen')
            self.assertEqual(eintrag.entity_type, 'User')
            self.assertEqual(eintrag.entity_id, ziel.id)
            self.assertIn('neu_audit', eintrag.details)
            self.assertIn('benutzer', eintrag.details)
            # Wer gehandelt hat, muss erkennbar sein
            self.assertEqual(eintrag.user.username, 'chef_audit')

    def test_erster_admin_wird_korrekt_protokolliert(self):
        # Regression: der Aufruf lautete log_audit_event(user.id, "USER_CREATE",
        # "<Satz>") - eine Zahl stand als Aktion, der Satz in der Integer-Spalte
        # entity_id. Der Eintrag war damit unbrauchbar.
        self.client.post('/register',
                         data={'username': 'erster_admin', 'password': 'geheim123'},
                         follow_redirects=True)

        with app.app_context():
            eintrag = AuditLog.query.filter_by(action='USER_CREATE').first()
            self.assertIsNotNone(eintrag, 'Die Registrierung muss in der Historie stehen')
            self.assertEqual(eintrag.entity_type, 'User')
            admin = User.query.filter_by(username='erster_admin').first()
            self.assertEqual(eintrag.entity_id, admin.id)
            # current_user ist beim Registrieren noch anonym; der Eintrag muss
            # trotzdem dem neuen Administrator zugeordnet sein.
            self.assertEqual(eintrag.user_id, admin.id)

    # ── Rolle ────────────────────────────────────────────────────────────────

    def test_rollenwechsel_haelt_alte_und_neue_rolle_fest(self):
        self._login_admin()
        zid = self._benutzer_anlegen('rollen_ziel', role='benutzer')

        self.client.post(f'/users/set_role/{zid}', data={'role': 'lesen'},
                         follow_redirects=True)

        with app.app_context():
            eintrag = AuditLog.query.filter_by(action='USER_ROLE').first()
            self.assertIsNotNone(eintrag, 'Der Rollenwechsel muss protokolliert werden')
            self.assertEqual(eintrag.entity_id, zid)
            # Beide Rollen: ohne die alte ist nicht nachvollziehbar, was vorher galt
            self.assertIn('benutzer', eintrag.details)
            self.assertIn('lesen', eintrag.details)

    # ── Bearbeiten ───────────────────────────────────────────────────────────

    def test_edit_haelt_die_geaenderten_felder_fest(self):
        self._login_admin()
        zid = self._benutzer_anlegen('edit_ziel', role='benutzer')

        self.client.post(f'/users/edit/{zid}',
                         data={'username': 'edit_ziel_neu', 'role': 'moderator'},
                         follow_redirects=True)

        with app.app_context():
            eintrag = AuditLog.query.filter_by(action='USER_UPDATE').first()
            self.assertIsNotNone(eintrag, 'Die Bearbeitung muss protokolliert werden')
            self.assertIn('edit_ziel', eintrag.details)
            self.assertIn('edit_ziel_neu', eintrag.details)
            self.assertIn('moderator', eintrag.details)

    def test_edit_ohne_aenderung_wird_als_solche_vermerkt(self):
        self._login_admin()
        zid = self._benutzer_anlegen('unveraendert', role='benutzer')

        self.client.post(f'/users/edit/{zid}',
                         data={'username': 'unveraendert', 'role': 'benutzer'},
                         follow_redirects=True)

        with app.app_context():
            eintrag = AuditLog.query.filter_by(action='USER_UPDATE').first()
            self.assertIsNotNone(eintrag)
            self.assertIn('Ohne inhaltliche', eintrag.details)

    # ── Löschen ──────────────────────────────────────────────────────────────

    def test_benutzer_loeschen_haelt_den_namen_fest(self):
        self._login_admin()
        zid = self._benutzer_anlegen('weg_damit', role='benutzer')

        self.client.post(f'/users/delete/{zid}', follow_redirects=True)

        with app.app_context():
            self.assertIsNone(User.query.filter_by(username='weg_damit').first(),
                              'Der Benutzer sollte gelöscht sein')
            eintrag = AuditLog.query.filter_by(action='USER_DELETE').first()
            self.assertIsNotNone(eintrag, 'Das Löschen muss protokolliert werden')
            self.assertEqual(eintrag.entity_id, zid)
            # Die Zeile ist weg - der Name kann nur aus dem Eintrag selbst kommen
            self.assertIn('weg_damit', eintrag.details)
            self.assertIn('benutzer', eintrag.details)

    # ── Bereichszuweisung ────────────────────────────────────────────────────

    def test_bereichszuweisung_wird_protokolliert(self):
        admin_id = self._login_admin()
        with app.app_context():
            bereich = Bereich(name='Audit-Labor', owner_id=admin_id)
            ziel = User(username='bereich_ziel', role='benutzer')
            ziel.set_password('pass123')
            db.session.add_all([bereich, ziel])
            db.session.commit()
            zid, bid = ziel.id, bereich.id

        self.client.post(f'/users/assign_bereiche/{zid}',
                         data={'bereich_ids': [str(bid)]}, follow_redirects=True)

        with app.app_context():
            eintrag = AuditLog.query.filter_by(action='USER_BEREICHE').first()
            self.assertIsNotNone(eintrag, 'Die Bereichszuweisung muss protokolliert werden')
            self.assertEqual(eintrag.entity_id, zid)
            self.assertIn('Audit-Labor', eintrag.details)
            # vorher -> nachher
            self.assertIn('keine', eintrag.details)

    # ── Gefahrstoffe: Verschieben und Kopieren ───────────────────────────────

    def test_verschieben_haelt_alten_und_neuen_standort_fest(self):
        admin_id = self._login_admin()
        stoff_id, schrank1_id, schrank2_id, _ = self._standort_und_stoff(admin_id)

        self.client.post(f'/move/{stoff_id}', data={'unterbereich_id': str(schrank2_id)},
                         follow_redirects=True)

        with app.app_context():
            self.assertEqual(Gefahrstoff.query.get(stoff_id).unterbereich_id, schrank2_id)
            eintrag = AuditLog.query.filter_by(action='MOVE').first()
            self.assertIsNotNone(eintrag, 'Das Verschieben muss protokolliert werden')
            self.assertEqual(eintrag.entity_id, stoff_id)
            # Beide Standorte: ohne den alten ist die Verschiebung nicht nachvollziehbar
            self.assertIn('Schrank 1', eintrag.details)
            self.assertIn('Schrank 2', eintrag.details)
            self.assertIn('Audit-Labor', eintrag.details)

    def test_kopieren_wird_protokolliert(self):
        admin_id = self._login_admin()
        stoff_id, _, schrank2_id, _ = self._standort_und_stoff(admin_id)

        self.client.post(f'/copy/{stoff_id}', data={'unterbereich_id': str(schrank2_id)},
                         follow_redirects=True)

        with app.app_context():
            self.assertEqual(Gefahrstoff.query.count(), 2, 'Die Kopie sollte existieren')
            eintrag = AuditLog.query.filter_by(action='COPY').first()
            self.assertIsNotNone(eintrag, 'Das Kopieren muss protokolliert werden')
            # Der Eintrag beschreibt die Kopie und nennt die Quelle
            kopie = Gefahrstoff.query.filter(Gefahrstoff.id != stoff_id).first()
            self.assertEqual(eintrag.entity_id, kopie.id)
            self.assertIn(f'#{stoff_id}', eintrag.details)
            self.assertIn('Schrank 2', eintrag.details)

    # ── Standorte löschen ────────────────────────────────────────────────────

    def test_unterbereich_loeschen_wird_protokolliert(self):
        admin_id = self._login_admin()
        stoff_id, schrank1_id, _, _ = self._standort_und_stoff(admin_id)

        self.client.post(f'/location/delete_unterbereich/{schrank1_id}', follow_redirects=True)

        with app.app_context():
            self.assertIsNone(Unterbereich.query.get(schrank1_id))
            # Der Gefahrstoff bleibt erhalten, verliert aber den Standort
            stoff = Gefahrstoff.query.get(stoff_id)
            self.assertIsNotNone(stoff, 'Der Gefahrstoff darf nicht mitgelöscht werden')
            self.assertIsNone(stoff.unterbereich_id)
            eintrag = AuditLog.query.filter_by(action='DELETE',
                                               entity_type='Unterbereich').first()
            self.assertIsNotNone(eintrag, 'Das Löschen muss protokolliert werden')
            self.assertIn('Schrank 1', eintrag.details)
            self.assertIn('1 Gefahrstoff', eintrag.details)

    def test_bereich_loeschen_protokolliert_die_folgen(self):
        admin_id = self._login_admin()
        stoff_id, _, _, bereich_id = self._standort_und_stoff(admin_id)

        self.client.post(f'/location/delete_bereich/{bereich_id}', follow_redirects=True)

        with app.app_context():
            self.assertIsNone(Bereich.query.get(bereich_id))
            self.assertEqual(Unterbereich.query.count(), 0, 'Die Unterbereiche gehen mit')
            # Wichtig: die Gefahrstoffe überleben, verlieren aber den Standort
            stoff = Gefahrstoff.query.get(stoff_id)
            self.assertIsNotNone(stoff, 'Gefahrstoffe dürfen nicht mitgelöscht werden')
            self.assertIsNone(stoff.unterbereich_id)
            eintrag = AuditLog.query.filter_by(action='DELETE', entity_type='Bereich').first()
            self.assertIsNotNone(eintrag, 'Das Löschen muss protokolliert werden')
            self.assertIn('Audit-Labor', eintrag.details)
            # Die Folgen stehen im Eintrag, sonst sieht man nur einen Namen verschwinden
            self.assertIn('2 Unterbereich', eintrag.details)
            self.assertIn('1 Gefahrstoff', eintrag.details)

    # ── Standorte anlegen ────────────────────────────────────────────────────

    def test_bereich_anlegen_wird_protokolliert(self):
        # Bis v3.15 war nur das Löschen eines Standorts protokolliert, das
        # Anlegen nicht.
        self._login_admin()

        self.client.post('/locations',
                         data={'action': 'add_bereich', 'bereich_name': 'Neues Labor'},
                         follow_redirects=True)

        with app.app_context():
            bereich = Bereich.query.filter_by(name='Neues Labor').first()
            self.assertIsNotNone(bereich, 'Der Bereich sollte angelegt sein')
            eintrag = AuditLog.query.filter_by(action='CREATE',
                                               entity_type='Bereich').first()
            self.assertIsNotNone(eintrag, 'Das Anlegen muss protokolliert werden')
            self.assertEqual(eintrag.entity_id, bereich.id)
            self.assertIn('Neues Labor', eintrag.details)
            self.assertEqual(eintrag.user.username, 'chef_audit')

    def test_unterbereich_anlegen_haelt_den_pfad_fest(self):
        self._login_admin()
        with app.app_context():
            admin = User.query.filter_by(role='admin').first()
            bereich = Bereich(name='Labor A', owner_id=admin.id)
            db.session.add(bereich)
            db.session.commit()
            bid = bereich.id

        self.client.post('/locations',
                         data={'action': 'add_unterbereich',
                               'unterbereich_name': 'Schrank 1',
                               'parent_selection': f'B_{bid}'},
                         follow_redirects=True)

        with app.app_context():
            unter = Unterbereich.query.filter_by(name='Schrank 1').first()
            self.assertIsNotNone(unter, 'Der Unterbereich sollte angelegt sein')
            eintrag = AuditLog.query.filter_by(action='CREATE',
                                               entity_type='Unterbereich').first()
            self.assertIsNotNone(eintrag, 'Das Anlegen muss protokolliert werden')
            self.assertEqual(eintrag.entity_id, unter.id)
            # Der Bereich gehört in den Eintrag, nicht nur der Name
            self.assertIn('Labor A / Schrank 1', eintrag.details)

    def test_verschachtelter_unterbereich_erscheint_mit_elternkette(self):
        # Ein Unterbereich kann unter einem anderen hängen. Ohne die Elternkette
        # hiessen zwei gleichnamige Schränke in verschiedenen Regalen im Log
        # identisch - der Eintrag wäre nicht eindeutig.
        self._login_admin()
        with app.app_context():
            admin = User.query.filter_by(role='admin').first()
            bereich = Bereich(name='Labor A', owner_id=admin.id)
            db.session.add(bereich)
            db.session.commit()
            regal = Unterbereich(name='Regal 1', bereich_id=bereich.id)
            db.session.add(regal)
            db.session.commit()
            regal_id = regal.id

        self.client.post('/locations',
                         data={'action': 'add_unterbereich',
                               'unterbereich_name': 'Schrank 1',
                               'parent_selection': f'U_{regal_id}'},
                         follow_redirects=True)

        with app.app_context():
            unter = Unterbereich.query.filter_by(name='Schrank 1').first()
            self.assertIsNotNone(unter, 'Der verschachtelte Unterbereich sollte angelegt sein')
            self.assertEqual(unter.parent_id, regal_id)
            eintrag = AuditLog.query.filter_by(action='CREATE',
                                               entity_type='Unterbereich').first()
            self.assertIn('Labor A / Regal 1 / Schrank 1', eintrag.details)

    # ── Passwort, Login, System ──────────────────────────────────────────────

    def test_passwortaenderung_im_profil_wird_protokolliert(self):
        self._login_admin()

        res = self.client.post('/profile',
                               data={'old_password': 'pass123',
                                     'new_password': 'NeuesGeheim456',
                                     'confirm_password': 'NeuesGeheim456'},
                               follow_redirects=True)
        self.assertIn('erfolgreich geändert', res.get_data(as_text=True))

        with app.app_context():
            eintrag = AuditLog.query.filter_by(action='USER_PASSWORD').first()
            self.assertIsNotNone(eintrag,
                                 'Die Passwortänderung muss protokolliert werden')
            self.assertEqual(eintrag.entity_id, User.query.filter_by(
                username='chef_audit').first().id)
            # Wie bei der Unterschrift: nur das Ereignis, nie das Passwort
            self.assertNotIn('NeuesGeheim456', eintrag.details or '')
            self.assertNotIn('pass123', eintrag.details or '')

    def test_lokaler_login_wird_protokolliert(self):
        # Bisher wurde nur der LDAP-Login erfasst.
        self._login_admin()

        with app.app_context():
            eintrag = AuditLog.query.filter_by(action='LOGIN').first()
            self.assertIsNotNone(eintrag, 'Der lokale Login muss protokolliert werden')
            self.assertIn('Lokaler Login', eintrag.details)
            self.assertEqual(eintrag.user.username, 'chef_audit')

    def test_repository_url_wird_protokolliert(self):
        # subprocess wird ersetzt: der Test darf kein echtes git-Kommando im
        # Arbeitsverzeichnis ausführen, das würde die Herkunft des Repos ändern.
        self._login_admin()

        with mock.patch('subprocess.check_call'):
            self.client.post('/admin/system/update_repo',
                             data={'repo_url': 'https://example.invalid/repo.git'},
                             follow_redirects=True)

        with app.app_context():
            eintrag = AuditLog.query.filter_by(action='SYSTEM_UPDATE').first()
            self.assertIsNotNone(eintrag,
                                 'Die Änderung der Repository-URL muss protokolliert werden')
            self.assertIn('example.invalid', eintrag.details)

    def test_update_ausloesen_wird_protokolliert(self):
        # Der Update-Thread würde update.sh starten - das macht git pull und
        # startet einen Server - und den Prozess am Ende mit os._exit beenden.
        # Deshalb werden Thread, subprocess und os._exit hier ersetzt.
        self._login_admin()

        with mock.patch('threading.Thread'), mock.patch('os._exit'), \
                mock.patch('subprocess.Popen'):
            self.client.post('/admin/system/do_update',
                             data={'target_branch': 'beta'}, follow_redirects=True)

        with app.app_context():
            eintrag = AuditLog.query.filter_by(action='SYSTEM_UPDATE').first()
            self.assertIsNotNone(eintrag, 'Das Auslösen des Updates muss protokolliert werden')
            self.assertIn('beta', eintrag.details)

    # ── Anzeige ──────────────────────────────────────────────────────────────

    def test_historie_rendert_und_uebersetzt_die_aktionen(self):
        # Prüft zugleich, dass das Template fehlerfrei rendert - ein Jinja-Fehler
        # in audit_logs.html würde sonst erst im Betrieb auffallen.
        admin_id = self._login_admin()
        zid = self._benutzer_anlegen('beschriftung', role='benutzer')
        self.client.post(f'/users/set_role/{zid}', data={'role': 'lesen'},
                         follow_redirects=True)
        self.client.post(f'/users/delete/{zid}', follow_redirects=True)

        stoff_id, _, schrank2_id, _ = self._standort_und_stoff(admin_id)
        self.client.post(f'/move/{stoff_id}', data={'unterbereich_id': str(schrank2_id)},
                         follow_redirects=True)
        self.client.post(f'/copy/{stoff_id}', data={'unterbereich_id': str(schrank2_id)},
                         follow_redirects=True)

        res = self.client.get('/audit_logs')
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        # Die Aktionen erscheinen auf Deutsch, nicht als roher Code
        self.assertIn('Rolle geändert', html)
        self.assertIn('Benutzer gelöscht', html)
        self.assertIn('Verschoben', html)
        self.assertIn('Kopiert', html)
        self.assertNotIn('USER_ROLE', html)
        self.assertNotIn('USER_DELETE', html)
        self.assertNotIn('MOVE', html)
        self.assertNotIn('COPY', html)
    def test_historie_zeigt_systemeintraege_ohne_datensatz_id(self):
        # Systemeinträge (Repository-URL, Update) haben keine entity_id. Ohne
        # Sonderbehandlung in der Anzeige stünde dort "System #None".
        self._login_admin()

        self.client.post('/profile',
                         data={'old_password': 'pass123',
                               'new_password': 'NeuesGeheim456',
                               'confirm_password': 'NeuesGeheim456'},
                         follow_redirects=True)
        with mock.patch('subprocess.check_call'):
            self.client.post('/admin/system/update_repo',
                             data={'repo_url': 'https://example.invalid/repo.git'},
                             follow_redirects=True)

        res = self.client.get('/audit_logs')
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn('Passwort geändert', html)
        self.assertIn('Systemänderung', html)
        self.assertNotIn('USER_PASSWORD', html)
        self.assertNotIn('SYSTEM_UPDATE', html)
        self.assertNotIn('#None', html)

    # ── Löschen eines Benutzers: Pseudonymisierung ───────────────────────────

    def test_eintraege_bleiben_nach_benutzerloeschung_zugeordnet(self):
        # Vorher setzte SQLAlchemy beim Löschen user_id auf NULL. Damit verlor
        # die Historie nicht nur den Namen - das ist gewollt, siehe
        # DATENSCHUTZ_UND_TOM.md - sondern auch den Bezug zwischen den
        # Einträgen: sie standen danach alle als "System / Unbekannt" da.
        self._login_admin()
        zid = self._benutzer_anlegen('geht_gehen', role='benutzer')

        # Der Benutzer tut etwas, das protokolliert wird.
        self.client.get('/logout')
        self.client.post('/login', data={'username': 'geht_gehen', 'password': 'pass123'},
                         follow_redirects=True)
        with app.app_context():
            # Nach user_id filtern: der Login des Administrators aus _login_admin
            # steht ebenfalls als LOGIN in der Historie.
            eintrag = AuditLog.query.filter_by(action='LOGIN', user_id=zid).first()
            self.assertIsNotNone(eintrag)
            self.assertEqual(eintrag.user_id, zid)
            self.assertEqual(eintrag.user.username, 'geht_gehen')

        # Der Administrator löscht das Konto.
        self.client.get('/logout')
        self.client.post('/login', data={'username': 'chef_audit', 'password': 'pass123'},
                         follow_redirects=True)
        self.client.post(f'/users/delete/{zid}', follow_redirects=True)

        with app.app_context():
            self.assertIsNone(User.query.filter_by(id=zid).first(), 'Das Konto ist weg')
            eintrag = AuditLog.query.filter_by(action='LOGIN', user_id=zid).first()
            self.assertEqual(eintrag.user_id, zid,
                             'Die ID muss als Pseudonym erhalten bleiben')
            self.assertIsNone(eintrag.user,
                              'Der Name darf nicht erhalten bleiben (Pseudonymisierung)')

    def test_anzeige_kennzeichnet_eintraege_geloeschter_benutzer(self):
        self._login_admin()
        zid = self._benutzer_anlegen('weg_damit2', role='benutzer')

        self.client.get('/logout')
        self.client.post('/login', data={'username': 'weg_damit2', 'password': 'pass123'},
                         follow_redirects=True)
        self.client.get('/logout')
        self.client.post('/login', data={'username': 'chef_audit', 'password': 'pass123'},
                         follow_redirects=True)
        self.client.post(f'/users/delete/{zid}', follow_redirects=True)

        res = self.client.get('/audit_logs')
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        # Einträge des gelöschten Kontos sind als solche erkennbar und nicht
        # mit Systemeinträgen vermischt.
        self.assertIn(f'Benutzer #{zid}', html)
        self.assertIn('(gelöscht)', html)

    # ── Keine Geheimnisse in der Historie ────────────────────────────────────

    def test_passwort_steht_nicht_in_der_historie(self):
        # Gegenstück zur Unterschrift: das Passwort ist personenbezogen und wird
        # als Ereignis vermerkt, nie im Klartext.
        self._login_admin()
        self.client.post('/users/create',
                         data={'username': 'pw_test', 'password': 'SuperGeheim123',
                               'role': 'benutzer'},
                         follow_redirects=True)

        zid = self._benutzer_anlegen('pw_ziel', role='benutzer')
        self.client.post(f'/users/edit/{zid}',
                         data={'username': 'pw_ziel', 'role': 'benutzer',
                               'password': 'NochGeheimer456'},
                         follow_redirects=True)

        with app.app_context():
            eintraege = AuditLog.query.all()
            self.assertTrue(eintraege, 'Es sollten Einträge existieren')
            for eintrag in eintraege:
                self.assertNotIn('SuperGeheim123', eintrag.details or '')
                self.assertNotIn('NochGeheimer456', eintrag.details or '')
            # Das Ereignis selbst muss aber vermerkt sein
            self.assertTrue(any('Passwort' in (e.details or '') for e in eintraege),
                            'Der Passwortwechsel sollte als Ereignis vermerkt sein')


if __name__ == '__main__':
    unittest.main()
