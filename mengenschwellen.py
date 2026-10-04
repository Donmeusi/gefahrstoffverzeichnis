"""Mengenschwellen-Prüfung nach TRGS 510.

Prüft je Lagerabschnitt, ob die gelagerten Mengen die Kleinmengen der TRGS 510
überschreiten - ab denen eine Lagerung nur noch im Lager zulässig ist - und ob
die Mengen erreicht sind, ab denen die zusätzlichen Schutzmaßnahmen greifen.

Lagerabschnitt
--------------
Die TRGS 510 rechnet nicht je Einzelstoff, sondern je Lagerabschnitt. In dieser
App ist das der Unterbereich des Standortbaums: alles, was im selben Unterbereich
(verschachtelt: Regal, Schrank, Fach) liegt, wird zusammengezählt. Die
Zusammenlagerung in trgs510.py nutzt dieselbe Ebene - beide Prüfungen sprechen
damit über denselben Bereich.

Aufbau
------
SCHWELLEN ist eine Tabelle aus Regeln. Jede Regel nennt die Einstufung
(H-Sätze primär, Lagerklasse als Ersatz), die Menge, ab der im Lager gelagert
werden muss (Tabelle 1 Spalte 3 = Kleinmenge), und - wo die TRGS eine nennt -
die Menge, ab der zusätzliche Schutzmaßnahmen greifen (Spalte 4). Die Zahlen
stehen bewusst nur hier, mit Quellenangabe; die Prüffunktionen selbst enthalten
keine. Geprüft wird primär über die H-Sätze: das ist die Systematik der TRGS 510
(Tabelle 1 ordnet nach Einstufung, nicht nach Lagerklasse). Nur wenn ein Stoff
keine passende H-Satz-Regel trifft, greift seine Lagerklasse als Ersatz.

Quelle der Zahlen
-----------------
TRGS 510 "Lagerung von Gefahrstoffen in ortsbeweglichen Behältern", Ausgabe
Dezember 2020, Fassung 16.02.2021, GMBl 2021 S. 178-216 (Nr. 9-10). Maßgeblich
ist Abschnitt 1 Absätze 7-9 mit Tabelle 1 (Spalten 3 und 4) und der dortigen
Fußnote zur Zusammenlagerung sowie Absatz 10. Abgeglichen am 04.10.2026 gegen
die amtliche Fassung (Quelle: BAuA, veröffentlicht in der Vorschriftensammlung
der Gewerbeaufsicht Baden-Württemberg). Die Mengen sind Nettolagermengen.

Grenzen - bitte lesen
---------------------
* Die App kennt keine Dichte. Mengen in L/ml werden ohne Umrechnung wie kg
  behandelt (1 L = 1 kg). Das ist eine Näherung und wird im Ergebnis als solche
  gekennzeichnet. Die TRGS lässt bei Gasen sowie Druckgaskartuschen und
  Aerosolpackungen die Einheit ausdrücklich wahlweise zu (kg oder l bzw. kg
  oder Stück).
* "Stück" lässt sich keiner Masse zuordnen und geht nicht in die Summen ein;
  solche Stoffe werden als Hinweis geführt, nicht als Zahl.
* Mehrere Zeilen der Tabelle 1 sind zusätzlich an die Anzahl der Gebinde
  geknüpft (Gase: "und > 1 Flasche", Kartuschen/Aerosole: "oder > 50 Stück").
  Die App kennt keine Gebindezahl; solche Regeln tragen einen 'hinweis' und
  werden allein über die Masse geprüft - das kann zu wenig melden.
* Die Werte sind eine Arbeitshilfe und kein Ersatz für die Gefährdungsbeurteilung.
  Maßgeblich bleibt der Text der TRGS 510 in der jeweils geltenden Fassung.
"""

import re

# Ab dieser Gesamtmenge aller Gefahrstoffe im Brandabschnitt ist eine Lagerung
# außerhalb von Lagern nicht mehr zulässig - TRGS 510 Nr. 1 Abs. 8 und Tabelle 1
# (Zeile "mehrere verschiedene Gefahrstoffe": Summe > 1.500 kg).
GESAMT_KLEINMENGEN_KG = 1500.0

