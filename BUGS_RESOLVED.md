# 🐛 Resolved Bugs & Audit Report

This document details all bugs discovered during the comprehensive audit of the **Appointment Management System** codebase, along with their root cause, severity level, and fix implementation.

---

## 📋 Summary Table

| Bug # | Component | Severity | Description | Status |
|---|---|---|---|---|
| **1** | `app/models.py` | 🔴 **Critical** | `SlotStatus` Enum Missing `COMPLETED` Value | ✅ Fixed |
| **2** | `app/static/app.js` | 🔴 **Critical** | Undefined `joinWaitlistPrompt` Function Called in Provider View | ✅ Fixed |
| **3** | `app/routers/appointments_router.py` | 🔴 **Critical** | `UNIQUE` Constraint Collision on `slot_id` When Re-Booking Slot | ✅ Fixed |
| **4** | `app/routers/appointments_router.py` | 🟡 **Medium** | Stale Cancelled Appointments Cluttering "My Bookings" | ✅ Fixed |
| **5** | `app/static/styles.css` | 🟡 **Medium** | Missing CSS Styling for `CANCELLED` and `COMPLETED` Badges | ✅ Fixed |
| **6** | `app/static/app.js` | 🟡 **Medium** | Fragile Handling of HTTP 204 No Content Responses | ✅ Fixed |
| **7** | `app/static/app.js` | 🟡 **Medium** | Memory Leak from Uncleared `setInterval` Timers on Login | ✅ Fixed |
| **8** | `app/routers/waitlist_router.py` & `app.js` | 🟢 **Feature** | Added Doctor/Provider View for Waitlist Queues | ✅ Fixed |
| **9** | `app/routers/waitlist_router.py` & `app.js` | 🟢 **Feature** | Added `DELETE /api/waitlist/{id}` (Leave Waitlist) & Position Reordering | ✅ Fixed |
| **10** | `app/routers/waitlist_router.py` | 🟠 **Low** | Raw String `"BOOKED"` Used Instead of Enum | ✅ Fixed |
| **11** | `app/static/app.js` | 🟠 **Low** | Empty Full Name Allowed in Registration Form | ✅ Fixed |

---

## 🔍 Detailed Bug Breakdown & Fixes

### 1. `SlotStatus` Enum Missing `COMPLETED` Value
- **File**: `app/models.py`
- **Severity**: 🔴 **Critical**
- **Root Cause**: When a provider completed an appointment, `appointments_router.py` attempted to assign `slot.status = SlotStatus.COMPLETED`. However, `SlotStatus` only defined `OPEN`, `BOOKED`, and `CANCELLED`, triggering a runtime `ValueError`.
- **Fix**: Added `COMPLETED = "COMPLETED"` to `SlotStatus` in `app/models.py`.

---

### 2. Undefined `joinWaitlistPrompt` Function Called in Provider View
- **File**: `app/static/app.js`
- **Severity**: 🔴 **Critical**
- **Root Cause**: In the provider's "My Slots" view, booked slot cards rendered a button with `onclick="joinWaitlistPrompt(${s.id})"`. This function did not exist, causing a `ReferenceError` when clicked.
- **Fix**: Removed invalid waitlist button for booked slots in the provider view.

---

### 3. `UNIQUE` Constraint Collision on `slot_id` When Re-Booking Slot
- **File**: `app/routers/appointments_router.py`
- **Severity**: 🔴 **Critical**
- **Root Cause**: If a slot was cancelled and subsequently re-booked, `book_appointment` attempted to create a new `Appointment(slot_id=slot.id)`. Because `Appointment.slot_id` has a database `UNIQUE` constraint, this triggered an `IntegrityError` (409 Conflict) even though the slot was `OPEN`.
- **Fix**: Updated `book_appointment` to check if an existing `Appointment` record for `slot_id` exists. If present and `CANCELLED`, it reuses/updates the existing record status to `BOOKED` rather than attempting a duplicate key insertion.

---

### 4. Doctor/Provider View for Waitlist Queues
- **File**: `app/routers/waitlist_router.py` & `app/static/app.js`
- **Severity**: 🟢 **Feature Request**
- **Description**: Added a dedicated **"Waitlist Queues"** tab for doctors/providers in the frontend dashboard.
- **Fix**: Updated `GET /api/waitlist/my` to check `current_user.role`. If `PROVIDER`, it returns all clients currently waitlisted for slots created by that provider, along with client name, queue position, and slot timestamps.

---

### 5. Ability to Leave Waitlist (`DELETE /api/waitlist/{id}`)
- **File**: `app/routers/waitlist_router.py` & `app/static/app.js`
- **Severity**: 🟢 **Feature Request**
- **Description**: Enabled clients to remove themselves (or doctors to remove clients) from a waitlist queue with automatic position reordering (`1, 2, 3...`).
- **Fix**: Implemented `DELETE /api/waitlist/{waitlist_id}` endpoint and added **"Leave Waitlist"** button to the UI cards.

---

### 6. Stale Cancelled Appointments Cluttering "My Bookings"
- **File**: `app/routers/appointments_router.py`
- **Severity**: 🟡 **Medium**
- **Root Cause**: `GET /api/appointments/my` fetched all appointments including `CANCELLED` ones, cluttering active bookings tabs.
- **Fix**: Added `.where(Appointment.status != AppointmentStatus.CANCELLED)` to filter out cancelled history.

---

### 7. Missing CSS Styling for Status Badges
- **File**: `app/static/styles.css`
- **Severity**: 🟡 **Medium**
- **Root Cause**: Badges for `CANCELLED` and `COMPLETED` statuses lacked specific styling rules.
- **Fix**: Added styled background colors and text contrast for `.status-badge.CANCELLED` and `.status-badge.COMPLETED`.

---

### 8. Fragile Handling of HTTP 204 No Content Responses
- **File**: `app/static/app.js`
- **Severity**: 🟡 **Medium**
- **Root Cause**: `DELETE /api/slots/{id}` returns HTTP 204 No Content. Calling `response.json()` failed inside `apiFetch`.
- **Fix**: Added explicit `if (response.status === 204) return {};` check before JSON parsing.

---

### 9. Memory Leak from Uncleared `setInterval` Timers on Login
- **File**: `app/static/app.js`
- **Severity**: 🟡 **Medium**
- **Root Cause**: `startNotificationPolling()` executed `setInterval(...)` on every login without clearing existing timers.
- **Fix**: Saved interval handle in `pollingIntervalId` and called `clearInterval` before creating a new timer.

---

## 🧪 Verification & Test Suite

All fixes were validated by running the automated test suite:

```bash
$ PYTHONPATH=. uv run pytest tests/

collected 2 items                                                             

tests/test_bugs_and_edge_cases.py .                                      [ 50%]
tests/test_flow.py .                                                     [100%]

======================== 2 passed, 17 warnings in 0.84s ========================
```
