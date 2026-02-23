import logging
import os

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "speaker-embeddings")
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")

# TitaNet embedding dimension
EMBEDDING_DIM = 192

# Minimum segment length for reliable speaker embedding (milliseconds)
MIN_SEGMENT_MS = 3000

# Default similarity threshold for speaker matching (legacy)
DEFAULT_THRESHOLD = 0.5

# New matching algorithm thresholds
MIN_THRESHOLD = 0.55      # Minimum score to consider a match
MIN_MARGIN = 0.10         # Minimum gap between top-1 and top-2 for HIGH confidence
TOP_K_MATCHES = 3         # Number of candidates to retrieve from Pinecone

# Stitching parameters for speaker identification
STITCHING_MIN_UTTERANCE_MS = 2000   # Only use utterances > 2s for stitching
STITCHING_SINGLE_THRESHOLD_MS = 10000  # Use single utterance if >= 10s
STITCHING_MAX_SINGLE_MS = 20000        # Cap single utterance at 20s
STITCHING_TARGET_DURATION_MS = 20000   # Target 20s when stitching
STITCHING_MAX_COUNT = 5                # Max utterances to stitch

# Speaker clip playback parameters
CLIP_MIN_DURATION_MS = 2000   # Minimum for playback and enrollment
CLIP_MAX_DURATION_MS = 5000   # Maximum clip duration

# Voice Activity Detection (silero-vad)
VAD_THRESHOLD = 0.5  # Speech probability threshold

# Voiceprint profile updates
USE_EMA_UPDATES = True     # Use EMA for profile updates (vs weighted average)
EMA_ALPHA = 0.3            # EMA decay factor (higher = more weight on new sample)
EMA_MIN_SAMPLES = 4        # Minimum samples before switching from weighted avg to EMA

# Session management
SESSION_TTL_HOURS = 1  # Meeting session expiry time (reduced for faster cleanup)

# OpenAI API for LLM summaries
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = "gpt-5.2-chat-latest"  # GPT-5.2 Instant: ~$0.10 per summary


def validate():
    """Check required environment variables and warn about any that are missing."""
    required = {
        "PINECONE_API_KEY": PINECONE_API_KEY,
        "ASSEMBLYAI_API_KEY": ASSEMBLYAI_API_KEY,
        "OPENAI_API_KEY": OPENAI_API_KEY,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        logger.warning("Missing required environment variables: %s. Some features will not work.",
                        ", ".join(missing))
    return missing