# Ab dieser Gesamtmenge brauchen die Maßnahmen des Abschnitts 13 (Zusammen-
# lagerung) nicht ergriffen zu werden - TRGS 510 Nr. 1 Abs. 10. Nur ein
# Hinweiswert; die Zusammenlagerung selbst prüft trgs510.py.
ZUSAMMENLAGERUNG_AB_KG = 200.0

# Umrechnungsfaktoren in Kilogramm. L und ml werden 1:1 wie kg behandelt, weil
# die App keine Dichte kennt (siehe Modulkopf).
MASSEINHEITEN = {
    'kg': 1.0,
    'g': 0.001,
    'L': 1.0,
    'l': 1.0,
    'ml': 0.001,
}

# Erkennt H-Satz-Codes in einem Freitextfeld ('H225, H319' -> H225, H319).
# Kombinierte Sätze wie 'H300+H310' liefert der Ausdruck als zwei Treffer -
# das ist gewollt, beide Einzelcodes zählen.
H_SATZ_MUSTER = re.compile(r'H\d{3}[A-Za-z]*')

# Tabelle der Mengenschwellen - 1:1 aus Tabelle 1 der TRGS 510 (Spalten 3 und 4),
# abgeglichen am 04.10.2026. Bezeichnungen und Mengen folgen dem Wortlaut.
#
#   kleinmenge_kg  Spalte 3 "Lagern im Lager": ab hier muss im Lager gelagert
#                  werden (bis hierher ist es eine Kleinmenge)
#   zusatz_ab_kg   Spalte 4 "Zusätzliche/besondere Schutzmaßnahmen"
#   bedingung_h    Zusatzbedingung: der Stoff muss zusätzlich einen dieser
#                  H-Sätze tragen, sonst greift die Regel nicht
#   ausschluss_h   Gegenbedingung: trägt der Stoff einen dieser H-Sätze, greift
#                  die Regel nicht (trennt z. B. Gase von Flüssigkeiten/Feststoffen)
#   hinweis        was die App nicht prüfen kann (Gebindezahl, Einheiten)
SCHWELLEN = (
    # ── entzündbare Flüssigkeiten ────────────────────────────────────────────
    {
        'gruppe': 'entzfluessig_kat12',
        'bezeichnung': 'Entzündbare Flüssigkeiten Kat. 1/2 (H224, H225)',
        'h_saetze': ('H224', 'H225'),
        'lgk': ('3',),
        'bedingung_h': (), 'ausschluss_h': (),
        'kleinmenge_kg': 20.0,
        'zusatz_ab_kg': 200.0,
        'hinweis': None,
        'quelle': 'TRGS 510 Nr. 1 Tabelle 1 (H224/H225: H224 > 10 kg, Summe > 20 kg)',
    },
    {
        # Teilmenge der Zeile oben - eigener Eintrag, weil Tabelle 1 für H224
        # eine eigene Grenze nennt ("H224 > 10 kg") und die Summe H224/H225
        # daneben ("Summe H224/H225 > 20 kg"). Diese Zeile zählt nur H224.
        'gruppe': 'entzfluessig_h224',
        'bezeichnung': 'davon H224 (höchstens 10 kg)',
        'h_saetze': ('H224',),
        'lgk': (),
        'bedingung_h': (), 'ausschluss_h': (),
        'kleinmenge_kg': 10.0,
        'zusatz_ab_kg': None,
        'hinweis': None,
        'quelle': 'TRGS 510 Nr. 1 Tabelle 1 (Spalte 3, H224)',
    },
    {
        'gruppe': 'entzfluessig_kat3',
        'bezeichnung': 'Entzündbare Flüssigkeiten Kat. 3 (H226)',
        'h_saetze': ('H226',),
        'lgk': ('3',),
        'bedingung_h': (), 'ausschluss_h': (),
        'kleinmenge_kg': 100.0,
        'zusatz_ab_kg': 1000.0,
        'hinweis': 'Entfällt bei ausschließlicher Lagerung mit Flammpunkt > 55 °C '
                   '(Fußnote 3: Dieselkraftstoff, Heizöl)',
        'quelle': 'TRGS 510 Nr. 1 Tabelle 1 (H226)',
    },
    {
        'gruppe': 'entzfeststoff',
        'bezeichnung': 'Entzündbare Feststoffe Kat. 1/2 (H228)',
        'h_saetze': ('H228',),
        'lgk': ('4.1B',),
        'bedingung_h': (), 'ausschluss_h': (),
        'kleinmenge_kg': 200.0,
        'zusatz_ab_kg': 200.0,
        'hinweis': None,
        'quelle': 'TRGS 510 Nr. 1 Tabelle 1 (H228)',
    },
    # ── selbstzersetzlich, pyrophor, selbsterhitzungsfähig, wasserreaktiv ────
    {
        'gruppe': 'selbstzersetzlich',
        'bezeichnung': 'Selbstzersetzliche Gefahrstoffe Typ C, D, E, F (H242)',
        'h_saetze': ('H242',),
        'lgk': (),
        'bedingung_h': (), 'ausschluss_h': (),
        'kleinmenge_kg': 100.0,
        'zusatz_ab_kg': 200.0,
        'hinweis': None,
        'quelle': 'TRGS 510 Nr. 1 Tabelle 1 (H242)',
    },
    {
        'gruppe': 'pyrophor',
        'bezeichnung': 'Pyrophore Flüssigkeiten und Feststoffe Kat. 1 (H250)',
        'h_saetze': ('H250',),
        'lgk': ('4.2',),
        'bedingung_h': (), 'ausschluss_h': (),
        'kleinmenge_kg': 100.0,
        'zusatz_ab_kg': 200.0,
        'hinweis': None,
        'quelle': 'TRGS 510 Nr. 1 Tabelle 1 (H250)',
    },
    {
        'gruppe': 'selbsterhitzung',
        'bezeichnung': 'Selbsterhitzungsfähige Gefahrstoffe Kat. 1/2 (H251, H252)',
        'h_saetze': ('H251', 'H252'),
        'lgk': ('4.2',),
        'bedingung_h': (), 'ausschluss_h': (),
        'kleinmenge_kg': 200.0,
        'zusatz_ab_kg': 200.0,
        'hinweis': None,
        'quelle': 'TRGS 510 Nr. 1 Tabelle 1 (H251, H252)',
    },
    {
        'gruppe': 'wasserreaktiv',
        'bezeichnung': 'Stoffe, die mit Wasser entzündbare Gase entwickeln, Kat. 1-3 (H260, H261)',
        'h_saetze': ('H260', 'H261'),
        'lgk': ('4.3',),
        'bedingung_h': (), 'ausschluss_h': (),
        'kleinmenge_kg': 200.0,
        'zusatz_ab_kg': 200.0,
        'hinweis': None,
        'quelle': 'TRGS 510 Nr. 1 Tabelle 1 (H260, H261)',
    },
    # ── brandfördernd ───────────────────────────────────────────────────────
    {
        'gruppe': 'brandfoerdernd_kat1',
        'bezeichnung': 'Oxidierende Flüssigkeiten und Feststoffe Kat. 1 (H271)',
        'h_saetze': ('H271',),
        'lgk': ('5.1A',),
        'bedingung_h': (), 'ausschluss_h': (),
        'kleinmenge_kg': 1.0,
        'zusatz_ab_kg': 5.0,
        'hinweis': 'Zusätzliche Maßnahmen nach Abschnitt 9 greifen bereits ab > 200 kg',
        'quelle': 'TRGS 510 Nr. 1 Tabelle 1 (H271: > 1 kg, dann > 5 kg)',
    },
    {
        'gruppe': 'brandfoerdernd_kat23',
        'bezeichnung': 'Oxidierende Flüssigkeiten und Feststoffe Kat. 2/3 (H272)',
        'h_saetze': ('H272',),
        'lgk': ('5.1B', '5.1C'),
        'bedingung_h': (), 'ausschluss_h': (),
        'kleinmenge_kg': 50.0,
        'zusatz_ab_kg': 200.0,
        'hinweis': None,
        'quelle': 'TRGS 510 Nr. 1 Tabelle 1 (H272)',
    },
    {
        'gruppe': 'explosiv_desens',
        'bezeichnung': 'Desensibilisierte explosive Gefahrstoffe Kat. 1-4 (H206, H207, H208)',
        'h_saetze': ('H206', 'H207', 'H208'),
        'lgk': ('4.1A',),
        'bedingung_h': (), 'ausschluss_h': (),
        'kleinmenge_kg': 100.0,
        'zusatz_ab_kg': 200.0,
        'hinweis': 'Nicht im Anwendungsbereich des Sprengstoffgesetzes (Fußnote 4)',
        'quelle': 'TRGS 510 Nr. 1 Tabelle 1 (H206-H208)',
    },
    # ── toxisch, CMR, zielorgantoxisch ──────────────────────────────────────
    {
        'gruppe': 'akut_toxisch',
        'bezeichnung': 'Akut toxische Flüssigkeiten und Feststoffe Kat. 1-3 '
                       '(H300, H301, H310, H311, H330, H331)',
        'h_saetze': ('H300', 'H301', 'H310', 'H311', 'H330', 'H331'),
        'lgk': ('6.1A', '6.1B', '6.1C', '6.1D',),
        'bedingung_h': (), 'ausschluss_h': ('H280', 'H281'),
        'kleinmenge_kg': 50.0,
        'zusatz_ab_kg': 200.0,
        'hinweis': 'Gilt für Flüssigkeiten/Feststoffe; akut toxische Gase siehe eigene Zeile',
        'quelle': 'TRGS 510 Nr. 1 Tabelle 1 (H300/H310/H330, H301/H311/H331)',
    },
    {
        'gruppe': 'akut_toxisch_gas',
        'bezeichnung': 'Akut toxische Gase Kat. 1-3 (H330, H331 mit H280/H281)',
        'h_saetze': ('H330', 'H331'),
        'lgk': (),
        'bedingung_h': ('H280', 'H281'), 'ausschluss_h': (),
        'kleinmenge_kg': 0.5,
        'zusatz_ab_kg': 200.0,
        'hinweis': 'Gilt ab > 0,5 kg oder > 1 l; Zusatzmaßnahmen ab > 200 kg oder > 400 l',
        'quelle': 'TRGS 510 Nr. 1 Tabelle 1 (H330/H331 mit H280 oder H281)',
    },
    {
        'gruppe': 'cmr_kat1',
        'bezeichnung': 'Keimzellmutagen / karzinogen / reproduktionstoxisch Kat. 1A, 1B '
                       '(H340, H350, H350i, H360, H360F, H360D, H360FD, H360Fd, H360Df)',
        'h_saetze': ('H340', 'H350', 'H350i', 'H360', 'H360F', 'H360D',
                     'H360FD', 'H360Fd', 'H360Df'),
        'lgk': (),
        'bedingung_h': (), 'ausschluss_h': (),
        'kleinmenge_kg': 50.0,
        'zusatz_ab_kg': 200.0,
        'hinweis': None,
        'quelle': 'TRGS 510 Nr. 1 Tabelle 1 (H340, H350, H350i, H360-Reihe)',
    },
    {
        'gruppe': 'zielorgantoxisch_kat1',
        'bezeichnung': 'Zielorgantoxische Gefahrstoffe Kat. 1 (H370, H372)',
        'h_saetze': ('H370', 'H372'),
        'lgk': (),
        'bedingung_h': (), 'ausschluss_h': (),
        'kleinmenge_kg': 50.0,
        'zusatz_ab_kg': 200.0,
        'hinweis': None,
        'quelle': 'TRGS 510 Nr. 1 Tabelle 1 (H370, H372)',
    },
    # ── Gase, Aerosole, Druckgaskartuschen ──────────────────────────────────
    {
        'gruppe': 'entz_gase',
        'bezeichnung': 'Entzündbare Gase Kat. 1A, 1B, 2 (H220, H221)',
        'h_saetze': ('H220', 'H221'),
        'lgk': ('2A',),
        'bedingung_h': (), 'ausschluss_h': (),
        'kleinmenge_kg': 50.0,
        'zusatz_ab_kg': 200.0,
        'hinweis': 'Tabelle 1 knüpft zusätzlich an "> 1 Flasche"; die Gebindezahl '
                   'kennt die App nicht. Kartuschen: eigenes Limit (> 20 kg oder > 50 Stück)',
        'quelle': 'TRGS 510 Nr. 1 Tabelle 1 (H220, H221)',
    },
    {
        'gruppe': 'oxidierende_gase',
        'bezeichnung': 'Oxidierende Gase Kat. 1 (H270)',
        'h_saetze': ('H270',),
        'lgk': (),
        'bedingung_h': (), 'ausschluss_h': (),
        'kleinmenge_kg': 50.0,
        'zusatz_ab_kg': 200.0,
        'hinweis': 'Tabelle 1 knüpft zusätzlich an "> 1 Flasche"; die Gebindezahl '
                   'kennt die App nicht',
        'quelle': 'TRGS 510 Nr. 1 Tabelle 1 (H270)',
    },
    {
        'gruppe': 'gase_unter_druck',
        'bezeichnung': 'Gase unter Druck, nicht akut toxisch / entzündbar / oxidierend '
                       '(H280, H281)',
        'h_saetze': ('H280', 'H281'),
        'lgk': ('2A',),
        'bedingung_h': (), 'ausschluss_h': (),
        'kleinmenge_kg': 50.0,
        'zusatz_ab_kg': None,
        'hinweis': 'Tabelle 1 knüpft zusätzlich an "> 1 Flasche"; die Gebindezahl '
                   'kennt die App nicht',
        'quelle': 'TRGS 510 Nr. 1 Tabelle 1 (H280, H281)',
    },
    {
        'gruppe': 'aerosole',
        'bezeichnung': 'Aerosole Kat. 1, 2, 3 in Aerosolpackungen (H222, H223, H229)',
        'h_saetze': ('H222', 'H223', 'H229'),
        'lgk': ('2B',),
        'bedingung_h': (), 'ausschluss_h': (),
        'kleinmenge_kg': 20.0,
        'zusatz_ab_kg': 200.0,
        'hinweis': 'Tabelle 1: > 20 kg oder > 50 Stück',
        'quelle': 'TRGS 510 Nr. 1 Tabelle 1 (H222, H223, H229)',
    },
    # ── Ersatz über die Lagerklasse (Tabelle 1 nennt keine LGK) ─────────────
    {
        'gruppe': 'brennbar_fluessig_lgk10',
        'bezeichnung': 'Brennbare Flüssigkeiten ohne Einstufung als entzündbar (LGK 10)',
        'h_saetze': (),
        'lgk': ('10',),
        'bedingung_h': (), 'ausschluss_h': (),
        'kleinmenge_kg': 1000.0,
        'zusatz_ab_kg': 1000.0,
        'hinweis': 'Ersatzzuordnung über die Lagerklasse; Tabelle 1 benennt diese '
                   'Gruppe über die Eigenschaft, nicht über H-Sätze',
        'quelle': 'TRGS 510 Nr. 1 Tabelle 1 (brennbare Flüssigkeiten ohne Einstufung '
                  'als entzündbar)',
    },
    {
        'gruppe': 'sonstige',
        'bezeichnung': 'Sonstige Gefahrstoffe ohne vorgenannte Einstufung (LGK 12/13)',
        'h_saetze': (),
        'lgk': ('12', '13'),
        'bedingung_h': (), 'ausschluss_h': (),
        'kleinmenge_kg': 1000.0,
        'zusatz_ab_kg': None,
        'hinweis': 'Tabelle 1: "andere als gefährlich eingestufte Stoffe/Gemische, '
                   'alle nicht vorgenannten Gefahrenhinweise > 1.000 kg"',
        'quelle': 'TRGS 510 Nr. 1 Tabelle 1 (andere Gefahrstoffe)',
    },
)

