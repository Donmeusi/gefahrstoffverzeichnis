#!/usr/bin/env python3
"""Deutsche Stoffbezeichnungen aus Wikidata.

Warum es dieses Modul gibt: Die Autovervollstaendigung holt die GHS-Daten bei
PubChem, und PubChem kennt **nur englische** Bezeichnungen - aus CAS 50-00-0
wird "formaldehyde". Die H- und P-Saetze sind dort Codes (H225, P210) und damit
sprachneutral, die Piktogramme ebenfalls; ins Formular kam also als einziges
englisches Feld der **Name**.

Wikidata fuehrt zu einer CAS-Nummer (Eigenschaft P231) Bezeichnungen in vielen
Sprachen, darunter Deutsch. Abgefragt wird ueber den SPARQL-Endpunkt, ohne
Schluessel und ohne Konto.

⚠️ Zwei Dinge, die den Umgang mit dem Ergebnis bestimmen:

1. **Es kann mehrere Treffer geben, und keiner ist "falsch".** Zu 7647-01-0
   stehen dort sowohl "Chlorwasserstoff" (Q211086, das Gas) als auch
   "Salzsaeure" (Q2409, die waessrige Loesung). Welcher Name ins Verzeichnis
   gehoert, entscheidet der Nutzer, nicht dieses Modul - es liefert deshalb eine
   Liste und waehlt nicht selbst aus.

2. **Die PubChem-Kennung P662 sortiert objektiv.** Traegt ein Wikidata-Eintrag
   dieselbe PubChem-CID, die PubChem zur CAS-Nummer aufgeloest hat, ist er
   derselbe Stoff - dieser Eintrag steht dann vorn. Bei 7647-01-0 zeigt das auf
   "Chlorwasserstoff" (CID 313); "Salzsaeure" hat keine Kennung und bleibt als
   Alternative erhalten. Die Sortierung ist eine Hilfe, keine Entscheidung.

Wikidata ist ein Wiki: die **Bezeichnung** ist als Anzeigename brauchbar, die
Einstufung daraus **nicht**. Klassifizierungsdaten kommen weiter aus PubChem
bzw. aus dem Sicherheitsdatenblatt; die Piktogramme leitet `piktogramme.py`
aus den H-Saetzen ab.
"""
import json
import urllib.error
import urllib.parse
import urllib.request

ENDPUNKT = 'https://query.wikidata.org/sparql'

# Wikimedia verlangt einen aussagekraeftigen User-Agent; Anfragen ohne einen
# werden abgewiesen (HTTP 403). Der Kontakt ist bewusst allgemein gehalten -
# er dient der Zuordnung der Anfrage, nicht als Ansprechpartner.
KOPFZEILEN = {
    'Accept': 'application/sparql-results+json',
    'User-Agent': 'Gefahrstoffverzeichnis/1.0 (CAS-Namensabfrage; Python urllib)',
}

ABFRAGE = '''SELECT ?item ?name ?cid WHERE {{
  ?item wdt:P231 "{cas}" .
  ?item rdfs:label ?name FILTER(lang(?name) = "de")
  OPTIONAL {{ ?item wdt:P662 ?cid }}
}} LIMIT 25'''


def treffer_aus_antwort(daten, cid=None):
    """Baut aus einer SPARQL-Antwort die Kandidatenliste.

    Von der Netzabfrage getrennt, damit die Sortierung und das Entdoppeln ohne
    Internet pruefbar sind (siehe test_wikidata.py).
    """
    # Ein Stoff kann mehrere Zeilen liefern (mehrere P662-Werte), deshalb je
    # QID sammeln und die Kennungen mitfuehren statt die Zeilen zu wiederholen.
    treffer = {}
    for zeile in (daten or {}).get('results', {}).get('bindings', []):
        qid = zeile.get('item', {}).get('value', '').rsplit('/', 1)[-1]
        name = zeile.get('name', {}).get('value', '').strip()
        if not qid or not name:
            continue
        eintrag = treffer.setdefault(qid, {'qid': qid, 'name': name, 'cids': []})
        cid_wert = zeile.get('cid', {}).get('value')
        if cid_wert:
            eintrag['cids'].append(str(cid_wert))

    namen = sorted(treffer.values(), key=lambda e: e['name'].lower())

    # Passende PubChem-Kennung nach vorn; bei Gleichstand bleibt die
    # alphabetische Reihenfolge erhalten (sorted ist stabil).
    if cid is not None:
        passend = str(cid)
        namen.sort(key=lambda e: 0 if passend in e['cids'] else 1)

    return [{'qid': e['qid'], 'name': e['name']} for e in namen]


def namen_zu_cas(cas, cid=None, zeitlimit=8):
    """Deutsche Bezeichnungen zu einer CAS-Nummer.

    Gibt eine Liste von ``{'qid': ..., 'name': ...}`` zurueck, nach Relevanz
    sortiert (passende PubChem-Kennung zuerst), ohne Doppelte. Bei jedem Fehler
    - kein Netz, Zeitueberschreitung, unerwartete Antwort - kommt eine **leere
    Liste** zurueck: die Namensabfrage ist Beiwerk, sie darf den Autofill nicht
    zum Absturz bringen. Der Aufrufer faellt dann auf den PubChem-Namen zurueck.
    """
    cas = (cas or '').strip()
    if not cas:
        return []

    # Zweite Absicherung: CAS stammt aus dem URL-Pfad. Das Escape haelt den
    # Wert im SPARQL-Stringliteral, auch wenn ein Aufrufer die Pruefung im
    # Routen-Handler umgeht.
    cas_literal = cas.replace('\\', '\\\\').replace('"', '\\"')
    ziel = ENDPUNKT + '?query=' + urllib.parse.quote(ABFRAGE.format(cas=cas_literal))
    try:
        anfrage = urllib.request.Request(ziel, headers=KOPFZEILEN)
        antwort = urllib.request.urlopen(anfrage, timeout=zeitlimit)
        daten = json.loads(antwort.read())
    except (urllib.error.URLError, urllib.error.HTTPError, OSError,
            ValueError, TimeoutError):
        return []

    return treffer_aus_antwort(daten, cid)
