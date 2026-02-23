"""Enrollment service for speaker recognition."""
import json
import logging
from pathlib import Path
from typing import Optional

from services.speaker_encoder import get_embedding
from services.pinecone_db import add_speaker_sample, list_all_speakers
from services.audio import convert_to_wav, get_duration_ms
from services.vad_service import get_speech_duration_ms

import config

logger = logging.getLogger(__name__)

# Local tracking of enrolled speakers
SPEAKERS_FILE = Path("speakers.json")


def load_speakers() -> dict:
    """Load enrolled speakers from local JSON file."""
    if SPEAKERS_FILE.exists():
        return json.loads(SPEAKERS_FILE.read_text())
    return {}


def save_speakers(speakers: dict) -> None:
    """Save enrolled speakers to local JSON file."""
    SPEAKERS_FILE.write_text(json.dumps(speakers, indent=2))


def validate_audio_duration(duration_ms: int) -> tuple[bool, Optional[str]]:
    """Validate audio duration for enrollment.

    Args:
        duration_ms: Audio duration in milliseconds

    Returns:
        Tuple of (is_valid, warning_message)
        - is_valid: False if audio is too short
        - warning_message: Warning text if duration is suboptimal, None otherwise
    """
    duration_s = duration_ms / 1000

    if duration_ms < 5000:
        return False, f"Audio too short ({duration_s:.1f}s). Need at least 5 seconds."

    warning = None
    if duration_ms < 10000:
        warning = f"Recording is {duration_s:.1f}s. 10-30 seconds recommended for best results."
    elif duration_ms > 60000:
        warning = f"Recording is {duration_s:.1f}s. 15-30 seconds is sufficient."

    return True, warning


async def enroll_speaker(
    name: str,
    audio_path: str,
    wav_path: str,
    weight: int = 2
) -> dict:
    """Enroll a speaker from an audio file.

    Args:
        name: Speaker name
        audio_path: Path to the original audio file
        wav_path: Path to write the converted WAV file
        weight: Sample weight (2 for dedicated enrollment, 1 for meeting audio)

    Returns:
        Dict with success status, speaker name, total_samples, and optional warning

    Raises:
        ValueError: If audio is too short or name is empty
    """
    name = name.strip()
    if not name:
        raise ValueError("Speaker name is required")

    # Validate audio duration
    duration_ms = get_duration_ms(audio_path)
    is_valid, warning = validate_audio_duration(duration_ms)

    if not is_valid:
        raise ValueError(warning)

    # Convert to WAV
    convert_to_wav(audio_path, wav_path)

    # Check actual speech content via VAD
    speech_ms = get_speech_duration_ms(wav_path)
    logger.info("Enrollment audio: %.1fs raw, %.1fs speech", duration_ms / 1000, speech_ms / 1000)

    if speech_ms < config.MIN_SEGMENT_MS:
        raise ValueError(
            f"Not enough speech detected ({speech_ms/1000:.1f}s). "
            "Try recording in a quieter environment."
        )

    if speech_ms < 5000 and not warning:
        warning = (
            f"Only {speech_ms/1000:.1f}s of speech detected in "
            f"{duration_ms/1000:.1f}s recording. 10+ seconds of speech recommended."
        )

    # Extract embedding
    logger.info(f"Extracting embedding for speaker: {name}")
    embedding = get_embedding(wav_path)

    # Add to Pinecone
    total_weight = add_speaker_sample(name, embedding, weight=weight)

    # Track locally
    speakers = load_speakers()
    speakers[name] = total_weight
    save_speakers(speakers)

    logger.info(f"Enrolled speaker: {name} (total weight: {total_weight})")

    result = {
        "success": True,
        "speaker": name,
        "total_samples": total_weight
    }
    if warning:
        result["warning"] = warning

    return result


def enroll_from_embedding(
    name: str,
    embedding: list,
    weight: int = 1
) -> dict:
    """Enroll a speaker from an existing embedding.

    Args:
        name: Speaker name
        embedding: Pre-computed voice embedding
        weight: Sample weight (1 for meeting audio)

    Returns:
        Dict with success status, speaker name, and total_samples
    """
    name = name.strip()
    if not name:
        raise ValueError("Speaker name is required")

    # Add to Pinecone
    total_weight = add_speaker_sample(name, embedding, weight=weight)

    # Update local tracking
    speakers = load_speakers()
    speakers[name] = total_weight
    save_speakers(speakers)

    logger.info(f"Enrolled speaker '{name}' from embedding (total weight: {total_weight})")

    return {
        "success": True,
        "speaker": name,
        "total_samples": total_weight
    }


def sync_speakers_from_pinecone() -> dict:
    """Sync local speakers.json with Pinecone.

    Returns:
        Dict with sync status and speaker list
    """
    pinecone_speakers = list_all_speakers()

    if pinecone_speakers:
        save_speakers(pinecone_speakers)
        logger.info(f"Synced {len(pinecone_speakers)} speaker(s) from Pinecone: {list(pinecone_speakers.keys())}")
    else:
        logger.info("No speakers found in Pinecone")

    return {
        "success": True,
        "synced": len(pinecone_speakers),
        "speakers": list(pinecone_speakers.keys())
    }