def h_codes(h_saetze):
    """H-Satz-Codes aus dem Freitextfeld als Menge ('H225, H319' -> {H225, H319})."""
    if not h_saetze:
        return set()
    return set(H_SATZ_MUSTER.findall(h_saetze))


def menge_in_kg(menge, einheit):
    """Menge in Kilogramm umrechnen.

    Rückgabe: (kg oder None, Hinweis oder None). None heißt "nicht rechenbar" -
    keine Menge erfasst oder eine Einheit ohne Massenbezug (Stück). Solche
    Stoffe gehen nicht in die Summe ein, werden aber als Hinweis geführt, damit
    die Lücke sichtbar bleibt.
    """
    if menge is None or menge == '':
        return None, 'keine Menge erfasst'
    try:
        menge = float(menge)
    except (TypeError, ValueError):
        return None, 'Menge nicht als Zahl lesbar'
    einheit = (einheit or 'kg').strip()
    faktor = MASSEINHEITEN.get(einheit)
    if faktor is None:
        return None, f'Einheit „{einheit}" lässt sich keiner Masse zuordnen'
    return menge * faktor, None


def _passt(regel, h_menge):
    """Prüft eine Regel gegen die H-Satz-Menge eines Stoffes.

    Über die Schnittmenge mit 'h_saetze' hinaus können zwei Bedingungen greifen:
    'bedingung_h' verlangt zusätzlich mindestens einen dieser H-Sätze (trennt
    z. B. akut toxische Gase von toxischen Flüssigkeiten), 'ausschluss_h'
    schließt den Stoff aus, wenn er einen davon trägt (verhindert, dass ein Gas
    zusätzlich an der Zeile für Flüssigkeiten/Feststoffe gemessen wird).
    """
    if not h_menge & set(regel['h_saetze']):
        return False
    bedingung = regel.get('bedingung_h') or ()
    if bedingung and not (h_menge & set(bedingung)):
        return False
    ausschluss = regel.get('ausschluss_h') or ()
    if ausschluss and (h_menge & set(ausschluss)):
        return False
    return True


