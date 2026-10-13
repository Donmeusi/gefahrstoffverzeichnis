#!/usr/bin/env python3
"""Piktogramme und Signalwort aus den H-Saetzen - nach CLP, ohne fremde Quelle.

Wozu: Bisher kamen die Piktogramme aus der Autovervollstaendigung von PubChem.
Dort mischt dieselbe CAS-Nummer Quellen aus verschiedenen Rechtsraeumen - fuer
Salzsaeure (7647-01-0) steht neben der EU-Einstufung der VO (EG) 1272/2008 auch
japanisches Recht (NITE-CMC) mit H330, H334, H370 und H372. Welche Quelle
gewaehlt wird, entscheidet der Code anhand des Namens; fehlt eine EU-Angabe,
greift irgendeine. Fuer ein Gefahrstoffverzeichnis ist das keine Grundlage.

Deshalb leitet die Anwendung Piktogramme und Signalwort jetzt selbst aus den
H-Saetzen ab. Die H-Satz-**Codes** sind sprachneutral (H314 heisst ueberall
H314), also genuegt eine Tabelle Code -> Piktogramm/Signalwort. Sie steht unten
und stammt aus der Verordnung, nicht aus einer Datenbank.

Maßgeblich ist **Anhang I** der CLP-VO (je Gefahrenklasse die Tabelle mit
Einstufung / Piktogramm-Code / Signalwort-Code / Gefahrenhinweis-Code); die
Piktogramme selbst und ihre Zuordnung zu den Klassen stehen in **Anhang V**.
Anhang VI Teil 3 (die Stoffliste) ist hier NICHT die Quelle.

Bildungsregel:
* Piktogramme = Vereinigung der Piktogramme aller Kategorien, in denen der Code
  nach Anhang I vorkommt.
* Signalwort = das strengste der beteiligten Kategorien. Kommt ein Code in
  mehreren Kategorien mit unterschiedlichem Signalwort vor, gilt "Gefahr"
  (konservativ; die betreffenden Codes sind in der Tabelle als AMBIVALENT
  gekennzeichnet).
* **Ein Code ohne Piktogramm ist ein gueltiges Ergebnis**, keine Luecke: H205
  (Unterklasse 1.5), H362 (Laktation), H412 und H413 (Gewaehrd. Chronisch 3/4)
  tragen nach CLP keines.

⚠️ Zwei Fallen beim Einlesen der Codes:
* **Die Schreibweise ist bedeutungstragend.** `H360Fd` und `H360FD` sind
  verschiedene Codes, ebenso `H361fd` und `H361FD`. Ein Vergleich, der die
  Schreibweise ignoriert, wirft sie zusammen - hier wird deshalb genau
  verglichen, nur das fuehrende "H" wird gross geschrieben.
* **Kombinationssaetze gehoeren zusammen.** `H300+H310` ist ein eigener Code
  (akute Toxizitaet auf mehreren Aufnahmewegen) und darf nicht in H300 und H310
  zerlegt werden. Deshalb werden sie zuerst gesucht und aus dem Text entfernt.

Aufbau: Tabelle `ZUORDNUNG`, dann die Ableitung. Verwendet von `main.py`
(Autovervollstaendigung und SDB-Parser). Geprueft in `test_piktogramme.py`.
"""
import re

