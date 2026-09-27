"""Erzeugt die Bildschirmaufnahmen für das Benutzerhandbuch (handbuch-bilder/).

Baut eine **isolierte** Instanz der Anwendung mit plausiblen Beispieldaten
(Gefahrstoffe, Standorte, Dokumente, Fristen, ein CMR-Fall), rendert die Seiten
über den Testclient und lässt Chrome Aufnahmen davon machen.

Aufrufen mit dem venv der Anwendung:

    python3 werkzeuge/handbuchbilder.py

Voraussetzungen: die Abhängigkeiten der Anwendung (Flask und so weiter) sowie
Google Chrome unter dem üblichen macOS-Pfad. Ein abweichender Pfad lässt sich
über die Umgebungsvariable CHROME setzen.

Die Aufnahmen sind bewusst reproduzierbar: Wer die Oberfläche ändert, kann die
Bilder neu erzeugen, statt sie nachzubauen. Danach das PDF neu erzeugen (siehe
Kopf von handbuch-druck.css).

Hinweis: Ein erneuter Lauf kann einzelne Bilder minimal verändern — gemessen
rund 0,4 % der Pixel bei einem Helligkeitsunterschied von 1 von 255 Stufen.
Das ist Kantenglättung, kein Inhaltsunterschied; die Aufnahmen sind mit dem
Auge identisch. Wer keine solchen Diffs im Repo will, macht die Bilder nur
dann neu, wenn sich die Oberfläche tatsächlich geändert hat.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZIEL = os.path.join(REPO, 'handbuch-bilder')
CHROME = os.environ.get(
    'CHROME', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')

# Breite und Höhe der Aufnahmen. 1440 px Breite entspricht der Breite, in der
# die Navigation unverdichtet sichtbar ist; die Höhen sind je Seite so gewählt,
# dass der interessante Teil vollständig im Bild ist.
SEITEN = [
    ('00-login', '/login', 1440, 760, False),
    ('01-dashboard', '/', 1440, 1000, True),
    ('02-gefahrstoff-anlegen', '/add', 1440, 1700, True),
    ('03-gefahrstoff-detail', '@aceton', 1440, 1000, True),
    ('04-fristen', '/fristen', 1440, 900, True),
    ('05-schrank-aushang', '@lager/print', 1440, 1150, True),
    ('06-betriebsanweisung', '@aceton/ba', 1440, 1250, True),
]


def instanz_laden():
    """Importiert die Anwendung mit einer isolierten Datenbank in /tmp.

    ⚠️ APP_DATA_DIR muss VOR dem Import gesetzt sein: main.py liest den Wert
    beim Import und bildet daraus den Datenbankpfad. Ohne das schreibt dieses
    Skript in die echte data/gefahrstoffe.db — genau der Fehler, den die
    Testdateien bis v3.17 hatten (siehe testkonfiguration.py, das dasselbe für
    die Tests tut).
    """
    daten = tempfile.mkdtemp(prefix='gsv-handbuch-')
    os.environ['APP_DATA_DIR'] = daten
    sys.path.insert(0, REPO)

    import main as m

    # Sicherung, falls die Zeile oben jemand entfernt oder umbaut: lieber
    # abbrechen als in die echte Datenbank schreiben.
    if os.path.abspath(m.app_data_dir) == os.path.join(REPO, 'data'):
        raise SystemExit(
            'ABBRUCH: APP_DATA_DIR zeigt auf die echte Datenbank '
            f'({m.app_data_dir}). Es wird nichts geschrieben.')

    m.app.config['WTF_CSRF_ENABLED'] = False
    return m, daten


def vor_jahren(heute, jahre):
    """Datum n Jahre zurück; n darf ein Bruchteil sein (0.5 = ein halbes Jahr)."""
    return heute - timedelta(days=int(round(jahre * 365.25)))


def daten_anlegen(m, daten):
    """Legt die Beispieldaten an. Gibt die IDs zurück, die für die Seiten
    gebraucht werden (Aceton und das TRGS-510-Lager) — bewusst über den Namen
    gesucht statt fest verdrahtet, damit es nicht von der Reihenfolge abhängt.
    """
    heute = datetime.utcnow().date()
    db = m.db.session

    with m.app.app_context():
        m.db.create_all()
        chef = m.User(username='m.mustermann', role='admin')
        chef.set_password('handbuch123')
        db.add(chef)
        db.commit()

        labor = m.Bereich(name='Laborgebäude A', owner_id=chef.id)
        lager = m.Bereich(name='Zentrales Lager', owner_id=chef.id)
        db.add_all([labor, lager])
        db.commit()

        raum101 = m.Unterbereich(name='Raum 101 – Nassbereich', bereich_id=labor.id)
        raum102 = m.Unterbereich(name='Raum 102 – Chemikalienschrank', bereich_id=labor.id)
        lager510 = m.Unterbereich(name='Gefahrstofflager (TRGS 510)', bereich_id=lager.id)
        db.add_all([raum101, raum102, lager510])
        db.commit()

        # (Name, CAS, EG, Signalwort, Piktogramme, H-Sätze, P-Sätze, Lagerklasse,
        #  Menge, Einheit, Standort-ID, SDB-Jahre zurück, Prüfung, Prüf-Jahre)
        # Die Mischung ist Absicht: sie erzeugt alle Stufen der Fristenliste.
        stoffe = [
            ('Aceton', '67-64-1', '200-662-2', 'Gefahr', 'GHS02,GHS07',
             'H225,H319,H336', 'P210,P233,P305+P351+P338', '3', 2.5, 'L',
             raum102.id, 1.0, 'nein', 0.5),
            ('Ethanol 96 %', '64-17-5', '200-578-6', 'Gefahr', 'GHS02',
             'H225,H319', 'P210,P233,P280', '3', 5.0, 'L', raum101.id, 4.0, 'nie', 0),
            ('2-Propanol', '67-63-0', '200-661-7', 'Gefahr', 'GHS02,GHS07',
             'H225,H319,H336', 'P210,P261,P305+P351+P338', '3', 1.0, 'L',
             raum102.id, 1.0, 'ja', 0.5),
            ('Natriumhydroxid', '1310-73-2', '215-185-5', 'Gefahr', 'GHS05',
             'H290,H314', 'P280,P305+P351+P338,P310', '8B', 500.0, 'g',
             raum102.id, 2.0, 'nie', 0),
            ('Salzsäure 32 %', '7647-01-0', '231-595-7', 'Gefahr', 'GHS05,GHS07',
             'H290,H314,H335', 'P260,P280,P303+P361+P353', '8B', 1.0, 'L',
             lager510.id, 6.0, 'nein', 3.5),
            ('Wasserstoffperoxid 30 %', '7722-84-1', '231-765-0', 'Gefahr',
             'GHS02,GHS05,GHS07', 'H272,H302,H315,H318',
             'P210,P280,P305+P351+P338', '5.1B', 1.0, 'L', lager510.id, 3.5, 'ja', 1.0),
            ('Formaldehyd-Lösung 37 %', '50-00-0', '200-001-8', 'Gefahr',
             'GHS05,GHS06,GHS08', 'H301,H314,H317,H335,H341,H350',
             'P201,P260,P280,P301+P310', '6.1D', 0.5, 'L', raum102.id, 1.0, 'nein', 1.0),
        ]
        for (name, cas, eg, wort, pik, h, p, lgk, menge, einheit, ort,
             sdb_jahre, pruefung, pruef_jahre) in stoffe:
            db.add(m.Gefahrstoff(
                name=name, cas_nummer=cas, eg_nummer=eg, signalwort=wort,
                # Piktogramme komma-getrennt, wie /add sie speichert
                piktogramme=pik, h_saetze=h, p_saetze=p, lagerklasse=lgk,
                menge=menge, mengeneinheit=einheit, unterbereich_id=ort,
                user_id=chef.id, lagerort='Schrank 2, Fach A',
                sicherheitsdatenblatt=f'{name.split()[0]}_SDB.pdf',
                betriebsanweisung=f'{name.split()[0]}_BA.pdf',
                sdb_datum=vor_jahren(heute, sdb_jahre) if sdb_jahre else None,
                # 'nie' heißt: gar keine Prüfung dokumentiert (erscheint als Zahl)
                substitutionspruefung=None if pruefung == 'nie' else pruefung,
                substitution_geprueft_am=(None if pruefung == 'nie'
                                          else vor_jahren(heute, pruef_jahre)),
                ersatzstoff='Ethanol 70 %' if pruefung == 'ja' else None,
                gefahrenkategorien=('Entzündbare Flüssigkeiten' if lgk == '3'
                                    else 'Ätz-/Reizwirkung'),
            ))

        # Ohne Sicherheitsdatenblatt - zeigt "Kein SDB hinterlegt"
        db.add(m.Gefahrstoff(name='Kaliumpermanganat', cas_nummer='7722-64-7',
                             signalwort='Gefahr', piktogramme='GHS03,GHS07',
                             h_saetze='H272,H302,H410', lagerklasse='5.1B',
                             menge=250.0, mengeneinheit='g',
                             unterbereich_id=lager510.id, user_id=chef.id))

        # CMR-Stoff: wartet auf Freigabe und ist deshalb nicht sichtbar
        db.add(m.Gefahrstoff(name='Chloroform', cas_nummer='67-66-3',
                             eg_nummer='200-663-8', signalwort='Gefahr',
                             piktogramme='GHS06,GHS08',
                             h_saetze='H302,H315,H319,H331,H351,H361d',
                             lagerklasse='6.1D', menge=0.5, mengeneinheit='L',
                             unterbereich_id=raum102.id, user_id=chef.id,
                             is_approved=False,
                             sicherheitsdatenblatt='Chloroform_SDB.pdf',
                             sdb_datum=vor_jahren(heute, 1)))
        db.commit()

        # Ein Standort lange nicht inventarisiert -> Inventurfrist
        for s in m.Gefahrstoff.query.filter_by(unterbereich_id=lager510.id).all():
            s.last_inventur_datum = datetime.utcnow() - timedelta(days=430)
        for s in m.Gefahrstoff.query.filter_by(unterbereich_id=raum101.id).all():
            s.last_inventur_datum = datetime.utcnow() - timedelta(days=30)
        db.commit()

        # Dokumente kopieren, damit die Links im Bild echt wirken
        uploads = os.path.join(daten, 'uploads')
        os.makedirs(uploads, exist_ok=True)
        for quelle, feld in [('dummy_sdb.pdf', 'sicherheitsdatenblatt'),
                             ('dummy_ba.pdf', 'betriebsanweisung')]:
            for stoff in m.Gefahrstoff.query.all():
                name = getattr(stoff, feld)
                if name and not os.path.exists(os.path.join(uploads, name)):
                    shutil.copy2(os.path.join(REPO, quelle),
                                 os.path.join(uploads, name))

        # Eine ausgefüllte Betriebsanweisung, damit der Ausdruck nicht leer ist.
        # Die Codes müssen in BA_GEBOTSZEICHEN vorkommen - unbekannte filtert
        # load_ba_gebotszeichen heraus (M016 etwa gibt es dort nicht).
        aceton = m.Gefahrstoff.query.filter_by(name='Aceton').first()
        aceton.ba_gebotszeichen = 'M004,M009,M022'   # Augen, Hände, Hautschutz
        aceton.ba_texte = (
            '{"ba_taetigkeit": "Umgang mit Aceton als Reinigungsmittel im '
            'Nassbereich.", "ba_schutzmassnahmen": "Schutzbrille und '
            'Nitrilhandschuhe tragen. Nur im Abzug oder bei geöffnetem Fenster '
            'arbeiten. Zündquellen fernhalten."}')
        db.commit()

        aceton_id = aceton.id
        lager_id = m.Unterbereich.query.filter_by(
            name='Gefahrstofflager (TRGS 510)').first().id
        print(f"Beispieldaten: {m.Gefahrstoff.query.count()} Gefahrstoffe, "
              f"{m.Bereich.query.count()} Bereiche, "
              f"{m.Unterbereich.query.count()} Standorte")

    return aceton_id, lager_id


def pfad_aufloesen(kuerzel, aceton_id, lager_id):
    """Ersetzt die Platzhalter in SEITEN durch echte Adressen."""
    return {
        '@aceton': f'/view/{aceton_id}',
        '@aceton/ba': f'/gefahrstoff/{aceton_id}/betriebsanweisung',
        '@lager/print': f'/location/{lager_id}/print',
    }.get(kuerzel, kuerzel)


def aufnahmen_machen(m, aceton_id, lager_id, arbeitsverzeichnis):
    """Rendert die Seiten und lässt Chrome Aufnahmen machen."""
    client = m.app.test_client()
    client.post('/login',
                data={'username': 'm.mustermann', 'password': 'handbuch123'},
                follow_redirects=True)

    os.makedirs(ZIEL, exist_ok=True)
    for name, kuerzel, breite, hoehe, eingeloggt in SEITEN:
        pfad = pfad_aufloesen(kuerzel, aceton_id, lager_id)
        c = client if eingeloggt else m.app.test_client()
        antwort = c.get(pfad)
        if antwort.status_code != 200:
            print(f"  {name}: HTTP {antwort.status_code} — übersprungen")
            continue

        # Statische Dateien auf file:// umbiegen: die Seite wird aus einer
        # Datei geladen, nicht über den Server, sonst fehlen CSS und Schriften.
        html = antwort.get_data(as_text=True)
        html = html.replace('href="/static/', f'href="file://{REPO}/static/')
        html = html.replace('src="/static/', f'src="file://{REPO}/static/')
        quelle = os.path.join(arbeitsverzeichnis, f'{name}.html')
        with open(quelle, 'w', encoding='utf-8') as f:
            f.write(html)

        ziel = os.path.join(ZIEL, f'{name}.png')
        subprocess.run(
            [CHROME, '--headless=new', '--disable-gpu', '--no-sandbox',
             f'--window-size={breite},{hoehe}', '--virtual-time-budget=4000',
             f'--screenshot={ziel}', f'file://{quelle}'],
            capture_output=True, timeout=120)
        groesse = os.path.getsize(ziel) if os.path.exists(ziel) else 0
        print(f"  {name}: {breite}x{hoehe}, {groesse // 1024} KB")


def main():
    if not os.path.exists(CHROME):
        raise SystemExit(
            f'Chrome nicht gefunden unter {CHROME}. Pfad über die '
            'Umgebungsvariable CHROME setzen.')

    m, daten = instanz_laden()
    arbeitsverzeichnis = tempfile.mkdtemp(prefix='gsv-handbuch-html-')
    print(f"Isolierte Instanz unter {daten}")
    aceton_id, lager_id = daten_anlegen(m, daten)
    aufnahmen_machen(m, aceton_id, lager_id, arbeitsverzeichnis)
    print(f"\nFertig. Bilder in {ZIEL}")
    print("PDF neu erzeugen: siehe Kopf von handbuch-druck.css")


if __name__ == '__main__':
    main()
