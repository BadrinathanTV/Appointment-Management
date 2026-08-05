from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from sqlalchemy.exc import IntegrityError
from datetime import datetime

from app.database import get_session
from app.models import (
    Appointment, AppointmentRead, AppointmentStatus,
    Slot, SlotStatus, Waitlist, Notification, User, UserRole
)
from app.auth import get_current_user

router = APIRouter(prefix="/api/appointments", tags=["Appointments"])

@router.post("/book/{slot_id}", response_model=AppointmentRead, status_code=status.HTTP_201_CREATED)
def book_appointment(
    slot_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    if current_user.role != UserRole.CLIENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Providers cannot book client appointments"
        )
    
    slot = session.get(Slot, slot_id)
    if not slot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slot not found")
        
    if slot.status != SlotStatus.OPEN:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Slot is no longer open for booking"
        )

    # Race-condition safe atomic booking
    try:
        existing_appt = session.exec(
            select(Appointment).where(Appointment.slot_id == slot.id)
        ).first()

        if existing_appt:
            if existing_appt.status == AppointmentStatus.BOOKED:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Race Condition Handled: Slot was already booked by another request."
                )
            # Reuse cancelled appointment record
            existing_appt.client_id = current_user.id
            existing_appt.status = AppointmentStatus.BOOKED
            existing_appt.created_at = datetime.utcnow()
            slot.status = SlotStatus.BOOKED
            session.add(existing_appt)
            session.add(slot)
            session.commit()
            session.refresh(existing_appt)
            appointment = existing_appt
        else:
            appointment = Appointment(
                slot_id=slot.id,
                client_id=current_user.id,
                status=AppointmentStatus.BOOKED
            )
            slot.status = SlotStatus.BOOKED
            session.add(appointment)
            session.add(slot)
            session.commit()
            session.refresh(appointment)
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Race Condition Handled: Slot was already booked by another request."
        )

    provider = session.get(User, slot.provider_id)
    return AppointmentRead(
        id=appointment.id,
        slot_id=appointment.slot_id,
        client_id=appointment.client_id,
        client_name=current_user.name,
        service_name=slot.service_name,
        provider_name=provider.name if provider else "Unknown",
        start_time=slot.start_time,
        end_time=slot.end_time,
        status=appointment.status,
        created_at=appointment.created_at
    )

