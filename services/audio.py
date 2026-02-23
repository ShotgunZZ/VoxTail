"""Audio preprocessing utilities."""
from typing import List, Optional, Tuple
from pydub import AudioSegment


def convert_to_wav(input_path: str, output_path: str):
    """Convert any audio file to 16kHz mono WAV.

    Args:
        input_path: Path to input audio file
        output_path: Path to save converted WAV file
    """
    audio = AudioSegment.from_file(input_path)
    audio = audio.set_frame_rate(16000).set_channels(1)
    audio.export(output_path, format="wav")


def load_wav(wav_path: str) -> AudioSegment:
    """Load a WAV file into memory for reuse across multiple operations."""
    return AudioSegment.from_file(wav_path)


def extract_segment(input_path: str, start_ms: int, end_ms: int, output_path: str,
                     audio: Optional[AudioSegment] = None):
    """Extract a segment from an audio file.

    Args:
        input_path: Path to input audio file
        start_ms: Start time in milliseconds
        end_ms: End time in milliseconds
        output_path: Path to save extracted segment
        audio: Pre-loaded AudioSegment to avoid re-reading from disk
    """
    if audio is None:
        audio = AudioSegment.from_file(input_path)
    segment = audio[start_ms:end_ms]
    segment = segment.set_frame_rate(16000).set_channels(1)
    segment.export(output_path, format="wav")


def get_duration_ms(input_path: str) -> int:
    """Get audio duration in milliseconds.

    Args:
        input_path: Path to audio file

    Returns:
        Duration in milliseconds
    """
    audio = AudioSegment.from_file(input_path)
    return len(audio)


def stitch_segments(input_path: str, segments: List[Tuple[int, int]], output_path: str,
                     audio: Optional[AudioSegment] = None) -> int:
    """Stitch multiple segments from an audio file together.

    Args:
        input_path: Path to input audio file
        segments: List of (start_ms, end_ms) tuples
        output_path: Path to save stitched audio
        audio: Pre-loaded AudioSegment to avoid re-reading from disk

    Returns:
        Total duration of stitched audio in milliseconds
    """
    if audio is None:
        audio = AudioSegment.from_file(input_path)
    stitched = AudioSegment.empty()

    for start_ms, end_ms in segments:
        segment = audio[start_ms:end_ms]
        stitched += segment

    stitched = stitched.set_frame_rate(16000).set_channels(1)
    stitched.export(output_path, format="wav")

    return len(stitched)
