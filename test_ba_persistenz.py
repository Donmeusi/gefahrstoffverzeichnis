"""Tests für die dauerhaft gespeicherte Betriebsanweisung.

Deckt die drei heiklen Stellen ab: Sanitisierung der contenteditable-Inhalte,
Rechteprüfung (die Rolle "lesen" darf nicht schreiben) und die Obergrenze der
Gebotszeichen. Ausführen mit:

    python -m unittest test_ba_persistenz
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Muss vor dem Import von main gesetzt sein: main legt die Datenbank beim
# Import an. So schreibt der Test nicht in die echte data/gefahrstoffe.db.
os.environ.setdefault('APP_DATA_DIR', tempfile.mkdtemp(prefix='gsv-test-'))
os.environ.setdefault('FLASK_SECRET_KEY', 'test-key')

from main import (  # noqa: E402
    app, db, User, Bereich, Unterbereich, Gefahrstoff, AuditLog,
    sanitize_ba_html, BA_TEXT_FIELDS, BA_GEBOTSZEICHEN, BA_GEBOTSZEICHEN_CODES,
    BA_MAX_GEBOTSZEICHEN,
)


class TestSanitizeBaHtml(unittest.TestCase):
    """Die Inhalte werden mit |safe gerendert, dürfen also kein aktives Markup enthalten."""

    def test_script_wird_entfernt(self):
        ergebnis = sanitize_ba_html('<ul><li>ok</li></ul><script>alert(1)</script>')
        self.assertIn('<ul>', ergebnis)
        self.assertNotIn('script', ergebnis.lower())

    def test_attribute_werden_verworfen(self):
        ergebnis = sanitize_ba_html('<img src=x onerror=alert(1)><div style="color:red">x</div>')
        self.assertNotIn('onerror', ergebnis.lower())
        self.assertNotIn('style=', ergebnis.lower())
        self.assertNotIn('<img', ergebnis.lower())

    def test_erlaubte_tags_bleiben(self):
        ergebnis = sanitize_ba_html('<ul><li><b>H225</b> entzündbar<br></li></ul>')
        for tag in ('<ul>', '<li>', '<b>', '<br>'):
            self.assertIn(tag, ergebnis)

    def test_text_wird_escaped(self):
        self.assertIn('&lt;', sanitize_ba_html('a < b'))

    def test_leere_eingabe(self):
        self.assertEqual(sanitize_ba_html(None), '')
        self.assertEqual(sanitize_ba_html(''), '')

    def test_laengenbegrenzung(self):
        self.assertLessEqual(len(sanitize_ba_html('x' * 50000)), 20000)


class TestBetriebsanweisungSpeichern(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        with app.app_context():
            db.create_all()
            self.bereich = Bereich(name='Labor')
            db.session.add(self.bereich)
            db.session.commit()
            self.unterbereich = Unterbereich(name='Schrank 1', bereich_id=self.bereich.id)
            db.session.add(self.unterbereich)
            db.session.commit()

            admin = User(username='admin', role='admin')
            admin.set_password('x')
            leser = User(username='leser', role='lesen')
            leser.set_password('x')
            db.session.add_all([admin, leser])
            db.session.commit()
            leser.assigned_bereiche.append(self.bereich)
            db.session.commit()

            stoff = Gefahrstoff(name='Aceton', h_saetze='H225', unterbereich_id=self.unterbereich.id)
            db.session.add(stoff)
            db.session.commit()
            self.stoff_id = stoff.id

        self.client = app.test_client()
        self.client.post('/login', data={'username': 'admin', 'password': 'x'},
                         follow_redirects=True)

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def _speichern(self, **felder):
        daten = {'action': 'save'}
        daten.update(felder)
        return self.client.post(
            f'/gefahrstoff/{self.stoff_id}/betriebsanweisung/speichern',
            data=daten, follow_redirects=True)

    def _stoff(self):
        with app.app_context():
            return db.session.get(Gefahrstoff, self.stoff_id)

    def test_seite_laedt(self):
        antwort = self.client.get(f'/gefahrstoff/{self.stoff_id}/betriebsanweisung')
        self.assertEqual(antwort.status_code, 200)

    def test_vorbelegung_ist_augenschutz_und_handschuhe(self):
        html = self.client.get(f'/gefahrstoff/{self.stoff_id}/betriebsanweisung').get_data(as_text=True)
        block = html.split('<div id="gebotszeichen-list">')[1].split('</div>')[0]
        self.assertIn('data-code="M004"', block)   # Augenschutz
        self.assertIn('data-code="M009"', block)   # Schutzhandschuhe

    def test_speichern_und_round_trip(self):
        self._speichern(ba_h_saetze='<ul><li>H225: Leicht entflammbar</li></ul>',
                        ba_gebotszeichen='M004,M009')
        stoff = self._stoff()
        self.assertEqual(stoff.ba_gebotszeichen, 'M004,M009')
        self.assertIn('H225: Leicht entflammbar', json.loads(stoff.ba_texte)['ba_h_saetze'])

        html = self.client.get(f'/gefahrstoff/{self.stoff_id}/betriebsanweisung').get_data(as_text=True)
        self.assertIn('H225: Leicht entflammbar', html)

    def test_skript_landet_nicht_in_der_datenbank(self):
        self._speichern(ba_h_saetze='<ul><li>x</li></ul><script>alert(1)</script>')
        self.assertNotIn('script', json.loads(self._stoff().ba_texte)['ba_h_saetze'].lower())

    def test_nicht_gesendete_felder_bleiben_unberuehrt(self):
        """Ohne JavaScript werden die Bereiche nicht übertragen - dann nichts überschreiben.

        Ein Teil-Submit darf bereits gespeicherte Felder nicht verwerfen.
        """
        self._speichern(ba_h_saetze='<ul><li>original</li></ul>')
        self._speichern(ba_schutzmassnahmen='<ul><li>nur das hier</li></ul>')
        texte = json.loads(self._stoff().ba_texte)
        self.assertIn('ba_h_saetze', texte)
        self.assertIn('ba_schutzmassnahmen', texte)
        self.assertIn('original', texte['ba_h_saetze'])

    def test_leeres_feld_wird_entfernt(self):
        """Ein mitgesendetes, aber leeres Feld bedeutet: bewusst geleert."""
        self._speichern(ba_h_saetze='<ul><li>original</li></ul>',
                        ba_entsorgung='<p>weg damit</p>')
        self._speichern(ba_h_saetze='', ba_entsorgung='')
        self.assertIsNone(self._stoff().ba_texte)

    def test_arbeitsbereich_und_stoffname_werden_nicht_gespeichert(self):
        """Arbeitsbereich und Stoffname kommen live aus der Datenbank."""
        self._speichern(ba_h_saetze='<ul><li>x</li></ul>',
                        ba_arbeitsbereich='Labor / Schrank 1', ba_bezeichnung='Aceton')
        texte = json.loads(self._stoff().ba_texte)
        self.assertIn('ba_h_saetze', texte)
        self.assertNotIn('ba_arbeitsbereich', texte)
        self.assertNotIn('ba_bezeichnung', texte)

    def test_gebotszeichen_obergrenze_und_unbekannte_codes(self):
        self._speichern(ba_gebotszeichen='M001,M002,M003,M004,M008,M009,M010,M999')
        gespeichert = self._stoff().ba_gebotszeichen.split(',')
        self.assertEqual(len(gespeichert), BA_MAX_GEBOTSZEICHEN)
        self.assertNotIn('M999', gespeichert)
        # Reihenfolge folgt der Auswahlliste, nicht der Eingabe
        self.assertEqual(gespeichert, list(BA_GEBOTSZEICHEN_CODES[:BA_MAX_GEBOTSZEICHEN]))

    def test_leser_rolle_darf_nicht_speichern(self):
        self._speichern(ba_gebotszeichen='M017')
        vorher = self._stoff().ba_gebotszeichen

        # Eigener Client: /logout ist GET-only, ein POST darauf liefert 405 und
        # die Admin-Session bliebe bestehen.
        leser_client = app.test_client()
        leser_client.post('/login', data={'username': 'leser', 'password': 'x'},
                          follow_redirects=True)
        leser_client.post(f'/gefahrstoff/{self.stoff_id}/betriebsanweisung/speichern',
                          data={'action': 'save', 'ba_gebotszeichen': 'M001'},
                          follow_redirects=True)

        self.assertEqual(self._stoff().ba_gebotszeichen, vorher)

    def test_leser_sieht_keine_speichern_knoepfe(self):
        leser_client = app.test_client()
        leser_client.post('/login', data={'username': 'leser', 'password': 'x'},
                          follow_redirects=True)
        html = leser_client.get(f'/gefahrstoff/{self.stoff_id}/betriebsanweisung').get_data(as_text=True)
        self.assertNotIn('Speichern</button>', html)
        self.assertNotIn('Zurücksetzen</button>', html)

    def test_zuruecksetzen_leert_beides(self):
        self._speichern(ba_h_saetze='<ul><li>x</li></ul>', ba_gebotszeichen='M004')
        self.client.post(f'/gefahrstoff/{self.stoff_id}/betriebsanweisung/speichern',
                         data={'action': 'reset'}, follow_redirects=True)
        stoff = self._stoff()
        self.assertIsNone(stoff.ba_texte)
        self.assertIsNone(stoff.ba_gebotszeichen)

    def test_audit_log_wird_geschrieben(self):
        self._speichern(ba_h_saetze='<ul><li>x</li></ul>')
        with app.app_context():
            eintraege = AuditLog.query.filter_by(entity_type='Gefahrstoff').all()
        self.assertTrue(eintraege)
        self.assertIn('Betriebsanweisung', eintraege[-1].details)


class TestGebotszeichenBeschriftung(unittest.TestCase):
    """Die Beschriftungen müssen zur tatsächlichen Grafik der Dateien passen."""

    def test_codes_sind_eindeutig(self):
        codes = [code for code, _ in BA_GEBOTSZEICHEN]
        self.assertEqual(len(codes), len(set(codes)))

    def test_jede_beschriftung_hat_eine_datei(self):
        ordner = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'symbols')
        for code, _ in BA_GEBOTSZEICHEN:
            self.assertTrue(os.path.exists(os.path.join(ordner, code + '.svg')),
                            f'{code}.svg fehlt')

    def test_bekannte_zuordnungen(self):
        """Stichproben gegen die offizielle ISO-7010-Liste.

        M002/M003/M004/M024 waren zuvor falsch beschriftet; diese Erwartungen
        halten den korrigierten Stand fest.
        """
        namen = dict(BA_GEBOTSZEICHEN)
        self.assertEqual(namen['M001'], 'Allgemeines Gebotszeichen')
        self.assertEqual(namen['M002'], 'Anleitung beachten')
        self.assertEqual(namen['M003'], 'Gehörschutz benutzen')
        self.assertEqual(namen['M004'], 'Augenschutz benutzen')
        self.assertEqual(namen['M008'], 'Fußschutz benutzen')
        self.assertEqual(namen['M009'], 'Schutzhandschuhe benutzen')
        self.assertEqual(namen['M011'], 'Hände waschen')
        self.assertEqual(namen['M017'], 'Atemschutz benutzen')
        self.assertEqual(namen['M024'], 'Diesen Weg benutzen')


if __name__ == '__main__':
    unittest.main()