@router.get("/my", response_model=List[AppointmentRead])
def get_my_appointments(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    if current_user.role == UserRole.CLIENT:
        query = select(Appointment, Slot, User).join(
            Slot, Appointment.slot_id == Slot.id
        ).join(
            User, Slot.provider_id == User.id
        ).where(
            Appointment.client_id == current_user.id,
            Appointment.status != AppointmentStatus.CANCELLED
        )
        
        results = session.exec(query).all()
        res = []
        for appt, slot, provider in results:
            res.append(
                AppointmentRead(
                    id=appt.id,
                    slot_id=appt.slot_id,
                    client_id=appt.client_id,
                    client_name=current_user.name,
                    service_name=slot.service_name,
                    provider_name=provider.name,
                    start_time=slot.start_time,
                    end_time=slot.end_time,
                    status=appt.status,
                    created_at=appt.created_at
                )
            )
        return res

    else:
        # Provider view: appointments for slots created by this provider
        query = select(Appointment, Slot, User).join(
            Slot, Appointment.slot_id == Slot.id
        ).join(
            User, Appointment.client_id == User.id
        ).where(
            Slot.provider_id == current_user.id,
            Appointment.status != AppointmentStatus.CANCELLED
        )
        
        results = session.exec(query).all()
        res = []
        for appt, slot, client in results:
            res.append(
                AppointmentRead(
                    id=appt.id,
                    slot_id=appt.slot_id,
                    client_id=appt.client_id,
                    client_name=client.name,
                    service_name=slot.service_name,
                    provider_name=current_user.name,
                    start_time=slot.start_time,
                    end_time=slot.end_time,
                    status=appt.status,
                    created_at=appt.created_at
                )
            )
        return res

@router.post("/{appointment_id}/cancel", response_model=AppointmentRead)
def cancel_appointment(
    appointment_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    appt = session.get(Appointment, appointment_id)
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
        
    slot = session.get(Slot, appt.slot_id)
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")

    # Authorization check
    if current_user.role == UserRole.CLIENT and appt.client_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to cancel this appointment")
    if current_user.role == UserRole.PROVIDER and slot.provider_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to cancel this appointment")

    if appt.status != AppointmentStatus.BOOKED:
        raise HTTPException(status_code=400, detail="Only active booked appointments can be cancelled")

    # Mark existing appointment cancelled
    appt.status = AppointmentStatus.CANCELLED
    session.add(appt)
    
    # Notify current client about cancellation
    notification_cancel = Notification(
        user_id=appt.client_id,
        message=f"Appointment for '{slot.service_name}' on {slot.start_time.strftime('%b %d, %H:%M')} has been cancelled."
    )
    session.add(notification_cancel)

    # Check for waitlist promotion
    first_waitlist = session.exec(
        select(Waitlist).where(Waitlist.slot_id == slot.id).order_by(Waitlist.position)
    ).first()

    if first_waitlist:
        promoted_client_id = first_waitlist.client_id
        
        # Remove promoted waitlist entry
        session.delete(first_waitlist)
        
        # Promote waitlisted client to this appointment slot
        appt.client_id = promoted_client_id
        appt.status = AppointmentStatus.BOOKED
        appt.created_at = datetime.utcnow()
        slot.status = SlotStatus.BOOKED

        session.add(appt)
        session.add(slot)
        
        # Send notification to promoted user
        notification_promoted = Notification(
            user_id=promoted_client_id,
            message=f"🎉 Good news! A slot opened up and you were auto-booked for '{slot.service_name}' on {slot.start_time.strftime('%b %d, %H:%M')}!"
        )
        session.add(notification_promoted)
        
        # Reorder remaining waitlist entries
        remaining_waitlist = session.exec(
            select(Waitlist).where(Waitlist.slot_id == slot.id).order_by(Waitlist.position)
        ).all()
        for idx, item in enumerate(remaining_waitlist, start=1):
            item.position = idx
            session.add(item)

        session.commit()
        session.refresh(appt)
        
        promoted_client = session.get(User, promoted_client_id)
        provider = session.get(User, slot.provider_id)
        return AppointmentRead(
            id=appt.id,
            slot_id=appt.slot_id,
            client_id=promoted_client_id,
            client_name=promoted_client.name,
            service_name=slot.service_name,
            provider_name=provider.name if provider else "Unknown",
            start_time=slot.start_time,
            end_time=slot.end_time,
            status=appt.status,
            created_at=appt.created_at
        )

    else:
        # No waitlist, just mark slot open
        slot.status = SlotStatus.OPEN
        session.add(slot)
        session.commit()
        session.refresh(appt)

        client = session.get(User, appt.client_id)
        provider = session.get(User, slot.provider_id)
        return AppointmentRead(
            id=appt.id,
            slot_id=appt.slot_id,
            client_id=appt.client_id,
            client_name=client.name if client else "Unknown",
            service_name=slot.service_name,
            provider_name=provider.name if provider else "Unknown",
            start_time=slot.start_time,
            end_time=slot.end_time,
            status=appt.status,
            created_at=appt.created_at
        )

@router.post("/{appointment_id}/complete", response_model=AppointmentRead)
def complete_appointment(
    appointment_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    if current_user.role != UserRole.PROVIDER:
        raise HTTPException(status_code=403, detail="Only providers can mark appointments completed")
        
    appt = session.get(Appointment, appointment_id)
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
        
    slot = session.get(Slot, appt.slot_id)
    if not slot or slot.provider_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    if appt.status != AppointmentStatus.BOOKED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot mark completed: This appointment was cancelled or modified by the client."
        )

    appt.status = AppointmentStatus.COMPLETED
    slot.status = SlotStatus.COMPLETED
    session.add(appt)
    session.add(slot)
    session.commit()
    session.refresh(appt)

    client = session.get(User, appt.client_id)
    return AppointmentRead(
        id=appt.id,
        slot_id=appt.slot_id,
        client_id=appt.client_id,
        client_name=client.name if client else "Unknown",
        service_name=slot.service_name,
        provider_name=current_user.name,
        start_time=slot.start_time,
        end_time=slot.end_time,
        status=appt.status,
        created_at=appt.created_at
    )