ZUORDNUNG = {
    # --- 2.1 Explosive Stoffe/Gemische und Erzeugnisse mit Explosivstoff ---
    #     Piktogramm GHS01 nur fuer instabil + Unterklassen 1.1-1.4 (Anhang V, Nr. 1.1
    #     bzw. Nr. 1.6); Unterklasse 1.5 = kein Piktogramm.
    'H200': {'piktogramme': ['GHS01'], 'signalwort': 'Gefahr'},   # instabil, explosiv
    'H201': {'piktogramme': ['GHS01'], 'signalwort': 'Gefahr'},   # Unterklasse 1.1
    'H202': {'piktogramme': ['GHS01'], 'signalwort': 'Gefahr'},   # Unterklasse 1.2
    'H203': {'piktogramme': ['GHS01'], 'signalwort': 'Gefahr'},   # Unterklasse 1.3
    'H204': {'piktogramme': ['GHS01'], 'signalwort': 'Achtung'},  # Unterklasse 1.4
    'H205': {'piktogramme': [],        'signalwort': 'Gefahr'},   # Unterklasse 1.5 (kein Piktogramm)
    # --- 2.17 Desensibilisierte explosive Stoffe/Gemische (Anhang V Nr. 1.2: GHS02) ---
    'H206': {'piktogramme': ['GHS02'], 'signalwort': 'Gefahr'},   # Kat. 1
    'H207': {'piktogramme': ['GHS02'], 'signalwort': 'Gefahr'},   # Kat. 2 Gefahr / Kat. 3 Achtung -> AMBIVALENT
    'H208': {'piktogramme': ['GHS02'], 'signalwort': 'Achtung'},  # Kat. 4

    # --- 2.2 Entzuendbare Gase (Anhang V Nr. 1.2: GHS02; Kat. 2 ohne Piktogramm) ---
    'H220': {'piktogramme': ['GHS02'], 'signalwort': 'Gefahr'},   # Kat. 1A
    'H221': {'piktogramme': ['GHS02'], 'signalwort': 'Gefahr'},   # Kat. 1B Gefahr / Kat. 2 Achtung -> AMBIVALENT
    'H230': {'piktogramme': ['GHS02'], 'signalwort': 'Gefahr'},   # chemisch instabiles Gas A (Kat. 1A)
    'H231': {'piktogramme': ['GHS02'], 'signalwort': 'Gefahr'},   # chemisch instabiles Gas B (Kat. 1A)
    'H232': {'piktogramme': ['GHS02'], 'signalwort': 'Gefahr'},   # pyrophores Gas (Kat. 1A)
    # --- 2.3 Aerosole (Anhang V Nr. 1.2: GHS02 fuer Kat. 1, 2; Kat. 3 ohne Piktogramm) ---
    'H222': {'piktogramme': ['GHS02'], 'signalwort': 'Gefahr'},   # Kat. 1
    'H223': {'piktogramme': ['GHS02'], 'signalwort': 'Achtung'},  # Kat. 2
    'H229': {'piktogramme': ['GHS02'], 'signalwort': 'Gefahr'},   # Kat. 1 Gefahr / Kat. 2+3 Achtung -> AMBIVALENT
    # --- 2.6 Entzuendbare Fluessigkeiten (Anhang V Nr. 1.2: GHS02) ---
    'H224': {'piktogramme': ['GHS02'], 'signalwort': 'Gefahr'},   # Kat. 1
    'H225': {'piktogramme': ['GHS02'], 'signalwort': 'Gefahr'},   # Kat. 2
    'H226': {'piktogramme': ['GHS02'], 'signalwort': 'Achtung'},  # Kat. 3
    # --- 2.7 Entzuendbare Feststoffe (Anhang V Nr. 1.2: GHS02) ---
    'H228': {'piktogramme': ['GHS02'], 'signalwort': 'Gefahr'},   # Kat. 1 Gefahr / Kat. 2 Achtung -> AMBIVALENT

    # --- 2.8 Selbstzersetzliche Stoffe / 2.15 Organische Peroxide ---
    'H240': {'piktogramme': ['GHS01'],          'signalwort': 'Gefahr'},  # Typ A (Anhang V Nr. 1.1)
    'H241': {'piktogramme': ['GHS01', 'GHS02'], 'signalwort': 'Gefahr'},  # Typ B (GHS01+ GHS02)
    'H242': {'piktogramme': ['GHS02'],          'signalwort': 'Gefahr'},  # C&D Gefahr / E&F Achtung -> AMBIVALENT

    # --- 2.9/2.10 Pyrophore Fluessigkeiten/Feststoffe (Anhang V Nr. 1.2: GHS02) ---
    'H250': {'piktogramme': ['GHS02'], 'signalwort': 'Gefahr'},   # Kat. 1
    # --- 2.11 Selbsterhitzungsfaehige Stoffe/Gemische ---
    'H251': {'piktogramme': ['GHS02'], 'signalwort': 'Gefahr'},   # Kat. 1
    'H252': {'piktogramme': ['GHS02'], 'signalwort': 'Achtung'},  # Kat. 2
    # --- 2.12 Stoffe/Gemische, die in Beruehrung mit Wasser entzuendbare Gase entwickeln ---
    'H260': {'piktogramme': ['GHS02'], 'signalwort': 'Gefahr'},   # Kat. 1
    'H261': {'piktogramme': ['GHS02'], 'signalwort': 'Gefahr'},   # Kat. 2 Gefahr / Kat. 3 Achtung -> AMBIVALENT
    # --- 2.4/2.13/2.14 Oxidierende Gase/Fluessigkeiten/Feststoffe (Anhang V Nr. 1.3: GHS03) ---
    'H270': {'piktogramme': ['GHS03'], 'signalwort': 'Gefahr'},   # ox. Gas Kat. 1
    'H271': {'piktogramme': ['GHS03'], 'signalwort': 'Gefahr'},   # ox. Fluess./Festst. Kat. 1
    'H272': {'piktogramme': ['GHS03'], 'signalwort': 'Gefahr'},   # Kat. 2 Gefahr / Kat. 3 Achtung -> AMBIVALENT
    # --- 2.5 Gase unter Druck (Anhang V Nr. 1.4: GHS04) ---
    'H280': {'piktogramme': ['GHS04'], 'signalwort': 'Achtung'},  # verdichtet/verfluessigt/geloest
    'H281': {'piktogramme': ['GHS04'], 'signalwort': 'Achtung'},  # tiefgekuehlt verfluessigt
    # --- 2.16 Gegenueber Metallen korrosive Stoffe/Gemische (Anhang V Nr. 1.5: GHS05) ---
    'H290': {'piktogramme': ['GHS05'], 'signalwort': 'Achtung'},  # Kat. 1

    # --- 3.1 Akute Toxizitaet (Anhang V Nr. 2.1: GHS06 fuer Kat. 1-3; Nr. 2.3: GHS07 fuer Kat. 4) ---
    'H300': {'piktogramme': ['GHS06'], 'signalwort': 'Gefahr'},   # oral Kat. 1/2
    'H301': {'piktogramme': ['GHS06'], 'signalwort': 'Gefahr'},   # oral Kat. 3
    'H302': {'piktogramme': ['GHS07'], 'signalwort': 'Achtung'},  # oral Kat. 4
    'H310': {'piktogramme': ['GHS06'], 'signalwort': 'Gefahr'},   # dermal Kat. 1/2
    'H311': {'piktogramme': ['GHS06'], 'signalwort': 'Gefahr'},   # dermal Kat. 3
    'H312': {'piktogramme': ['GHS07'], 'signalwort': 'Achtung'},  # dermal Kat. 4
    'H330': {'piktogramme': ['GHS06'], 'signalwort': 'Gefahr'},   # inhalativ Kat. 1/2
    'H331': {'piktogramme': ['GHS06'], 'signalwort': 'Gefahr'},   # inhalativ Kat. 3
    'H332': {'piktogramme': ['GHS07'], 'signalwort': 'Achtung'},  # inhalativ Kat. 4

    # --- 3.2 Aetzwirkung auf die Haut / Hautreizung ---
    'H314': {'piktogramme': ['GHS05'], 'signalwort': 'Gefahr'},   # Kat. 1 (1A/1B/1C), Anhang V Nr. 2.2
    'H315': {'piktogramme': ['GHS07'], 'signalwort': 'Achtung'},  # Kat. 2, Anhang V Nr. 2.3
    # --- 3.3 Schwere Augenschaedigung / Augenreizung ---
    'H318': {'piktogramme': ['GHS05'], 'signalwort': 'Gefahr'},   # Kat. 1
    'H319': {'piktogramme': ['GHS07'], 'signalwort': 'Achtung'},  # Kat. 2
    # --- 3.4 Sensibilisierung der Atemwege / der Haut ---
    'H334': {'piktogramme': ['GHS08'], 'signalwort': 'Gefahr'},   # Atemwege Kat. 1 (1A/1B), Anhang V Nr. 2.4
    'H317': {'piktogramme': ['GHS07'], 'signalwort': 'Achtung'},  # Haut Kat. 1 (1A/1B), Anhang V Nr. 2.3

    # --- 3.5 Keimzellmutagenitaet (Anhang V Nr. 2.4: GHS08) ---
    'H340': {'piktogramme': ['GHS08'], 'signalwort': 'Gefahr'},   # Kat. 1 (1A/1B)
    'H341': {'piktogramme': ['GHS08'], 'signalwort': 'Achtung'},  # Kat. 2
    # --- 3.6 Karzinogenitaet (Anhang V Nr. 2.4: GHS08) ---
    'H350':  {'piktogramme': ['GHS08'], 'signalwort': 'Gefahr'},  # Kat. 1 (1A/1B)
    'H350i': {'piktogramme': ['GHS08'], 'signalwort': 'Gefahr'},  # Kat. 1 (1A/1B), inhalativ
    'H351':  {'piktogramme': ['GHS08'], 'signalwort': 'Achtung'}, # Kat. 2
    # --- 3.7 Reproduktionstoxizitaet (Anhang V Nr. 2.4: GHS08; Laktation ohne Piktogramm, Nr. 2.5) ---
    'H360':   {'piktogramme': ['GHS08'], 'signalwort': 'Gefahr'},   # Kat. 1 (1A/1B)
    'H360F':  {'piktogramme': ['GHS08'], 'signalwort': 'Gefahr'},   # Kat. 1 (1A/1B)
    'H360D':  {'piktogramme': ['GHS08'], 'signalwort': 'Gefahr'},   # Kat. 1 (1A/1B)
    'H360FD': {'piktogramme': ['GHS08'], 'signalwort': 'Gefahr'},   # Kat. 1 (1A/1B)
    'H360Fd': {'piktogramme': ['GHS08'], 'signalwort': 'Gefahr'},   # Kat. 1 (1A/1B)
    'H360Df': {'piktogramme': ['GHS08'], 'signalwort': 'Gefahr'},   # Kat. 1 (1A/1B)
    'H361':   {'piktogramme': ['GHS08'], 'signalwort': 'Achtung'},  # Kat. 2
    'H361f':  {'piktogramme': ['GHS08'], 'signalwort': 'Achtung'},  # Kat. 2
    'H361d':  {'piktogramme': ['GHS08'], 'signalwort': 'Achtung'},  # Kat. 2
    'H361fd': {'piktogramme': ['GHS08'], 'signalwort': 'Achtung'},  # Kat. 2
    'H362':   {'piktogramme': [],        'signalwort': None},       # Zusatzkat. Laktation (kein Piktogramm, kein Signalwort)

    # --- 3.8 Spezifische Zielorgan-Toxizitaet, einmalige Exposition ---
    'H370': {'piktogramme': ['GHS08'], 'signalwort': 'Gefahr'},   # Kat. 1 (Anhang V Nr. 2.4)
    'H371': {'piktogramme': ['GHS08'], 'signalwort': 'Achtung'},  # Kat. 2
    'H335': {'piktogramme': ['GHS07'], 'signalwort': 'Achtung'},  # Kat. 3, Atemwegsreizung (Anhang V Nr. 2.3)
    'H336': {'piktogramme': ['GHS07'], 'signalwort': 'Achtung'},  # Kat. 3, narkotisierende Wirkung
    # --- 3.9 Spezifische Zielorgan-Toxizitaet, wiederholte Exposition (Anhang V Nr. 2.4) ---
    'H372': {'piktogramme': ['GHS08'], 'signalwort': 'Gefahr'},   # Kat. 1
    'H373': {'piktogramme': ['GHS08'], 'signalwort': 'Achtung'},  # Kat. 2
    # --- 3.10 Aspirationsgefahr (Anhang V Nr. 2.4: GHS08) ---
    'H304': {'piktogramme': ['GHS08'], 'signalwort': 'Gefahr'},   # Kat. 1

    # --- 4.1 Gewaessergefaehrdend (Anhang V Nr. 3.1: GHS09 fuer Akut 1, Chronisch 1, 2) ---
    'H400': {'piktogramme': ['GHS09'], 'signalwort': 'Achtung'},  # Akut 1
    'H410': {'piktogramme': ['GHS09'], 'signalwort': 'Achtung'},  # Chronisch 1
    'H411': {'piktogramme': ['GHS09'], 'signalwort': None},       # Chronisch 2 (kein Signalwort)
    'H412': {'piktogramme': [],        'signalwort': None},       # Chronisch 3 (kein Piktogramm, kein Signalwort)
    'H413': {'piktogramme': [],        'signalwort': None},       # Chronisch 4 (kein Piktogramm, kein Signalwort)
    # --- 5.1 Die Ozonschicht schaedigend (Anhang V Teil 4 Nr. 4.1: GHS07) ---
    'H420': {'piktogramme': ['GHS07'], 'signalwort': 'Achtung'},  # Kat. 1

    # --- Kombinationsgefahrenhinweise akute Toxizitaet (Anhang I Tabelle 3.1.2) ---
    'H300+H310':      {'piktogramme': ['GHS06'], 'signalwort': 'Gefahr'},   # Kat. 1/2
    'H300+H330':      {'piktogramme': ['GHS06'], 'signalwort': 'Gefahr'},   # Kat. 1/2
    'H310+H330':      {'piktogramme': ['GHS06'], 'signalwort': 'Gefahr'},   # Kat. 1/2
    'H300+H310+H330': {'piktogramme': ['GHS06'], 'signalwort': 'Gefahr'},   # Kat. 1/2
    'H301+H311':      {'piktogramme': ['GHS06'], 'signalwort': 'Gefahr'},   # Kat. 3
    'H301+H331':      {'piktogramme': ['GHS06'], 'signalwort': 'Gefahr'},   # Kat. 3
    'H311+H331':      {'piktogramme': ['GHS06'], 'signalwort': 'Gefahr'},   # Kat. 3
    'H301+H311+H331': {'piktogramme': ['GHS06'], 'signalwort': 'Gefahr'},   # Kat. 3
    'H302+H312':      {'piktogramme': ['GHS07'], 'signalwort': 'Achtung'},  # Kat. 4
    'H302+H332':      {'piktogramme': ['GHS07'], 'signalwort': 'Achtung'},  # Kat. 4
    'H312+H332':      {'piktogramme': ['GHS07'], 'signalwort': 'Achtung'},  # Kat. 4
    'H302+H312+H332': {'piktogramme': ['GHS07'], 'signalwort': 'Achtung'},  # Kat. 4
}

