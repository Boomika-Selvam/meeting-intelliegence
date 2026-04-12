"""
backend/api.py
FastAPI backend — all REST endpoints for Meeting Intelligence App.
Handles: auth, file upload, processing, meeting CRUD, exports.
"""

import os
import json
import logging
import tempfile
import shutil
from datetime import datetime
from typing import Optional

from fastapi import (
    FastAPI, File, UploadFile, Form, HTTPException,
    Depends, status, Query, Request
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel

# ── Internal modules ─────────────────────────────────────────────────────────
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.db import (
    init_db, create_user, get_user_by_username,
    save_meeting, get_meetings, get_meeting_by_id,
    get_latest_meeting, delete_meeting
)
from utils.auth import (
    hash_password, verify_password,
    create_access_token, decode_access_token
)
from models.transcriber import transcribe
from models.nlp_processor import process_transcript

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s"
)
logger = logging.getLogger("meeting-intelligence")

# ── App init ──────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Meeting Intelligence API",
    description="AI-powered meeting transcription, summarization, and action item extraction",
    version="1.0.0"
)

# CORS — allow frontend (served on same origin or localhost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OAuth2 scheme for JWT
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Allowed upload file extensions
ALLOWED_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".wav", ".mp3", ".m4a", ".ogg", ".flac"}
MAX_FILE_SIZE_MB = 500  # 500 MB limit


# ── DB Init on startup ────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    init_db()
    logger.info("Meeting Intelligence API started.")


# ── Auth helpers ──────────────────────────────────────────────────────────────

async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Dependency: validate JWT and return current user dict."""
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = get_user_by_username(payload.get("sub", ""))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    username: str


# ═══════════════════════════════════════════════════════════════════
# AUTH ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

@app.post("/api/auth/signup", response_model=TokenResponse, tags=["Auth"])
async def signup(body: SignupRequest):
    """Register a new user and return an access token."""
    if len(body.username) < 3:
        raise HTTPException(400, "Username must be at least 3 characters")
    if len(body.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")

    hashed = hash_password(body.password)
    user = create_user(body.username, hashed)
    if not user:
        raise HTTPException(400, "Username already taken")

    token = create_access_token({"sub": body.username})
    return TokenResponse(access_token=token, token_type="bearer", username=body.username)


@app.post("/api/auth/login", response_model=TokenResponse, tags=["Auth"])
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Authenticate user and return JWT access token."""
    user = get_user_by_username(form_data.username)
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token({"sub": user["username"]})
    return TokenResponse(access_token=token, token_type="bearer", username=user["username"])


@app.get("/api/auth/me", tags=["Auth"])
async def me(current_user: dict = Depends(get_current_user)):
    """Return current authenticated user info."""
    return {"id": current_user["id"], "username": current_user["username"]}


# ═══════════════════════════════════════════════════════════════════
# UPLOAD & PROCESS ENDPOINT
# ═══════════════════════════════════════════════════════════════════

