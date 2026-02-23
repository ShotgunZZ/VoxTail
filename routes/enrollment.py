"""Enrollment routes for speaker registration."""
import logging
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Request

from services.enrollment_svc import enroll_speaker, enroll_from_embedding
from services.analytics import log_event
from services.session_mgmt import get_session_store
from services.audio import extract_segment, stitch_segments
from services.speaker_encoder import get_embedding
from routes.utils import temp_file, save_upload
import config

logger = logging.getLogger(__name__)
router = APIRouter(tags=["enrollment"])


@router.post("/enroll")
async def enroll_speaker_endpoint(
    request: Request,
    name: str = Form(...),
    audio: UploadFile = File(...)
):
    """Enroll a new speaker from an audio sample."""
    suffix = Path(audio.filename).suffix or ".wav"

    with temp_file(suffix) as temp_path:
        await save_upload(audio, temp_path)

        with temp_file(".wav") as wav_path:
            try:
                result = await enroll_speaker(name, temp_path, wav_path, weight=2)
                device_id = request.headers.get("x-device-id", "unknown")
                log_event("speaker.enrolled", device_id=device_id)
                return result
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))


@router.post("/enroll-from-meeting")
async def enroll_from_meeting(
    request: Request,
    meeting_id: str = Form(...),
    speaker_id: str = Form(...),
    speaker_name: str = Form(...)
):
    """Enroll a speaker using audio segments from a meeting.

    Args:
        meeting_id: ID of the meeting session
        speaker_id: Speaker ID from the meeting (e.g., "A", "B")
        speaker_name: Name to assign to this speaker
    """
    speaker_name = speaker_name.strip()
    if not speaker_name:
        raise HTTPException(status_code=400, detail="Speaker name is required")

    # Get meeting session
    session_store = get_session_store()
    session = session_store.get(meeting_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Meeting session not found or expired")

    # Check if speaker exists in this meeting
    if speaker_id not in session.speaker_segments:
        raise HTTPException(status_code=404, detail=f"Speaker {speaker_id} not found in meeting")

    segments = session.speaker_segments[speaker_id]
    if not segments:
        raise HTTPException(status_code=400, detail=f"No audio segments for speaker {speaker_id}")

    # Check if we already have an embedding for this speaker
    if speaker_id in session.speaker_embeddings:
        # Use existing embedding from the meeting
        embedding = session.speaker_embeddings[speaker_id]
        logger.info(f"Using existing embedding for speaker {speaker_id} from meeting {meeting_id}")
    else:
        # Extract segments and generate embedding
        wav_path = session.audio_path
        total_duration = sum(end - start for start, end in segments)

        if total_duration < config.MIN_SEGMENT_MS:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient audio for speaker {speaker_id} ({total_duration/1000:.1f}s). Need at least {config.MIN_SEGMENT_MS/1000}s."
            )

        with temp_file(".wav") as segment_path:
            if len(segments) == 1:
                extract_segment(wav_path, segments[0][0], segments[0][1], segment_path)
            else:
                stitch_segments(wav_path, segments, segment_path)

            embedding = get_embedding(segment_path)

    # Enroll using the embedding
    try:
        result = enroll_from_embedding(speaker_name, embedding, weight=1)
        result["source"] = "meeting"
        result["meeting_id"] = meeting_id

        device_id = request.headers.get("x-device-id", "unknown")
        log_event("speaker.enrolled", device_id=device_id)

        # Update session speaker record with enrolled name
        for sr in session.speakers:
            if sr["meeting_speaker_id"] == speaker_id:
                sr["assigned_name"] = speaker_name
                break

        # Mark speaker as handled and check for auto-cleanup
        if session_store.mark_speaker_handled(meeting_id, speaker_id):
            result["session_cleaned_up"] = True
        else:
            result["session_cleaned_up"] = False

        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