def _regeln_fuer_stoff(h_menge, lagerklasse):
    """Regeln, die auf einen Stoff zutreffen - H-Sätze zuerst.

    Trifft mindestens eine H-Satz-Regel, gelten diese; die Lagerklasse dient
    nur als Ersatz, wenn die H-Sätze keine Zuordnung erlauben. Das verhindert
    falsche Treffer: ein Stoff der LGK 3 mit H226 soll nicht zusätzlich an der
    20-kg-Regel für H224/H225 gemessen werden.
    """
    h_treffer = [r for r in SCHWELLEN if r['h_saetze'] and _passt(r, h_menge)]
    if h_treffer:
        return h_treffer

    lk = (lagerklasse or '').strip().upper()
    if not lk:
        return []
    return [r for r in SCHWELLEN if r['lgk'] and lk in set(r['lgk'])]


def _befund(regel, treffer):
    """Aus Regel und Trefferliste den Status ableiten.

    'treffer' ist eine Liste von (name, kg). Rückgabe: Befund-Dict, oder None,
    wenn die Kleinmenge eingehalten ist (dann gehört der Abschnitt nicht in die
    Arbeitsliste).
    """
    summe = sum(kg for _, kg in treffer)
    kleinmenge = regel['kleinmenge_kg']
    zusatz = regel['zusatz_ab_kg']

    if zusatz is not None and summe > zusatz:
        status = 'zusatz'
    elif summe > kleinmenge:
        status = 'ueberschritten'
    else:
        return None

    return {
        'gruppe': regel['gruppe'],
        'bezeichnung': regel['bezeichnung'],
        'summe_kg': summe,
        'kleinmenge_kg': kleinmenge,
        'zusatz_ab_kg': zusatz,
        'status': status,
        'stoffnamen': [name for name, _ in treffer],
        'ueberschreitung_kg': summe - kleinmenge,
        'hinweis': regel.get('hinweis'),
        'quelle': regel['quelle'],
    }


