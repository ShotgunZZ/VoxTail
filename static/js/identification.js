/**
 * Identification UI orchestrator for VoxTail
 *
 * Coordinates file upload, recording, and delegates to:
 * - speaker-cards.js (speaker card rendering & interactions)
 * - transcript.js (transcript rendering)
 * - summary.js (AI summary generation & display)
 */

import { state, setMeetingState } from './state.js';
import { identifySpeakers } from './api-client.js';
import { escapeHtml, formatDuration } from './utils.js';
import { loadSpeakers } from './enrollment.js';
import * as recorder from './recorder.js';
import { navigateTo } from './main.js';
import { initSpeakerCards, renderSpeakerSummary, resetHandledCount, commitPendingDecisions } from './speaker-cards.js';
import { initTranscript, renderTranscript, renderMeetingInfo } from './transcript.js';
import { initSummary, handleGenerateSummary } from './summary.js';

// DOM Elements
let identifyDropZone, identifyFileInput, identifyFileInfo, identifyBtn, identifyStatus;
let recordBtn, recordTimer, recordingControls, recordCta;

/**
 * Initialize identification UI
 */
export function initIdentification() {
    identifyDropZone = document.getElementById('identifyDropZone');
    identifyFileInput = document.getElementById('identifyFile');
    identifyFileInfo = document.getElementById('identifyFileInfo');
    identifyBtn = document.getElementById('identifyBtn');
    identifyStatus = document.getElementById('identifyStatus');

    // Recording UI elements
    recordBtn = document.getElementById('recordBtn');
    recordTimer = document.getElementById('recordTimer');
    recordingControls = document.getElementById('recordingControls');
    recordCta = document.getElementById('recordCta');

    // Initialize sub-modules
    initSpeakerCards({
        speakerSummaryEl: document.getElementById('speakerSummary'),
        progressBarEl: document.getElementById('progressBar'),
        progressTextEl: document.getElementById('progressText'),
        confirmSpeakersBtnEl: document.getElementById('confirmSpeakersBtn'),
    }, {
        onSpeakerChanged: renderTranscript,
    });

    initTranscript({
        transcriptElement: document.getElementById('transcript'),
    });

    initSummary({
        generateSummaryBtnEl: document.getElementById('generateSummaryBtn'),
        summaryStatusEl: document.getElementById('summaryStatus'),
        summaryContentEl: document.getElementById('summaryContent'),
    });

    setupDropZone();
    setupRecording();
    setupScreenActions();
    identifyBtn.addEventListener('click', handleIdentify);
}

/**
 * Setup confirm/skip actions on Speaker ID screen
 */
function setupScreenActions() {
    const confirmSpeakersBtn = document.getElementById('confirmSpeakersBtn');
    if (confirmSpeakersBtn) {
        confirmSpeakersBtn.addEventListener('click', async () => {
            confirmSpeakersBtn.disabled = true;
            confirmSpeakersBtn.textContent = 'Saving...';
            try {
                await commitPendingDecisions();
                // Reset button before navigating (in case user returns)
                confirmSpeakersBtn.textContent = 'Confirm Speakers';
                confirmSpeakersBtn.disabled = false;
                navigateTo('screenResults');
                renderMeetingInfo();
                handleGenerateSummary();
            } catch (error) {
                console.error('Failed to commit speaker decisions:', error);
                alert(error.message);
                confirmSpeakersBtn.disabled = false;
                confirmSpeakersBtn.textContent = 'Confirm Speakers';
            }
        });
    }
}

/**
 * Setup live recording functionality
 */
function setupRecording() {
    if (!recordBtn) return;

    if (!recorder.isRecordingSupported()) {
        recordBtn.disabled = true;
        recordBtn.title = 'Recording not supported in this browser';
        return;
    }

    recorder.onRecordingStart(() => {
        recordBtn.classList.add('recording');
        if (recordCta) recordCta.textContent = 'Tap to Stop';
        recordingControls.classList.remove('hidden');
        identifyBtn.disabled = true;
    });

    recorder.onRecordingStop((audioBlob, duration) => {
        recordBtn.classList.remove('recording');
        if (recordCta) recordCta.textContent = 'Tap to Record';
        recordingControls.classList.add('hidden');

        // Show upload section so identify button is visible on mobile
        const uploadSection = document.getElementById('uploadSection');
        if (uploadSection) uploadSection.classList.remove('hidden');

        const extension = recorder.getFileExtension();
        const fileName = `recording_${Date.now()}.${extension}`;
        const file = new File([audioBlob], fileName, { type: audioBlob.type });

        handleFileSelect(file);

        identifyStatus.className = 'status success';
        identifyStatus.textContent = `Recording saved: ${formatDuration(duration * 1000)}. Click "Identify Speakers" to process.`;
    });

    recorder.onRecordingError((error) => {
        recordBtn.classList.remove('recording');
        if (recordCta) recordCta.textContent = 'Tap to Record';
        recordingControls.classList.add('hidden');

        identifyStatus.className = 'status error';
        identifyStatus.textContent = `Recording error: ${error.message || error}`;
    });

    recorder.onTimerUpdate((formattedTime) => {
        if (recordTimer) {
            recordTimer.textContent = formattedTime;
        }
    });

    recordBtn.addEventListener('click', async () => {
        if (recorder.isRecording()) {
            recorder.stopRecording();
        } else {
            const started = await recorder.startRecording();
            if (!started) {
                identifyStatus.className = 'status error';
                identifyStatus.textContent = 'Microphone access denied. Please allow microphone access to record.';
            }
        }
    });
}

