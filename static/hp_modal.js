let hpData = null;
let currentTargetInputId = null;

// Fetch data on load
document.addEventListener('DOMContentLoaded', () => {
    fetch('/static/hp_data.json')
        .then(response => response.json())
        .then(data => {
            hpData = data;
            console.log("Loaded HP data", data);
        })
        .catch(err => console.error("Error loading HP data:", err));
});

function openHpModal(inputId) {
    if (!hpData) {
        alert("Daten werden noch geladen. Bitte versuche es gleich noch einmal.");
        return;
    }
    
    currentTargetInputId = inputId;
    const isH = inputId === 'h_saetze';
    
    document.getElementById('hpModalTitle').innerText = isH ? "H- und EUH-Sätze auswählen" : "P-Sätze auswählen";
    document.getElementById('hpModalSearch').value = "";
    
    const targetInput = document.getElementById(inputId);
    const existingValues = targetInput.value.split(',').map(s => s.trim()).filter(s => s);
    
    renderHpList(isH, existingValues, "");
    
    document.getElementById('hpModal').style.display = 'flex';
}

function closeHpModal() {
    document.getElementById('hpModal').style.display = 'none';
    currentTargetInputId = null;
}

function renderHpList(isH, selectedValues, filterText) {
    const listContainer = document.getElementById('hpModalList');
    listContainer.innerHTML = "";
    
    let itemsToRender = [];
    if (isH) {
        itemsToRender = itemsToRender.concat(hpData.h_saetze || []);
        itemsToRender = itemsToRender.concat(hpData.euh_saetze || []);
    } else {
        itemsToRender = itemsToRender.concat(hpData.p_saetze || []);
    }
    
    filterText = filterText.toLowerCase();
    if (filterText) {
        itemsToRender = itemsToRender.filter(item => 
            item.code.toLowerCase().includes(filterText) || 
            item.text.toLowerCase().includes(filterText)
        );
    }
    
    if (itemsToRender.length === 0) {
        listContainer.innerHTML = "<p style='padding: 1rem; color: var(--text-muted);'>Keine Sätze gefunden.</p>";
        return;
    }
    
    itemsToRender.forEach(item => {
        const isChecked = selectedValues.includes(item.code);
        
        const label = document.createElement('label');
        label.className = 'hp-item';
        
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.value = item.code;
        checkbox.checked = isChecked;
        
        const textSpan = document.createElement('span');
        textSpan.innerHTML = `<strong>${item.code}</strong>: ${item.text}`;
        
        label.appendChild(checkbox);
        label.appendChild(textSpan);
        listContainer.appendChild(label);
    });
}

function filterHpList() {
    if (!currentTargetInputId) return;
    
    const isH = currentTargetInputId === 'h_saetze';
    const filterText = document.getElementById('hpModalSearch').value;
    
    // Preserve currently checked items visually while searching? 
    // Usually standard checkboxes in a rendered list lose state if re-rendered.
    // To handle this properly, let's grab the current DOM state first.
    
    const currentChecked = Array.from(document.querySelectorAll('#hpModalList input[type="checkbox"]:checked')).map(cb => cb.value);
    
    // We also need to keep track of items that were checked but are HIDDEN by the search filter.
    // For simplicity, whenever we filter, we just render, but this might lose selection.
    // A better approach: just use CSS to hide/show items instead of re-rendering.
    
    const items = document.querySelectorAll('.hp-item');
    items.forEach(item => {
        const text = item.innerText.toLowerCase();
        if (text.includes(filterText.toLowerCase())) {
            item.style.display = 'flex';
        } else {
            item.style.display = 'none';
        }
    });
}

function saveHpSelection() {
    if (!currentTargetInputId) return;
    
    const checkboxes = document.querySelectorAll('#hpModalList input[type="checkbox"]:checked');
    const selectedCodes = Array.from(checkboxes).map(cb => cb.value);
    
    const targetInput = document.getElementById(currentTargetInputId);
    targetInput.value = selectedCodes.join(', ');
    
    closeHpModal();
}