def pruefe_unterbereich(stoffe):
    """Mengenprüfung für einen Lagerabschnitt (Liste von Gefahrstoffen).

    Jeder Stoff wird über seine H-Sätze (ersatzweise Lagerklasse) einer Regel
    zugeordnet; je Regel werden die Massen summiert und mit der Kleinmenge
    verglichen. Zusätzlich wird die Gesamtmenge gegen die Obergrenze für alle
    Kleinmengen eines Brandabschnitts geprüft.

    Rückgabe: Liste von Befunden (Dicts), in denen die Kleinmenge überschritten
    ist. Eingehaltene Gruppen erscheinen nicht - das Ergebnis ist als
    Arbeitsliste gedacht, nicht als vollständige Bilanz.
    """
    nach_regel = {}
    nicht_rechenbar = []
    gesamt_kg = 0.0

    for stoff in stoffe:
        if getattr(stoff, 'is_deleted', False):
            continue
        kg, hinweis = menge_in_kg(getattr(stoff, 'menge', None),
                                  getattr(stoff, 'mengeneinheit', None))
        if kg is None:
            nicht_rechenbar.append(getattr(stoff, 'name', '?'))
            continue
        gesamt_kg += kg
        for regel in _regeln_fuer_stoff(h_codes(getattr(stoff, 'h_saetze', None)),
                                        getattr(stoff, 'lagerklasse', None)):
            nach_regel.setdefault(regel['gruppe'], (regel, []))[1].append(
                (getattr(stoff, 'name', '?'), kg))

    befunde = []
    for _, (regel, treffer) in sorted(nach_regel.items()):
        befund = _befund(regel, treffer)
        if befund:
            befunde.append(befund)

    if gesamt_kg > GESAMT_KLEINMENGEN_KG:
        befunde.append({
            'gruppe': 'gesamt',
            'bezeichnung': 'Gesamtmenge aller Kleinmengen im Lagerabschnitt',
            'summe_kg': gesamt_kg,
            'kleinmenge_kg': GESAMT_KLEINMENGEN_KG,
            'zusatz_ab_kg': None,
            'status': 'gesamt',
            'stoffnamen': [],
            'ueberschreitung_kg': gesamt_kg - GESAMT_KLEINMENGEN_KG,
            'hinweis': None,
            'quelle': 'TRGS 510 Nr. 1 Abs. 8 und Tabelle 1 '
                      '(Summe aller Kleinmengen > 1.500 kg je Brandabschnitt)',
        })

    for befund in befunde:
        befund['ohne_menge'] = nicht_rechenbar
    return befunde


