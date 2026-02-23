"""Summary routes for meeting transcript summarization."""
import logging

from fastapi import APIRouter, HTTPException, Request

from services.session_mgmt import get_session_store
from services.analytics import log_event
from services.speaker_mapping import build_speaker_name_map
from services.llm_summary import generate_summary

logger = logging.getLogger(__name__)
router = APIRouter(tags=["summary"])


@router.post("/meeting/{meeting_id}/summary")
async def create_meeting_summary(meeting_id: str, request: Request):
    """Generate an AI summary of the meeting transcript.

    Returns executive summary, action items, key decisions, and topics.
    The summary is cached in the session for later use (Slack, Drive, etc.).
    """
    session_store = get_session_store()
    session = session_store.get(meeting_id)

    if session is None:
        raise HTTPException(status_code=404, detail="Meeting session not found or expired")

    # Check if we have utterances to summarize
    if not session.utterances:
        raise HTTPException(status_code=400, detail="No transcript available to summarize")

    # Build labeled utterances with speaker names
    speaker_name_map = build_speaker_name_map(session.speakers, "Speaker {sid}")

    labeled_utterances = [
        {
            "speaker_name": speaker_name_map.get(utt["speaker"], f"Speaker {utt['speaker']}"),
            "text": utt["text"]
        }
        for utt in session.utterances
    ]

    try:
        summary = generate_summary(labeled_utterances, session.language)

        # Store summary in session for Phase 5 & 6 (Slack, Drive)
        session.summary = summary.to_dict()

        device_id = request.headers.get("x-device-id", "unknown")
        speaker_names = [
            s.get("assigned_name") or f"Speaker {s.get('meeting_speaker_id', '?')}"
            for s in session.speakers
        ]
        log_event("summary.generated", device_id=device_id, speakers=speaker_names)

        return {
            "success": True,
            "meeting_id": meeting_id,
            "summary": summary.to_dict()
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Summary generation failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate summary. Please try again.")


@router.get("/meeting/{meeting_id}/summary")
async def get_meeting_summary(meeting_id: str):
    """Get the cached summary for a meeting (if already generated)."""
    session_store = get_session_store()
    session = session_store.get(meeting_id)

    if session is None:
        raise HTTPException(status_code=404, detail="Meeting session not found or expired")

    if not hasattr(session, 'summary') or session.summary is None:
        raise HTTPException(status_code=404, detail="Summary not yet generated. POST to create one.")

    return {
        "success": True,
        "meeting_id": meeting_id,
        "summary": session.summary
    }
