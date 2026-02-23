"""Sharing routes for Slack and Google Drive integrations."""
import logging

from fastapi import APIRouter, HTTPException, Request

import config
from services.session_mgmt import get_session_store
from services.analytics import log_event

logger = logging.getLogger(__name__)
router = APIRouter(tags=["sharing"])


def _require_admin(request: Request):
    """Raise 403 if the caller is not using the admin code."""
    if config.ADMIN_CODE:
        code = request.headers.get("X-Invite-Code", "")
        if code != config.ADMIN_CODE:
            raise HTTPException(status_code=403, detail="Admin access required")


@router.post("/meeting/{meeting_id}/share/slack")
async def share_to_slack(meeting_id: str, request: Request):
    """Post meeting summary to Slack via incoming webhook."""
    _require_admin(request)
    if not config.SLACK_WEBHOOK_URL:
        raise HTTPException(status_code=501, detail="Slack integration not configured")

    session_store = get_session_store()
    session = session_store.get(meeting_id)

    if session is None:
        raise HTTPException(status_code=404, detail="Meeting session not found or expired")
    if session.summary is None:
        raise HTTPException(status_code=400, detail="Generate a summary first before sharing")

    try:
        from services.slack_svc import send_to_slack
        send_to_slack(
            summary=session.summary,
            audio_duration=session.audio_duration,
            created_at=session.created_at,
        )
        device_id = request.headers.get("x-device-id", "unknown")
        log_event("share.slack", device_id=device_id)
        return {"success": True, "message": "Summary posted to Slack"}
    except Exception as e:
        logger.error("Slack sharing failed: %s", e)
        raise HTTPException(status_code=502, detail="Failed to post to Slack. Please try again.")


@router.post("/meeting/{meeting_id}/share/gdrive")
async def share_to_gdrive(meeting_id: str, request: Request):
    """Upload meeting notes as a Google Doc to shared Drive folder."""
    _require_admin(request)
    if not config.GOOGLE_SERVICE_ACCOUNT_JSON or not config.GOOGLE_DRIVE_FOLDER_ID:
        raise HTTPException(status_code=501, detail="Google Drive integration not configured")

    session_store = get_session_store()
    session = session_store.get(meeting_id)

    if session is None:
        raise HTTPException(status_code=404, detail="Meeting session not found or expired")
    if session.summary is None:
        raise HTTPException(status_code=400, detail="Generate a summary first before sharing")

    try:
        from services.gdrive_svc import upload_to_drive
        result = upload_to_drive(
            summary=session.summary,
            audio_duration=session.audio_duration,
            created_at=session.created_at,
        )
        device_id = request.headers.get("x-device-id", "unknown")
        log_event("share.gdrive", device_id=device_id)
        return {"success": True, "url": result["url"], "message": "Uploaded to Google Drive"}
    except Exception as e:
        logger.error("Google Drive sharing failed: %s", e)
        raise HTTPException(status_code=502, detail="Failed to upload to Google Drive. Please try again.")
