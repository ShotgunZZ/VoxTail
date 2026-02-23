"""Identification routes for speaker recognition in meetings."""
import json
import uuid
import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse

from services.assemblyai_svc import transcribe_with_diarization
from services.audio import convert_to_wav, extract_segment
from services.audio_segmentation import extract_speaker_embeddings
from services.matching import match_speakers_competitively
from services.speaker_mapping import build_speaker_name_map
from services.session_mgmt import get_session_store, MeetingSession
from routes.utils import save_upload
from services.analytics import log_event

logger = logging.getLogger(__name__)
router = APIRouter(tags=["identification"])


def _sse_event(event: str, data: dict) -> str:
    """Format a Server-Sent Event string."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/identify")
async def identify_speakers(
    request: Request,
    audio: UploadFile = File(...)
):
    """Identify speakers in a meeting recording.

    Streams Server-Sent Events with progress updates, then a final 'done' event
    containing the full result JSON.
    """
    # Save upload before generator starts (UploadFile only readable during request)
    session_store = get_session_store()
    session_store.cleanup_expired()
    meeting_id = str(uuid.uuid4())
    session_store.cleanup_previous_session(meeting_id)

    suffix = Path(audio.filename).suffix or ".wav"
    meeting_audio_path = session_store.audio_dir / f"{meeting_id}{suffix}"
    await save_upload(audio, str(meeting_audio_path))
    device_id = request.headers.get("x-device-id", "unknown")
    logger.info(f"Meeting {meeting_id}: audio saved to {meeting_audio_path}")

    async def generate():
        try:
            yield _sse_event("progress", {
                "stage": "transcribing",
                "message": "Transcribing audio (this takes a while for longer recordings)..."
            })

            logger.info("Starting transcription with diarization...")
            # Run transcription in background thread with SSE heartbeats
            # to keep the connection alive through Railway's idle timeout
            transcription_result = {}
            transcription_done = asyncio.Event()

            async def _transcribe():
                try:
                    transcription_result["value"] = await asyncio.to_thread(
                        transcribe_with_diarization, str(meeting_audio_path)
                    )
                finally:
                    transcription_done.set()

            transcription_task = asyncio.create_task(_transcribe())
            while not transcription_done.is_set():
                try:
                    await asyncio.wait_for(transcription_done.wait(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
            await transcription_task  # propagate exceptions

            result = transcription_result["value"]
            utterances = result["utterances"]

            if not utterances:
                meeting_audio_path.unlink(missing_ok=True)
                yield _sse_event("done", {
                    "success": True,
                    "meeting_id": None,
                    "speakers": [],
                    "utterances": [],
                    "message": "No speech detected in audio"
                })
                return

            unique_speakers = set(u["speaker"] for u in utterances)
            logger.info(f"Found {len(unique_speakers)} unique speakers: {unique_speakers}")

            yield _sse_event("progress", {
                "stage": "converting",
                "message": "Converting audio format..."
            })

            wav_path = session_store.audio_dir / f"{meeting_id}.wav"
            await asyncio.to_thread(convert_to_wav, str(meeting_audio_path), str(wav_path))

            yield _sse_event("progress", {
                "stage": "analyzing",
                "message": "Analyzing speaker voices..."
            })

            speaker_embeddings, speaker_segments = await asyncio.to_thread(
                extract_speaker_embeddings, unique_speakers, utterances, str(wav_path)
            )

            yield _sse_event("progress", {
                "stage": "matching",
                "message": "Matching speakers to voiceprints..."
            })

            match_results = await asyncio.to_thread(match_speakers_competitively, speaker_embeddings)

            speakers_response = []
            for speaker_id in unique_speakers:
                segments = speaker_segments.get(speaker_id, [])
                segments_dict = [{"start": s, "end": e} for s, e in segments]

                speaker_utts = [u for u in utterances if u["speaker"] == speaker_id]
                longest_utterance_ms = max(
                    (u["end"] - u["start"] for u in speaker_utts),
                    default=0
                )

                if speaker_id in match_results:
                    result_dict = match_results[speaker_id].to_dict()
                    result_dict["segments"] = segments_dict
                    result_dict["longest_utterance_ms"] = longest_utterance_ms
                    speakers_response.append(result_dict)

                    mr = match_results[speaker_id]
                    if mr.assigned_name:
                        logger.info(f"Speaker {speaker_id} -> {mr.assigned_name} ({mr.confidence.value}, score: {mr.top_match.score:.2f})")
                    else:
                        logger.info(f"Speaker {speaker_id} -> {mr.confidence.value} (needs {'confirmation' if mr.needs_confirmation else 'naming'})")
                else:
                    speakers_response.append({
                        "meeting_speaker_id": speaker_id,
                        "confidence": "low",
                        "top_score": 0.0,
                        "margin": 0.0,
                        "candidates": [],
                        "assigned_name": None,
                        "needs_confirmation": False,
                        "needs_naming": True,
                        "segments": segments_dict,
                        "longest_utterance_ms": longest_utterance_ms
                    })

            speaker_name_map = build_speaker_name_map(speakers_response, "Unknown ({sid})")

            labeled_utterances = [
                {
                    "speaker_id": utt["speaker"],
                    "speaker_name": speaker_name_map[utt["speaker"]],
                    "text": utt["text"],
                    "start": utt["start"],
                    "end": utt["end"]
                }
                for utt in utterances
            ]

            pending_speakers = {
                sr["meeting_speaker_id"]
                for sr in speakers_response
                if sr["confidence"] in ("medium", "low")
            }
            logger.info(f"Meeting {meeting_id}: {len(pending_speakers)} speakers need action: {pending_speakers}")

            session = MeetingSession(
                meeting_id=meeting_id,
                audio_path=str(wav_path),
                original_audio_path=str(meeting_audio_path),
                speakers=speakers_response,
                utterances=utterances,
                speaker_segments={k: list(v) for k, v in speaker_segments.items()},
                speaker_embeddings={k: list(v) for k, v in speaker_embeddings.items()},
                audio_duration=result["audio_duration"],
                language=result.get("language_code", "unknown"),
                pending_speakers=pending_speakers,
            )
            session_store.save(session)

            log_event("meeting.processed", device_id=device_id,
                      duration=result["audio_duration"],
                      speaker_count=len(unique_speakers))

            yield _sse_event("done", {
                "success": True,
                "meeting_id": meeting_id,
                "speakers": speakers_response,
                "utterances": labeled_utterances,
                "audio_duration": result["audio_duration"],
                "language": result.get("language_code", "unknown")
            })

        except Exception as e:
            logger.exception(f"Meeting {meeting_id}: identification failed")
            yield _sse_event("error", {"message": "Identification failed. Please try again."})
        except BaseException:
            logger.warning(f"Meeting {meeting_id}: client disconnected during identification")
        finally:
            # Clean up temp files if session was never saved
            if not session_store.get(meeting_id):
                meeting_audio_path.unlink(missing_ok=True)
                wav_file = session_store.audio_dir / f"{meeting_id}.wav"
                wav_file.unlink(missing_ok=True)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/meeting/{meeting_id}")
async def get_meeting(meeting_id: str):
    """Get meeting session data."""
    session_store = get_session_store()
    session = session_store.get(meeting_id)

    if session is None:
        raise HTTPException(status_code=404, detail="Meeting session not found or expired")

    return {
        "success": True,
        "meeting_id": meeting_id,
        "speakers": session.speakers,
        "audio_duration": session.audio_duration,
        "language": session.language
    }


@router.get("/meeting/{meeting_id}/speaker/{speaker_id}/clip")
async def get_speaker_clip(meeting_id: str, speaker_id: str):
    """Return audio clip of speaker's longest utterance (2-5 seconds)."""
    import config

    session_store = get_session_store()
    session = session_store.get(meeting_id)

    if session is None:
        raise HTTPException(status_code=404, detail="Meeting session not found or expired")

    # Find all utterances for this speaker and pick the longest
    speaker_utts = [u for u in session.utterances if u["speaker"] == speaker_id]
    if not speaker_utts:
        raise HTTPException(status_code=404, detail="Speaker not found in meeting")

    longest_utt = max(speaker_utts, key=lambda u: u["end"] - u["start"])
    duration_ms = longest_utt["end"] - longest_utt["start"]

    if duration_ms < config.CLIP_MIN_DURATION_MS:
        raise HTTPException(status_code=400, detail="Audio too short for playback")

    audio_path = session.audio_path
    if not Path(audio_path).exists():
        raise HTTPException(status_code=404, detail="Audio file no longer available")

    # Cap at max duration
    start_ms = longest_utt["start"]
    end_ms = min(longest_utt["end"], start_ms + config.CLIP_MAX_DURATION_MS)

    clip_path = str(session_store.audio_dir / f"{meeting_id}_{speaker_id}_clip.wav")

    try:
        await asyncio.to_thread(extract_segment, audio_path, start_ms, end_ms, clip_path)
    except Exception as e:
        logger.error(f"Failed to extract speaker clip: {e}")
        raise HTTPException(status_code=500, detail="Failed to extract audio clip")

    return FileResponse(clip_path, media_type="audio/wav", filename=f"speaker_{speaker_id}_clip.wav")
