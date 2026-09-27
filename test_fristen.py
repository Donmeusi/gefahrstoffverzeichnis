"""Tests für die Fristenliste.

Ausgangslage: Die Frist für Sicherheitsdatenblätter stand zweimal mit
unterschiedlichen Zahlen im Code — `index()` zählte für die Kachel „Veraltete
SDBs" alles ab 3 Jahren, `sicherheitsdatenblaetter.html` rechnete dieselbe
Regel mit drei Stufen im Template nach. Diese Datei sichert ab, dass die
Entscheidung in `sdb_status()` fällt und dass die Liste zeigt, was zu tun ist.

Mit ausführen:
    /tmp/gsv-venv/bin/python -W ignore::ResourceWarning test_fristen.py
"""
import unittest
import os
import re
import sys
from datetime import date, datetime, timedelta
from types import SimpleNamespace

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Muss vor dem Import von main stehen: der Datenbank-Engine wird beim Import
# erzeugt. Siehe testkonfiguration.py.
import testkonfiguration  # noqa: F401,E402

from main import (
    app, db, User, Bereich, Unterbereich, Gefahrstoff,
    sdb_status, SDB_FRIST_JAHRE, SDB_DRINGEND_JAHRE,
)

HEUTE = date(2026, 9, 27)


def vor_jahren(jahre, tage=0):
    """Datum 'jahre' Jahre vor HEUTE, optional um Tage verschoben."""
    return date(HEUTE.year - jahre, HEUTE.month, HEUTE.day) - timedelta(days=tage)


def stoff_attrappe(sdb_datum=None, hat_sdb=True):
    """Nur die zwei Felder, die sdb_status() liest — kein Datenbankeintrag."""
    return SimpleNamespace(sdb_datum=sdb_datum,
                           sicherheitsdatenblatt='blatt.pdf' if hat_sdb else None)


class TestSdbStatus(unittest.TestCase):
    """Die Regel selbst — reine Funktion, ohne Datenbank."""

    def test_aktuell(self):
        self.assertEqual(sdb_status(stoff_attrappe(vor_jahren(2)), HEUTE)[0], 'ok')

    def test_pruefen_ab_drei_jahren(self):
        stufe, faellig = sdb_status(stoff_attrappe(vor_jahren(3, 1)), HEUTE)
        self.assertEqual(stufe, 'pruefen')
        self.assertIsNotNone(faellig)
        self.assertLessEqual(faellig, HEUTE)

    def test_dringend_ab_fuenf_jahren(self):
        stufe, faellig = sdb_status(stoff_attrappe(vor_jahren(5, 1)), HEUTE)
        self.assertEqual(stufe, 'dringend')
        self.assertLessEqual(faellig, HEUTE)

    def test_grenze_genau_drei_jahre_gilt_als_faellig(self):
        # Auf den Tag genau: die Frist ist erreicht, nicht erst überschritten.
        self.assertEqual(sdb_status(stoff_attrappe(vor_jahren(3)), HEUTE)[0], 'pruefen')

    def test_ein_tag_vor_der_frist_ist_aktuell(self):
        self.assertEqual(sdb_status(stoff_attrappe(vor_jahren(3, -1)), HEUTE)[0], 'ok')

    def test_ohne_dokument(self):
        stufe, faellig = sdb_status(stoff_attrappe(None, hat_sdb=False), HEUTE)
        self.assertEqual(stufe, 'fehlt')
        self.assertIsNone(faellig)

    def test_ohne_datum(self):
        stufe, faellig = sdb_status(stoff_attrappe(None, hat_sdb=True), HEUTE)
        self.assertEqual(stufe, 'ohne_datum')
        self.assertIsNone(faellig)

    def test_schalttag_stuerzt_nicht_ab(self):
        # 29.02. + 3 Jahre ergibt kein gültiges Datum - die Frist wird auf den
        # 28.02. gelegt.
        _, faellig = sdb_status(stoff_attrappe(date(2020, 2, 29)), date(2024, 3, 1))
        self.assertEqual(faellig, date(2023, 2, 28))


