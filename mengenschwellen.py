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
(H-Sätze primär, Lagerklasse als Ersatz), die Kleinmenge und - wo die TRGS eine
nennt - die Menge, ab der zusätzliche Schutzmaßnahmen greifen. Die Zahlen stehen
bewusst nur hier, mit Quellenangabe; die Prüffunktionen selbst enthalten keine.
Geprüft wird primär über die H-Sätze: das ist die Systematik der TRGS 510
(Tabelle 1 ordnet nach Einstufung, nicht nach Lagerklasse). Nur wenn ein Stoff
keine passende H-Satz-Regel trifft, greift seine Lagerklasse als Ersatz.

Grenzen - bitte lesen
---------------------
* Die App kennt keine Dichte. Mengen in L/ml werden ohne Umrechnung wie kg
  behandelt (1 L = 1 kg). Das ist eine Näherung und wird im Ergebnis als solche
  gekennzeichnet.
* "Stück" lässt sich keiner Masse zuordnen und geht nicht in die Summen ein;
  solche Stoffe werden als Hinweis geführt, nicht als Zahl.
* Die Werte sind eine Arbeitshilfe und kein Ersatz für die Gefährdungsbeurteilung.
  Maßgeblich ist der Text der TRGS 510 in der jeweils geltenden Fassung. Die
  Zahlen unten sind gegen die Fassung Dezember 2020 (GMBl 2021 S. 178-216)
  eingetragen und vor einem produktiven Einsatz am Regelwerkstext zu prüfen.
