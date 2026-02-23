"""Speaker embedding service using SpeechBrain's ECAPA-TDNN model."""
import logging
from typing import List

import torch
import numpy as np
import soundfile as sf
from speechbrain.inference.speaker import EncoderClassifier

from services.vad_service import strip_silence

logger = logging.getLogger(__name__)

_model = None


def get_model():
    """Load ECAPA-TDNN model (cached after first load)."""
    global _model
    if _model is None:
        logger.info("Loading speaker embedding model...")
        _model = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            savedir="pretrained_models/spkrec-ecapa-voxceleb",
            run_opts={"device": "cpu"}
        )
        logger.info("Speaker embedding model loaded.")
    return _model


def get_embedding(audio_path: str) -> List[float]:
    """Extract 192-dimensional speaker embedding from audio file.

    Args:
        audio_path: Path to WAV audio file (16kHz mono recommended)

    Returns:
        List of 192 floats representing the speaker's voice fingerprint
    """
    model = get_model()

    # Load audio
    audio_data, sample_rate = sf.read(audio_path)

    # Convert stereo to mono if needed
    if len(audio_data.shape) > 1:
        audio_data = np.mean(audio_data, axis=1)

    # Resample to 16kHz if needed
    if sample_rate != 16000:
        duration = len(audio_data) / sample_rate
        target_length = int(duration * 16000)
        indices = np.linspace(0, len(audio_data) - 1, target_length)
        audio_data = np.interp(indices, np.arange(len(audio_data)), audio_data)

    # Convert to tensor and strip silence via VAD
    signal = torch.tensor(audio_data, dtype=torch.float32)
    signal = strip_silence(signal, sample_rate=16000)
    signal = signal.unsqueeze(0)  # [1, num_samples]

    # Extract embedding
    embedding = model.encode_batch(signal)

    return embedding.squeeze().tolist()
