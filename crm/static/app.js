// CRM Application JavaScript
const API_BASE = '/api/policies';

let allPolicies = [];
let currentEditId = null;
let currentDeleteId = null;

// Load policies on page load
document.addEventListener('DOMContentLoaded', () => {
    loadPolicies();
});

// Load all policies from API
async function loadPolicies() {
    try {
        const response = await fetch(API_BASE);
        const data = await response.json();
        
        if (data.success) {
            allPolicies = data.policies;
            renderPolicies(allPolicies);
        } else {
            showError('שגיאה בטעינת הכללים: ' + (data.error || 'שגיאה לא ידועה'));
        }
    } catch (error) {
        showError('שגיאה בטעינת הכללים: ' + error.message);
        document.getElementById('policiesTableBody').innerHTML = 
            '<tr><td colspan="7" class="loading">שגיאה בטעינת הנתונים</td></tr>';
    }
}

// Render policies table
function renderPolicies(policies) {
    const tbody = document.getElementById('policiesTableBody');
    const emptyState = document.getElementById('emptyState');
    
    if (policies.length === 0) {
        tbody.innerHTML = '';
        emptyState.style.display = 'block';
        return;
    }
    
    emptyState.style.display = 'none';
    
    tbody.innerHTML = policies.map(policy => `
        <tr>
            <td><strong>${escapeHtml(policy.domain)}</strong></td>
            <td class="path-cell">${policy.path ? escapeHtml(policy.path) : '<span style="color: #94a3b8;">—</span>'}</td>
            <td class="type-cell">${escapeHtml(policy.type)}</td>
            <td>
                <span class="status-badge ${policy.state}">
                    ${policy.state === 'block' ? 'חסום' : 'מותר'}
                </span>
            </td>
            <td>${policy.description ? escapeHtml(policy.description) : '<span style="color: #94a3b8;">—</span>'}</td>
            <td>
                <span class="enabled-badge ${policy.enabled ? 'active' : 'inactive'}">
                    ${policy.enabled ? 'פעיל' : 'לא פעיל'}
                </span>
            </td>
            <td>
                <div class="action-buttons">
                    <button class="btn btn-primary btn-sm" onclick="editPolicy(${policy.id})">
                        ערוך
                    </button>
                    <button class="btn btn-danger btn-sm" onclick="deletePolicy(${policy.id})">
                        מחק
                    </button>
                </div>
            </td>
        </tr>
    `).join('');
}

// Filter policies
function filterPolicies() {
    const searchTerm = document.getElementById('searchInput').value.toLowerCase();
    const enabledOnly = document.getElementById('enabledFilter').checked;
    
    let filtered = allPolicies;
    
    if (enabledOnly) {
        filtered = filtered.filter(p => p.enabled);
    }
    
    if (searchTerm) {
        filtered = filtered.filter(p => 
            p.domain.toLowerCase().includes(searchTerm) ||
            (p.description && p.description.toLowerCase().includes(searchTerm)) ||
            (p.path && p.path.toLowerCase().includes(searchTerm))
        );
    }
    
    renderPolicies(filtered);
}

// Open add modal
function openAddModal() {
    currentEditId = null;
    document.getElementById('modalTitle').textContent = 'הוסף כלל חדש';
    document.getElementById('policyForm').reset();
    document.getElementById('enabled').checked = true;
    document.getElementById('type').value = '*';
    document.getElementById('state').value = 'block';
    document.getElementById('policyModal').style.display = 'flex';
}

// Edit policy
async function editPolicy(id) {
    try {
        const response = await fetch(`${API_BASE}/${id}`);
        const data = await response.json();
        
        if (data.success) {
            const policy = data.policy;
            currentEditId = id;
            
            document.getElementById('modalTitle').textContent = 'ערוך כלל';
            document.getElementById('domain').value = policy.domain;
            document.getElementById('path').value = policy.path || '';
            document.getElementById('type').value = policy.type;
            document.getElementById('state').value = policy.state;
            document.getElementById('description').value = policy.description || '';
            document.getElementById('enabled').checked = policy.enabled;
            
            document.getElementById('policyModal').style.display = 'flex';
        } else {
            showError('שגיאה בטעינת הכלל: ' + (data.error || 'שגיאה לא ידועה'));
        }
    } catch (error) {
        showError('שגיאה בטעינת הכלל: ' + error.message);
    }
}

// Save policy (create or update)
async function savePolicy(event) {
    event.preventDefault();
    
    const formData = {
        domain: document.getElementById('domain').value.trim(),
        path: document.getElementById('path').value.trim() || null,
        type: document.getElementById('type').value,
        state: document.getElementById('state').value,
        description: document.getElementById('description').value.trim() || null,
        enabled: document.getElementById('enabled').checked
    };
    
    try {
        let response;
        if (currentEditId) {
            // Update
            response = await fetch(`${API_BASE}/${currentEditId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(formData)
            });
        } else {
            // Create
            response = await fetch(API_BASE, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(formData)
            });
        }
        
        const data = await response.json();
        
        if (data.success) {
            closeModal();
            loadPolicies();
        } else {
            showError('שגיאה בשמירת הכלל: ' + (data.error || 'שגיאה לא ידועה'));
        }
    } catch (error) {
        showError('שגיאה בשמירת הכלל: ' + error.message);
    }
}

// Delete policy
function deletePolicy(id) {
    currentDeleteId = id;
    document.getElementById('deleteModal').style.display = 'flex';
}

// Confirm delete
async function confirmDelete() {
    if (!currentDeleteId) return;
    
    try {
        const response = await fetch(`${API_BASE}/${currentDeleteId}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.success) {
            closeDeleteModal();
            loadPolicies();
        } else {
            showError('שגיאה במחיקת הכלל: ' + (data.error || 'שגיאה לא ידועה'));
        }
    } catch (error) {
        showError('שגיאה במחיקת הכלל: ' + error.message);
    }
}

// Close modals
function closeModal() {
    document.getElementById('policyModal').style.display = 'none';
    currentEditId = null;
}

function closeDeleteModal() {
    document.getElementById('deleteModal').style.display = 'none';
    currentDeleteId = null;
}

// Close modal on background click
document.getElementById('policyModal')?.addEventListener('click', (e) => {
    if (e.target.id === 'policyModal') {
        closeModal();
    }
});

document.getElementById('deleteModal')?.addEventListener('click', (e) => {
    if (e.target.id === 'deleteModal') {
        closeDeleteModal();
    }
});

// Utility functions
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showError(message) {
    alert(message); // Can be replaced with a better notification system
}
