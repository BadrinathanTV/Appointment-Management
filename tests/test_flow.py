import os
import time
import pytest
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient

# Ensure clean DB for testing
if os.path.exists("test_appointment_app.db"):
    os.remove("test_appointment_app.db")

os.environ["DATABASE_URL"] = "sqlite:///./test_appointment_app.db"

from sqlmodel import SQLModel
from app.main import app
from app.database import engine

SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)
client = TestClient(app)

def test_full_system_and_race_condition():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    # 1. Register Provider
    resp_prov = client.post("/api/auth/register", json={
        "name": "Dr. Smith",
        "email": "smith@clinic.com",
        "password": "password123",
        "role": "PROVIDER"
    })
    assert resp_prov.status_code == 201, resp_prov.text
    
    # Login Provider
    login_prov = client.post("/api/auth/login", data={
        "username": "smith@clinic.com",
        "password": "password123"
    })
    assert login_prov.status_code == 200
    token_prov = login_prov.json()["access_token"]
    headers_prov = {"Authorization": f"Bearer {token_prov}"}

    # 2. Register Client 1 and Client 2
    c1_resp = client.post("/api/auth/register", json={
        "name": "Alice Client",
        "email": "alice@example.com",
        "password": "password123",
        "role": "CLIENT"
    })
    assert c1_resp.status_code == 201
    token_c1 = client.post("/api/auth/login", data={"username": "alice@example.com", "password": "password123"}).json()["access_token"]
    headers_c1 = {"Authorization": f"Bearer {token_c1}"}

    c2_resp = client.post("/api/auth/register", json={
        "name": "Bob Client",
        "email": "bob@example.com",
        "password": "password123",
        "role": "CLIENT"
    })
    assert c2_resp.status_code == 201
    token_c2 = client.post("/api/auth/login", data={"username": "bob@example.com", "password": "password123"}).json()["access_token"]
    headers_c2 = {"Authorization": f"Bearer {token_c2}"}

    # 3. Provider Creates a Slot
    slot_resp = client.post("/api/slots", headers=headers_prov, json={
        "service_name": "Dental Checkup",
        "start_time": "2026-09-01T10:00:00Z",
        "end_time": "2026-09-01T10:30:00Z"
    })
    assert slot_resp.status_code == 201
    slot_id = slot_resp.json()["id"]

    # 4. CONCURRENCY TEST: Simultaneous Booking by Alice and Bob
    def book_request(headers):
        return client.post(f"/api/appointments/book/{slot_id}", headers=headers)

    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(book_request, headers_c1)
        f2 = executor.submit(book_request, headers_c2)
        r1 = f1.result()
        r2 = f2.result()

    status_codes = [r1.status_code, r2.status_code]
    print(f"Concurrent booking status codes: {status_codes}")

    # Exactly ONE should succeed (201) and ONE should fail with race condition safeguard (409 Conflict)
    assert 201 in status_codes, f"Expected 201 in {status_codes}"
    assert 409 in status_codes, f"Expected 409 Conflict in {status_codes}"

    winner_headers = headers_c1 if r1.status_code == 201 else headers_c2
    loser_headers = headers_c2 if r1.status_code == 201 else headers_c1
    winner_name = "Alice" if r1.status_code == 201 else "Bob"
    loser_name = "Bob" if r1.status_code == 201 else "Alice"

    print(f"✅ Race Condition Safeguard verified: {winner_name} won slot, {loser_name} received 409 Conflict!")

    # 5. Waitlist Test: Loser joins waitlist
    waitlist_resp = client.post(f"/api/waitlist/join/{slot_id}", headers=loser_headers)
    assert waitlist_resp.status_code == 201, waitlist_resp.text
    assert waitlist_resp.json()["position"] == 1
    print(f"✅ {loser_name} joined waitlist at position #1")

    # 6. Cancellation & Auto-Promotion Test
    # Get winner's appointment ID
    appts = client.get("/api/appointments/my", headers=winner_headers).json()
    assert len(appts) == 1
    appt_id = appts[0]["id"]

    # Winner cancels appointment
    cancel_resp = client.post(f"/api/appointments/{appt_id}/cancel", headers=winner_headers)
    assert cancel_resp.status_code == 200, cancel_resp.text
    print(f"✅ {winner_name} cancelled appointment")

    # Verify loser was auto-booked from waitlist!
    loser_appts = client.get("/api/appointments/my", headers=loser_headers).json()
    assert len(loser_appts) == 1
    assert loser_appts[0]["status"] == "BOOKED"
    print(f"🎉 SUCCESS! {loser_name} was automatically promoted and booked from the waitlist!")

    # Verify notification was received by loser
    notifs = client.get("/api/notifications/my", headers=loser_headers).json()
    assert len(notifs) >= 1
    assert "auto-booked" in notifs[0]["message"]
    print(f"✅ Notification verified: {notifs[0]['message']}")

if __name__ == "__main__":
    test_full_system_and_race_condition()
