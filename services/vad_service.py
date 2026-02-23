"""Voice Activity Detection using Silero VAD.

Strips silence from audio before embedding extraction to produce
cleaner speaker embeddings. Uses silero-vad (~2MB model, <1ms per chunk on CPU).
"""
import logging

import soundfile as sf
import torch
from silero_vad import load_silero_vad, get_speech_timestamps

import config

logger = logging.getLogger(__name__)

_model = None


def get_vad_model():
    """Load Silero VAD model (cached after first load)."""
    global _model
    if _model is None:
        logger.info("Loading Silero VAD model...")
        _model = load_silero_vad()
        logger.info("Silero VAD model loaded.")
    return _model


def get_speech_segments(audio_tensor, sample_rate=16000):
    """Return list of speech segments as {'start': sample_idx, 'end': sample_idx}.

    Args:
        audio_tensor: 1D torch tensor of audio samples
        sample_rate: Audio sample rate (16000 recommended)

    Returns:
        List of dicts with 'start' and 'end' keys (sample indices)
    """
    model = get_vad_model()
    return get_speech_timestamps(
        audio_tensor, model,
        threshold=config.VAD_THRESHOLD,
        min_silence_duration_ms=100,
        speech_pad_ms=30
    )


def get_speech_duration_ms(audio_path: str) -> float:
    """Return milliseconds of speech detected in audio file.

    Loads audio, runs VAD, and sums speech segment lengths without modifying anything.
    """
    data, sample_rate = sf.read(audio_path, dtype="float32")
    audio_tensor = torch.from_numpy(data)
    if audio_tensor.dim() > 1:
        audio_tensor = audio_tensor.mean(dim=1)
    if sample_rate != 16000:
        # Resample to 16kHz for Silero VAD
        import torchaudio.functional as F
        audio_tensor = F.resample(audio_tensor, sample_rate, 16000)
        sample_rate = 16000
    segments = get_speech_segments(audio_tensor, sample_rate)
    if not segments:
        return 0.0
    total_samples = sum(s['end'] - s['start'] for s in segments)
    return total_samples / sample_rate * 1000


def strip_silence(audio_tensor, sample_rate=16000):
    """Return audio tensor with silence removed, concatenating speech segments.

    Args:
        audio_tensor: 1D torch tensor of audio samples
        sample_rate: Audio sample rate

    Returns:
        1D torch tensor with only speech portions concatenated
    """
    segments = get_speech_segments(audio_tensor, sample_rate)
    if not segments:
        logger.warning("VAD detected no speech — returning original audio")
        return audio_tensor
    speech = torch.cat([audio_tensor[s['start']:s['end']] for s in segments])
    original_ms = len(audio_tensor) / sample_rate * 1000
    speech_ms = len(speech) / sample_rate * 1000
    logger.info("VAD: %.1fs total → %.1fs speech (removed %.0f%% silence)",
                original_ms / 1000, speech_ms / 1000,
                (1 - speech_ms / original_ms) * 100 if original_ms > 0 else 0)
    return speech