# Codes, deren Zuordnung nicht sicher belegbar war. Leer heisst: alle 91 Codes sind belegt.
UNSICHER = []


# ─── Ableitung ──────────────────────────────────────────────────────────────

# Kombinationssatz zuerst: H300+H310, auch dreiteilig. Der Trenner darf
# Leerzeichen tragen ("H300 + H310"), wie Sicherheitsdatenblaetter ihn setzen.
# ⚠️ Die Grenze nach links ist noetig: ohne sie liest das Muster aus "EUH014"
# ein "H014" heraus - und EUH-Saetze stehen in derselben Angabe wie H-Saetze.
# Das fuehrende H darf klein sein (aus PDF-Texten kommt beides); die Endung
# bleibt bewusst schreibweiseabhaengig, siehe codes_aus_text.
_KOMBINATION = re.compile(r'(?<![A-Za-z])[Hh]\d{3}[a-zA-Z]*(?:\s*\+\s*[Hh]\d{3}[a-zA-Z]*)+')
# Einzelcode. Kleinbuchstaben im Anhang sind Teil des Codes (H360Fd).
_EINZELN = re.compile(r'(?<![A-Za-z])[Hh]\d{3}[a-zA-Z]*')

# Rangfolge fuer das Signalwort eines Stoffes: das strengste gewinnt.
_RANG = {None: 0, 'Achtung': 1, 'Gefahr': 2}


