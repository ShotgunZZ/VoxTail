"""Speaker management routes."""
import logging

from fastapi import APIRouter, HTTPException

from services.enrollment_svc import load_speakers, save_speakers, sync_speakers_from_pinecone
from services.pinecone_db import delete_speaker as delete_speaker_embedding

logger = logging.getLogger(__name__)
router = APIRouter(tags=["speakers"])


@router.get("/speakers")
async def list_speakers():
    """List all enrolled speakers."""
    speakers = load_speakers()
    return {
        "speakers": [
            {"name": name, "samples": int(count) if isinstance(count, (int, float)) else len(count)}
            for name, count in speakers.items()
        ]
    }


@router.delete("/speakers/{name}")
async def delete_speaker(name: str):
    """Delete a speaker and their samples."""
    speakers = load_speakers()
    if name not in speakers:
        raise HTTPException(status_code=404, detail=f"Speaker '{name}' not found")

    # Delete from Pinecone
    delete_speaker_embedding(name)

    # Delete from local tracking
    del speakers[name]
    save_speakers(speakers)

    logger.info(f"Deleted speaker: {name}")
    return {"success": True, "deleted": name}


@router.post("/speakers/sync")
async def sync_speakers():
    """Manually sync speakers from Pinecone."""
    try:
        return sync_speakers_from_pinecone()
    except Exception as e:
        logger.exception("Speaker sync failed")
        raise HTTPException(status_code=500, detail="Sync failed. Please try again.")
