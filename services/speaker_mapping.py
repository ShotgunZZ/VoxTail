"""Shared speaker name mapping utility."""
from typing import Dict, List


def build_speaker_name_map(
    speakers: List[dict],
    unknown_format: str = "Unknown ({sid})"
) -> Dict[str, str]:
    """Build a mapping from meeting_speaker_id to display name.

    Args:
        speakers: List of speaker dicts with 'meeting_speaker_id' and optional 'assigned_name'.
        unknown_format: Format string for unnamed speakers. Use {sid} as placeholder.

    Returns:
        Dict mapping speaker ID to display name.
    """
    name_map = {}
    for sr in speakers:
        sid = sr["meeting_speaker_id"]
        if sr.get("assigned_name"):
            name_map[sid] = sr["assigned_name"]
        else:
            name_map[sid] = unknown_format.format(sid=sid)
    return name_map
