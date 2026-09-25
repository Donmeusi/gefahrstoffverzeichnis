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
    sanitize_ba_html, sanitize_ba_unterschrift, BA_TEXT_FIELDS, BA_GEBOTSZEICHEN,
    BA_GEBOTSZEICHEN_CODES, BA_MAX_GEBOTSZEICHEN,
    BA_SIGNATUR_BILD_PRAEFIX, BA_SIGNATUR_MAX_BILD,
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
        # M999 ist ein nie vergebener Code, M002 ein am 25.09.2026 entfernter.
        # Beide müssen herausfallen -- darauf verlässt sich auch die Anzeige
        # bereits gespeicherter Betriebsanweisungen.
        self._speichern(ba_gebotszeichen='M001,M002,M003,M004,M008,M009,M010,M999')
        gespeichert = self._stoff().ba_gebotszeichen.split(',')
        self.assertEqual(len(gespeichert), BA_MAX_GEBOTSZEICHEN)
        self.assertNotIn('M999', gespeichert)
        self.assertNotIn('M002', gespeichert)
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

    def test_nummernfeld_ist_anklickbar(self):
        """Regression: das Nummernfeld war nicht bearbeitbar.

        Ein leeres <span> hat Breite 0 und damit keine Fläche zum Anklicken. Die
        Mindestgröße kommt aus der CSS-Regel für leere inline-Felder; damit die
        greift, muss das Feld die Klasse tragen. Beides wird hier festgehalten.
        """
        html = self.client.get(f'/gefahrstoff/{self.stoff_id}/betriebsanweisung').get_data(as_text=True)
        self.assertIn('class="nummer-feld"', html)
        self.assertIn('span[contenteditable="true"]:empty', html)

    def test_zuruecksetzen_leert_beides(self):
        self._speichern(ba_h_saetze='<ul><li>x</li></ul>', ba_gebotszeichen='M004')
        self.client.post(f'/gefahrstoff/{self.stoff_id}/betriebsanweisung/speichern',
                         data={'action': 'reset'}, follow_redirects=True)
        stoff = self._stoff()
        self.assertIsNone(stoff.ba_texte)
        self.assertIsNone(stoff.ba_gebotszeichen)

    PNG = ('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ'
           'AAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==')

    def _unterschrift(self, daten):
        self.client.post(f'/gefahrstoff/{self.stoff_id}/betriebsanweisung/speichern',
                         data={'action': 'save', 'ba_unterschrift': json.dumps(daten)},
                         follow_redirects=True)

    def test_nummer_wird_gespeichert_und_angezeigt(self):
        self._speichern(ba_nummer='2026-014')
        self.assertIn('2026-014', json.loads(self._stoff().ba_texte)['ba_nummer'])
        html = self.client.get(f'/gefahrstoff/{self.stoff_id}/betriebsanweisung').get_data(as_text=True)
        self.assertIn('2026-014', html)

    def test_gezeichnete_unterschrift_round_trip(self):
        self._unterschrift({'typ': 'bild', 'wert': self.PNG})
        stoff = self._stoff()
        self.assertEqual(json.loads(stoff.ba_unterschrift)['typ'], 'bild')
        html = self.client.get(f'/gefahrstoff/{self.stoff_id}/betriebsanweisung').get_data(as_text=True)
        self.assertIn('data:image/png;base64,', html)
        self.assertIn(self.PNG, html)

    def test_eingetippter_name_round_trip(self):
        self._unterschrift({'typ': 'name', 'wert': 'M. Mustermann'})
        html = self.client.get(f'/gefahrstoff/{self.stoff_id}/betriebsanweisung').get_data(as_text=True)
        self.assertIn('gez. M. Mustermann', html)

    def test_name_mit_markup_wird_escaped_ausgegeben(self):
        """Der Name wird als Text gespeichert und darf nicht als HTML wirken."""
        self._unterschrift({'typ': 'name', 'wert': '<script>alert(1)</script>'})
        html = self.client.get(f'/gefahrstoff/{self.stoff_id}/betriebsanweisung').get_data(as_text=True)
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertIn('&lt;script&gt;', html)

    def test_ungueltige_unterschrift_wird_nicht_gespeichert(self):
        self._unterschrift({'typ': 'bild', 'wert': 'javascript:alert(1)'})
        self.assertIsNone(self._stoff().ba_unterschrift)

    def test_unterschrift_entfernen(self):
        self._unterschrift({'typ': 'name', 'wert': 'M. Mustermann'})
        self._unterschrift({})
        self.assertIsNone(self._stoff().ba_unterschrift)

    def test_unterschrift_landet_nicht_im_audit_log(self):
        """Name und Bild sind personenbezogen - im Protokoll steht nur die Tatsache."""
        self._unterschrift({'typ': 'name', 'wert': 'M. Mustermann'})
        with app.app_context():
            eintraege = AuditLog.query.filter_by(entity_type='Gefahrstoff').all()
        self.assertTrue(eintraege)
        for e in eintraege:
            self.assertNotIn('Mustermann', e.details or '')
        # Der Eintrag zum Speichern nennt die Tatsache, nicht den Inhalt. (Der
        # letzte Eintrag ist inzwischen die Ablage als PDF, deshalb nicht [-1].)
        self.assertTrue(any('Unterschrift gesetzt' in (e.details or '') for e in eintraege))

    def test_zuruecksetzen_leert_auch_die_unterschrift(self):
        self._unterschrift({'typ': 'name', 'wert': 'M. Mustermann'})
        self.client.post(f'/gefahrstoff/{self.stoff_id}/betriebsanweisung/speichern',
                         data={'action': 'reset'}, follow_redirects=True)
        self.assertIsNone(self._stoff().ba_unterschrift)

    # ── Keine Nebenwirkungen beim Speichern ────────────────────────────────

    def _dateien(self):
        ordner = app.config['UPLOAD_FOLDER']
        return set(os.listdir(ordner)) if os.path.isdir(ordner) else set()

    def test_speichern_legt_keine_dateien_an(self):
        """Der Entwurf bleibt in der Datenbank - es wird nichts abgelegt."""
        vorher = self._dateien()
        self._speichern(ba_nummer='2026-014', ba_gebotszeichen='M004,M009')
        self.assertEqual(self._dateien(), vorher)

    def test_speichern_ruehrt_eine_vorhandene_betriebsanweisung_nicht_an(self):
        with app.app_context():
            stoff = db.session.get(Gefahrstoff, self.stoff_id)
            stoff.betriebsanweisung = 'hochgeladen_BA.pdf'
            db.session.commit()
        self._speichern(ba_nummer='2026-014')
        self.assertEqual(self._stoff().betriebsanweisung, 'hochgeladen_BA.pdf')

    def test_erfolgsmeldung_ist_sichtbar(self):
        """Regression: ba_print.html erbt nicht von base.html.

        Ohne eigenen Meldungsblock blieb nach dem Speichern jede Rueckmeldung
        unsichtbar - auch die schlichte Bestaetigung.
        """
        antwort = self.client.post(
            f'/gefahrstoff/{self.stoff_id}/betriebsanweisung/speichern',
            data={'action': 'save', 'ba_nummer': '2026-014'}, follow_redirects=True)
        self.assertIn('Betriebsanweisung gespeichert', antwort.get_data(as_text=True))