@app.post("/api/meetings/upload", tags=["Meetings"])
async def upload_and_process(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Upload an audio/video file and run the full AI pipeline:
    1. Transcription (Whisper)
    2. Summarization (T5/BART)
    3. Task Extraction
    4. Deadline Detection
    5. Store in SQLite
    """
    # Validate extension
    _, ext = os.path.splitext(file.filename or "")
    if ext.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type: {ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

    # Save to temp file
    tmp_dir = tempfile.mkdtemp()
    tmp_path = os.path.join(tmp_dir, file.filename or f"upload{ext}")

    try:
        logger.info(f"[API] Receiving file: {file.filename}")
        with open(tmp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        file_size_mb = os.path.getsize(tmp_path) / (1024 * 1024)
        if file_size_mb > MAX_FILE_SIZE_MB:
            raise HTTPException(413, f"File too large ({file_size_mb:.1f} MB). Max: {MAX_FILE_SIZE_MB} MB")

        # ── Step 1: Transcribe ───────────────────────────────────────────────
        logger.info("[API] Starting transcription...")
        transcript = transcribe(tmp_path, model_size="base")

        if not transcript:
            raise HTTPException(422, "Transcription produced no output. Check audio quality.")

        # ── Step 2-4: NLP Processing ─────────────────────────────────────────
        logger.info("[API] Running NLP pipeline...")
        nlp_results = process_transcript(transcript)

        # ── Step 5: Save to DB ───────────────────────────────────────────────
        meeting_id = save_meeting(
            user_id=current_user["id"],
            filename=file.filename or "unknown",
            transcript=transcript,
            summary=nlp_results["summary"],
            tasks=nlp_results["tasks"],
            deadlines=nlp_results["deadlines"],
        )
        logger.info(f"[API] Meeting saved with ID: {meeting_id}")

        # Return the full result
        return {
            "id": meeting_id,
            "filename": file.filename,
            "transcript": transcript,
            "summary": nlp_results["summary"],
            "tasks": json.loads(nlp_results["tasks"]),
            "deadlines": json.loads(nlp_results["deadlines"]),
            "created_at": datetime.utcnow().isoformat(),
            "status": "success"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] Processing error: {e}", exc_info=True)
        raise HTTPException(500, f"Processing failed: {str(e)}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════
# MEETING CRUD ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

@app.get("/api/meetings", tags=["Meetings"])
async def list_meetings(
    search: str = Query("", description="Search in filename, summary, tasks"),
    date: str = Query("", description="Filter by date YYYY-MM-DD"),
    current_user: dict = Depends(get_current_user)
):
    """List all meetings for the current user with optional search/filter."""
    meetings = get_meetings(current_user["id"], search=search, date_filter=date)
    # Parse JSON fields for response
    for m in meetings:
        m["tasks"] = _safe_json_loads(m.get("tasks", "[]"), [])
        m["deadlines"] = _safe_json_loads(m.get("deadlines", "[]"), [])
    return {"meetings": meetings, "total": len(meetings)}


@app.get("/api/meetings/latest", tags=["Meetings"])
async def latest_meeting(current_user: dict = Depends(get_current_user)):
    """Get the most recently processed meeting."""
    meeting = get_latest_meeting(current_user["id"])
    if not meeting:
        return {"meeting": None}
    meeting["tasks"] = _safe_json_loads(meeting.get("tasks", "[]"), [])
    meeting["deadlines"] = _safe_json_loads(meeting.get("deadlines", "[]"), [])
    return {"meeting": meeting}


@app.get("/api/meetings/{meeting_id}", tags=["Meetings"])
async def get_meeting(
    meeting_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific meeting by ID."""
    meeting = get_meeting_by_id(meeting_id, current_user["id"])
    if not meeting:
        raise HTTPException(404, "Meeting not found")
    meeting["tasks"] = _safe_json_loads(meeting.get("tasks", "[]"), [])
    meeting["deadlines"] = _safe_json_loads(meeting.get("deadlines", "[]"), [])
    return {"meeting": meeting}


@app.delete("/api/meetings/{meeting_id}", tags=["Meetings"])
async def remove_meeting(
    meeting_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Delete a meeting."""
    deleted = delete_meeting(meeting_id, current_user["id"])
    if not deleted:
        raise HTTPException(404, "Meeting not found")
    return {"message": "Meeting deleted successfully"}


# ═══════════════════════════════════════════════════════════════════
# EXPORT ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

@app.get("/api/meetings/{meeting_id}/export/json", tags=["Export"])
async def export_json(
    meeting_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Download meeting results as JSON."""
    meeting = get_meeting_by_id(meeting_id, current_user["id"])
    if not meeting:
        raise HTTPException(404, "Meeting not found")

    meeting["tasks"] = _safe_json_loads(meeting.get("tasks", "[]"), [])
    meeting["deadlines"] = _safe_json_loads(meeting.get("deadlines", "[]"), [])

    # Write to temp file and return
    tmp = tempfile.mktemp(suffix=".json")
    with open(tmp, "w") as f:
        json.dump(meeting, f, indent=2, default=str)

    return FileResponse(
        tmp,
        media_type="application/json",
        filename=f"meeting_{meeting_id}_results.json"
    )


@app.get("/api/meetings/{meeting_id}/export/txt", tags=["Export"])
async def export_txt(
    meeting_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Download meeting results as plain text."""
    meeting = get_meeting_by_id(meeting_id, current_user["id"])
    if not meeting:
        raise HTTPException(404, "Meeting not found")

    tasks = _safe_json_loads(meeting.get("tasks", "[]"), [])
    deadlines = _safe_json_loads(meeting.get("deadlines", "[]"), [])

    lines = [
        f"MEETING INTELLIGENCE REPORT",
        f"{'='*60}",
        f"File: {meeting['filename']}",
        f"Processed: {meeting['created_at']}",
        f"",
        f"SUMMARY",
        f"{'-'*60}",
        meeting.get("summary", "N/A"),
        f"",
        f"ACTION ITEMS / TASKS",
        f"{'-'*60}",
    ]
    for i, task in enumerate(tasks, 1):
        lines.append(f"  {i}. {task}")

    lines += [
        f"",
        f"DEADLINES",
        f"{'-'*60}",
    ]
    for d in deadlines:
        lines.append(f"  • {d.get('sentence', d)}")

    lines += [
        f"",
        f"FULL TRANSCRIPT",
        f"{'-'*60}",
        meeting.get("transcript", "N/A"),
    ]

    content = "\n".join(lines)
    tmp = tempfile.mktemp(suffix=".txt")
    with open(tmp, "w") as f:
        f.write(content)

    return FileResponse(
        tmp,
        media_type="text/plain",
        filename=f"meeting_{meeting_id}_report.txt"
    )


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/api/health", tags=["System"])
async def health():
    return {"status": "ok", "service": "Meeting Intelligence API"}


# ── Utility helpers ───────────────────────────────────────────────────────────

def _safe_json_loads(value, default):
    """Parse JSON string safely, returning default on failure."""
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default
