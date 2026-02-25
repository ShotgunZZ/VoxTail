# Port Speech Quality Gate + VAD-Cleaned Clips

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Bring VoxTail open-source release to parity with the private version on speech quality gate and VAD-cleaned playback clips.

**Architecture:** Direct copy + patch from `speaker-recognition/` (private) into `voxtail-release/` (open source). Two features: (1) speech quality flag that propagates from segment extraction through identification to frontend, blocking enrollment/reinforcement for low-quality speakers; (2) VAD-cleaned playback clips that stitch all identification segments and strip silence before serving.

**Tech Stack:** Python/FastAPI backend, Silero VAD, vanilla JS frontend

---

### Task 1: Add `MIN_IDENTIFICATION_SPEECH_MS` to config

**Files:**
- Modify: `voxtail-release/config.py:33-37`

**Step 1: Add the config constant**

After `STITCHING_MAX_COUNT = 5` (line 33), add:

```python
# Minimum speech duration for reliable identification (below this = quality warning)
MIN_IDENTIFICATION_SPEECH_MS = 8000
```

This should go before `# Speaker clip playback parameters`.

---

### Task 2: Add `strip_silence_file()` to VAD service

**Files:**
- Modify: `voxtail-release/services/vad_service.py:67-89`

**Step 1: Add the function**

Insert `strip_silence_file()` between `get_speech_duration_ms()` and `strip_silence()`:

```python
def strip_silence_file(input_path: str, output_path: str):
    """Strip silence from a WAV file and save the cleaned audio.

    Loads audio, runs strip_silence() to remove non-speech portions,
    and writes the result as 16kHz mono WAV.

    Args:
        input_path: Path to input WAV file
        output_path: Path to save cleaned WAV file
    """
    data, sample_rate = sf.read(input_path, dtype="float32")
    audio_tensor = torch.from_numpy(data)
    if audio_tensor.dim() > 1:
        audio_tensor = audio_tensor.mean(dim=1)
    if sample_rate != 16000:
        import torchaudio.functional as F
        audio_tensor = F.resample(audio_tensor, sample_rate, 16000)
        sample_rate = 16000
    cleaned = strip_silence(audio_tensor, sample_rate)
    sf.write(output_path, cleaned.numpy(), sample_rate)
```

---

### Task 3: Update `audio_segmentation.py` — 3-tuple return with speech quality

**Files:**
- Modify: `voxtail-release/services/audio_segmentation.py`

**Step 1: Update `select_segments_for_speaker` to return 3-tuple**

Change return type hint (line 22) from:
```python
) -> Tuple[List[Tuple[int, int]], Optional[str]]:
```
to:
```python
) -> Tuple[List[Tuple[int, int]], Optional[str], float]:
```

Update docstring Returns to:
```
        Tuple of (segments list, temp_wav_path or None, speech_ms).
        temp_wav_path is the extracted audio ready for embedding, caller must delete it.
```

Change early return (line 52) from `return [], None` to `return [], None, 0.0`

Add `speech_ms` tracking — the variable already exists (line 57), it just needs to be returned.

Remove the raw duration cap check (lines 71-72):
```python
        # Check if adding this would exceed raw duration cap
        if total_raw_ms + utt_duration > config.STITCHING_MAX_SINGLE_MS and segments:
            break
```
(This matches the private version which uses speech-duration-based budgeting instead.)

Change the `if not segments` return (line 109) from `return [], None` to `return [], None, 0.0`

Change final return (line 116) from `return segments, temp_path` to `return segments, temp_path, speech_ms`

**Step 2: Update `extract_speaker_embeddings` to return 3-tuple with `speech_quality`**

Change return type hint (line 123) from:
```python
) -> Tuple[Dict[str, List[float]], Dict[str, List[Tuple[int, int]]]]:
```
to:
```python
) -> Tuple[Dict[str, List[float]], Dict[str, List[Tuple[int, int]]], Dict[str, dict]]:
```