class TestFristenliste(unittest.TestCase):
    """Liste und Seite — mit Datenbank."""

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

    def _umgebung(self):
        """Admin mit einem Bereich, einem Unterbereich und vier Stoffen.

        Die SDB-Daten liegen relativ zu HEUTE (also zur echten Laufzeit), weil
        fristen_liste() mit dem heutigen Datum rechnet.
        """
        with app.app_context():
            admin = User(username='chef_frist', role='admin')
            admin.set_password('pass123')
            db.session.add(admin)
            db.session.commit()

            bereich = Bereich(name='Labor A', owner_id=admin.id)
            db.session.add(bereich)
            db.session.commit()

            unterbereich = Unterbereich(name='Schrank 1', bereich_id=bereich.id)
            db.session.add(unterbereich)
            db.session.commit()

            heute = datetime.utcnow().date()
            juengstes = date(heute.year - 2, heute.month, heute.day)   # aktuell
            mittel    = date(heute.year - 4, heute.month, heute.day)   # prüfen
            alt       = date(heute.year - 6, heute.month, heute.day)   # dringend
            for name, datum, hat_sdb in [
                ('Frischstoff', juengstes, True),
                ('Mittelaltstoff', mittel, True),
                ('Altstoff', alt, True),
                ('OhneBlatt', None, False),
            ]:
                db.session.add(Gefahrstoff(
                    name=name, unterbereich_id=unterbereich.id, user_id=admin.id,
                    sicherheitsdatenblatt='blatt.pdf' if hat_sdb else None,
                    sdb_datum=datum,
                ))
            db.session.commit()

        self.client.post('/login', data={'username': 'chef_frist', 'password': 'pass123'},
                         follow_redirects=True)

    def _seite(self):
        res = self.client.get('/fristen')
        self.assertEqual(res.status_code, 200)
        return res.get_data(as_text=True)

    def test_aktuelle_sdb_erscheinen_nicht_in_der_liste(self):
        self._umgebung()
        html = self._seite()
        self.assertNotIn('Frischstoff', html, 'Ein aktuelles SDB gehört nicht in die Liste')

    def test_veraltete_und_fehlende_sdb_erscheinen(self):
        self._umgebung()
        html = self._seite()
        self.assertIn('Mittelaltstoff', html)
        self.assertIn('SDB prüfen', html)
        self.assertIn('Altstoff', html)
        self.assertIn('SDB dringend aktualisieren', html)
        self.assertIn('OhneBlatt', html)
        self.assertIn('Kein SDB hinterlegt', html)

    def test_inventur_frist_je_standort(self):
        self._umgebung()
        with app.app_context():
            # Der Standort wurde lange nicht inventarisiert - und der Stoff
            # "Frischstoff" hat ein aktuelles SDB, taucht also nur deshalb auf.
            stoff = Gefahrstoff.query.filter_by(name='Frischstoff').first()
            stoff.last_inventur_datum = datetime.utcnow() - timedelta(days=400)
            db.session.commit()

            # Ein zweiter Standort, frisch inventarisiert.
            b2 = Unterbereich.query.first()
            frisch = Unterbereich(name='Schrank 2', bereich_id=b2.bereich_id)
            db.session.add(frisch)
            db.session.commit()
            db.session.add(Gefahrstoff(
                name='FrischInventiert', unterbereich_id=frisch.id,
                user_id=1, sicherheitsdatenblatt='blatt.pdf',
                sdb_datum=datetime.utcnow().date(),
                last_inventur_datum=datetime.utcnow(),
            ))
            db.session.commit()

        html = self._seite()
        self.assertIn('Inventur fällig', html)
        # Schrank 1 ist überfällig, Schrank 2 nicht
        self.assertIn('Labor A / Schrank 1', html)
        self.assertNotIn('Labor A / Schrank 2', html)

    def test_standort_ohne_inventur_ist_faellig(self):
        # Alle vier Stoffe haben noch nie eine Inventur gesehen.
        self._umgebung()
        self.assertIn('noch nie erfasst', self._seite())

    def test_zugriff_nur_auf_eigene_bereiche(self):
        self._umgebung()
        with app.app_context():
            # Ein Benutzer, der nur einen zweiten Bereich sieht.
            benutzer = User(username='benutzer_frist', role='benutzer')
            benutzer.set_password('pass123')
            db.session.add(benutzer)
            db.session.commit()
            fremd = Bereich(name='Fremdes Labor', owner_id=benutzer.id)
            db.session.add(fremd)
            db.session.commit()
            fremd_ub = Unterbereich(name='Fremdschrank', bereich_id=fremd.id)
            db.session.add(fremd_ub)
            db.session.commit()
            db.session.add(Gefahrstoff(
                name='Fremdstoff', unterbereich_id=fremd_ub.id, user_id=benutzer.id,
                sicherheitsdatenblatt='blatt.pdf',
                sdb_datum=date(2019, 1, 1),      # längst überfällig
            ))
            db.session.commit()
            benutzer.assigned_bereiche.append(fremd)
            db.session.commit()

        self.client.get('/logout')
        self.client.post('/login', data={'username': 'benutzer_frist', 'password': 'pass123'},
                         follow_redirects=True)
        html = self._seite()
        self.assertIn('Fremdstoff', html, 'Der eigene Bereich muss sichtbar sein')
        self.assertNotIn('Altstoff', html, 'Fremde Bereiche dürfen nicht auftauchen')

    def test_lesen_bekommt_keine_aktionsknoepfe(self):
        self._umgebung()
        with app.app_context():
            leser = User(username='leser_frist', role='lesen')
            leser.set_password('pass123')
            db.session.add(leser)
            db.session.commit()
            leser.assigned_bereiche.append(Bereich.query.first())
            db.session.commit()

        self.client.get('/logout')
        self.client.post('/login', data={'username': 'leser_frist', 'password': 'pass123'},
                         follow_redirects=True)
        html = self._seite()
        # Die Einträge sind sichtbar ...
        self.assertIn('Altstoff', html)
        # ... aber ohne Knopf, weil die Rolle nichts ändern darf
        self.assertNotIn('SDB-Datum eintragen', html)
        self.assertNotIn('Inventur starten', html)

    def test_kachelzahl_und_liste_stimmen_ueberein(self):
        """Die Kachel auf der Startseite und die Liste kommen aus einer Regel.

        Das war der Ausgangsfehler: die Kachel zählte ab 3 Jahren, die
        SDB-Seite rechnete mit 3 und 5 Jahren - zwei Zahlen für eine Frist.
        """
        self._umgebung()
        with app.app_context():
            heute = datetime.utcnow().date()
            erwartet = sum(
                1 for s in Gefahrstoff.query.all()
                if sdb_status(s, heute)[0] in ('dringend', 'pruefen')
            )

        startseite = self.client.get('/').get_data(as_text=True)
        treffer = re.search(r'kpi-value">(\d+)</span>\s*<span class="kpi-label">Veraltete SDBs',
                            startseite)
        self.assertIsNotNone(treffer, 'Die Kachel "Veraltete SDBs" wurde nicht gefunden')
        self.assertEqual(int(treffer.group(1)), erwartet)
        self.assertEqual(erwartet, 2, 'Mittelaltstoff und Altstoff sind fällig')

        # Und dieselben zwei Stoffe stehen auch in der Liste
        fristen = self._seite()
        self.assertEqual(fristen.count('SDB prüfen') + fristen.count('SDB dringend aktualisieren'),
                         2)

    def test_sdb_seite_nutzt_dieselben_stufen(self):
        """Die SDB-Seite darf nicht wieder eigene Schwellen bekommen."""
        self._umgebung()
        html = self.client.get('/sicherheitsdatenblaetter').get_data(as_text=True)
        self.assertIn('Dringend aktualisieren', html)   # Altstoff
        self.assertIn('Aktualisierung prüfen', html)    # Mittelaltstoff
        self.assertIn('Aktuell', html)                  # Frischstoff

    def test_zaehler_in_der_navigation(self):
        self._umgebung()
        html = self._seite()
        # Zähler-Badge im Navigationsbalken
        self.assertIn('Fristen', html)
        self.assertIn('>4</span>', html, 'Vier offene Fristen (3 SDB + 1 Inventur)')


if __name__ == '__main__':
    unittest.main()
