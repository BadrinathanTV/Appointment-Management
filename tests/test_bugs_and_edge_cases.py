import os
import pytest
from fastapi.testclient import TestClient

# Ensure clean DB for testing
if os.path.exists("test_bugs_app.db"):
    os.remove("test_bugs_app.db")

os.environ["DATABASE_URL"] = "sqlite:///./test_bugs_app.db"

from sqlmodel import SQLModel
from app.main import app
from app.database import engine

SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)
client = TestClient(app)

def test_slot_completion_and_cancelled_filtering():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    # 1. Register Provider & Client
    p_reg = client.post("/api/auth/register", json={
        "name": "Dr. House", "email": "house@clinic.com", "password": "password123", "role": "PROVIDER"
    })
    assert p_reg.status_code == 201
    p_token = client.post("/api/auth/login", data={"username": "house@clinic.com", "password": "password123"}).json()["access_token"]
    p_headers = {"Authorization": f"Bearer {p_token}"}

    c_reg = client.post("/api/auth/register", json={
        "name": "Patient Zero", "email": "patient@example.com", "password": "password123", "role": "CLIENT"
    })
    assert c_reg.status_code == 201
    c_token = client.post("/api/auth/login", data={"username": "patient@example.com", "password": "password123"}).json()["access_token"]
    c_headers = {"Authorization": f"Bearer {c_token}"}

    # 2. Provider Creates Slot 1 & Slot 2
    s1 = client.post("/api/slots", headers=p_headers, json={
        "service_name": "MRI Scan", "start_time": "2026-09-10T10:00:00Z", "end_time": "2026-09-10T10:30:00Z"
    }).json()
    
    s2 = client.post("/api/slots", headers=p_headers, json={
        "service_name": "Blood Test", "start_time": "2026-09-10T11:00:00Z", "end_time": "2026-09-10T11:30:00Z"
    }).json()

    # 3. Client Books Slot 1
    appt1 = client.post(f"/api/appointments/book/{s1['id']}", headers=c_headers).json()

    # 4. Test Completion bug fix: Provider completes Slot 1 -> SlotStatus.COMPLETED
    comp_resp = client.post(f"/api/appointments/{appt1['id']}/complete", headers=p_headers)
    assert comp_resp.status_code == 200
    assert comp_resp.json()["status"] == "COMPLETED"

    # Verify slot status is now COMPLETED
    my_slots = client.get("/api/slots/my", headers=p_headers).json()
    completed_slot = next(s for s in my_slots if s["id"] == s1["id"])
    assert completed_slot["status"] == "COMPLETED"

    # 5. Client Books Slot 2 then Cancels
    appt2 = client.post(f"/api/appointments/book/{s2['id']}", headers=c_headers).json()
    cancel_resp = client.post(f"/api/appointments/{appt2['id']}/cancel", headers=c_headers)
    assert cancel_resp.status_code == 200

    # Test Cancelled Filtering bug fix: my appointments should NOT include appt2 (cancelled)
    c_appts = client.get("/api/appointments/my", headers=c_headers).json()
    appt_ids = [a["id"] for a in c_appts]
    assert appt2["id"] not in appt_ids

    # 6. Provider attempts to complete cancelled appt2 -> 400 Bad Request
    fail_comp = client.post(f"/api/appointments/{appt2['id']}/complete", headers=p_headers)
    assert fail_comp.status_code == 400

    # 7. Test Slot Deletion 204 No Content
    del_resp = client.delete(f"/api/slots/{s2['id']}", headers=p_headers)
    assert del_resp.status_code == 204

    # 8. Test Provider Waitlist retrieval
    s3 = client.post("/api/slots", headers=p_headers, json={
        "service_name": "X-Ray", "start_time": "2026-09-12T10:00:00Z", "end_time": "2026-09-12T10:30:00Z"
    }).json()
    book_resp = client.post(f"/api/appointments/book/{s3['id']}", headers=c_headers)
    assert book_resp.status_code == 201, book_resp.text
    
    # Register 2nd client & join waitlist for s3
    c2_token = client.post("/api/auth/register", json={
        "name": "Patient Two", "email": "p2@example.com", "password": "password123", "role": "CLIENT"
    }).json()
    t2 = client.post("/api/auth/login", data={"username": "p2@example.com", "password": "password123"}).json()["access_token"]
    h2 = {"Authorization": f"Bearer {t2}"}
    wl_join_resp = client.post(f"/api/waitlist/join/{s3['id']}", headers=h2)
    assert wl_join_resp.status_code == 201, wl_join_resp.text

    # Provider queries waitlists
    prov_wl = client.get("/api/waitlist/my", headers=p_headers).json()
    assert len(prov_wl) == 1
    assert prov_wl[0]["client_name"] == "Patient Two"
    assert prov_wl[0]["service_name"] == "X-Ray"
    assert prov_wl[0]["position"] == 1

    # 9. Test Leaving Waitlist (DELETE /api/waitlist/{id})
    wl_id = prov_wl[0]["id"]
    leave_resp = client.delete(f"/api/waitlist/{wl_id}", headers=h2)
    assert leave_resp.status_code == 204
    assert len(client.get("/api/waitlist/my", headers=h2).json()) == 0
