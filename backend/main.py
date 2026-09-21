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
    else:
        # Auto-start historical replay loop in stable NORMAL condition so SCADA is live and non-fluctuating
        from app.historical_replay_service import historical_replay_engine
        historical_replay_engine.start(condition="NORMAL", speed_hz=0.5)
    yield
    # Shutdown: Stop workers cleanly
    if settings.SERIAL_WORKER_ENABLED:
        serial_worker.stop()
    else:
        from app.historical_replay_service import historical_replay_engine
        historical_replay_engine.stop()

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

frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"

# 1. Register API and WebSocket routes FIRST (prevents static mount interception)
app.include_router(router)
app.include_router(ws_router)

# 2. Mount static assets
app.mount("/static", StaticFiles(directory=static_dir), name="static")
if (frontend_dist / "assets").exists():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="frontend_assets")

# 3. Dedicated route for Classic SCADA HMI
@app.get("/classic")
def serve_scada_classic():
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"status": "Classic SCADA not found"}

# 4. Modern React SPA root & path catch-all (with fallback to classic)
@app.get("/")
@app.get("/{full_path:path}")
def serve_spa(full_path: str = ""):
    if full_path.startswith("api/") or full_path.startswith("ws/") or full_path in ("docs", "redoc", "openapi.json"):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Endpoint not found")
    
    react_index = frontend_dist / "index.html"
    if react_index.exists():
        return FileResponse(react_index)

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
