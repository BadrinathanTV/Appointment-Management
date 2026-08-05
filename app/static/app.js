// State Management
let currentUser = null;
let currentToken = localStorage.getItem('access_token');
let currentTab = 'open-slots';
let pollingIntervalId = null;

// Utility Functions
function showToast(message, type = 'success') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `
    <span>${type === 'success' ? '✅' : '⚠️'}</span>
    <div>${message}</div>
  `;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

async function apiFetch(endpoint, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {})
  };
  
  if (currentToken) {
    headers['Authorization'] = `Bearer ${currentToken}`;
  }

  const response = await fetch(endpoint, { ...options, headers });

  if (response.status === 401) {
    logout();
    throw new Error('Session expired. Please log in again.');
  }

  // 204 No Content has no body
  if (response.status === 204) return {};

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || 'An unexpected error occurred.');
  }
  return data;
}

// Auth Functions
async function initAuth() {
  if (currentToken) {
    try {
      currentUser = await apiFetch('/api/auth/me');
      updateNav();
      renderDashboard();
      startNotificationPolling();
    } catch (e) {
      logout();
    }
  } else {
    renderAuth();
  }
}

function logout() {
  currentToken = null;
  currentUser = null;
  localStorage.removeItem('access_token');
  updateNav();
  renderAuth();
}

function updateNav() {
  const navActions = document.getElementById('nav-actions');
  if (currentUser) {
    navActions.innerHTML = `
      <div class="user-badge">
        <span>👤 ${currentUser.name}</span>
        <span class="role-tag ${currentUser.role.toLowerCase()}">${currentUser.role}</span>
      </div>
      <div class="notif-wrapper">
        <button class="notif-bell" onclick="toggleNotifications()">
          🔔 <span id="notif-badge" class="notif-badge" style="display:none">0</span>
        </button>
        <div id="notif-dropdown" class="notif-dropdown">
          <div style="font-weight:700; margin-bottom:0.5rem; display:flex; justify-content:space-between;">
            <span>Notifications</span>
          </div>
          <div id="notif-list">No notifications</div>
        </div>
      </div>
      <button class="btn btn-secondary btn-sm" onclick="logout()">Logout</button>
    `;
    loadNotifications();
  } else {
    navActions.innerHTML = '';
  }
}

// Render Views
function renderAuth() {
  const main = document.getElementById('app-content');
  main.innerHTML = `
    <div class="auth-wrapper">
      <div class="auth-header">
        <h2>Welcome Back</h2>
        <p>Book appointments & manage waitlists effortlessly</p>
      </div>

      <div class="tabs" style="justify-content:center; margin-bottom:1.5rem;">
        <button class="tab-btn active" id="tab-login" onclick="switchAuthTab('login')">Login</button>
        <button class="tab-btn" id="tab-register" onclick="switchAuthTab('register')">Register</button>
      </div>

      <form id="auth-form" onsubmit="handleAuthSubmit(event)">
        <div id="register-fields" style="display:none;">
          <div class="form-group">
            <label>Full Name</label>
            <input type="text" id="auth-name" class="form-control" placeholder="John Doe">
          </div>
          <div class="form-group">
            <label>Account Role</label>
            <select id="auth-role" class="form-control">
              <option value="CLIENT" ${window.PORTAL_ROLE === 'CLIENT' ? 'selected' : ''}>Client (Book Appointments)</option>
              <option value="PROVIDER" ${window.PORTAL_ROLE === 'PROVIDER' ? 'selected' : ''}>Provider (Offer Services & Slots)</option>
            </select>
          </div>
        </div>

        <div class="form-group">
          <label>Email Address</label>
          <input type="email" id="auth-email" class="form-control" required placeholder="user@example.com">
        </div>

        <div class="form-group">
          <label>Password</label>
          <input type="password" id="auth-password" class="form-control" required placeholder="••••••••">
        </div>

        <button type="submit" id="auth-submit-btn" class="btn btn-primary" style="width:100%; margin-top:1rem;">
          Login
        </button>
      </form>
    </div>
  `;
}

