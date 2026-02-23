"""Speaker Recognition Web App."""
import logging
import os
import shutil
import sys

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

import config
from routes import api_router
from services.enrollment_svc import sync_speakers_from_pinecone

TEMP_AUDIO_DIR = "meeting_audio_temp"

# Configure logging to stdout (Railway treats stderr as errors)
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
# Reduce noise from speechbrain debug logs
logging.getLogger("speechbrain").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

app = FastAPI(title="Speaker Recognition MVP")


@app.middleware("http")
async def check_invite_code(request: Request, call_next):
    """Gate all /api/* routes behind an invite code (if configured)."""
    if (
        request.url.path.startswith("/api/")
        and request.url.path != "/api/validate-invite"
    ):
        code = request.headers.get("X-Invite-Code", "")
        valid_codes = [c for c in [config.INVITE_CODE, config.ADMIN_CODE] if c]
        if valid_codes and code not in valid_codes:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing invite code"}
            )
    return await call_next(request)


@app.post("/api/validate-invite")
async def validate_invite(request: Request):
    """Validate an invitation code and return admin status."""
    body = await request.json()
    code = body.get("code", "")

    # No gate configured
    if not config.INVITE_CODE and not config.ADMIN_CODE:
        return {"valid": True, "admin": True}

    # Check admin code first
    if config.ADMIN_CODE and code == config.ADMIN_CODE:
        return {"valid": True, "admin": True}

    # Check regular invite code
    if config.INVITE_CODE and code == config.INVITE_CODE:
        return {"valid": True, "admin": False}

    return JSONResponse(
        status_code=401,
        content={"valid": False, "detail": "Invalid invite code"}
    )


# Mount API routes
app.include_router(api_router)

# Serve sw.js with no-cache so browsers always check for updates
@app.get("/static/sw.js")
async def service_worker():
    return FileResponse("static/sw.js", media_type="application/javascript",
                        headers={"Cache-Control": "no-cache"})

# Serve static files (frontend)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.on_event("startup")
async def startup_tasks():
    """Run startup tasks: validate config, cleanup temp files, and sync speakers."""
    config.validate()

    # Clean up stale temp audio files from previous runs
    if os.path.exists(TEMP_AUDIO_DIR):
        try:
            shutil.rmtree(TEMP_AUDIO_DIR)
            logger.info(f"Cleaned up {TEMP_AUDIO_DIR}/ directory")
        except Exception as e:
            logger.warning(f"Could not clean up {TEMP_AUDIO_DIR}/: {e}")

    # Recreate temp directory
    os.makedirs(TEMP_AUDIO_DIR, exist_ok=True)

    # Sync local speakers.json with Pinecone
    logger.info("Syncing speakers with Pinecone...")
    try:
        result = sync_speakers_from_pinecone()
        if result["synced"]:
            logger.info(f"Synced {result['synced']} speaker(s) from Pinecone: {result['speakers']}")
    except Exception as e:
        logger.warning(f"Could not sync with Pinecone: {e}. Using local speakers.json if available.")

    # Pre-load speaker embedding model to fail fast if not enough memory
    logger.info("Pre-loading speaker embedding model...")
    try:
        from services.speaker_encoder import get_model
        get_model()
        logger.info("Speaker embedding model loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load speaker embedding model: {e}")

    # Re-suppress speechbrain debug logs (model loading resets logger levels)
    logging.getLogger("speechbrain").setLevel(logging.WARNING)


@app.get("/")
async def index():
    """Serve the main page."""
    return FileResponse("static/index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
