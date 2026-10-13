#!/usr/bin/env python3
"""Wie viel Platz bleibt auf breiten Schirmen ungenutzt?

Die Anwendung ist ueber .container auf 1280 px gedeckelt und waechst darueber
hinaus nicht mit (siehe den Kommentar bei .data-table--dense in style.css).
Auf einem 2560-px-Schirm liegen damit rechnerisch 1280 px brach. Dieses Skript
misst das nach, statt es zu schaetzen - und liefert dieselben Zahlen nach einer
Aenderung erneut, damit man den Unterschied sieht.

Gemessen wird je Seite und je Fensterbreite:
  * der Seitenueberlauf (muss 0 bleiben, sonst scrollt die Seite waagerecht),
  * Breite und Seitenraender des Inhaltsrahmens (<main>) - der ungenutzte Rand
    ist das, was der Nutzer als "nur in der Mitte" sieht,
  * das breiteste Blockelement (Karte, Tabelle, Formular) mit seinem Selektor:
    daran entscheidet sich, ob eine Seite die zusaetzliche Breite ueberhaupt
    sinnvoll fuellen kann.

Aufruf:  ~/.venvs/gsv/bin/python werkzeuge/seitenbreiten.py [breite ...]

Ohne Argumente werden 1280, 1440, 1920 und 2560 px gemessen. Die Messung
braucht eine Weile: jede Kombination ist ein eigener Chrome-Start.
"""
import html as htmlmodul
import json
import os
import re
import subprocess
import sys
import tempfile
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'werkzeuge'))
import handbuchbilder as hb  # noqa: E402  (Instanz + Beispieldaten)

CHROME = hb.CHROME
PASSWORT = 'handbuch123'
ADMIN = 'm.mustermann'

BREITEN = [1280, 1440, 1920, 2560]
HOEHE = 1000

# Seiten, die die Breitenfrage entscheiden: die Tabelle mit den meisten
# Spalten, die uebrigen Listenseiten, ein Formular, eine Detailseite mit
# Fliesstext und die textlastige Systemseite. "@aceton" und "@lager" sind
# Platzhalter und werden nach dem Anlegen der Daten ersetzt.
SEITEN = [
    ('uebersicht', '/'),
    ('fristen', '/fristen'),
    ('mengenschwellen', '/mengenschwellen'),
    ('standorte', '/locations'),
    ('benutzer', '/users'),
    ('historie', '/audit_logs'),
    ('formular', '/add'),
    ('detailseite', '@aceton'),
    ('profil', '/profile'),
    ('system', '/admin/system'),
    ('betriebsanweisungen', '/betriebsanweisungen'),
]