"""

import re

# Ab dieser Gesamtmenge (alle Kleinmengen eines Brandabschnitts zusammen) ist
# eine Lagerung außerhalb von Lagern nicht mehr zulässig - TRGS 510 Nr. 4.3.1.
GESAMT_KLEINMENGEN_KG = 1500.0

# Ab dieser Gesamtmenge im Lagerabschnitt greifen die Zusammenlagerungsregeln
# (TRGS 510 Nr. 13). Nur ein Hinweiswert - die Zusammenlagerung selbst prüft
# trgs510.py.
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

# Tabelle der Mengenschwellen. 'kleinmenge_kg' = bis hierher gilt die Lagerung
# als Kleinmenge (keine Lagerung im Lager erforderlich). 'zusatz_ab_kg' = ab
# hier greifen die zusätzlichen Schutzmaßnahmen; None, wo die TRGS für diese
# Gruppe keine eigene Schwelle nennt.
SCHWELLEN = (
    {
        'gruppe': 'entzfluessig_kat12',
        'bezeichnung': 'Entzündbare Flüssigkeiten Kat. 1/2 (H224, H225)',
        'h_saetze': ('H224', 'H225'),
        'lgk': ('3',),
        'kleinmenge_kg': 20.0,
        'zusatz_ab_kg': 200.0,
        'quelle': 'TRGS 510 Nr. 4.3.1 (Tabelle 1), Nr. 12 (Tabelle 9)',
    },
    {
        # Teilmenge der Gruppe oben: H224 ist allein auf 10 kg begrenzt, auch
        # wenn die Summe H224+H225 20 kg nicht überschreitet. Deshalb eine
        # eigene Zeile - sie zählt nur die H224-Stoffe.
        'gruppe': 'entzfluessig_h224',
        'bezeichnung': 'davon H224 (höchstens 10 kg)',
        'h_saetze': ('H224',),
        'lgk': (),
        'kleinmenge_kg': 10.0,
        'zusatz_ab_kg': None,
        'quelle': 'TRGS 510 Nr. 4.3.1 (Tabelle 1, Fußnote H224)',
    },
    {
        'gruppe': 'entzfluessig_kat3',
        'bezeichnung': 'Entzündbare Flüssigkeiten Kat. 3 (H226)',
        'h_saetze': ('H226',),
        'lgk': ('3',),
        'kleinmenge_kg': 100.0,
        'zusatz_ab_kg': 1000.0,
        'quelle': 'TRGS 510 Nr. 4.3.1 (Tabelle 1), Nr. 12 (Tabelle 9)',
    },
    {
        'gruppe': 'entzfeststoff',
        'bezeichnung': 'Entzündbare Feststoffe Kat. 1/2 (H228)',
        'h_saetze': ('H228',),
        'lgk': ('4.1B',),
        'kleinmenge_kg': 200.0,
        'zusatz_ab_kg': None,
        'quelle': 'TRGS 510 Nr. 4.3.1 (Tabelle 1)',
    },
    {
        'gruppe': 'explosiv_desens',
        'bezeichnung': 'Desensibilisierte Explosivstoffe (H206-H208)',
        'h_saetze': ('H206', 'H207', 'H208'),
        'lgk': ('4.1A',),
        'kleinmenge_kg': 100.0,
        'zusatz_ab_kg': None,
        'quelle': 'TRGS 510 Nr. 4.3.1 (Tabelle 1)',
    },
    {
        'gruppe': 'pyrophor',
        'bezeichnung': 'Pyrophore Stoffe (H250)',
        'h_saetze': ('H250',),
        'lgk': ('4.2',),
        'kleinmenge_kg': 100.0,
        'zusatz_ab_kg': None,
        'quelle': 'TRGS 510 Nr. 4.3.1 (Tabelle 1)',
    },
    {
        'gruppe': 'selbsterhitzung',
        'bezeichnung': 'Selbsterhitzungsfähige Stoffe (H251, H252)',
        'h_saetze': ('H251', 'H252'),
        'lgk': ('4.2',),
        'kleinmenge_kg': 200.0,
        'zusatz_ab_kg': None,
        'quelle': 'TRGS 510 Nr. 4.3.1 (Tabelle 1)',
    },
    {
        'gruppe': 'wasserreaktiv',
        'bezeichnung': 'Stoffe, die mit Wasser entzündbare Gase bilden (H260, H261)',
        'h_saetze': ('H260', 'H261'),
        'lgk': ('4.3',),
        'kleinmenge_kg': 200.0,
        'zusatz_ab_kg': None,
        'quelle': 'TRGS 510 Nr. 4.3.1 (Tabelle 1)',
    },
    {
        'gruppe': 'brandfoerdernd_kat1',
        'bezeichnung': 'Brandfördernde Stoffe Kat. 1 (H271)',
        'h_saetze': ('H271',),
        'lgk': ('5.1A',),
        'kleinmenge_kg': 1.0,
        'zusatz_ab_kg': 5.0,
        'quelle': 'TRGS 510 Nr. 4.3.1 (Tabelle 1)',
    },
    {
        'gruppe': 'brandfoerdernd_kat23',
        'bezeichnung': 'Brandfördernde Stoffe Kat. 2/3 (H272)',
        'h_saetze': ('H272',),
        'lgk': ('5.1B', '5.1C'),
        'kleinmenge_kg': 50.0,
        'zusatz_ab_kg': None,
        'quelle': 'TRGS 510 Nr. 4.3.1 (Tabelle 1)',
    },
    {
        'gruppe': 'akut_toxisch',
        'bezeichnung': 'Akut toxische Stoffe (H300, H301, H310, H311, H330, H331)',
        'h_saetze': ('H300', 'H301', 'H310', 'H311', 'H330', 'H331'),
        'lgk': ('6.1A', '6.1B', '6.1C', '6.1D'),
        'kleinmenge_kg': 50.0,
        'zusatz_ab_kg': None,
        'quelle': 'TRGS 510 Nr. 4.3.1 (Tabelle 1)',
    },
    {
        'gruppe': 'aerosole',
        'bezeichnung': 'Aerosolpackungen / Druckgaspackungen',
        'h_saetze': ('H222', 'H223', 'H229'),
        'lgk': ('2B',),
        'kleinmenge_kg': 20.0,
        'zusatz_ab_kg': None,
        'quelle': 'TRGS 510 Nr. 4.3.1 (Tabelle 1: 20 kg oder 50 Stück)',
    },
    {
        'gruppe': 'brennbar_fluessig_lgk10',
        'bezeichnung': 'Brennbare Flüssigkeiten ohne entzündbar-Einstufung (LGK 10)',
        'h_saetze': (),
        'lgk': ('10',),
        'kleinmenge_kg': 1000.0,
        'zusatz_ab_kg': None,
        'quelle': 'TRGS 510 Nr. 4.3.1 (Tabelle 1)',
    },
    {
        'gruppe': 'sonstige',
        'bezeichnung': 'Sonstige Gefahrstoffe (LGK 12/13)',
        'h_saetze': (),
        'lgk': ('12', '13'),
        'kleinmenge_kg': 1000.0,
        'zusatz_ab_kg': None,
        'quelle': 'TRGS 510 Nr. 4.3.1 (Tabelle 1)',
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


def _regeln_fuer_stoff(h_menge, lagerklasse):
    """Regeln, die auf einen Stoff zutreffen - H-Sätze zuerst.

    Trifft mindestens eine H-Satz-Regel, gelten diese; die Lagerklasse dient
    nur als Ersatz, wenn die H-Sätze keine Zuordnung erlauben. Das verhindert
    falsche Treffer: ein Stoff der LGK 3 mit H226 soll nicht zusätzlich an der
    20-kg-Regel für H224/H225 gemessen werden.
    """
    h_treffer = [r for r in SCHWELLEN if r['h_saetze'] and h_menge & set(r['h_saetze'])]
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
            'quelle': 'TRGS 510 Nr. 4.3.1 (1500 kg je Brandabschnitt)',
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
