"""Pinecone vector database service for speaker embeddings."""
import logging
from typing import Optional, Tuple, List

from pinecone import Pinecone
import config

logger = logging.getLogger(__name__)

_index = None


def get_index():
    """Get Pinecone index (cached)."""
    global _index
    if _index is None:
        pc = Pinecone(api_key=config.PINECONE_API_KEY)
        _index = pc.Index(config.PINECONE_INDEX_NAME)
    return _index


def get_speaker_embedding(speaker_name: str) -> Optional[Tuple[List[float], int]]:
    """Fetch existing embedding for a speaker.

    Returns:
        Tuple of (embedding, sample_count) or None if not found
    """
    result = get_index().fetch(ids=[speaker_name])
    if speaker_name in result.vectors:
        vec = result.vectors[speaker_name]
        sample_count = vec.metadata.get("sample_count", 1)
        return vec.values, sample_count
    return None


def upsert_speaker(speaker_name: str, embedding: List[float], sample_count: int):
    """Store or update a speaker embedding in Pinecone.

    Args:
        speaker_name: Name of the speaker (used as vector ID)
        embedding: 192-dim embedding vector
        sample_count: Number of samples averaged into this embedding
    """
    get_index().upsert(vectors=[{
        "id": speaker_name,
        "values": embedding,
        "metadata": {"speaker_name": speaker_name, "sample_count": sample_count}
    }])


def add_speaker_sample(speaker_name: str, new_embedding: List[float], weight: int = 1) -> int:
    """Add a new sample for a speaker, updating the stored embedding.

    Uses weighted averaging for early samples to build a stable baseline,
    then switches to Exponential Moving Average (EMA) for adaptive updates.

    Weight scheme:
    - Dedicated enrollment samples: weight=2 (higher quality, dedicated recording)
    - Meeting audio samples: weight=1 (reinforcement from meetings)

    Args:
        speaker_name: Name of the speaker
        new_embedding: New 192-dim embedding to add
        weight: Weight for this sample (default: 1 for meeting, use 2 for dedicated enrollment)

    Returns:
        Total sample count after adding
    """
    existing = get_speaker_embedding(speaker_name)

    if existing is None:
        # First sample - just store it with its weight
        upsert_speaker(speaker_name, new_embedding, weight)
        return weight

    old_embedding, old_weight = existing
    new_total_weight = old_weight + weight

    if config.USE_EMA_UPDATES and old_weight >= config.EMA_MIN_SAMPLES:
        # EMA: recent samples have more influence, profile adapts over time
        alpha = config.EMA_ALPHA
        averaged = [
            (1 - alpha) * old_embedding[i] + alpha * new_embedding[i]
            for i in range(len(new_embedding))
        ]
        logger.info("Updated '%s' via EMA (alpha=%.2f, samples=%d)", speaker_name, alpha, new_total_weight)
    else:
        # Weighted average for early samples (need stable baseline first)
        averaged = [
            (old_embedding[i] * old_weight + new_embedding[i] * weight) / new_total_weight
            for i in range(len(new_embedding))
        ]

    upsert_speaker(speaker_name, averaged, new_total_weight)
    return new_total_weight


def delete_speaker(speaker_name: str):
    """Delete a speaker's embedding."""
    get_index().delete(ids=[speaker_name])


def list_all_speakers() -> dict:
    """List all enrolled speakers from Pinecone.

    Returns:
        Dict of {speaker_name: sample_count}
    """
    index = get_index()
    speakers = {}

    # List all vector IDs in the index
    try:
        # Use list operation to get all vector IDs
        for ids in index.list():
            if ids:
                # Fetch metadata for these vectors
                result = index.fetch(ids=ids)
                for vec_id, vec_data in result.vectors.items():
                    sample_count = int(vec_data.metadata.get("sample_count", 1))
                    speakers[vec_id] = sample_count
    except Exception as e:
        logger.warning("Could not list speakers from Pinecone: %s", e)

    return speakers


def find_speaker(embedding: List[float], threshold: float = 0.5) -> Tuple[str, float]:
    """Find the closest matching speaker.

    Args:
        embedding: 192-dim embedding to match
        threshold: Minimum similarity score (0-1, after normalization)

    Returns:
        Tuple of (speaker_name, normalized_confidence_score)
    """
    result = get_index().query(
        vector=embedding,
        top_k=1,
        include_metadata=True
    )

    if not result.matches:
        return "Unknown", 0.0

    raw_score = result.matches[0].score
    # Normalize from [-1, 1] to [0, 1]
    normalized_score = (raw_score + 1) / 2

    if normalized_score >= threshold:
        return result.matches[0].metadata["speaker_name"], normalized_score

    return "Unknown", normalized_score


def find_speaker_top_k(embedding: List[float], top_k: int = 3) -> List[Tuple[str, float]]:
    """Find the top-k matching speakers.

    Args:
        embedding: 192-dim embedding to match
        top_k: Number of candidates to retrieve

    Returns:
        List of (speaker_name, normalized_score) tuples, sorted by score descending
    """
    result = get_index().query(
        vector=embedding,
        top_k=top_k,
        include_metadata=True
    )

    if not result.matches:
        return []

    matches = []
    for match in result.matches:
        raw_score = match.score
        # Normalize from [-1, 1] to [0, 1]
        normalized_score = (raw_score + 1) / 2
        speaker_name = match.metadata.get("speaker_name", match.id)
        matches.append((speaker_name, normalized_score))

    return matches
