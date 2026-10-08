#!/usr/bin/env python3
"""Messung der Hauptnavigation: Wie breit ist sie, und ab welcher Fensterbreite
laueft die Seite waagerecht ueber?

Die Schwellen in style.css (@media min-width 1200px und max-width 1199px) haengen
an diesen Zahlen. Wird ein Menuepunkt ergaenzt oder entfernt, hier nachmessen.

Warum es dieses Skript gibt: die Schwellen der Navigation in style.css sind
dreimal von Hand nachgezogen worden, und beim dritten Mal ging es schief (die
obere Grenze bei 1610 px war falsch herum, die Seite scrollte zwischen 1290 und
2000 px). Die Messung lag damals nur unter /tmp und war beim naechsten Mal weg.
Deshalb wird hier gemessen statt geschaetzt.

Vorgehen:
  1. Die Anwendung wird mit einer isolierten Datenbank in /tmp geladen; die
     Beispieldaten kommen aus werkzeuge/handbuchbilder.py (Admin, Moderator und
     Leser dazu).
  2. Die Startseite wird JE ROLLE ueber den Testclient gerendert, /static/ auf
     file:// umgebogen und ein Mess-Script vor </body> eingehaengt, das den
     Ueberlauf in ein <pre id="messwerte"> schreibt.
  3. Chrome laeuft JE BREITE einmal (--window-size) und wird per --dump-dom
     ausgelesen.

⚠️ Vier Fallen, die alle schon falsche Zahlen geliefert haben:
  * iframes sind Flex-Kinder und werden auf die Fensterbreite GESTAUCHT, wenn
    ihnen nicht flex: 0 0 auto mitgegeben wird - dann misst man still zu kleine
    Breiten. Deshalb wird hier ohne iframes gemessen und der innere viewport
    mitprotokolliert.
  * Ein iframe-Harness vertraegt sich NICHT mit --virtual-time-budget: das
    Budget ist aufgebraucht, bevor die iframes geladen sind, und Chrome dumpte
    den DOM mitten in der Messung ("laeuft" als Ergebnis).
  * document.fonts.ready muss abgewartet werden, sonst misst man die
    Ersatzschrift. Das Mess-Script misst zusaetzlich nach fonts.ready und nach
    load; der Dump muss "Source Sans 3" als Schrift nennen, sonst gilt er nicht.
  * Chrome beendet sich bei --dump-dom nicht von selbst - hier wird gepollt
    und danach beendet.

Aufruf:  ~/.venvs/gsv/bin/python werkzeuge/navbreiten.py
"""
import html as htmlmodul
import json
import os
import re
import subprocess
import sys
import tempfile
import time

def repo_finden():
    """Projektverzeichnis: ueber GSV_REPO, sonst aufwaerts vom Skript aus."""
    if os.environ.get('GSV_REPO'):
        return os.environ['GSV_REPO']
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(4):
        if os.path.exists(os.path.join(d, 'main.py')):
            return d
        d = os.path.dirname(d)
    return '/Users/donmeusi/projects/gefahrstoffverzeichnis'


REPO = repo_finden()
sys.path.insert(0, os.path.join(REPO, 'werkzeuge'))
import handbuchbilder as hb  # noqa: E402  (liefert Instanz + Beispieldaten)

CHROME = hb.CHROME
PASSWORT = 'handbuch123'
ROLLEN = ['admin', 'moderator', 'lesen']
BENUTZER = {'admin': 'm.mustermann', 'moderator': 'm.mod', 'lesen': 'm.leser'}

# Alle Breiten, die fuer die Entscheidung gebraucht werden: uebliche
# Geraetebreiten, die alten Schwellen und die Kandidaten +-1 px.
BREITEN = [1024, 1140, 1199, 1200, 1201, 1240, 1280, 1440, 1920, 2560]
# Die beiden anderen Rollen haben kuerzere Menues - fuer sie genuegen die
# Eckwerte und die Schwelle.
BREITEN_KURZ = [1199, 1200, 1440]

MESS_SCRIPT = """
<script>
// Messung in die Seite selbst schreiben: Chrome liest sie per --dump-dom aus.
(function () {
  function messen() {
    const de = document.documentElement;
    const nav = document.querySelector('.nav-container');
    const ul = document.querySelector('.nav-links');
    const a = document.querySelector('.nav-links a');
    const aus = {
      viewport: window.innerWidth,
      seite: de.scrollWidth - de.clientWidth,
      leiste: nav ? nav.scrollWidth - nav.clientWidth : 0,
      leiste_breite: nav ? nav.scrollWidth : 0,
      container: nav ? Math.round(nav.getBoundingClientRect().width) : 0,
      menue: ul && getComputedStyle(ul).display === 'none' ? 'klapp' : 'liste',
      schrift: a ? getComputedStyle(a).fontSize : '-',
      schriftart: a ? getComputedStyle(a).fontFamily.split(',')[0].replace(/"/g, '') : '-'
    };
    let pre = document.getElementById('messwerte');
    if (!pre) {
      pre = document.createElement('pre');
      pre.id = 'messwerte';
      document.body.appendChild(pre);
    }
    pre.textContent = JSON.stringify(aus);
  }
  messen();
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(messen);
  window.addEventListener('load', messen);
})();
</script>
"""


