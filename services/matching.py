"""Speaker matching service with competitive assignment."""
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from enum import Enum

import numpy as np
from scipy.optimize import linear_sum_assignment

import config
from services.pinecone_db import find_speaker_top_k

logger = logging.getLogger(__name__)


class ConfidenceLevel(str, Enum):
    """Confidence level for speaker matches."""
    HIGH = "high"      # Auto-assign: score >= threshold AND margin >= min_margin
    MEDIUM = "medium"  # Needs confirmation: score >= threshold AND margin < min_margin
    LOW = "low"        # Unknown: score < threshold


@dataclass
class MatchCandidate:
    """A potential speaker match."""
    speaker_name: str
    score: float


@dataclass
class SpeakerMatchResult:
    """Result of matching a meeting speaker against the portfolio."""
    meeting_speaker_id: str
    confidence: ConfidenceLevel
    top_match: Optional[MatchCandidate]
    candidates: List[MatchCandidate]
    margin: float
    assigned_name: Optional[str] = None

    @property
    def needs_confirmation(self) -> bool:
        """Whether user needs to confirm between candidates."""
        return self.confidence == ConfidenceLevel.MEDIUM

    @property
    def needs_naming(self) -> bool:
        """Whether user needs to name this unknown speaker."""
        return self.confidence == ConfidenceLevel.LOW

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "meeting_speaker_id": self.meeting_speaker_id,
            "confidence": self.confidence.value,
            "top_score": round(self.top_match.score, 3) if self.top_match else 0.0,
            "margin": round(self.margin, 3),
            "candidates": [
                {"name": c.speaker_name, "score": round(c.score, 3)}
                for c in self.candidates
            ],
            "assigned_name": self.assigned_name,
            "needs_confirmation": self.needs_confirmation,
            "needs_naming": self.needs_naming
        }


def match_speakers_competitively(
    speaker_embeddings: Dict[str, List[float]],
    min_threshold: float = None,
    min_margin: float = None,
    top_k: int = None
) -> Dict[str, SpeakerMatchResult]:
    """Match meeting speakers to portfolio speakers using competitive assignment.

    Algorithm:
    1. For each meeting speaker, query top-k matches from Pinecone
    2. Classify each match as HIGH/MEDIUM/LOW confidence
    3. Apply competitive assignment (greedy by score)
    4. Demote duplicate assignments to LOW confidence

    Args:
        speaker_embeddings: Dict of {meeting_speaker_id: embedding}
        min_threshold: Minimum score to consider a match (default: config.MIN_THRESHOLD)
        min_margin: Minimum margin for HIGH confidence (default: config.MIN_MARGIN)
        top_k: Number of candidates to retrieve (default: config.TOP_K_MATCHES)

    Returns:
        Dict of {meeting_speaker_id: SpeakerMatchResult}
    """
    min_threshold = min_threshold if min_threshold is not None else config.MIN_THRESHOLD
    min_margin = min_margin if min_margin is not None else config.MIN_MARGIN
    top_k = top_k if top_k is not None else config.TOP_K_MATCHES

    results: Dict[str, SpeakerMatchResult] = {}
    all_match_scores: List[Tuple[str, str, float]] = []  # (meeting_id, portfolio_name, score)

    # Step 1: Query Pinecone for each speaker
    for meeting_id, embedding in speaker_embeddings.items():
        raw_matches = find_speaker_top_k(embedding, top_k)
        candidates = [MatchCandidate(name, score) for name, score in raw_matches]

        if not candidates:
            # No matches at all - definitely unknown
            results[meeting_id] = SpeakerMatchResult(
                meeting_speaker_id=meeting_id,
                confidence=ConfidenceLevel.LOW,
                top_match=None,
                candidates=[],
                margin=0.0
            )
            continue

        top_score = candidates[0].score
        second_score = candidates[1].score if len(candidates) > 1 else 0.0
        margin = top_score - second_score

        # Step 2: Classify confidence
        if top_score >= min_threshold and margin >= min_margin:
            confidence = ConfidenceLevel.HIGH
        elif top_score >= min_threshold:
            confidence = ConfidenceLevel.MEDIUM
        else:
            confidence = ConfidenceLevel.LOW

        results[meeting_id] = SpeakerMatchResult(
            meeting_speaker_id=meeting_id,
            confidence=confidence,
            top_match=candidates[0],
            candidates=candidates,
            margin=margin
        )

        # Track candidates for competitive assignment (only if potentially assignable)
        if confidence != ConfidenceLevel.LOW:
            for c in candidates:
                if c.score >= min_threshold:
                    all_match_scores.append((meeting_id, c.speaker_name, c.score))

    # Step 3: Optimal competitive assignment via Hungarian algorithm
    # Build a score matrix of assignable meeting speakers × portfolio speakers
    assignable_ids = [mid for mid in results
                      if results[mid].confidence != ConfidenceLevel.LOW]

    if assignable_ids:
        # Collect all portfolio speakers that appear as candidates
        portfolio_names = sorted({name for _, name, _ in all_match_scores})
        score_lookup = {}
        for mid, name, score in all_match_scores:
            score_lookup[(mid, name)] = max(score, score_lookup.get((mid, name), 0.0))

        # Build cost matrix (Hungarian minimizes, so use 1 - score)
        cost_matrix = np.ones((len(assignable_ids), len(portfolio_names)))
        for i, mid in enumerate(assignable_ids):
            for j, pname in enumerate(portfolio_names):
                score = score_lookup.get((mid, pname), 0.0)
                cost_matrix[i, j] = 1.0 - score

        row_ind, col_ind = linear_sum_assignment(cost_matrix)

        assigned_portfolio_speakers = set()
        for i, j in zip(row_ind, col_ind):
            mid = assignable_ids[i]
            pname = portfolio_names[j]
            score = 1.0 - cost_matrix[i, j]

            if score >= min_threshold and pname not in assigned_portfolio_speakers:
                results[mid].assigned_name = pname
                assigned_portfolio_speakers.add(pname)
            else:
                # Score too low or duplicate — demote to LOW
                results[mid].confidence = ConfidenceLevel.LOW
                results[mid].assigned_name = None

        # Demote any assignable speakers not in the optimal solution
        for mid in assignable_ids:
            if results[mid].assigned_name is None and results[mid].confidence != ConfidenceLevel.LOW:
                results[mid].confidence = ConfidenceLevel.LOW

        logger.info("Hungarian assignment: %d meeting speakers → %d portfolio matches",
                     len(assignable_ids), len(assigned_portfolio_speakers))

    return results
