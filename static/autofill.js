document.addEventListener('DOMContentLoaded', function() {
    const btnAutofill = document.getElementById('btn_autofill_cas');
    const casInput = document.getElementById('cas_nummer');
    
    if (btnAutofill && casInput) {
        btnAutofill.addEventListener('click', async () => {
            const cas = casInput.value.trim();
            if (!cas) {
                alert("Bitte geben Sie zuerst eine CAS-Nummer ein.");
                casInput.focus();
                return;
            }
            
            // UI Feedback
            const originalText = btnAutofill.innerHTML;
            btnAutofill.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Lade Daten...';
            btnAutofill.disabled = true;
            
            try {
                const response = await fetch(`/api/autofill/${encodeURIComponent(cas)}`);
                const data = await response.json();
                
                if (!response.ok) {
                    throw new Error(data.error || 'Unbekannter Fehler bei der Abfrage.');
                }
                
                // Bezeichnung. Bis 13.10.2026 kam sie von PubChem und war
                // damit englisch ("formaldehyde" statt "Formaldehyd"); die
                // H-/P-Saetze sind dagegen Codes und sprachneutral. Die
                // deutschen Namen liefert jetzt Wikidata.
                const namen = Array.isArray(data.namen) ? data.namen : [];
                if (namen.length > 1) {
                    // Mehrere Treffer: der Nutzer waehlt (Salzsaeure-Fall).
                    namenWaehlen(namen);
                } else if (namen.length === 1) {
                    namenSetzen(namen[0].name);
                } else if (data.name) {
                    // Kein Wikidata-Treffer. Der Name stammt dann aus der
                    // amtlichen Tabelle (dort englisch) oder aus PubChem
                    // (ebenfalls englisch); name_quelle sagt, woher.
                    namenSetzen(data.name, data.name_quelle);
                }

                if (data.signalwort && document.getElementById('signalwort')) {
                    document.getElementById('signalwort').value = data.signalwort;
                }
                
                if (data.h_saetze && document.getElementById('h_saetze')) {
                    document.getElementById('h_saetze').value = data.h_saetze;
                }
                
                if (data.p_saetze && document.getElementById('p_saetze')) {
                    document.getElementById('p_saetze').value = data.p_saetze;
                }

                // Gefahrenkategorien kommen nur, wenn der Stoff in Anhang VI
                // der CLP-Verordnung steht. Das Formular erwartet sie mit
                // Semikolon getrennt.
                if (data.gefahrenkategorien && document.getElementById('gefahrenkategorien')) {
                    document.getElementById('gefahrenkategorien').value = data.gefahrenkategorien;
                }

                // Checkboxes für Piktogramme
                if (data.piktogramme && data.piktogramme.length > 0) {
                    const checkboxes = document.querySelectorAll('input[name="piktogramme"]');
                    checkboxes.forEach(cb => {
                        if (data.piktogramme.includes(cb.value)) {
                            cb.checked = true;
                        }
                    });
                }
                
                // Erfolgsmeldung Button kurz grün färben (Klasse statt
                // Inline-Farben - die hätten den Dunkelmodus übergangen).
                // Die Herkunft steht mit dabei: 'amtlich' heißt, die Einstufung
                // stammt aus Anhang VI der CLP-Verordnung; 'abgeleitet' heißt,
                // der Stoff steht dort nicht und die Angaben sind aus den
                // H-Sätzen hergeleitet bzw. von PubChem übernommen.
                const amtlich = data.quelle === 'echa';
                btnAutofill.innerHTML = '<i class="fa-solid fa-check"></i> Fertig!'
                    + (amtlich ? ' (amtlich)' : ' (abgeleitet)');
                btnAutofill.title = amtlich
                    ? 'Einstufung aus Anhang VI der CLP-Verordnung'
                    : 'Aus den H-Sätzen hergeleitet - Stoff steht nicht in Anhang VI';
                btnAutofill.classList.remove('btn-outline');
                btnAutofill.classList.add('btn-primary', 'is-ok');

                setTimeout(() => {
                    btnAutofill.innerHTML = originalText;
                    btnAutofill.classList.add('btn-outline');
                    btnAutofill.classList.remove('btn-primary', 'is-ok');
                    btnAutofill.disabled = false;
                }, 3000);
                
            } catch (error) {
                alert(`Fehler: ${error.message}`);
                btnAutofill.innerHTML = originalText;
                btnAutofill.disabled = false;
            }
        });
    }
});

// ─── Bezeichnung ────────────────────────────────────────────────────────────
// Die Funktionen stehen ausserhalb von DOMContentLoaded, weil der Dialog in
// base.html per onclick aufgerufen wird.

function namenSchreiben(name) {
    const feld = document.getElementById('name');
    if (feld) feld.value = name;
}

// Ueberschreibt nur nach Rueckfrage - ein schon eingetragener Name kann vom
// Nutzer stammen und soll nicht still verschwinden.
//
// ⚠️ Und ein **nicht deutscher** Name wird auch bei leerem Feld vorgelegt.
// Sonst landete unbemerkt "acetone; propan-2-one; propanone" im Verzeichnis,
// wenn Wikidata gerade nichts liefert und der Rueckfall auf die englische
// Bezeichnung aus der amtlichen Tabelle (oder aus PubChem) greift.
// quelle: 'wikidata' = deutsch, 'echa'/'pubchem' = englisch.
function namenSetzen(name, quelle) {
    const feld = document.getElementById('name');
    if (!feld) return;

    const nichtDeutsch = quelle === 'echa' || quelle === 'pubchem';
    const herkunft = nichtDeutsch
        ? '\n\nAchtung: keine deutsche Bezeichnung. Quelle: '
          + (quelle === 'echa' ? 'Anhang VI der CLP-Verordnung (englisch)'
                               : 'PubChem (englisch)')
          + '.'
        : '';
    if ((feld.value || nichtDeutsch) && !confirm(`Namen "${name}" übernehmen?${herkunft}`)) {
        return;
    }
    namenSchreiben(name);
}

function namenWaehlen(namen) {
    const liste = document.getElementById('nameModalList');
    const modal = document.getElementById('nameModal');
    if (!liste || !modal) return;

    liste.innerHTML = '';
    namen.forEach(function (eintrag, i) {
        const zeile = document.createElement('label');
        zeile.className = 'pick-item';

        const auswahl = document.createElement('input');
        auswahl.type = 'radio';
        auswahl.name = 'name_wahl';
        auswahl.value = eintrag.name;
        auswahl.checked = (i === 0);
        zeile.appendChild(auswahl);

        // textContent statt innerHTML: die Bezeichnungen kommen von aussen
        // (Wikidata) und haben in HTML nichts zu suchen.
        const text = document.createElement('span');
        text.textContent = eintrag.name;
        zeile.appendChild(text);

        if (i === 0) {
            const hinweis = document.createElement('span');
            hinweis.className = 'pick-hint';
            hinweis.textContent = 'passt zur PubChem-Kennung';
            zeile.appendChild(hinweis);
        }
        liste.appendChild(zeile);
    });

    modal.style.display = 'flex';
}

function closeNameModal() {
    const modal = document.getElementById('nameModal');
    if (modal) modal.style.display = 'none';
}

function applyNameSelection() {
    const gewaehlt = document.querySelector('#nameModalList input[name="name_wahl"]:checked');
    // Ohne erneute Rueckfrage: die Auswahl im Dialog ist die Entscheidung.
    if (gewaehlt) namenSchreiben(gewaehlt.value);
    closeNameModal();
}
