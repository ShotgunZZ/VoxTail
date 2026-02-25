"""Audio segmentation logic for speaker identification."""
import logging
import os
import tempfile
from typing import Dict, List, Optional, Tuple

from pydub import AudioSegment

from services.audio import extract_segment, stitch_segments, load_wav
from services.speaker_encoder import get_embedding
from services.vad_service import get_speech_duration_ms
import config

logger = logging.getLogger(__name__)


def select_segments_for_speaker(
    speaker_utts: list,
    speaker_id: str,
    wav_path: str,
    audio: AudioSegment
) -> Tuple[List[Tuple[int, int]], Optional[str], float]:
    """Select segments for a speaker using incremental VAD-aware selection.

    Starts with the longest utterance, checks how much speech VAD detects,
    and adds more utterances until we have enough clean speech.

    Args:
        speaker_utts: Utterances for this speaker, each with 'start' and 'end' keys (ms).
        speaker_id: Speaker ID for logging.
        wav_path: Path to the full meeting WAV file.
        audio: Pre-loaded AudioSegment of the WAV file.

    Returns:
        Tuple of (segments list, temp_wav_path or None, speech_ms).
        temp_wav_path is the extracted audio ready for embedding, caller must delete it.
    """
    sorted_utts = sorted(
        speaker_utts,
        key=lambda x: x["end"] - x["start"],
        reverse=True
    )

    # Filter out utterances shorter than minimum
    candidates = [
        u for u in sorted_utts
        if (u["end"] - u["start"]) >= config.STITCHING_MIN_UTTERANCE_MS
    ]

    if not candidates:
        logger.info("Speaker %s: no utterances >= %dms", speaker_id, config.STITCHING_MIN_UTTERANCE_MS)
        return [], None, 0.0

    segments = []
    total_raw_ms = 0
    temp_path = None
    speech_ms = 0.0
    prev_speech_ms = 0.0

    for i, utt in enumerate(candidates):
        utt_duration = utt["end"] - utt["start"]

        # Cap individual utterance at max single duration
        start = utt["start"]
        end = utt["end"]
        if utt_duration > config.STITCHING_MAX_SINGLE_MS:
            end = start + config.STITCHING_MAX_SINGLE_MS
            utt_duration = config.STITCHING_MAX_SINGLE_MS

        segments.append((start, end))
        total_raw_ms += utt_duration

        # Extract current segments to temp file and check VAD speech duration
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)

        fd, temp_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)

        if len(segments) == 1:
            extract_segment(str(wav_path), segments[0][0], segments[0][1], temp_path, audio=audio)
        else:
            stitch_segments(str(wav_path), segments, temp_path, audio=audio)

        prev_speech_ms = speech_ms
        speech_ms = get_speech_duration_ms(temp_path)
        added_speech = speech_ms - prev_speech_ms

        logger.info(
            "Speaker %s: utterance %d (%.1fs raw → %.1fs speech), total %.1fs speech",
            speaker_id, i + 1, utt_duration / 1000, added_speech / 1000, speech_ms / 1000
        )

        # Enough speech or hit max segments
        if speech_ms >= config.STITCHING_SINGLE_THRESHOLD_MS:
            logger.info("Speaker %s: %.1fs speech — sufficient", speaker_id, speech_ms / 1000)
            break
        if len(segments) >= config.STITCHING_MAX_COUNT:
            logger.info("Speaker %s: hit max %d segments (%.1fs speech)", speaker_id, config.STITCHING_MAX_COUNT, speech_ms / 1000)
            break

    if not segments:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
        return [], None, 0.0

    logger.info(
        "Speaker %s: selected %d utterance(s), %.1fs raw → %.1fs speech",
        speaker_id, len(segments), total_raw_ms / 1000, speech_ms / 1000
    )

    return segments, temp_path, speech_ms


def extract_speaker_embeddings(
    unique_speakers: set,
    utterances: list,
    wav_path: str
) -> Tuple[Dict[str, List[float]], Dict[str, List[Tuple[int, int]]], Dict[str, dict]]:
    """Extract embeddings and select segments for all speakers in a meeting.

    Args:
        unique_speakers: Set of speaker IDs from diarization.
        utterances: All utterances from transcription.
        wav_path: Path to the converted WAV file.

    Returns:
        Tuple of (speaker_embeddings dict, speaker_segments dict, speech_quality dict).
    """
    speaker_embeddings = {}
    speaker_segments = {}
    speech_quality = {}

    # Load WAV once — avoids re-reading the full file for each speaker
    audio = load_wav(wav_path)
    logger.info("Loaded WAV into memory for segment extraction")

    for speaker_id in unique_speakers:
        speaker_utts = [u for u in utterances if u["speaker"] == speaker_id]
        segments, segment_path, speech_ms = select_segments_for_speaker(
            speaker_utts, speaker_id, wav_path, audio
        )
        speaker_segments[speaker_id] = segments
        speech_quality[speaker_id] = {
            "speech_ms": speech_ms,
            "low_quality": speech_ms < config.MIN_IDENTIFICATION_SPEECH_MS
        }

        if not segment_path:
            total_duration = sum(end - start for start, end in segments)
            logger.info("Speaker %s: insufficient audio (%.1fs)", speaker_id, total_duration / 1000)
            continue

        try:
            raw_duration = sum(end - start for start, end in segments) / 1000
            logger.info(
                "Speaker %s: extracting embedding from VAD-cleaned audio (%d segments, %.1fs raw)",
                speaker_id, len(segments), raw_duration
            )
            embedding = get_embedding(segment_path)
            speaker_embeddings[speaker_id] = embedding
        finally:
            if os.path.exists(segment_path):
                os.remove(segment_path)

    logger.info("Extracted embeddings for %d/%d speakers", len(speaker_embeddings), len(unique_speakers))
    return speaker_embeddings, speaker_segments, speech_quality
