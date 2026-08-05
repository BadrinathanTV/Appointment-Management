from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from datetime import datetime

from app.database import get_session
from app.models import (
    Waitlist, Slot, SlotStatus, Appointment, User, UserRole
)
from app.auth import get_current_user

router = APIRouter(prefix="/api/waitlist", tags=["Waitlist"])

@router.post("/join/{slot_id}", status_code=status.HTTP_201_CREATED)
def join_waitlist(
    slot_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    if current_user.role != UserRole.CLIENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only clients can join waitlists"
        )

    slot = session.get(Slot, slot_id)
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")

    if slot.status == SlotStatus.OPEN:
        raise HTTPException(
            status_code=400,
            detail="Slot is currently open! You can book it directly instead of joining the waitlist."
        )

    # Check if user is already holding active appointment for this slot
    existing_appt = session.exec(
        select(Appointment).where(
            Appointment.slot_id == slot.id,
            Appointment.client_id == current_user.id,
            Appointment.status == "BOOKED"
        )
    ).first()
    if existing_appt:
        raise HTTPException(status_code=400, detail="You already have an active booking for this slot")

    # Check if user is already in waitlist for this slot
    existing_waitlist = session.exec(
        select(Waitlist).where(
            Waitlist.slot_id == slot.id,
            Waitlist.client_id == current_user.id
        )
    ).first()
    if existing_waitlist:
        raise HTTPException(status_code=400, detail=f"You are already on position #{existing_waitlist.position} on the waitlist")

    # Calculate position
    count = session.exec(select(Waitlist).where(Waitlist.slot_id == slot.id)).all()
    position = len(count) + 1

    entry = Waitlist(
        slot_id=slot.id,
        client_id=current_user.id,
        position=position
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)

    return {
        "message": f"Successfully joined waitlist for '{slot.service_name}'.",
        "waitlist_id": entry.id,
        "position": entry.position
    }

@router.get("/my")
def get_my_waitlists(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    query = select(Waitlist, Slot, User).join(
        Slot, Waitlist.slot_id == Slot.id
    ).join(
        User, Slot.provider_id == User.id
    ).where(Waitlist.client_id == current_user.id)

    results = session.exec(query).all()
    out = []
    for w, slot, provider in results:
        out.append({
            "id": w.id,
            "slot_id": w.slot_id,
            "service_name": slot.service_name,
            "provider_name": provider.name,
            "start_time": slot.start_time,
            "end_time": slot.end_time,
            "position": w.position,
            "created_at": w.created_at
        })
    return out
