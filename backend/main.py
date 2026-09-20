import asyncio
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.database import init_db, migrate_db
from app.api import router, ws_router
from app.serial_worker import serial_worker
from app.websocket_manager import ws_manager

static_dir = Path(__file__).resolve().parent / "app" / "static"
static_dir.mkdir(parents=True, exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize SQLite database schema, run migrations, set event loop
    init_db()       # Creates all new tables (alert_events, etc.)
    migrate_db()    # Adds new columns to existing tables (safe, idempotent)
    ws_manager.set_loop(asyncio.get_running_loop())
    if settings.SERIAL_WORKER_ENABLED:
        serial_worker.start()
    yield
    # Shutdown: Stop workers cleanly
    if settings.SERIAL_WORKER_ENABLED:
        serial_worker.stop()

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Phase 3 DSP Feature Extraction, Joint Health Scoring & Anomaly Detection",
    version="3.0.0",
    lifespan=lifespan
)

# Standard industrial CORS policy
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. Register API and WebSocket routes FIRST (prevents static mount interception)
app.include_router(router)
app.include_router(ws_router)

# 2. Mount static assets under /static
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# 3. Dedicated root route serving the SCADA HMI
@app.get("/")
def serve_scada_root():
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {
        "system": settings.PROJECT_NAME,
        "phase": "PHASE 3: DSP Feature Extraction, Joint Health Scoring & Anomaly Detection",
        "status": "OPERATIONAL",
        "docs_url": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8001, reload=True)
