"""Confirmation and cleanup routes for speaker recognition."""
import logging

from fastapi import APIRouter, Form, HTTPException

from services.enrollment_svc import enroll_from_embedding, load_speakers, save_speakers
from services.session_mgmt import get_session_store
from services.pinecone_db import add_speaker_sample

logger = logging.getLogger(__name__)
router = APIRouter(tags=["confirmation"])


@router.post("/confirm-speaker")
async def confirm_speaker(
    meeting_id: str = Form(...),
    speaker_id: str = Form(...),
    confirmed_name: str = Form(...),
    enroll: bool = Form(default=True)
):
    """Confirm a MEDIUM confidence speaker match.

    Optionally enrolls the speaker to reinforce their voice model.

    Args:
        meeting_id: ID of the meeting session
        speaker_id: Speaker ID from the meeting (e.g., "A", "B")
        confirmed_name: The confirmed speaker name
        enroll: Whether to add this sample to the speaker's voice model (default: True)
    """
    confirmed_name = confirmed_name.strip()
    if not confirmed_name:
        raise HTTPException(status_code=400, detail="Confirmed name is required")

    # Get meeting session
    session_store = get_session_store()
    session = session_store.get(meeting_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Meeting session not found or expired")

    # Check if speaker exists in this meeting
    if speaker_id not in session.speaker_segments:
        raise HTTPException(status_code=404, detail=f"Speaker {speaker_id} not found in meeting")

    result = {
        "success": True,
        "speaker_id": speaker_id,
        "confirmed_name": confirmed_name,
        "enrolled": False,
        "session_cleaned_up": False
    }

    # Optionally enroll to reinforce the speaker model
    if enroll and speaker_id in session.speaker_embeddings:
        # Skip reinforcement for low speech quality speakers
        speaker_data = next((sr for sr in session.speakers if sr["meeting_speaker_id"] == speaker_id), None)
        if speaker_data and not speaker_data.get("low_speech_quality"):
            embedding = session.speaker_embeddings[speaker_id]
            # Use weight=1 for meeting reinforcement (dedicated enrollment uses weight=2)
            total_weight = add_speaker_sample(confirmed_name, embedding, weight=1)

            # Update local tracking
            speakers = load_speakers()
            speakers[confirmed_name] = total_weight
            save_speakers(speakers)

            result["enrolled"] = True
            result["total_weight"] = total_weight
            logger.info(f"Reinforced speaker '{confirmed_name}' from meeting {meeting_id} (total weight: {total_weight})")
        else:
            logger.info(f"Skipped reinforcement for '{confirmed_name}' - low speech quality")

    # Update session speaker record with confirmed name
    for sr in session.speakers:
        if sr["meeting_speaker_id"] == speaker_id:
            sr["assigned_name"] = confirmed_name
            break

    # Mark speaker as handled and check for auto-cleanup
    if session_store.mark_speaker_handled(meeting_id, speaker_id):
        result["session_cleaned_up"] = True

    return result


@router.post("/meeting/{meeting_id}/cleanup")
async def cleanup_meeting(meeting_id: str):
    """Clean up a meeting session and its audio files.

    Call this when done with a meeting to free up resources.
    """
    session_store = get_session_store()

    if not session_store.exists(meeting_id):
        raise HTTPException(status_code=404, detail="Meeting session not found")

    session_store.delete(meeting_id)

    return {"success": True, "meeting_id": meeting_id}
