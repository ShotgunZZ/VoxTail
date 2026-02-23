# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Open-Source Release Status

This is the **public release copy** of VoxTail, prepared for open-source on GitHub. See [docs/RELEASE_PLAN.md](docs/RELEASE_PLAN.md) for what was done, remaining manual steps (push to GitHub, Railway template, deploy button URL), and design decisions.

## Project Overview

VoxTail is a speaker recognition web app that enrolls speakers via voice samples and identifies who said what in meeting recordings. Uses SpeechBrain ECAPA-TDNN for 192-dim voice embeddings, Pinecone for vector search, and AssemblyAI for transcription + diarization.

## Development Commands

```bash
# Environment setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
brew install ffmpeg  # macOS - required for audio processing

# Configure API keys
cp .env.example .env
# Edit .env: PINECONE_API_KEY, PINECONE_INDEX_NAME, ASSEMBLYAI_API_KEY, OPENAI_API_KEY

# One-time Pinecone index setup (192 dimensions, cosine similarity)
python setup_pinecone.py

# Run the app
python app.py
# Access at http://localhost:8000
```

## Architecture

### Backend Structure

```
app.py                    # FastAPI entry point - mounts routers, startup sync
routes/
├── __init__.py           # Combines all routers under /api prefix
├── enrollment.py         # POST /api/enroll, /api/enroll-from-meeting
├── identification.py     # POST /api/identify (SSE stream), GET /api/meeting/{id}, GET /api/meeting/{id}/speaker/{sid}/clip
├── speakers.py           # GET/DELETE /api/speakers, POST /api/speakers/sync
├── confirmation.py       # POST /api/confirm-speaker, /api/meeting/{id}/cleanup
└── utils.py              # temp_file context manager, save_upload helper
services/
├── enrollment_svc.py     # Business logic: enroll_speaker, validate_audio_duration
├── session_mgmt.py       # MeetingSession dataclass, SessionStore class
├── speaker_encoder.py    # ECAPA-TDNN model wrapper (lazy-loaded singleton)
├── pinecone_db.py        # Vector DB: add_speaker_sample, find_speaker_top_k
├── matching.py           # Competitive matching: HIGH/MEDIUM/LOW confidence
├── assemblyai_svc.py     # Transcription + speaker diarization
├── audio.py              # convert_to_wav, extract_segment, stitch_segments
├── file_utils.py         # temp_file context manager (services-layer, used by audio_segmentation)
├── audio_segmentation.py # Segment selection + embedding extraction per speaker
├── vad_service.py        # Silero VAD — strips silence before embedding extraction
├── speaker_mapping.py    # Shared speaker name mapping utility
├── llm_summary.py        # OpenAI GPT integration for meeting summaries
└── analytics.py          # Anonymous usage analytics — structured log events for Railway
config.py                 # All thresholds and parameters (with validate())
```

### Frontend Structure

```
static/
├── index.html            # HTML only (~65 lines)
├── css/
│   ├── tokens.css        # CSS custom properties (design tokens)
│   ├── base.css          # Reset, buttons, forms, drop zone, spinner
│   ├── speaker-cards.css # Speaker cards, confidence badges, toggles
│   ├── transcript.css    # Transcript layout, utterances, avatars
│   ├── summary.css       # Summary cards, accordion, copy buttons
│   ├── history.css       # History cards, settings section, clear button
│   └── layout.css        # Desktop/mobile media queries (loaded last)
└── js/
    ├── main.js           # Entry point, screen navigation, PWA registration
    ├── api-client.js     # API fetch wrapper (includes X-Device-ID header, returns raw Response for SSE endpoints)
    ├── state.js          # Global state management
    ├── enrollment.js     # Enrollment UI component
    ├── identification.js # Orchestrator: file upload, recording, delegates to sub-modules
    ├── speaker-cards.js  # Speaker card orchestrator, audio playback
    ├── speaker-utils.js  # Speaker colors, initials helper
    ├── card-renderers.js # Speaker card HTML rendering (high/medium/low/decided)
    ├── pending-decisions.js # Deferred speaker decisions with undo support
    ├── transcript.js     # Transcript rendering with speaker avatars
    ├── summary.js        # AI summary generation, section rendering, copy-to-clipboard
    ├── history.js        # IndexedDB meeting history — save, render, delete, prune (max 50)
    ├── recorder.js       # MediaRecorder API wrapper
    └── utils.js          # escapeHtml, formatTime, formatDuration
```

### Key Data Flows

**Enrollment**: Upload audio → validate duration (min 5s) → convert to 16kHz WAV → VAD speech check (min 3s actual speech) → extract 192-dim embedding → weighted average with existing (if any) → upsert to Pinecone + speakers.json

**Identification**: Upload meeting → SSE stream begins → AssemblyAI diarization → for each speaker: stitch utterances (target 20s, use single if ≥10s) → extract embedding → competitive matching → stream labeled transcript with confidence levels. Progress events: `transcribing` → `converting` → `analyzing` → `matching` → `done`/`error`.

### Confidence Levels (services/matching.py)

- **HIGH**: Auto-assigned (score ≥ 0.55, margin ≥ 0.10)
- **MEDIUM**: Needs confirmation (score ≥ 0.55, margin < 0.10)
- **LOW**: Unknown speaker (score < 0.55)

Competitive assignment uses Hungarian algorithm (scipy `linear_sum_assignment`) for optimal bipartite matching — prevents suboptimal greedy cascading in multi-speaker meetings.

### Critical Implementation Details