def codes_aus_text(text):
    """Zieht die H-Codes aus einer Angabe wie "H225, H319, H336" oder "H300+H310".

    Nimmt auch eine Liste von Codes (der SDB-Parser sammelt sie so). Gibt die
    Codes in der Reihenfolge des Auftretens zurueck, ohne Doppelte. Nur das
    fuehrende "H" wird gross geschrieben - der Rest bleibt, weil H360Fd und
    H360FD sonst zusammenfielen.
    """
    if not text:
        return []
    if isinstance(text, (list, tuple, set)):
        text = ', '.join(str(t) for t in text)
    text = str(text)

    gefunden = [re.sub(r'\s+', '', t) for t in _KOMBINATION.findall(text)]
    rest = _KOMBINATION.sub(' ', text)
    gefunden += _EINZELN.findall(rest)

    ergebnis, gesehen = [], set()
    for code in gefunden:
        code = normalisieren(code)
        if code not in gesehen:
            gesehen.add(code)
            ergebnis.append(code)
    return ergebnis


def normalisieren(code):
    """Setzt das fuehrende "H" jeder Komponente gross, sonst nichts.

    Ein Kombinationssatz hat mehrere: aus "h300+H310" wird "H300+H310". Die
    Endung bleibt unangetastet - H360Fd und H360FD sind verschiedene Codes,
    und ein Vergleich, der die Schreibweise ignoriert, wuerde sie zusammenwerfen.
    """
    return '+'.join('H' + teil[1:] for teil in code.split('+'))