Update docstring Returns to:
```
        Tuple of (speaker_embeddings dict, speaker_segments dict, speech_quality dict).
```

Add `speech_quality = {}` after `speaker_segments = {}` (line 135).

Update the unpack (line 143) from:
```python
        segments, segment_path = select_segments_for_speaker(
```
to:
```python
        segments, segment_path, speech_ms = select_segments_for_speaker(
```

After `speaker_segments[speaker_id] = segments` (line 146), add:
```python
        speech_quality[speaker_id] = {
            "speech_ms": speech_ms,
            "low_quality": speech_ms < config.MIN_IDENTIFICATION_SPEECH_MS
        }
```

Before `get_embedding()` call, add logging:
```python
            raw_duration = sum(end - start for start, end in segments) / 1000
            logger.info(
                "Speaker %s: extracting embedding from VAD-cleaned audio (%d segments, %.1fs raw)",
                speaker_id, len(segments), raw_duration
            )
```

Before the final return, add:
```python
    logger.info("Extracted embeddings for %d/%d speakers", len(speaker_embeddings), len(unique_speakers))
```

Change final return from `return speaker_embeddings, speaker_segments` to `return speaker_embeddings, speaker_segments, speech_quality`

---

### Task 4: Update `routes/identification.py` — quality fields + VAD-cleaned clips + logging

**Files:**
- Modify: `voxtail-release/routes/identification.py`

**Step 1: Update imports (line 12)**

Change:
```python
from services.audio import convert_to_wav, extract_segment
```
to:
```python
from services.audio import convert_to_wav, extract_segment, stitch_segments
```

**Step 2: Add identification logging**

After `async def generate():` / `try:` (line 52), add:
```python
            logger.info(f"Meeting {meeting_id}: starting speaker identification")
```

**Step 3: Unpack speech_quality from extract_speaker_embeddings**

Change line 110 from:
```python
            speaker_embeddings, speaker_segments = await asyncio.to_thread(
```
to:
```python
            speaker_embeddings, speaker_segments, speech_quality = await asyncio.to_thread(
```

**Step 4: Add quality fields to speaker response dicts**

In the `if speaker_id in match_results:` block, after `result_dict["longest_utterance_ms"] = longest_utterance_ms` (line 135), add:
```python
                    sq = speech_quality.get(speaker_id, {})
                    result_dict["low_speech_quality"] = sq.get("low_quality", False)
                    result_dict["speech_duration_ms"] = sq.get("speech_ms", 0)
```

In the `else` block (the fallback dict, around line 154), add these two fields after `"longest_utterance_ms": longest_utterance_ms`:
```python
                        "low_speech_quality": speech_quality.get(speaker_id, {}).get("low_quality", False),
                        "speech_duration_ms": speech_quality.get(speaker_id, {}).get("speech_ms", 0),
```

**Step 5: Replace the entire clip endpoint**

Replace `get_speaker_clip` (lines 241-279) with:

```python
@router.get("/meeting/{meeting_id}/speaker/{speaker_id}/clip")
async def get_speaker_clip(meeting_id: str, speaker_id: str):
    """Return VAD-cleaned audio clip from the speaker's identification segments (up to 5s)."""
    import config
    from services.vad_service import strip_silence_file

    session_store = get_session_store()
    session = session_store.get(meeting_id)

    if session is None:
        raise HTTPException(status_code=404, detail="Meeting session not found or expired")

    segments = session.speaker_segments.get(speaker_id, [])
    if not segments:
        raise HTTPException(status_code=404, detail="Speaker not found in meeting")

    audio_path = session.audio_path
    if not Path(audio_path).exists():
        raise HTTPException(status_code=404, detail="Audio file no longer available")

    raw_clip_path = str(session_store.audio_dir / f"{meeting_id}_{speaker_id}_clip_raw.wav")
    clip_path = str(session_store.audio_dir / f"{meeting_id}_{speaker_id}_clip.wav")

    try:
        # Stitch all identification segments (same audio used for embedding)
        if len(segments) == 1:
            start_ms, end_ms = segments[0]
            await asyncio.to_thread(extract_segment, audio_path, start_ms, end_ms, raw_clip_path)
        else:
            await asyncio.to_thread(stitch_segments, audio_path, segments, raw_clip_path)

        # Strip silence using VAD (same processing as identification pipeline)
        await asyncio.to_thread(strip_silence_file, raw_clip_path, clip_path)

        # Cap at configured max duration
        from services.audio import load_wav
        clip_audio = await asyncio.to_thread(load_wav, clip_path)
        if len(clip_audio) > config.CLIP_MAX_DURATION_MS:
            clip_audio = clip_audio[:config.CLIP_MAX_DURATION_MS]
            clip_audio = clip_audio.set_frame_rate(16000).set_channels(1)
            await asyncio.to_thread(clip_audio.export, clip_path, format="wav")
    except Exception as e:
        logger.error(f"Failed to extract speaker clip: {e}")
        raise HTTPException(status_code=500, detail="Failed to extract audio clip")
    finally:
        Path(raw_clip_path).unlink(missing_ok=True)

    return FileResponse(clip_path, media_type="audio/wav", filename=f"speaker_{speaker_id}_clip.wav")
```

---

### Task 5: Update `routes/enrollment.py` — block enrollment for low-quality speakers

**Files:**
- Modify: `voxtail-release/routes/enrollment.py:68-71`

**Step 1: Add enrollment block**

After `if not segments:` check (line 71), add:

```python
    # Block enrollment for low speech quality speakers
    for sr in session.speakers:
        if sr["meeting_speaker_id"] == speaker_id and sr.get("low_speech_quality"):
            raise HTTPException(
                status_code=400,
                detail="Cannot enroll — not enough speech detected for a reliable voiceprint"
            )
```

---

### Task 6: Update `routes/confirmation.py` — use quality flag for reinforcement

**Files:**
- Modify: `voxtail-release/routes/confirmation.py:53-73`

**Step 1: Replace the inline duration check with quality flag check**

Replace the reinforcement block (lines 53-73):
```python
    # Optionally enroll to reinforce the speaker model
    if enroll and speaker_id in session.speaker_embeddings:
        segments = session.speaker_segments[speaker_id]
        total_duration = sum(end - start for start, end in segments)

        # Only reinforce if sufficient audio (>= 10s for quality)
        if total_duration >= 10000:
```

With:
```python
    # Optionally enroll to reinforce the speaker model
    if enroll and speaker_id in session.speaker_embeddings:
        # Skip reinforcement for low speech quality speakers
        speaker_data = next((sr for sr in session.speakers if sr["meeting_speaker_id"] == speaker_id), None)
        if speaker_data and not speaker_data.get("low_speech_quality"):
```

And change the else log message from:
```python
            logger.info(f"Skipped reinforcement for '{confirmed_name}' - insufficient audio ({total_duration/1000:.1f}s)")
```
to:
```python
            logger.info(f"Skipped reinforcement for '{confirmed_name}' - low speech quality")
```

---

### Task 7: Update `static/js/card-renderers.js` — quality warnings + hide controls

**Files:**
- Modify: `voxtail-release/static/js/card-renderers.js`

**Step 1: Copy the private version's card-renderers.js**

Replace the entire file content with the private version from `speaker-recognition/static/js/card-renderers.js`. This adds:
- `low_speech_quality` warning div in medium cards (after quote)
- `low_speech_quality` warning div in low cards (after quote)
- Conditional hide of rename button for low-quality medium speakers
- Conditional hide of enroll toggle for low-quality medium speakers
- Conditional hide of name input + enroll for low-quality low speakers
- Different "not enough speech" message for low-quality speakers

---

### Task 8: Update `static/css/speaker-cards.css` — add `.card-warning` style

