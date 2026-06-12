// ========================================
// إدارة المواعيد (للمريض والسكرتير)
// ========================================

// توليد ساعات العمل (من 8:00 إلى 16:00 كل نصف ساعة)
function generateTimeSlots() {
    const slots = [];
    for (let h = 8; h < 16; h++) {
        const hour = h.toString().padStart(2, '0');
        slots.push(`${hour}:00`);
        slots.push(`${hour}:30`);
    }
    return slots;
}

// التحقق مما إذا كانت الساعة قد مضت في اليوم الحالي
function isPastTime(date, hour) {
    if (!date || !hour) return false;
    
    const today = new Date().toISOString().split('T')[0];
    if (date !== today) return false;
    
    const now = new Date();
    const currentHour = now.getHours();
    const currentMinute = now.getMinutes();
    const [slotHour, slotMinute] = hour.split(':').map(Number);
    
    if (slotHour < currentHour) return true;
    if (slotHour === currentHour && slotMinute <= currentMinute) return true;
    
    return false;
}

// توليد الساعات مع مراعاة الوقت الحالي والتاريخ
function generateTimeSlotsWithCurrentTime(date) {
    const slots = [];
    for (let h = 8; h < 16; h++) {
        const hour = h.toString().padStart(2, '0');
        const slot1 = `${hour}:00`;
        const slot2 = `${hour}:30`;
        
        slots.push({ value: slot1, disabled: isPastTime(date, slot1) });
        slots.push({ value: slot2, disabled: isPastTime(date, slot2) });
    }
    return slots;
}

// تعبئة قائمة الساعات المتاحة
function initTimeSlots(selectId, selectedHour = null, date = null) {
    const heureSelect = document.getElementById(selectId);
    if (!heureSelect) return;
    
    if (!date) {
        const dateInput = document.getElementById('rdv_date') || document.getElementById('edit_date') || document.getElementById('date');
        if (dateInput) date = dateInput.value;
    }
    
    const slots = generateTimeSlotsWithCurrentTime(date);
    heureSelect.innerHTML = '<option value="">Sélectionner une heure</option>';
    
    slots.forEach(slot => {
        const option = document.createElement('option');
        option.value = slot.value;
        option.textContent = slot.value;
        
        if (slot.disabled) {
            option.disabled = true;
            option.style.backgroundColor = '#f3f4f6';
            option.style.color = '#9ca3af';
            option.title = 'Horaire passé';
        }
        
        if (selectedHour && selectedHour === slot.value && !slot.disabled) {
            option.selected = true;
        }
        
        heureSelect.appendChild(option);
    });
    
    heureSelect.disabled = false;
}

// منع اختيار تواريخ ماضية
function initDatePicker(dateInputId) {
    const dateInput = document.getElementById(dateInputId);
    if (!dateInput) return;
    
    const today = new Date().toISOString().split('T')[0];
    dateInput.min = today;
}

// فتح نافذة
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.style.display = 'flex';
}

// إغلاق نافذة
function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.style.display = 'none';
}

// جلب الأوقات المحجوزة لطبيب معين في تاريخ معين
async function getBookedSlots(medecinId, date) {
    if (!medecinId || !date) return [];
    
    try {
        const response = await fetch(`/secretaire/api/rendezvous/booked?medecin_id=${medecinId}&date=${date}`);
        const data = await response.json();
        return data.booked_slots || [];
    } catch (error) {
        console.error('Erreur:', error);
        return [];
    }
}

// تحديث عرض الساعات المحجوزة والماضية
async function updateSlotsDisplay(heureSelect, medecinId, date, selectedHeure = null) {
    if (!heureSelect || !medecinId || !date) return;
    
    const bookedSlots = await getBookedSlots(medecinId, date);
    const options = heureSelect.querySelectorAll('option');
    
    options.forEach(option => {
        if (!option.value) return;
        
        const isPast = isPastTime(date, option.value);
        
        if (isPast) {
            option.disabled = true;
            option.style.backgroundColor = '#f3f4f6';
            option.style.color = '#9ca3af';
            option.title = 'Horaire passé';
        } else if (bookedSlots.includes(option.value)) {
            option.disabled = true;
            option.style.backgroundColor = '#fee2e2';
            option.style.color = '#dc2626';
            option.title = 'Déjà réservé';
        } else {
            option.disabled = false;
            option.style.backgroundColor = '';
            option.style.color = '';
            option.title = '';
        }
        
        if (selectedHeure && selectedHeure === option.value && !option.disabled) {
            option.selected = true;
        }
    });
}

// ========== دوال السكرتير ==========

