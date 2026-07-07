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
                
                // Formular füllen
                if (data.name && document.getElementById('name')) {
                    // Nur überschreiben wenn leer oder Nutzer zustimmt
                    if (!document.getElementById('name').value || confirm(`Namen "${data.name}" aus PubChem übernehmen?`)) {
                        document.getElementById('name').value = data.name;
                    }
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
                
                // Checkboxes für Piktogramme
                if (data.piktogramme && data.piktogramme.length > 0) {
                    const checkboxes = document.querySelectorAll('input[name="piktogramme"]');
                    checkboxes.forEach(cb => {
                        if (data.piktogramme.includes(cb.value)) {
                            cb.checked = true;
                        }
                    });
                }
                
                // Erfolgsmeldung Button kurz grün färben
                btnAutofill.innerHTML = '<i class="fa-solid fa-check"></i> Fertig!';
                btnAutofill.classList.remove('btn-outline');
                btnAutofill.classList.add('btn-primary');
                btnAutofill.style.backgroundColor = '#10b981'; // Grün
                btnAutofill.style.borderColor = '#10b981';
                btnAutofill.style.color = '#ffffff';
                
                setTimeout(() => {
                    btnAutofill.innerHTML = originalText;
                    btnAutofill.classList.add('btn-outline');
                    btnAutofill.classList.remove('btn-primary');
                    btnAutofill.style.backgroundColor = '';
                    btnAutofill.style.borderColor = '';
                    btnAutofill.style.color = '';
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
