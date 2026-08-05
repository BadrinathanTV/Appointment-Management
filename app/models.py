from datetime import datetime
from enum import Enum
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship

class UserRole(str, Enum):
    PROVIDER = "PROVIDER"
    CLIENT = "CLIENT"

class SlotStatus(str, Enum):
    OPEN = "OPEN"
    BOOKED = "BOOKED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

class AppointmentStatus(str, Enum):
    BOOKED = "BOOKED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

class User(SQLModel, table=True):
    __tablename__ = "users"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str = Field(unique=True, index=True)
    password_hash: str
    role: UserRole = Field(default=UserRole.CLIENT)

class Slot(SQLModel, table=True):
    __tablename__ = "slots"

    id: Optional[int] = Field(default=None, primary_key=True)
    provider_id: int = Field(foreign_key="users.id")
    service_name: str
    start_time: datetime
    end_time: datetime
    status: SlotStatus = Field(default=SlotStatus.OPEN)

class Appointment(SQLModel, table=True):
    __tablename__ = "appointments"

    id: Optional[int] = Field(default=None, primary_key=True)
    # UNIQUE constraint guarantees at most one active/booked appointment per slot
    slot_id: int = Field(foreign_key="slots.id", unique=True, index=True)
    client_id: int = Field(foreign_key="users.id")
    status: AppointmentStatus = Field(default=AppointmentStatus.BOOKED)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Waitlist(SQLModel, table=True):
    __tablename__ = "waitlist"

    id: Optional[int] = Field(default=None, primary_key=True)
    slot_id: int = Field(foreign_key="slots.id", index=True)
    client_id: int = Field(foreign_key="users.id")
    position: int = Field(default=1)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Notification(SQLModel, table=True):
    __tablename__ = "notifications"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    message: str
    is_read: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

# Pydantic Schemas for Requests & Responses

class UserCreate(SQLModel):
    name: str
    email: str
    password: str
    role: UserRole = UserRole.CLIENT

class UserRead(SQLModel):
    id: int
    name: str
    email: str
    role: UserRole

class TokenResponse(SQLModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead

class SlotCreate(SQLModel):
    service_name: str
    start_time: datetime
    end_time: datetime

class SlotRead(SQLModel):
    id: int
    provider_id: int
    provider_name: Optional[str] = None
    service_name: str
    start_time: datetime
    end_time: datetime
    status: SlotStatus

class AppointmentRead(SQLModel):
    id: int
    slot_id: int
    client_id: int
    client_name: Optional[str] = None
    service_name: Optional[str] = None
    provider_name: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: AppointmentStatus
    created_at: datetime