// فتح نافذة إضافة موعد
function openNewRdvModal() {
    openModal('newRdvModal');
    
    const dateInput = document.getElementById('rdv_date');
    const medecinSelect = document.getElementById('rdv_medecin_id');
    const heureSelect = document.getElementById('rdv_heure');
    
    initDatePicker('rdv_date');
    
    if (dateInput) {
        const initialDate = dateInput.value || new Date().toISOString().split('T')[0];
        initTimeSlots('rdv_heure', null, initialDate);
        
        dateInput.onchange = function() {
            initTimeSlots('rdv_heure', null, dateInput.value);
            if (medecinSelect && medecinSelect.value) {
                updateSlotsDisplay(heureSelect, medecinSelect.value, dateInput.value);
            }
        };
    }
    
    if (medecinSelect && dateInput) {
        medecinSelect.onchange = function() {
            if (dateInput.value) {
                updateSlotsDisplay(heureSelect, medecinSelect.value, dateInput.value);
            }
        };
    }
}

// متغير عام لتخزين معرف الموعد الجاري تعديله
let currentEditRdvIdGlobal = null;

function openEditRdvModal(id, date, heure, medecinId) {
    currentEditRdvIdGlobal = id;
    
    const editRdvIdInput = document.getElementById('edit_rdv_id');
    const editMedecinSelect = document.getElementById('edit_medecin_id');
    const editDateInput = document.getElementById('edit_date');
    const editHeureSelect = document.getElementById('edit_heure');
    
    if (editRdvIdInput) editRdvIdInput.value = id;
    if (editMedecinSelect) editMedecinSelect.value = medecinId;
    if (editDateInput) {
        editDateInput.value = date;
        // ✅ منع التواريخ الماضية
        const today = new Date().toISOString().split('T')[0];
        editDateInput.min = today;
    }
    
    openModal('editRdvModal');
    
    initTimeSlots('edit_heure', heure, date);
    
    if (editMedecinSelect && editDateInput && editHeureSelect) {
        setTimeout(() => {
            updateSlotsDisplay(editHeureSelect, editMedecinSelect.value, editDateInput.value, heure);
        }, 100);
        
        editDateInput.onchange = function() {
            initTimeSlots('edit_heure', null, editDateInput.value);
            if (editMedecinSelect.value) {
                updateSlotsDisplay(editHeureSelect, editMedecinSelect.value, editDateInput.value);
            }
        };
        
        editMedecinSelect.onchange = function() {
            if (editDateInput.value) {
                updateSlotsDisplay(editHeureSelect, editMedecinSelect.value, editDateInput.value);
            }
        };
    }
}
// الحصول على معرف الموعد الجاري تعديله
function getCurrentEditRdvId() {
    return currentEditRdvIdGlobal;
}

// ========== دوال المريض ==========

// تهيئة صفحة حجز الموعد للمريض
function initPatientRdvPage() {
    const dateInput = document.getElementById('date');
    const medecinSelect = document.getElementById('medecin_id');
    const heureSelect = document.getElementById('heure');
    const submitBtn = document.querySelector('#rdvForm button[type="submit"]');
    
    if (!dateInput || !medecinSelect || !heureSelect) return;
    
    initDatePicker('date');
    initTimeSlots('heure', null, dateInput.value);
    
    async function updateDisplay() {
        const medecinId = medecinSelect.value;
        const date = dateInput.value;
        const selectedHeure = heureSelect.value;
        
        if (medecinId && date) {
            await updateSlotsDisplay(heureSelect, medecinId, date, selectedHeure);
            
            // التحقق من صحة الساعة المختارة
            const selectedOption = heureSelect.options[heureSelect.selectedIndex];
            if (selectedOption && selectedOption.disabled) {
                if (submitBtn) submitBtn.disabled = true;
                if (selectedOption.title === 'Déjà réservé') {
                    alert('Cet horaire est déjà réservé pour ce médecin');
                }
            } else if (submitBtn) {
                submitBtn.disabled = false;
            }
        }
    }
    
    dateInput.addEventListener('change', function() {
        initTimeSlots('heure', null, dateInput.value);
        updateDisplay();
    });
    
    medecinSelect.addEventListener('change', updateDisplay);
    heureSelect.addEventListener('change', updateDisplay);
    
    // تحديث أولي
    updateDisplay();
}

// تصدير الدوال للاستخدام العام
window.openNewRdvModal = openNewRdvModal;
window.openEditRdvModal = openEditRdvModal;
window.closeModal = closeModal;
window.initTimeSlots = initTimeSlots;
window.initDatePicker = initDatePicker;
window.initPatientRdvPage = initPatientRdvPage;
window.getCurrentEditRdvId = getCurrentEditRdvId;
window.updateSlotsDisplay = updateSlotsDisplay;
window.getBookedSlots = getBookedSlots;
window.isPastTime = isPastTime;