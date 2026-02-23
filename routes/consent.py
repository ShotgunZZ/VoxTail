"""Consent logging endpoint — records biometric consent acceptance."""
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()

consent_logger = logging.getLogger("voxtail.consent")


class ConsentBody(BaseModel):
    type: str = "biometric"
    version: str = "1.0"


@router.post("/consent")
async def accept_consent(body: ConsentBody, request: Request):
    device_id = request.headers.get("X-Device-ID", "unknown")
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "device_id": device_id,
        "event": "consent.accepted",
        "meta": {"type": body.type, "version": body.version},
    }
    consent_logger.info("[CONSENT] %s", json.dumps(entry))
    return {"accepted": True}