def unbekannte_codes(text):
    """Codes, die in ZUORDNUNG fehlen.

    Damit eine Luecke nicht stillschweigend zu "kein Piktogramm" wird, laesst
    sie sich hier abfragen - test_piktogramme.py prueft, dass die Liste fuer
    alle Codes aus static/hp_data.json leer ist.
    """
    return [c for c in codes_aus_text(text) if c not in ZUORDNUNG]


def piktogramme_fuer(text):
    """Piktogramm-Codes (GHS01-GHS09) zu einer H-Satz-Angabe, alphabetisch."""
    piktogramme = set()
    for code in codes_aus_text(text):
        eintrag = ZUORDNUNG.get(code)
        if eintrag:
            piktogramme.update(eintrag['piktogramme'])
    return sorted(piktogramme)


def signalwort_fuer(text):
    """Signalwort eines Stoffes: 'Gefahr', 'Achtung' oder None.

    Das strengste der beteiligten H-Saetze gewinnt - eine Mischung aus "Gefahr"
    und "Achtung" ergibt "Gefahr". Ohne zuordenbare H-Saetze kommt None zurueck;
    der Aufrufer entscheidet dann, ob er etwas anzeigt.
    """
    staerkstes = None
    for code in codes_aus_text(text):
        eintrag = ZUORDNUNG.get(code)
        if eintrag and _RANG[eintrag['signalwort']] > _RANG[staerkstes]:
            staerkstes = eintrag['signalwort']
    return staerkstes
