"""Meeting session management for speaker recognition."""
import glob
import os
import time
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import config

logger = logging.getLogger(__name__)


@dataclass
class MeetingSession:
    """Represents a meeting session with audio and speaker data."""
    meeting_id: str
    audio_path: str
    original_audio_path: str
    speakers: list
    utterances: list
    speaker_segments: dict
    speaker_embeddings: dict
    audio_duration: float
    language: str = "unknown"
    created_at: float = field(default_factory=time.time)
    # Speaker tracking for auto-cleanup
    pending_speakers: set = field(default_factory=set)  # MEDIUM + LOW speaker IDs needing action
    handled_speakers: set = field(default_factory=set)  # Speakers that have been confirmed/enrolled
    # LLM-generated summary (cached after generation)
    summary: dict = field(default_factory=lambda: None)

    def all_speakers_handled(self) -> bool:
        """Check if all pending speakers have been handled."""
        return self.pending_speakers <= self.handled_speakers


class SessionStore:
    """In-memory storage for meeting sessions with TTL-based cleanup."""

    def __init__(self, audio_dir: Path):
        self._sessions: dict[str, MeetingSession] = {}
        self._audio_dir = audio_dir
        self._audio_dir.mkdir(exist_ok=True)
        self._last_meeting_id: Optional[str] = None  # Track last meeting for cleanup on new upload

    @property
    def audio_dir(self) -> Path:
        """Get the directory for storing meeting audio files."""
        return self._audio_dir

    def get(self, meeting_id: str) -> Optional[MeetingSession]:
        """Get a session by meeting ID."""
        return self._sessions.get(meeting_id)

    def save(self, session: MeetingSession) -> None:
        """Save a meeting session."""
        self._sessions[session.meeting_id] = session
        self._last_meeting_id = session.meeting_id
        logger.info(f"Meeting {session.meeting_id}: session stored for enrollment")

    def cleanup_previous_session(self, current_meeting_id: str) -> bool:
        """Clean up the previous session when a new upload/recording starts.

        This is a fallback cleanup mechanism - if user uploads a new file
        before handling all speakers from the previous session, clean it up.
        """
        if self._last_meeting_id and self._last_meeting_id != current_meeting_id:
            if self._last_meeting_id in self._sessions:
                logger.info(f"Cleaning up previous session {self._last_meeting_id} (new upload started)")
                self.delete(self._last_meeting_id)
                return True
        return False

    def mark_speaker_handled(self, meeting_id: str, speaker_id: str) -> bool:
        """Mark a speaker as handled and auto-cleanup if all speakers are done.

        Returns True if cleanup was triggered, False otherwise.
        """
        session = self._sessions.get(meeting_id)
        if session is None:
            return False

        session.handled_speakers.add(speaker_id)
        logger.info(f"Meeting {meeting_id}: marked speaker {speaker_id} as handled "
                    f"({len(session.handled_speakers)}/{len(session.pending_speakers)})")

        # Check if all pending speakers have been handled
        if session.all_speakers_handled() and session.pending_speakers:
            if session.summary is not None:
                logger.info(f"Meeting {meeting_id}: all handled + summary done, cleaning up")
                self.delete(meeting_id)
                return True
            else:
                logger.info(f"Meeting {meeting_id}: all handled, deferring cleanup until summary")

        return False

    def delete(self, meeting_id: str) -> bool:
        """Delete a session and clean up its audio files."""
        if meeting_id not in self._sessions:
            return False

        session = self._sessions[meeting_id]

        # Remove audio files
        for path in [session.audio_path, session.original_audio_path]:
            if path and os.path.exists(path):
                os.remove(path)
                logger.info(f"Removed audio file: {path}")

        # Remove any generated clip files
        clip_pattern = str(self._audio_dir / f"{meeting_id}_*_clip.wav")
        for clip_path in glob.glob(clip_pattern):
            try:
                os.remove(clip_path)
                logger.info(f"Removed clip file: {clip_path}")
            except OSError as e:
                logger.warning(f"Failed to remove clip file {clip_path}: {e}")

        del self._sessions[meeting_id]
        logger.info(f"Cleaned up meeting session: {meeting_id}")
        return True

    def exists(self, meeting_id: str) -> bool:
        """Check if a session exists."""
        return meeting_id in self._sessions

    def cleanup_expired(self, max_age_hours: int = None) -> int:
        """Remove sessions older than max_age_hours. Returns count of removed sessions."""
        if max_age_hours is None:
            max_age_hours = config.SESSION_TTL_HOURS

        current_time = time.time()
        expired = [
            mid for mid, session in self._sessions.items()
            if current_time - session.created_at > max_age_hours * 3600
        ]

        for mid in expired:
            self.delete(mid)

        if expired:
            logger.info(f"Cleaned up {len(expired)} expired meeting sessions")

        return len(expired)


# Global session store instance
_session_store: Optional[SessionStore] = None


def get_session_store() -> SessionStore:
    """Get the global session store instance."""
    global _session_store
    if _session_store is None:
        _session_store = SessionStore(Path("meeting_audio_temp"))
    return _session_store