MESS_SCRIPT = """
<script>
// Die Messung wird in die Seite selbst geschrieben; Chrome liest sie per
// --dump-dom aus. Mehrfach messen (sofort, nach fonts.ready, nach load), weil
// die Ersatzschrift andere Breiten liefert.
(function () {
  function messen() {
    var de = document.documentElement;
    var rahmen = document.querySelector('main');
    var aus = {
      viewport: window.innerWidth,
      ueberlauf: de.scrollWidth - de.clientWidth,
      schriftart: getComputedStyle(document.body).fontFamily.split(',')[0].replace(/"/g, '')
    };
    if (rahmen) {
      var r = rahmen.getBoundingClientRect();
      aus.rahmen = Math.round(r.width);
      aus.rand_links = Math.round(r.left);
      aus.rand_rechts = Math.round(window.innerWidth - r.right);
      aus.inhalt = Math.round(rahmen.scrollWidth);
    }
    // Breitestes Blockelement im Inhaltsbereich finden: das zeigt, ob die
    // Seite die zusaetzliche Breite ueberhaupt fuellen kann.
    var kandidaten = document.querySelectorAll(
      'main > *, main .card, main .data-table, main form, main .kennzahl, main .row');
    var breitest = 0, wer = '-';
    for (var i = 0; i < kandidaten.length; i++) {
      var b = kandidaten[i].getBoundingClientRect().width;
      if (b > breitest) {
        breitest = b;
        wer = kandidaten[i].tagName.toLowerCase() +
              (kandidaten[i].className ? '.' + kandidaten[i].className.trim().split(/\\s+/).join('.') : '');
      }
    }
    aus.breitestes = Math.round(breitest);
    aus.breitestes_wer = wer.slice(0, 40);
    // Innere Überbreite der Tabellen: .table-responsive scrollt waagerecht,
    // ohne dass die Seite überläuft. Genau dagegen war das engere Polster von
    // .data-table--dense gerichtet - diese Zahl sagt, ob es noch gebraucht wird.
    var kasten = document.querySelectorAll('.table-responsive');
    var engster = 0;
    for (var j = 0; j < kasten.length; j++) {
      var u = kasten[j].scrollWidth - kasten[j].clientWidth;
      if (u > engster) { engster = u; }
    }
    aus.tabelle_ueberlauf = Math.round(engster);
    var pre = document.getElementById('messwerte');
    if (!pre) {
      pre = document.createElement('pre');
      pre.id = 'messwerte';
      // ⚠️ Das <pre> darf die Seite nicht selbst breiter machen: sein Inhalt
      // steht in EINER langen Zeile, und ein <pre> bricht nicht um. Ungeformt
      // schob es die Seite um bis zu 100 px auseinander - gemessen wurde dann
      // der eigene Messaufbau, nicht die Anwendung.
      pre.style.cssText = 'position:absolute;top:0;left:0;width:1px;'
                        + 'margin:0;overflow:hidden;white-space:normal;';
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


def seite_rendern(m, pfad, ziel):
    """Eine Seite als Admin rendern und fuer Chrome als Datei ablegen."""
    c = m.app.test_client()
    antwort = c.post('/login', data={'username': ADMIN, 'password': PASSWORT},
                     follow_redirects=True)
    if antwort.status_code != 200:
        raise SystemExit(f'ABBRUCH: Anmeldung fehlgeschlagen (HTTP {antwort.status_code})')
    antwort = c.get(pfad)
    if antwort.status_code != 200:
        raise SystemExit(f'ABBRUCH: {pfad} lieferte HTTP {antwort.status_code}')

    html = antwort.get_data(as_text=True)
    if 'nav-account' not in html:
        raise SystemExit(f'ABBRUCH: {pfad} ist nicht angemeldet gerendert')

    # Hell-Modus erzwingen: Headless-Chrome meldet prefers-color-scheme dark,
    # sonst wird der Dunkelmodus gemessen (andere Farben, gleiche Breiten -
    # aber die Zuordnung soll eindeutig sein).
    html = re.sub(r"<script>\s*\(function \(\) \{.*?gsv_theme.*?\}\)\(\);\s*</script>",
                  '', html, count=1, flags=re.S)
    html = html.replace('<html lang="de">', '<html lang="de" data-theme="light">')
    html = html.replace('href="/static/', f'href="file://{REPO}/static/')
    html = html.replace('src="/static/', f'src="file://{REPO}/static/')
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
             f'--window-size={breite},{HOEHE}', '--dump-dom', f'file://{datei}'],
            stdout=f, stderr=fehler)
    try:
        for _ in range(30):
            time.sleep(0.5)
            inhalt = open(zieldatei, encoding='utf-8', errors='replace').read()
            # Das Muster muss Attribute nach der id zulassen: das <pre> traegt
            # seit der Korrektur oben ein style-Attribut, und ein Muster mit
            # ">" direkt hinter id="messwerte" findet dann nichts mehr - der
            # Lauf meldet "keine Messwerte" und man sucht den Fehler im CSS.
            treffer = re.search(r'<pre id="messwerte"[^>]*>(.*?)</pre>', inhalt, re.S)
            # Nur akzeptieren, wenn die eigene Schrift geladen ist - sonst
            # misst man die Ersatzschrift und die Zahlen sind zu klein.
            if treffer and 'Source Sans 3' in treffer.group(1):
                return json.loads(htmlmodul.unescape(treffer.group(1)))
    finally:
        p.kill()
    return None


def bild_machen(datei, breite, ziel, profil):
    """Aufnahme der Seite in der angegebenen Breite (zum Ansehen, nicht Messen)."""
    os.makedirs(profil, exist_ok=True)
    subprocess.run(
        [CHROME, '--headless', '--disable-gpu', '--allow-file-access-from-files',
         f'--user-data-dir={profil}', '--virtual-time-budget=6000', '--hide-scrollbars',
         f'--window-size={breite},{HOEHE}', f'--screenshot={ziel}', f'file://{datei}'],
        capture_output=True)
    return ziel if os.path.exists(ziel) else None


def main():
    if not os.path.exists(CHROME):
        raise SystemExit(f'Chrome nicht gefunden: {CHROME} '
                          '(Pfad ueber die Umgebungsvariable CHROME setzen)')

    breiten = [int(a) for a in sys.argv[1:] if not a.startswith('--')] or BREITEN
    # --seiten=uebersicht,fristen  beschraenkt den Lauf auf einzelne Seiten.
    # Jede Messung ist ein eigener Chrome-Start, der volle Durchlauf dauert
    # daher Minuten; fuer eine einzelne Frage (etwa: passt die Uebersichtstabelle
    # noch ohne das engere Polster?) genuegt eine Seite.
    auswahl = None
    bild = False
    for a in sys.argv[1:]:
        if a.startswith('--seiten='):
            auswahl = [s.strip() for s in a.split('=', 1)[1].split(',') if s.strip()]
        elif a == '--bild':
            bild = True

    m, _ = hb.instanz_laden()
    aceton_id, lager_id = hb.daten_anlegen(m, _)

    arbeit = tempfile.mkdtemp(prefix='gsv-seitenbreiten-')
    dateien = {}
    for name, pfad in SEITEN:
        if auswahl and name not in auswahl:
            continue
        pfad = hb.pfad_aufloesen(pfad, aceton_id, lager_id)
        try:
            dateien[name] = seite_rendern(m, pfad, os.path.join(arbeit, f'{name}.html'))
        except SystemExit as e:
            print(f'  uebersprungen: {e}')

    kopf = ['seite', 'soll', 'viewport', 'rahmen', 'rand_li', 'rand_re',
            'breitestes', 'wer', 'tabelle', 'ueberlauf']
    print('\t'.join(kopf))
    fehlend = 0
    for name, datei in dateien.items():
        for breite in breiten:
            werte = einmal_messen(datei, breite,
                                  os.path.join(arbeit, f'profil-{name}-{breite}'))
            if not werte:
                fehlend += 1
                print(f'{name}\t{breite}\tKEINE MESSWERTE (Dump ohne '
                      'aufgeloeste Schrift)')
                continue
            print('\t'.join(str(x) for x in [
                name, breite, werte['viewport'], werte.get('rahmen', '-'),
                werte.get('rand_links', '-'), werte.get('rand_rechts', '-'),
                werte.get('breitestes', '-'), werte.get('breitestes_wer', '-'),
                werte.get('tabelle_ueberlauf', '-'), werte['ueberlauf']]))
    gesamt = sum(len(breiten) for _ in dateien)
    print(f'\nFertig. {gesamt - fehlend}/{gesamt} Messungen. '
          f'Seitendateien in {arbeit}')
    print('Merke: rand_li/rand_re ist der ungenutzte Rand - das, was der Nutzer '
          'als "nur in der Mitte" sieht.')

    if bild:
        print('\nAufnahmen:')
        for name, datei in dateien.items():
            for breite in breiten:
                ziel = os.path.join(arbeit, f'{name}-{breite}.png')
                if bild_machen(datei, breite, ziel,
                               os.path.join(arbeit, f'bildprofil-{name}-{breite}')):
                    print(f'  {ziel}')


if __name__ == '__main__':
    main()