let isRegisterMode = false;
function switchAuthTab(mode) {
  isRegisterMode = mode === 'register';
  document.getElementById('tab-login').classList.toggle('active', !isRegisterMode);
  document.getElementById('tab-register').classList.toggle('active', isRegisterMode);
  document.getElementById('register-fields').style.display = isRegisterMode ? 'block' : 'none';
  document.getElementById('auth-submit-btn').innerText = isRegisterMode ? 'Create Account' : 'Login';
}

async function handleAuthSubmit(e) {
  e.preventDefault();
  const email = document.getElementById('auth-email').value;
  const password = document.getElementById('auth-password').value;

  try {
    if (isRegisterMode) {
      const name = document.getElementById('auth-name').value.trim();
      const role = document.getElementById('auth-role').value;
      if (!name) {
        showToast('Please enter your full name.', 'error');
        return;
      }
      await apiFetch('/api/auth/register', {
        method: 'POST',
        body: JSON.stringify({ name, email, password, role })
      });
      showToast('Account created successfully! Logging you in...');
    }

    const formData = new URLSearchParams();
    formData.append('username', email);
    formData.append('password', password);

    const data = await apiFetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: formData
    });

    currentToken = data.access_token;
    currentUser = data.user;
    localStorage.setItem('access_token', currentToken);
    updateNav();
    renderDashboard();
    startNotificationPolling();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