def rollen_anlegen(m):
    """Moderator und Leser ergaenzen - die Beispieldaten haben nur einen Admin."""
    with m.app.app_context():
        for name, rolle in (('m.mod', 'moderator'), ('m.leser', 'lesen')):
            if m.User.query.filter_by(username=name).first():
                continue
            u = m.User(username=name, role=rolle)
            u.set_password(PASSWORT)
            m.db.session.add(u)
        m.db.session.commit()


def seite_rendern(m, rolle, ziel, menues_offen=False):
    """Startseite der Rolle rendern und als Datei ablegen."""
    c = m.app.test_client()
    c.post('/login', data={'username': BENUTZER[rolle], 'password': PASSWORT},
           follow_redirects=True)
    antwort = c.get('/')
    if antwort.status_code != 200:
        raise SystemExit(f'ABBRUCH: Startseite als {rolle} lieferte '
                         f'HTTP {antwort.status_code}')

    html = antwort.get_data(as_text=True)
    if 'nav-account' not in html:
        raise SystemExit(f'ABBRUCH: als {rolle} ist die Leiste nicht angemeldet '
                         'gerendert (Login fehlgeschlagen?)')

    # Hell-Modus erzwingen: Headless-Chrome meldet prefers-color-scheme dark,
    # und base.html setzt data-theme aus der Systemvorliebe.
    html = re.sub(r"<script>\s*\(function \(\) \{.*?gsv_theme.*?\}\)\(\);\s*</script>",
                  '', html, count=1, flags=re.S)
    html = html.replace('<html lang="de">', '<html lang="de" data-theme="light">')
    html = html.replace('href="/static/', f'href="file://{REPO}/static/')
    html = html.replace('src="/static/', f'src="file://{REPO}/static/')
    if menues_offen:
        html = html.replace('</body>',
                            '<script>document.querySelectorAll("details")'
                            '.forEach(function (d) { d.open = true; });</script></body>')
    html = html.replace('</body>', MESS_SCRIPT + '</body>')
    with open(ziel, 'w', encoding='utf-8') as f:
        f.write(html)
    return ziel


def einmal_messen(datei, breite, profil):
    """Eine Breite messen. Gibt das Werte-Dict zurueck oder None."""
    os.makedirs(profil, exist_ok=True)
    zieldatei = os.path.join(profil, 'dump.html')
    fehlerdatei = os.path.join(profil, 'chrome-stderr.txt')
    if os.path.exists(zieldatei):
        os.remove(zieldatei)
    with open(zieldatei, 'w') as f, open(fehlerdatei, 'w') as fehler:
        p = subprocess.Popen(
            [CHROME, '--headless', '--disable-gpu', '--allow-file-access-from-files',
             f'--user-data-dir={profil}', '--virtual-time-budget=6000',
             f'--window-size={breite},900', '--dump-dom', f'file://{datei}'],
            stdout=f, stderr=fehler)
    try:
        for _ in range(30):
            time.sleep(0.5)
            inhalt = open(zieldatei, encoding='utf-8', errors='replace').read()
            m = re.search(r'<pre id="messwerte">(.*?)</pre>', inhalt, re.S)
            if m and 'Source Sans 3' in m.group(1):
                return json.loads(htmlmodul.unescape(m.group(1)))
    finally:
        p.kill()
    return None


def main():
    if not os.path.exists(CHROME):
        raise SystemExit(f'Chrome nicht gefunden: {CHROME} '
                         '(Pfad ueber die Umgebungsvariable CHROME setzen)')

    m, _ = hb.instanz_laden()
    hb.daten_anlegen(m, _)
    rollen_anlegen(m)

    arbeit = tempfile.mkdtemp(prefix='gsv-navbreiten-')
    dateien = {}
    for rolle in ROLLEN:
        dateien[rolle] = seite_rendern(
            m, rolle, os.path.join(arbeit, f'seite-{rolle}.html'))
    dateien['admin-offen'] = seite_rendern(
        m, 'admin', os.path.join(arbeit, 'seite-admin-offen.html'), menues_offen=True)

    faelle = [('admin', dateien['admin'], b, 'zu') for b in BREITEN]
    for rolle in ('moderator', 'lesen'):
        faelle += [(rolle, dateien[rolle], b, 'zu') for b in BREITEN_KURZ]
    faelle += [('admin', dateien['admin-offen'], b, 'offen')
               for b in (320, 768, 1180, 1440, 1920)]

    print(f'{len(faelle)} Messungen, Arbeitsverzeichnis {arbeit}\n')
    kopf = ['rolle', 'zustand', 'soll', 'viewport', 'seitenueberlauf',
            'leisteueberlauf', 'leiste_breite', 'container', 'menue', 'schrift']
    print('\t'.join(kopf))
    fehlend = 0
    for rolle, datei, breite, zustand in faelle:
        werte = einmal_messen(datei, breite, os.path.join(arbeit, f'profil-{rolle}-{breite}'))
        if not werte:
            fehlend += 1
            print(f'{rolle}\t{zustand}\t{breite}\tKEINE MESSWERTE (Dump ohne '
                  'aufgeloeste Schrift)')
            continue
        print('\t'.join(str(x) for x in [
            rolle, zustand, breite, werte['viewport'], werte['seite'],
            werte['leiste'], werte['leiste_breite'], werte['container'],
            werte['menue'], werte['schrift']]))
    print(f'\nFertig. {len(faelle) - fehlend}/{len(faelle)} Messungen. '
          f'Seitendateien in {arbeit}')
    print('Merke: seitenueberlauf > 0 heisst, die Seite scrollt waagerecht.')


if __name__ == '__main__':
    main()
