"""
app.py
Main entry point for Meeting Intelligence Application.
Serves the FastAPI backend + static frontend from a single server.
Run: python app.py
"""

import os
import sys
import logging
import uvicorn

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from backend.api import app

# ── Serve frontend static files ───────────────────────────────────────────────
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

# Mount static files (CSS, JS, assets if any)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def serve_frontend():
    """Serve the main SPA frontend."""
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


# ── Run the server ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════╗
║          Meeting Intelligence — AI System            ║
╠══════════════════════════════════════════════════════╣
║  Starting server on http://localhost:8006            ║
║  API docs: http://localhost:8006/docs                ║
║  Frontend: http://localhost:8006                     ║
╚══════════════════════════════════════════════════════╝
    """)

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8006,
        reload=False,  # Set True for development hot-reload
        log_level="info",
        access_log=True,
    )