function renderDashboard() {
  const main = document.getElementById('app-content');
  const isProvider = currentUser.role === 'PROVIDER';

  main.innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1.5rem; flex-wrap:wrap; gap:1rem;">
      <div>
        <h1 style="font-size:1.8rem; font-weight:700;">${isProvider ? 'Provider Control Panel' : 'Available Services & Appointments'}</h1>
        <p style="color:var(--text-muted); font-size:0.9rem;">${isProvider ? 'Create and manage appointment slots' : 'Browse available slots or join waitlists'}</p>
      </div>

      ${isProvider ? `
        <button class="btn btn-primary" onclick="openCreateSlotModal()">
          ➕ Create New Slot
        </button>
      ` : ''}
    </div>

    <div class="tabs">
      ${isProvider ? `
        <button class="tab-btn ${currentTab === 'my-slots' ? 'active' : ''}" onclick="switchTab('my-slots')">My Slots</button>
        <button class="tab-btn ${currentTab === 'my-appointments' ? 'active' : ''}" onclick="switchTab('my-appointments')">Booked Appointments</button>
        <button class="tab-btn ${currentTab === 'my-waitlists' ? 'active' : ''}" onclick="switchTab('my-waitlists')">Waitlist Queues</button>
      ` : `
        <button class="tab-btn ${currentTab === 'open-slots' ? 'active' : ''}" onclick="switchTab('open-slots')">Browse Open Slots</button>
        <button class="tab-btn ${currentTab === 'my-appointments' ? 'active' : ''}" onclick="switchTab('my-appointments')">My Bookings</button>
        <button class="tab-btn ${currentTab === 'my-waitlists' ? 'active' : ''}" onclick="switchTab('my-waitlists')">My Waitlists</button>
      `}
    </div>

    <div id="tab-content" class="grid">
      Loading...
    </div>

    <!-- Create Slot Modal -->
    <div id="create-slot-modal" class="modal-backdrop">
      <div class="modal">
        <div class="modal-header">
          <h3>Create Appointment Slot</h3>
          <button class="modal-close" onclick="closeCreateSlotModal()">×</button>
        </div>
        <form onsubmit="handleCreateSlot(event)">
          <div class="form-group">
            <label>Service Name</label>
            <input type="text" id="slot-service" class="form-control" placeholder="e.g., General Health Consultation" required>
          </div>

          <div class="form-group">
            <label>Select Date</label>
            <input type="date" id="slot-date" class="form-control" required>
          </div>

          <div style="display:flex; gap:1rem;">
            <div class="form-group" style="flex:1;">
              <label>Start Time</label>
              <select id="slot-start-time" class="form-control" required>
                ${generateTimeOptions()}
              </select>
            </div>
            <div class="form-group" style="flex:1;">
              <label>Duration</label>
              <select id="slot-duration" class="form-control" required>
                <option value="15">15 Mins</option>
                <option value="30" selected>30 Mins</option>
                <option value="45">45 Mins</option>
                <option value="60">1 Hour</option>
                <option value="90">1.5 Hours</option>
                <option value="120">2 Hours</option>
              </select>
            </div>
          </div>

          <button type="submit" class="btn btn-primary" style="width:100%; margin-top:1rem;">Publish Slot</button>
        </form>
      </div>
    </div>
  `;

  // Default date to today
  const today = new Date().toISOString().split('T')[0];
  const dateInput = document.getElementById('slot-date');
  if (dateInput) dateInput.value = today;

  // Default tab based on role
  if (isProvider && currentTab === 'open-slots') currentTab = 'my-slots';
  if (!isProvider && currentTab === 'my-slots') currentTab = 'open-slots';

  loadTabData();
}

function generateTimeOptions() {
  const options = [];
  for (let h = 7; h <= 21; h++) {
    for (let m of [0, 30]) {
      const hourStr = String(h % 12 === 0 ? 12 : h % 12).padStart(2, '0');
      const minStr = String(m).padStart(2, '0');
      const ampm = h < 12 ? 'AM' : 'PM';
      const val = `${String(h).padStart(2, '0')}:${minStr}`;
      const label = `${hourStr}:${minStr} ${ampm}`;
      options.push(`<option value="${val}">${label}</option>`);
    }
  }
  return options.join('');
}

function switchTab(tab) {
  currentTab = tab;
  renderDashboard();
}

async function loadTabData(silent = false) {
  const container = document.getElementById('tab-content');
  if (!container) return;
  if (!silent) container.innerHTML = '<div>Loading...</div>';

  try {
    if (currentTab === 'open-slots') {
      const slots = await apiFetch('/api/slots/open');
      if (slots.length === 0) {
        container.innerHTML = '<div style="color:var(--text-muted); grid-column: 1/-1;">No open slots available right now.</div>';
        return;
      }
      container.innerHTML = slots.map(s => `
        <div class="card">
          <div class="card-header">
            <div>
              <div class="service-title">${s.service_name}</div>
              <div class="provider-sub">Provider: ${s.provider_name}</div>
            </div>
            <span class="status-badge ${s.status}">${s.status}</span>
          </div>
          <div class="card-body">
            <div class="time-row">📅 <span>${new Date(s.start_time).toLocaleDateString()}</span></div>
            <div class="time-row">⏰ <span>${new Date(s.start_time).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})} - ${new Date(s.end_time).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span></div>
          </div>
          <div class="card-footer">
            ${s.status === 'OPEN' ? `
              <button class="btn btn-primary btn-sm" style="flex:1" onclick="bookSlot(${s.id})">Book Appointment</button>
            ` : `
              <button class="btn btn-warning btn-sm" style="flex:1" onclick="joinWaitlist(${s.id})">Join Waitlist</button>
            `}
          </div>
        </div>
      `).join('');
    }
    else if (currentTab === 'my-slots') {
      const slots = await apiFetch('/api/slots/my');
      if (slots.length === 0) {
        container.innerHTML = '<div style="color:var(--text-muted); grid-column: 1/-1;">You have not created any slots yet.</div>';
        return;
      }
      container.innerHTML = slots.map(s => `
        <div class="card">
          <div class="card-header">
            <div>
              <div class="service-title">${s.service_name}</div>
            </div>
            <span class="status-badge ${s.status}">${s.status}</span>
          </div>
          <div class="card-body">
            <div class="time-row">📅 <span>${new Date(s.start_time).toLocaleDateString()}</span></div>
            <div class="time-row">⏰ <span>${new Date(s.start_time).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})} - ${new Date(s.end_time).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span></div>
          </div>
          <div class="card-footer">
            ${s.status === 'OPEN' ? `
              <button class="btn btn-danger btn-sm" style="flex:1" onclick="deleteSlot(${s.id})">Delete Slot</button>
            ` : ''}
          </div>
        </div>
      `).join('');
    }
    else if (currentTab === 'my-appointments') {
      const appts = await apiFetch('/api/appointments/my');
      if (appts.length === 0) {
        container.innerHTML = '<div style="color:var(--text-muted); grid-column: 1/-1;">No appointments found.</div>';
        return;
      }
      container.innerHTML = appts.map(a => `
        <div class="card">
          <div class="card-header">
            <div>
              <div class="service-title">${a.service_name}</div>
              <div class="provider-sub">${currentUser.role === 'PROVIDER' ? 'Client: ' + a.client_name : 'Provider: ' + a.provider_name}</div>
            </div>
            <span class="status-badge ${a.status}">${a.status}</span>
          </div>
          <div class="card-body">
            <div class="time-row">📅 <span>${new Date(a.start_time).toLocaleDateString()}</span></div>
            <div class="time-row">⏰ <span>${new Date(a.start_time).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})} - ${new Date(a.end_time).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span></div>
          </div>
          <div class="card-footer">
            ${a.status === 'BOOKED' ? `
              <button class="btn btn-danger btn-sm" onclick="cancelAppointment(${a.id})">Cancel</button>
              ${currentUser.role === 'PROVIDER' ? `
                <button class="btn btn-primary btn-sm" onclick="completeAppointment(${a.id})">Mark Complete</button>
              ` : ''}
            ` : ''}
          </div>
        </div>
      `).join('');
    }
    else if (currentTab === 'my-waitlists') {
      const waitlists = await apiFetch('/api/waitlist/my');
      if (waitlists.length === 0) {
        const msg = currentUser.role === 'PROVIDER' ? 'No clients currently on waitlist for your slots.' : 'You are not currently in any waitlist.';
        container.innerHTML = `<div style="color:var(--text-muted); grid-column: 1/-1;">${msg}</div>`;
        return;
      }
      container.innerHTML = waitlists.map(w => `
        <div class="card">
          <div class="card-header">
            <div>
              <div class="service-title">${w.service_name}</div>
              <div class="provider-sub">${currentUser.role === 'PROVIDER' ? 'Waiting Client: ' + w.client_name : 'Provider: ' + w.provider_name}</div>
            </div>
            <span class="status-badge BOOKED">QUEUE #${w.position}</span>
          </div>
          <div class="card-body">
            <div class="time-row">📅 <span>${new Date(w.start_time).toLocaleDateString()}</span></div>
            <div class="time-row">⏰ <span>${new Date(w.start_time).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span></div>
          </div>
          <div style="font-size:0.85rem; color:var(--text-muted); margin-bottom:0.75rem;">
            ${currentUser.role === 'PROVIDER' ? 'Client will be auto-booked if an active appointment is cancelled.' : 'If an appointment is cancelled, position #1 gets auto-booked!'}
          </div>
          <div class="card-footer">
            <button class="btn btn-danger btn-sm" style="flex:1;" onclick="leaveWaitlist(${w.id})">
              ${currentUser.role === 'PROVIDER' ? 'Remove from Waitlist' : 'Leave Waitlist'}
            </button>
          </div>
        </div>
      `).join('');
    }
  } catch (err) {
    if (!silent) container.innerHTML = `<div style="color:var(--danger)">Failed to load data: ${err.message}</div>`;
  }
}

async function bookSlot(slotId) {
  try {
    await apiFetch(`/api/appointments/book/${slotId}`, { method: 'POST' });
    showToast('Appointment booked successfully!');
    switchTab('my-appointments');
  } catch (err) {
    showToast(err.message, 'error');
    loadTabData(); // Refresh open slots to reflect latest DB status
  }
}

async function joinWaitlist(slotId) {
  try {
    const res = await apiFetch(`/api/waitlist/join/${slotId}`, { method: 'POST' });
    showToast(res.message);
    switchTab('my-waitlists');
  } catch (err) {
    showToast(err.message, 'error');
    loadTabData();
  }
}

async function cancelAppointment(apptId) {
  if (!confirm('Are you sure you want to cancel this appointment?')) return;
  try {
    const res = await apiFetch(`/api/appointments/${apptId}/cancel`, { method: 'POST' });
    showToast('Appointment cancelled successfully.');
    loadTabData();
    loadNotifications();
  } catch (err) {
    showToast(err.message, 'error');
    loadTabData();
  }
}

async function completeAppointment(apptId) {
  try {
    await apiFetch(`/api/appointments/${apptId}/complete`, { method: 'POST' });
    showToast('Appointment marked as completed!');
    loadTabData();
  } catch (err) {
    showToast(err.message, 'error');
    loadTabData(); // Auto-refresh UI to sync with client cancellation
  }
}

async function deleteSlot(slotId) {
  if (!confirm('Are you sure you want to delete this open slot?')) return;
  try {
    await apiFetch(`/api/slots/${slotId}`, { method: 'DELETE' });
    showToast('Slot deleted.');
    loadTabData();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function leaveWaitlist(waitlistId) {
  if (!confirm('Are you sure you want to leave/remove this waitlist position?')) return;
  try {
    await apiFetch(`/api/waitlist/${waitlistId}`, { method: 'DELETE' });
    showToast('Waitlist entry removed.');
    loadTabData();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// Create Slot Modal Handlers
function openCreateSlotModal() {
  document.getElementById('create-slot-modal').classList.add('active');
}

function closeCreateSlotModal() {
  document.getElementById('create-slot-modal').classList.remove('active');
}

async function handleCreateSlot(e) {
  e.preventDefault();
  const service_name = document.getElementById('slot-service').value;
  const dateVal = document.getElementById('slot-date').value;
  const startTimeVal = document.getElementById('slot-start-time').value;
  const durationVal = parseInt(document.getElementById('slot-duration').value, 10);

  if (!dateVal || !startTimeVal) {
    showToast('Please select a valid date and time.', 'error');
    return;
  }

  // Calculate start & end ISO timestamps
  const startDateTime = new Date(`${dateVal}T${startTimeVal}:00`);
  const endDateTime = new Date(startDateTime.getTime() + durationVal * 60 * 1000);

  const start_time = startDateTime.toISOString();
  const end_time = endDateTime.toISOString();

  try {
    await apiFetch('/api/slots', {
      method: 'POST',
      body: JSON.stringify({ service_name, start_time, end_time })
    });
    showToast('Slot published successfully!');
    closeCreateSlotModal();
    loadTabData();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// Notification Hub
async function loadNotifications() {
  if (!currentUser) return;
  try {
    const notifs = await apiFetch('/api/notifications/my');
    const badge = document.getElementById('notif-badge');
    const list = document.getElementById('notif-list');

    const unreadCount = notifs.filter(n => !n.is_read).length;
    if (unreadCount > 0) {
      badge.innerText = unreadCount;
      badge.style.display = 'flex';
    } else {
      badge.style.display = 'none';
    }

    if (notifs.length === 0) {
      list.innerHTML = '<div style="color:var(--text-muted); padding:0.5rem 0;">No notifications yet</div>';
    } else {
      list.innerHTML = notifs.map(n => `
        <div class="notif-item ${!n.is_read ? 'unread' : ''}" onclick="markNotifRead(${n.id})">
          <div>${n.message}</div>
          <div style="font-size:0.75rem; color:var(--text-muted); margin-top:0.2rem;">${new Date(n.created_at).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}</div>
        </div>
      `).join('');
    }
  } catch (err) {
    console.error('Failed to poll notifications', err);
  }
}

function toggleNotifications() {
  const dropdown = document.getElementById('notif-dropdown');
  dropdown.classList.toggle('active');
}

async function markNotifRead(id) {
  try {
    await apiFetch(`/api/notifications/${id}/read`, { method: 'POST' });
    loadNotifications();
  } catch (err) {}
}

function startNotificationPolling() {
  if (pollingIntervalId) clearInterval(pollingIntervalId);
  pollingIntervalId = setInterval(() => {
    loadNotifications();
    loadTabData(true); // Live auto-sync across doctor and client tabs
  }, 4000);
}

// App Initialization
document.addEventListener('DOMContentLoaded', initAuth);
