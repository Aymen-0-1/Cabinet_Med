let currentEditRdvId = null;

function openNewRdvModal() { document.getElementById('newRdvModal').style.display = 'flex'; }
function closeNewRdvModal() { document.getElementById('newRdvModal').style.display = 'none'; }
function closeEditRdvModal() { document.getElementById('editRdvModal').style.display = 'none'; }

function editRdv(id, dateTime, medecinId) {
    currentEditRdvId = id;
    document.getElementById('edit_rdv_id').value = id;
    document.getElementById('edit_medecin_id').value = medecinId;
    document.getElementById('edit_date').value = dateTime;
    document.getElementById('editRdvModal').style.display = 'flex';
}

document.getElementById('newRdvForm').addEventListener('submit', function(e) {
    e.preventDefault();
    const data = {
        patient_id: document.getElementById('rdv_patient_id').value,
        medecin_id: document.getElementById('rdv_medecin_id').value,
        date_rendezvous: document.getElementById('rdv_date').value,
        motif: document.getElementById('rdv_motif').value
    };
    
    fetch('/secretaire/api/rendezvous', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    }).then(r => r.json()).then(d => {
        if (d.success) {
            alert('Rendez-vous créé avec succès!');
            location.reload();
        } else {
            alert('Erreur: ' + d.message);
        }
    });
});

document.getElementById('editRdvForm').addEventListener('submit', function(e) {
    e.preventDefault();
    const data = {
        date_rendezvous: document.getElementById('edit_date').value,
        medecin_id: document.getElementById('edit_medecin_id').value
    };
    
    fetch('/secretaire/api/rendezvous/' + currentEditRdvId, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    }).then(r => r.json()).then(d => {
        if (d.success) {
            alert('Rendez-vous modifié avec succès!');
            location.reload();
        } else {
            alert('Erreur: ' + d.message);
        }
    });
});

function updateStatus(id, status) {
    fetch('/secretaire/api/rendezvous/' + id + '/status', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ statut: status })
    }).then(r => r.json()).then(d => {
        if (d.success) location.reload();
        else alert('Erreur: ' + d.message);
    });
}

function deleteRdv(id) {
    if (confirm('Supprimer ce rendez-vous ?')) {
        fetch('/secretaire/api/rendezvous/' + id, { method: 'DELETE' })
            .then(r => r.json()).then(d => {
                if (d.success) location.reload();
                else alert('Erreur: ' + d.message);
            });
    }
}

function filterTable() {
    const search = document.getElementById('searchInput').value.toLowerCase();
    const date = document.getElementById('dateFilter').value;
    const medecin = document.getElementById('medecinFilter').value;
    const status = document.getElementById('statusFilter').value;
    const rows = document.querySelectorAll('#rendezvousTable tr');
    rows.forEach(row => {
        const patient = row.cells[0]?.textContent.toLowerCase() || '';
        const rowDate = row.getAttribute('data-date') || '';
        const rowMedecin = row.getAttribute('data-medecin') || '';
        const rowStatus = row.getAttribute('data-status') || '';
        let show = true;
        if (search && !patient.includes(search)) show = false;
        if (date && rowDate !== date) show = false;
        if (medecin !== 'all' && rowMedecin !== medecin) show = false;
        if (status !== 'all' && rowStatus !== status) show = false;
        row.style.display = show ? '' : 'none';
    });
}

function resetFilters() {
    document.getElementById('searchInput').value = '';
    document.getElementById('dateFilter').value = '';
    document.getElementById('medecinFilter').value = 'all';
    document.getElementById('statusFilter').value = 'all';
    filterTable();
}

document.getElementById('searchInput').addEventListener('input', filterTable);
document.getElementById('dateFilter').addEventListener('change', filterTable);
document.getElementById('medecinFilter').addEventListener('change', filterTable);
document.getElementById('statusFilter').addEventListener('change', filterTable);

window.onclick = function(e) {
    if (e.target === document.getElementById('newRdvModal')) closeNewRdvModal();
    if (e.target === document.getElementById('editRdvModal')) closeEditRdvModal();
}
