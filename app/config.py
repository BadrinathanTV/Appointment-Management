import os

SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key-appointment-management-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./appointment_app.db")
