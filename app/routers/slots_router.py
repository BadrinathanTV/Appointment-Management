from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from datetime import datetime

from app.database import get_session
from app.models import Slot, SlotCreate, SlotRead, SlotStatus, User, UserRole
from app.auth import get_current_user

router = APIRouter(prefix="/api/slots", tags=["Slots"])

@router.post("", response_model=SlotRead, status_code=status.HTTP_201_CREATED)
def create_slot(
    slot_in: SlotCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    if current_user.role != UserRole.PROVIDER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only providers can create slots"
        )
    
    if slot_in.start_time >= slot_in.end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start time must be before end time"
        )

    slot = Slot(
        provider_id=current_user.id,
        service_name=slot_in.service_name,
        start_time=slot_in.start_time,
        end_time=slot_in.end_time,
        status=SlotStatus.OPEN
    )
    session.add(slot)
    session.commit()
    session.refresh(slot)
    
    return SlotRead(
        id=slot.id,
        provider_id=slot.provider_id,
        provider_name=current_user.name,
        service_name=slot.service_name,
        start_time=slot.start_time,
        end_time=slot.end_time,
        status=slot.status
    )

@router.get("/open", response_model=List[SlotRead])
def get_open_slots(
    service: Optional[str] = None,
    session: Session = Depends(get_session)
):
    query = select(Slot, User).join(User, Slot.provider_id == User.id).where(Slot.status == SlotStatus.OPEN)
    if service:
        query = query.where(Slot.service_name.ilike(f"%{service}%"))
    
    results = session.exec(query).all()
    slots_out = []
    for slot, provider in results:
        slots_out.append(
            SlotRead(
                id=slot.id,
                provider_id=slot.provider_id,
                provider_name=provider.name,
                service_name=slot.service_name,
                start_time=slot.start_time,
                end_time=slot.end_time,
                status=slot.status
            )
        )
    return slots_out

@router.get("/my", response_model=List[SlotRead])
def get_my_slots(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    if current_user.role != UserRole.PROVIDER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only providers have provider slots"
        )
    
    slots = session.exec(select(Slot).where(Slot.provider_id == current_user.id).order_by(Slot.start_time.desc())).all()
    return [
        SlotRead(
            id=s.id,
            provider_id=s.provider_id,
            provider_name=current_user.name,
            service_name=s.service_name,
            start_time=s.start_time,
            end_time=s.end_time,
            status=s.status
        )
        for s in slots
    ]

@router.delete("/{slot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_slot(
    slot_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    slot = session.get(Slot, slot_id)
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")
    
    if slot.provider_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this slot")
        
    if slot.status == SlotStatus.BOOKED:
        raise HTTPException(status_code=400, detail="Cannot delete a booked slot. Cancel the appointment first.")

    session.delete(slot)
    session.commit()
