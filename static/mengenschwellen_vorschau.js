/* Live-Vorschau der Mengenschwellen im Gefahrstoff-Formular (Stufe 3).
 *
 * Prüft die noch nicht gespeicherten Werte (Menge, Einheit, H-Sätze,
 * Lagerklasse, Standort) zusammen mit den bereits im Lagerabschnitt liegenden
 * Stoffen und zeigt das Ergebnis unter dem Formular. Es wird nichts blockiert -
 * nur hingewiesen; die verbindliche Prüfung steht auf /mengenschwellen.
 *
 * Die Felder werden auch von anderem JavaScript gesetzt (SDB-Autofill,
 * H-Satz-Auswahl im Dialog). Statt jede dieser Stellen anzufassen, wird neben
 * den Eingabe-Ereignissen ein kurzer Vergleichslauf über die Feldwerte
 * gefahren - so erscheint der Hinweis auch nach programmatischen Änderungen.
 */
(function () {
  const box = document.getElementById('mengenschwellen-vorschau');
  if (!box) return;

  const form = box.closest('form');
  if (!form) return;

  const feldIds = ['name', 'menge', 'mengeneinheit', 'h_saetze', 'lagerklasse', 'unterbereich_id'];
  const stoffId = box.dataset.stoffId || '';
  let timer = null;
  let letzteSignatur = null;

  function feld(id) {
    return document.getElementById(id);
  }

  function signatur() {
    return feldIds.map(id => (feld(id) ? feld(id).value : '')).join('\u0001');
  }

  function laden() {
    const unterbereich = feld('unterbereich_id') ? feld('unterbereich_id').value : '';
    // Ohne Standort gibt es keinen Lagerabschnitt und damit keine Summe.
    if (!unterbereich) {
      malen([]);
      return;
    }
    const params = new URLSearchParams({
      unterbereich_id: unterbereich,
      name: feld('name') ? feld('name').value : '',
      menge: feld('menge') ? feld('menge').value : '',
      mengeneinheit: feld('mengeneinheit') ? feld('mengeneinheit').value : '',
      h_saetze: feld('h_saetze') ? feld('h_saetze').value : '',
      lagerklasse: feld('lagerklasse') ? feld('lagerklasse').value : '',
    });
    if (stoffId) params.set('stoff_id', stoffId);

    fetch(box.dataset.url + '?' + params.toString(), {headers: {'Accept': 'application/json'}})
      .then(r => (r.ok ? r.json() : {hinweise: []}))
      .then(d => malen(d.hinweise || []))
      .catch(() => { /* Vorschau ist Beiwerk - Fehler still schlucken */ });
  }

  function malen(hinweise) {
    if (!hinweise.length) {
      box.style.display = 'none';
      box.innerHTML = '';
      return;
    }
    const punkte = hinweise.map(h => '<li>' + h.replace(/[<>&]/g, c => ({'<': '&lt;', '>': '&gt;', '&': '&amp;'}[c])) + '</li>').join('');
    box.innerHTML =
      '<h4><i class="fa-solid fa-scale-unbalanced"></i> Mengenschwellen im Lagerabschnitt (TRGS 510)</h4>' +
      '<ul>' + punkte + '</ul>' +
      '<p class="text-xs">Hinweis, keine Sperre - die Mengen werden so gespeichert, wie Sie sie eingetragen haben.</p>';
    box.style.display = '';
  }

  function planen() {
    clearTimeout(timer);
    timer = setTimeout(laden, 350);
  }

  feldIds.forEach(id => {
    const el = feld(id);
    if (el) {
      el.addEventListener('input', planen);
      el.addEventListener('change', planen);
    }
  });

  // Vergleichslauf: greift programmatische Änderungen auf (Autofill, H-Satz-Dialog),
  // ohne dass jede dieser Stellen ein Ereignis auslösen muss.
  setInterval(function () {
    const jetzt = signatur();
    if (jetzt !== letzteSignatur) {
      letzteSignatur = jetzt;
      planen();
    }
  }, 1200);

  letzteSignatur = signatur();
  laden();
})();