def alle_befunde(stoffe):
    """Befunde für alle Lagerabschnitte.

    'stoffe' ist eine Liste von Gefahrstoffen (Objekte mit den Feldern menge,
    mengeneinheit, h_saetze, lagerklasse, unterbereich_id und name). Stoffe
    ohne Standort werden übersprungen - ohne Lagerabschnitt gibt es keine
    Summe.

    Rückgabe: Liste von Befunden, jeder mit 'unterbereich_id'. Dringlichste
    zuerst: erreichte Zusatzschwellen vor reinen Kleinmengen-Überschreitungen,
    innerhalb dessen die größte Überschreitung vorn.
    """
    je_abschnitt = {}
    for stoff in stoffe:
        ub_id = getattr(stoff, 'unterbereich_id', None)
        if ub_id is None:
            continue
        je_abschnitt.setdefault(ub_id, []).append(stoff)

    befunde = []
    for ub_id, abschnitt_stoffe in je_abschnitt.items():
        for befund in pruefe_unterbereich(abschnitt_stoffe):
            befund['unterbereich_id'] = ub_id
            befunde.append(befund)

    rang = {'zusatz': 0, 'gesamt': 1, 'ueberschritten': 2}
    befunde.sort(key=lambda b: (
        rang.get(b['status'], 9),
        -b['ueberschreitung_kg'],
        b['bezeichnung'],
    ))
    return befunde


def stoffe_ohne_menge(stoffe):
    """Stoffe im Zugriffsbereich, die in keine Mengensumme eingehen können.

    Nur die Zahl für den Kopfbereich: 'Stück'-Stoffe und Stoffe ohne Menge
    fehlen in jeder Summe, ohne dass das in der Liste sichtbar wäre.
    """
    anzahl = 0
    for stoff in stoffe:
        if getattr(stoff, 'is_deleted', False):
            continue
        kg, _ = menge_in_kg(getattr(stoff, 'menge', None),
                            getattr(stoff, 'mengeneinheit', None))
        if kg is None:
            anzahl += 1
    return anzahl
