
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from app.database import init_db
from app.routers import (
    auth_router,
    slots_router,
    appointments_router,
    waitlist_router,
    notifications_router
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB tables on startup
    init_db()
    yield

app = FastAPI(
    title="Appointment Scheduler API",
    version="1.0.0",
    description="Modern appointment booking platform with double-booking race condition safeguards & waitlist promotion.",
    lifespan=lifespan
)

# Setup directories
base_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(base_dir, "static")
templates_dir = os.path.join(base_dir, "templates")

os.makedirs(static_dir, exist_ok=True)
os.makedirs(templates_dir, exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=templates_dir)

# Include Routers
app.include_router(auth_router.router)
app.include_router(slots_router.router)
app.include_router(appointments_router.router)
app.include_router(waitlist_router.router)
app.include_router(notifications_router.router)

@app.get("/", response_class=HTMLResponse)
def index_page(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/client", response_class=HTMLResponse)
def client_page(request: Request):
    return templates.TemplateResponse(request=request, name="client.html")

@app.get("/provider", response_class=HTMLResponse)
def provider_page(request: Request):
    return templates.TemplateResponse(request=request, name="provider.html")