class TestUnterschriftPruefung(unittest.TestCase):
    """Die Unterschrift landet als <img src> bzw. als Text im Ausdruck."""

    # Echtes 1x1-PNG (mit PIL geprueft). Ein erfundenes Base64 wuerde an der
    # Bildpruefung scheitern - das war zuerst der Fall.
    PNG = ('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ'
           'AAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==')

    def test_zeichnung_wird_angenommen(self):
        gespeichert = sanitize_ba_unterschrift(json.dumps({'typ': 'bild', 'wert': self.PNG}))
        self.assertIsNotNone(gespeichert)
        self.assertEqual(json.loads(gespeichert)['typ'], 'bild')

    def test_name_wird_angenommen_und_normalisiert(self):
        gespeichert = sanitize_ba_unterschrift(json.dumps({'typ': 'name', 'wert': '  M.   Mustermann '}))
        self.assertEqual(json.loads(gespeichert)['wert'], 'M. Mustermann')

    def test_kein_bild_format_wird_abgelehnt(self):
        """Ein SVG-Data-URL koennte Skript enthalten - nur PNG ist erlaubt."""
        svg = 'data:image/svg+xml;base64,PHN2Zz48c2NyaXB0PmFsZXJ0KDEpPC9zY3JpcHQ+PC9zdmc+'
        self.assertIsNone(sanitize_ba_unterschrift(json.dumps({'typ': 'bild', 'wert': svg})))

    def test_gefaehrliche_werte_werden_abgelehnt(self):
        for wert in ('http://example.com/x.png', 'javascript:alert(1)', '<img src=x onerror=1>', ''):
            with self.subTest(wert=wert):
                self.assertIsNone(
                    sanitize_ba_unterschrift(json.dumps({'typ': 'bild', 'wert': wert})))

    def test_zu_grosses_bild_wird_abgelehnt(self):
        zu_gross = BA_SIGNATUR_BILD_PRAEFIX + 'A' * (BA_SIGNATUR_MAX_BILD + 1)
        self.assertIsNone(sanitize_ba_unterschrift(json.dumps({'typ': 'bild', 'wert': zu_gross})))

    def test_unbekannter_typ_und_kaputtes_json(self):
        for roh in ('', 'kein json', '[]', 'null', '{}',
                    json.dumps({'typ': 'pdf', 'wert': 'x'}), json.dumps({'typ': 'name', 'wert': ''})):
            with self.subTest(roh=roh):
                self.assertIsNone(sanitize_ba_unterschrift(roh))


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
        halten den korrigierten Stand fest. M014/M022 waren früher unter den
        Beschriftungen anderer Zeichen geführt ("Schutzhelm", "Hautschutzcreme")
        und werden hier mit ihren offiziellen Bezeichnungen erwartet.

        M002 fehlt hier bewusst: das Zeichen wurde am 25.09.2026 wegen seiner
        CC-BY-SA-3.0-Lizenz aus der Auswahl entfernt (siehe
        static/symbols/SOURCES.md).
        """
        namen = dict(BA_GEBOTSZEICHEN)
        self.assertEqual(namen['M001'], 'Allgemeines Gebotszeichen')
        self.assertEqual(namen['M003'], 'Gehörschutz benutzen')
        self.assertEqual(namen['M004'], 'Augenschutz benutzen')
        self.assertEqual(namen['M008'], 'Fußschutz benutzen')
        self.assertEqual(namen['M009'], 'Schutzhandschuhe benutzen')
        self.assertEqual(namen['M011'], 'Hände waschen')
        self.assertEqual(namen['M014'], 'Kopfschutz benutzen')
        self.assertEqual(namen['M017'], 'Atemschutz benutzen')
        self.assertEqual(namen['M022'], 'Hautschutzmittel benutzen')
        self.assertEqual(namen['M024'], 'Diesen Weg benutzen')
        self.assertNotIn('M002', namen)


if __name__ == '__main__':
    unittest.main()