**Embedding Updates** (services/pinecone_db.py): Early samples use weighted mean (`(old * old_weight + new * weight) / total`). After `EMA_MIN_SAMPLES` (4), switches to Exponential Moving Average: `(1-α) * old + α * new` where α=0.3. This lets voiceprints adapt to voice changes over time. Dedicated enrollment uses weight=2, meeting audio uses weight=1.

**Voice Activity Detection** (services/vad_service.py): Silero VAD strips silence from audio before embedding extraction in `speaker_encoder.py`. Produces 5-10% cleaner embeddings by removing silence, breathing, and filler. The VAD model (~2MB) is lazy-loaded on first use.

**Session Management** (services/session_mgmt.py): `SessionStore` holds meeting sessions in-memory with 1-hour TTL. Sessions store audio paths, speaker embeddings, and segments for later enrollment from meeting audio.

**Auto-Cleanup** (services/session_mgmt.py): Audio files are automatically deleted when all MEDIUM/LOW confidence speakers have been handled AND the AI summary has been generated. The `MeetingSession` tracks `pending_speakers` (those needing action) and `handled_speakers` (those processed). Cleanup is deferred if `session.summary is None` so the session stays alive for summary generation after speaker confirmation. Fallback: uploading a new file cleans up the previous session, plus 1-hour TTL safety net.

**Deferred Speaker Decisions** (static/js/speaker-cards.js): Confirm/enroll actions are local-only until "Confirm Speakers" is clicked. Decisions are stored in a `pendingDecisions` Map with undo support. `commitPendingDecisions()` flushes all decisions to the backend APIs on final confirmation. The progress bar uses a snapshot of the original non-high speaker count as the denominator.

**Summary Timing** (static/js/identification.js): AI summary is generated AFTER speaker confirmation, not before. When MEDIUM/LOW speakers exist, `commitPendingDecisions()` sends all decisions to the backend, then summary triggers. When all speakers are HIGH confidence, summary triggers immediately on the results screen. The `confirm-speaker` and `enroll-from-meeting` endpoints write `assigned_name` back to `session.speakers[]` so the summary uses confirmed names.

**SSE Streaming** (routes/identification.py → static/js/identification.js): `POST /api/identify` returns a `StreamingResponse` (`text/event-stream`) from an async generator. All blocking calls (`transcribe_with_diarization`, `convert_to_wav`, `extract_speaker_embeddings`, `match_speakers_competitively`) run in background threads via `asyncio.to_thread()` to avoid blocking the event loop. During transcription (30-120+ seconds), SSE heartbeat comments (`: heartbeat\n\n`) are sent every 15 seconds to keep the connection alive through Railway's reverse proxy idle timeout. The generator catches `BaseException` (including `GeneratorExit`) to log client disconnects and has a `finally` block for temp file cleanup. Frontend `readSSEStream()` parses the stream and updates the UI with real-time progress messages. `api-client.js` returns the raw `Response` object for this endpoint (not parsed JSON).

**Speaker Audio Clips** (routes/identification.py): `GET /api/meeting/{id}/speaker/{speaker_id}/clip` returns a WAV audio clip of the speaker's longest utterance (2–5s, configured via `CLIP_MIN_DURATION_MS` / `CLIP_MAX_DURATION_MS` in config.py). Used by speaker cards for audio playback during confirmation.

**Stitching Parameters** (config.py): When longest utterance < 10s, stitch multiple utterances (min 2s each) targeting 20s total, max 5 segments.

**Meeting History** (static/js/history.js): Meetings are saved to browser-local IndexedDB after summary generation. Stores up to 50 entries with auto-pruning. The Settings screen (`screenSettings`) displays history as accordion cards with executive summary, action items, decisions, and topics. Clear-all button available in the settings section.

**Anonymous Analytics** (services/analytics.py): Structured JSON log lines prefixed with `[ANALYTICS]`, captured by Railway's built-in log system. Events: `meeting.processed` (duration, speaker_count), `summary.generated` (speaker names), `speaker.enrolled`. Each event includes an anonymous `device_id` from the `X-Device-ID` header.

**Device ID** (static/js/main.js → api-client.js): A persistent anonymous UUID generated via `crypto.randomUUID()` on first visit, stored in `localStorage` as `voxtail_device_id`. Sent as `X-Device-ID` header on all API requests.

## API Endpoints

- `POST /api/enroll` - Enroll speaker (form: name, audio)
- `POST /api/enroll-from-meeting` - Enroll from meeting segments
- `POST /api/identify` - Identify speakers via SSE stream (progress events → done with meeting_id)
- `GET /api/meeting/{id}` - Get meeting session data
- `GET /api/meeting/{id}/speaker/{speaker_id}/clip` - Audio clip of speaker's longest utterance (2-5s WAV)
- `POST /api/meeting/{id}/cleanup` - Clean up session
- `POST /api/meeting/{id}/summary` - Generate AI summary (executive summary, action items, decisions, topics)
- `GET /api/meeting/{id}/summary` - Get cached summary
- `GET /api/speakers` - List enrolled speakers
- `DELETE /api/speakers/{name}` - Delete speaker
- `POST /api/speakers/sync` - Sync from Pinecone
- `POST /api/confirm-speaker` - Confirm MEDIUM confidence match

## Important Notes

- Pinecone is source of truth; `speakers.json` syncs on startup
- AssemblyAI costs ~$0.90/hour of audio
- Model runs on CPU (device="cpu" in speaker_encoder.py)
- Frontend uses ES modules with `escapeHtml()` for XSS prevention
- **Service Worker Caching**: `static/sw.js` uses cache-first. After changing any file in `static/`, bump `CACHE_NAME` in `sw.js` (currently `v32`). The browser auto-reloads when the new SW activates. `app.py` serves `sw.js` with `Cache-Control: no-cache` so browsers always check for updates.

