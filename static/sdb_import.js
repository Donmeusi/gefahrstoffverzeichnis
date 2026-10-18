/* Daten aus einem Sicherheitsdatenblatt ins Formular übernehmen.
 *
 * Bedient den Kasten „Daten aus SDB importieren" in add.html und edit.html.
 * Die Route /api/parse_sdb liefert neben den Feldwerten auch
 *   quellen   - wo im Dokument der Wert steht (Abschnitt, Seite, Fundstelle)
 *   warnungen - Widersprüche und Unsicherheiten
 *
 * Zwei Regeln, die den Import vertrauenswürdig machen:
 *
 * 1. **Nichts überschreiben.** Ist ein Feld schon gefüllt und das SDB sagt
 *    etwas anderes, bleibt der eingetragene Wert stehen; der Unterschied
 *    erscheint als Konflikt im Ergebnis. Ein Datenblatt ist ein Vorschlag,
 *    keine Anweisung.
 * 2. **Nichts als HTML einsetzen.** Die Werte stammen aus einer fremden
 *    Datei. Sie werden ausschließlich über textContent gesetzt.
 */
(function () {
    'use strict';

    var FELDER = [
        {key: 'name', id: 'name', label: 'Name'},
        {key: 'cas', id: 'cas_nummer', label: 'CAS-Nummer'},
        {key: 'eg', id: 'eg_nummer', label: 'EG-Nummer'},
        {key: 'signalwort', id: 'signalwort', label: 'Signalwort'},
        {key: 'gefahrenkategorien', id: 'gefahrenkategorien',
         label: 'Gefahrenkategorien', liste: '; '},
        {key: 'h_saetze', id: 'h_saetze', label: 'H-Sätze'},
        {key: 'p_saetze', id: 'p_saetze', label: 'P-Sätze'},
        {key: 'sdb_datum', id: 'sdb_datum', label: 'SDB-Datum'},
        {key: 'lagerklasse', id: 'lagerklasse', label: 'Lagerklasse'}
    ];

    function wertAlsText(feld, data) {
        var wert = data[feld.key];
        if (Array.isArray(wert)) {
            return wert.join(feld.liste || ', ');
        }
        return wert == null ? '' : String(wert);
    }

    function quelleText(quellen, key) {
        var q = quellen && quellen[key];
        if (!q) return '';
        var teile = [];
        if (q.abschnitt) teile.push('Abschnitt ' + q.abschnitt);
        if (q.seite) teile.push('Seite ' + q.seite);
        return teile.join(' · ');
    }

    function abschnitt(titel) {
        var box = document.createElement('div');
        box.className = 'sdb-result-group';
        var h = document.createElement('div');
        h.className = 'sdb-result-title';
        h.textContent = titel;
        box.appendChild(h);
        return box;
    }

    function eintrag(text, klasse) {
        var li = document.createElement('li');
        if (klasse) li.className = klasse;
        li.textContent = text;
        return li;
    }

    function liste(items) {
        var ul = document.createElement('ul');
        ul.className = 'sdb-result-list';
        items.forEach(function (item) { ul.appendChild(item); });
        return ul;
    }

    function zeige(statusDiv, art, titel, teile) {
        statusDiv.className = 'status-box status-' + art;
        statusDiv.replaceChildren();

        var kopf = document.createElement('div');
        kopf.className = 'status-title';
        kopf.textContent = titel;
        statusDiv.appendChild(kopf);

        (teile || []).forEach(function (teil) {
            if (teil) statusDiv.appendChild(teil);
        });
        statusDiv.style.display = 'block';
    }

    function initialisiere() {
        var btn = document.getElementById('btn_parse_sdb');
        var dateiFeld = document.getElementById('sdb_upload');
        var statusDiv = document.getElementById('sdb_status');
        if (!btn || !dateiFeld || !statusDiv) return;

        btn.addEventListener('click', function () {
            if (!dateiFeld.files || !dateiFeld.files[0]) {
                zeige(statusDiv, 'error', 'Bitte wähle zuerst ein PDF aus.');
                return;
            }

            var formData = new FormData();
            formData.append('file', dateiFeld.files[0]);

            zeige(statusDiv, 'info', 'Dokument wird verarbeitet … Bitte warten.');
            btn.disabled = true;

            var tokenFeld = document.querySelector('input[name="csrf_token"]');
            var kopf = {};
            if (tokenFeld) kopf['X-CSRFToken'] = tokenFeld.value;

            fetch(statusDiv.dataset.url || '/api/parse_sdb', {
                method: 'POST',
                headers: kopf,
                body: formData
            }).then(function (antwort) {
                return antwort.json().then(function (data) {
                    if (!antwort.ok) {
                        throw new Error(data.error || 'Fehler beim Verarbeiten');
                    }
                    return data;
                });
            }).then(function (data) {
                var uebernommen = [];
                var konflikte = [];
                var quellen = data.quellen || {};

                FELDER.forEach(function (feld) {
                    var element = document.getElementById(feld.id);
                    if (!element) return;
                    var wert = wertAlsText(feld, data).trim();
                    if (!wert) return;

                    var quelle = quelleText(quellen, feld.key);
                    var vorhanden = (element.value || '').trim();

                    if (!vorhanden) {
                        element.value = wert;
                        uebernommen.push(eintrag(
                            feld.label + ': ' + wert + (quelle ? '  (' + quelle + ')' : '')
                        ));
                    } else if (vorhanden === wert) {
                        // Kein Konflikt, nur bestätigt.
                    } else {
                        konflikte.push(eintrag(
                            feld.label + ': im Formular „' + vorhanden +
                            '", im SDB „' + wert + '" – nicht überschrieben.'
                        ));
                    }
                });

                var neuePiktogramme = [];
                if (Array.isArray(data.piktogramme) && data.piktogramme.length) {
                    document.querySelectorAll('input[name="piktogramme"]').forEach(function (cb) {
                        if (data.piktogramme.indexOf(cb.value) !== -1 && !cb.checked) {
                            cb.checked = true;
                            neuePiktogramme.push(cb.value);
                        }
                    });
                }

                if (data.sdb_datum) {
                    var datumFeld = document.getElementById('sdb_datum');
                    if (datumFeld && typeof window.checkSdbDate === 'function') {
                        window.checkSdbDate(datumFeld);
                    }
                }

                // Das ausgelesene PDF gleich als SDB-Anhang übernehmen – der
                // Nutzer hat es ja schon ausgewählt.
                var sdbFeld = document.getElementById('sicherheitsdatenblatt');
                if (sdbFeld && dateiFeld.files.length > 0
                        && sdbFeld !== dateiFeld && window.DataTransfer) {
                    var transfer = new DataTransfer();
                    transfer.items.add(dateiFeld.files[0]);
                    sdbFeld.files = transfer.files;
                }

                var teile = [];
                if (uebernommen.length) {
                    var g = abschnitt('Aus dem SDB übernommen');
                    g.appendChild(liste(uebernommen));
                    teile.push(g);
                }
                if (neuePiktogramme.length) {
                    var p = abschnitt('Piktogramme gesetzt');
                    p.appendChild(liste([eintrag(neuePiktogramme.join(', '))]));
                    teile.push(p);
                }
                if (konflikte.length) {
                    var k = abschnitt('Bereits ausgefüllt – nicht überschrieben');
                    k.appendChild(liste(konflikte));
                    teile.push(k);
                }
                if (data.ist_gemisch && Array.isArray(data.bestandteile)
                        && data.bestandteile.length) {
                    var b = abschnitt('Gemisch – Bestandteile im SDB');
                    b.appendChild(liste(data.bestandteile.map(function (teil) {
                        var text = teil.cas || 'ohne CAS';
                        if (teil.konzentration) text += ' · ' + teil.konzentration;
                        if (teil.eg) text += ' · EG ' + teil.eg;
                        return eintrag(text);
                    })));
                    teile.push(b);
                }
                if (Array.isArray(data.warnungen) && data.warnungen.length) {
                    var w = abschnitt('Bitte prüfen');
                    w.appendChild(liste(data.warnungen.map(function (warnung) {
                        return eintrag(warnung.text, 'sdb-warnung');
                    })));
                    teile.push(w);
                }

                var hatWarnungen = Array.isArray(data.warnungen) && data.warnungen.length > 0;
                var hatKonflikte = konflikte.length > 0;
                var art = (hatWarnungen || hatKonflikte) ? 'warn' : 'ok';
                var titel = hatKonflikte
                    ? 'Daten ausgelesen – vorhandene Werte bleiben stehen.'
                    : (hatWarnungen
                        ? 'Daten ausgelesen – bitte die markierten Punkte prüfen.'
                        : 'Daten ausgelesen. Bitte trotzdem gegen das Original prüfen.');
                zeige(statusDiv, art, titel, teile);
            }).catch(function (fehler) {
                zeige(statusDiv, 'error', 'Fehler: ' + fehler.message);
            }).finally(function () {
                btn.disabled = false;
            });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initialisiere);
    } else {
        initialisiere();
    }
})();
