"""Anonymous usage analytics — structured log events captured by Railway."""
import json
import logging
from datetime import datetime, timezone

analytics_logger = logging.getLogger("voxtail.analytics")


def log_event(event: str, device_id: str = "unknown", **meta):
    """Log a structured analytics event.

    Args:
        event: Event name (e.g., "meeting.processed", "summary.generated")
        device_id: Anonymous device UUID from X-Device-ID header
        **meta: Additional metadata (duration, speakers, etc.)
    """
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "device_id": device_id,
        "event": event,
    }
    if meta:
        entry["meta"] = meta
    analytics_logger.info("[ANALYTICS] %s", json.dumps(entry))