/**
 * Setup drop zone for audio file selection
 */
function setupDropZone() {
    identifyDropZone.addEventListener('click', () => identifyFileInput.click());

    identifyDropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        identifyDropZone.classList.add('drag-over');
    });

    identifyDropZone.addEventListener('dragleave', () => {
        identifyDropZone.classList.remove('drag-over');
    });

    identifyDropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        identifyDropZone.classList.remove('drag-over');
        const file = e.dataTransfer.files[0];
        if (file) handleFileSelect(file);
    });

    identifyFileInput.addEventListener('change', () => {
        const file = identifyFileInput.files[0];
        if (file) handleFileSelect(file);
    });
}

/**
 * Handle file selection
 */
function handleFileSelect(file) {
    state.identifyFileSelected = file;
    identifyFileInfo.textContent = `Selected: ${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`;
    identifyFileInfo.style.display = 'block';
    identifyBtn.disabled = false;
}

/**
 * Read an SSE stream from a fetch Response.
 * Calls onEvent(eventType, parsedData) for each event.
 * Returns the parsed data from the 'done' event.
 * Throws on 'error' events.
 */
async function readSSEStream(response, onEvent) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let result = null;

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Process complete events (separated by double newline)
        const parts = buffer.split('\n\n');
        buffer = parts.pop(); // Keep incomplete part in buffer

        for (const part of parts) {
            if (!part.trim()) continue;

            let eventType = 'message';
            let dataStr = '';

            for (const line of part.split('\n')) {
                if (line.startsWith('event: ')) {
                    eventType = line.slice(7);
                } else if (line.startsWith('data: ')) {
                    dataStr = line.slice(6);
                }
            }

            if (!dataStr) continue;
            let payload;
            try {
                payload = JSON.parse(dataStr);
            } catch {
                throw new Error('Connection lost during processing. Please try again.');
            }

            if (eventType === 'error') {
                throw new Error(payload.message || 'Identification failed');
            }

            if (eventType === 'done') {
                result = payload;
            }

            onEvent(eventType, payload);
        }
    }

    if (!result) {
        throw new Error('Stream ended without result');
    }
    return result;
}

/**
 * Handle identify button click
 */
async function handleIdentify() {
    if (!state.identifyFileSelected) return;

    identifyBtn.disabled = true;
    identifyStatus.className = 'status loading';
    identifyStatus.innerHTML = '<span class="loading-spinner"></span>Uploading audio...';

    try {
        const response = await identifySpeakers(state.identifyFileSelected);

        // Parse SSE stream
        const data = await readSSEStream(response, (event, payload) => {
            if (event === 'progress') {
                identifyStatus.innerHTML = `<span class="loading-spinner"></span>${escapeHtml(payload.message)}`;
            }
        });

        // Handle no-speech case
        if (!data.meeting_id) {
            identifyStatus.className = 'status';
            identifyStatus.textContent = data.message || 'No speech detected in audio';
            identifyBtn.disabled = false;
            return;
        }

        setMeetingState(data.meeting_id, data.speakers, data.utterances, data.audio_duration);

        identifyStatus.className = 'status success';
        const duration = data.audio_duration ? ` (${formatDuration(data.audio_duration)})` : '';
        const language = data.language ? ` | Language: ${data.language}` : '';

        const highCount = data.speakers.filter(s => s.confidence === 'high').length;
        const mediumCount = data.speakers.filter(s => s.confidence === 'medium').length;
        const lowCount = data.speakers.filter(s => s.confidence === 'low').length;

        identifyStatus.textContent = `Found ${data.speakers.length} speakers: ${highCount} identified, ${mediumCount} need confirmation, ${lowCount} unknown${duration}${language}`;

        // Reset progress
        resetHandledCount();

        // Render results
        renderSpeakerSummary();
        renderTranscript();

        // Navigate to Speaker ID screen (mobile)
        const needsAction = mediumCount + lowCount;
        if (needsAction > 0) {
            navigateTo('screenSpeakerID');
        } else {
            // All speakers are HIGH confidence — no confirmation needed
            navigateTo('screenResults');
            renderMeetingInfo();
            handleGenerateSummary();
        }

    } catch (error) {
        identifyStatus.className = 'status error';
        if (error.message.includes('being processed')) {
            identifyStatus.textContent = 'Another meeting is being processed. Please wait a moment and try again.';
        } else {
            identifyStatus.textContent = error.message;
        }
    }
    identifyBtn.disabled = false;
}

// Re-export for external consumers
export { renderSpeakerSummary } from './speaker-cards.js';
export { renderTranscript } from './transcript.js';
