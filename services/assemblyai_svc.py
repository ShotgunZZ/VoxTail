"""AssemblyAI transcription service with speaker diarization."""
import logging

import assemblyai as aai
import config

logger = logging.getLogger(__name__)

aai.settings.api_key = config.ASSEMBLYAI_API_KEY


def transcribe_with_diarization(audio_path: str, language_code: str = None) -> dict:
    """Transcribe audio file with speaker diarization.

    Args:
        audio_path: Path to audio file
        language_code: Optional language code (e.g., "en", "zh", "es").
                      If None, automatic language detection is used.

    Returns:
        Dict containing:
            - utterances: List of {speaker, text, start, end}
            - audio_duration: Total duration in milliseconds
            - language_code: Detected or specified language
    """
    # Configure transcription with speaker diarization
    if language_code:
        # Use specified language
        transcription_config = aai.TranscriptionConfig(
            speaker_labels=True,
            language_code=language_code,
            speech_models=["universal-3-pro", "universal-2"]
        )
        logger.info("Transcribing audio with speaker diarization (language: %s)...", language_code)
    else:
        # Use automatic language detection
        transcription_config = aai.TranscriptionConfig(
            speaker_labels=True,
            language_detection=True,
            speech_models=["universal-3-pro", "universal-2"]
        )
        logger.info("Transcribing audio with speaker diarization (auto-detecting language)...")

    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(audio_path, config=transcription_config)

    if transcript.status == aai.TranscriptStatus.error:
        raise Exception(f"Transcription failed: {transcript.error}")

    utterances = [
        {
            "speaker": utt.speaker,  # "A", "B", "C", etc.
            "text": utt.text,
            "start": utt.start,      # milliseconds
            "end": utt.end
        }
        for utt in transcript.utterances
    ]

    detected_language = getattr(transcript, 'language_code', language_code or 'unknown')
    logger.info("Transcription complete: %d utterances (language: %s)", len(utterances), detected_language)

    return {
        "utterances": utterances,
        "audio_duration": transcript.audio_duration,
        "language_code": detected_language
    }