**Files:**
- Modify: `voxtail-release/static/css/speaker-cards.css`

**Step 1: Add the card-warning style**

After `.audio-insufficient` block (end of file), add:

```css
.card-warning {
    color: var(--orange);
    font-size: 0.8rem;
    margin-top: 0.25rem;
}
```

---

### Task 9: Bump service worker cache

**Files:**
- Modify: `voxtail-release/static/sw.js:2`

**Step 1: Bump cache version**

Change `voiceid-v32` to `voiceid-v33`.

---

### Task 10: Update `README.md` — document new features

**Files:**
- Modify: `voxtail-release/README.md`

**Step 1: Update Features section**

Add two new feature bullets after "Audio Clip Playback":
```markdown
- **Speech Quality Detection** — Warns when speakers have insufficient audio; blocks unreliable enrollments
- **VAD-Cleaned Clips** — Playback clips are processed through Voice Activity Detection to remove silence and background noise
```

**Step 2: Update Audio Clip Playback bullet**

Change:
```markdown
- **Audio Clip Playback** — Listen to speaker clips to verify identity
```
to:
```markdown
- **Audio Clip Playback** — Listen to VAD-cleaned speaker clips to verify identity
```

---

### Task 11: Update `CLAUDE.md` — document new features

**Files:**
- Modify: `voxtail-release/CLAUDE.md`

**Step 1: Update Speaker Audio Clips section**

Replace:
```
**Speaker Audio Clips** (routes/identification.py): `GET /api/meeting/{id}/speaker/{speaker_id}/clip` returns a WAV audio clip of the speaker's longest utterance (2–5s, configured via `CLIP_MIN_DURATION_MS` / `CLIP_MAX_DURATION_MS` in config.py). Used by speaker cards for audio playback during confirmation.
```
with:
```
**Speaker Audio Clips** (routes/identification.py): `GET /api/meeting/{id}/speaker/{speaker_id}/clip` returns a VAD-cleaned WAV audio clip from the speaker's identification segments (up to 5s, configured via `CLIP_MAX_DURATION_MS` in config.py). All identification segments are stitched together, then `strip_silence_file()` removes silence/pauses using Silero VAD — so playback matches the clean speech the identification model analyzed. Used by speaker cards for audio playback during confirmation.
```

**Step 2: Update Stitching Parameters section**

Replace:
```
**Stitching Parameters** (config.py): When longest utterance < 10s, stitch multiple utterances (min 2s each) targeting 20s total, max 5 segments.
```
with:
```
**Stitching Parameters** (config.py): Segment selection uses speech duration as the budget (not raw duration). Individual utterances capped at 20s, loop adds utterances until 10s of speech accumulated or 5 segments used. Speakers with < 8s speech (`MIN_IDENTIFICATION_SPEECH_MS`) after selection get `low_speech_quality` flag — still matched but enrollment/reinforcement blocked and UI shows warning.
```

**Step 3: Update Service Worker cache version note**

Change `currently `v32`` to `currently `v33``.

---

### Task 12: Verification — diff against private version

**Step 1: Run diff on key files to confirm only intentional differences remain**

```bash
cd "/Users/shaunz/Documents/Projects/AI Notetaker"
diff voxtail-release/config.py speaker-recognition/config.py
diff voxtail-release/services/vad_service.py speaker-recognition/services/vad_service.py
diff voxtail-release/services/audio_segmentation.py speaker-recognition/services/audio_segmentation.py
diff voxtail-release/routes/identification.py speaker-recognition/routes/identification.py
diff voxtail-release/routes/enrollment.py speaker-recognition/routes/enrollment.py
diff voxtail-release/routes/confirmation.py speaker-recognition/routes/confirmation.py
diff voxtail-release/static/js/card-renderers.js speaker-recognition/static/js/card-renderers.js
```

Expected: Only differences should be private-only features (access control, sharing, invite code).
