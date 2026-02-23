/**
 * Audio Recorder Module
 * Handles live audio recording using MediaRecorder API
 */

let mediaRecorder = null;
let audioChunks = [];
let recordingStartTime = null;
let timerInterval = null;
let recordedMimeType = '';

// Callbacks
let onRecordingStartCallback = null;
let onRecordingStopCallback = null;
let onRecordingErrorCallback = null;
let onTimerUpdateCallback = null;

/**
 * Check if recording is supported
 */
export function isRecordingSupported() {
    return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder);
}

/**
 * Get preferred MIME type for recording
 */
function getPreferredMimeType() {
    const types = [
        'audio/webm;codecs=opus',
        'audio/webm',
        'audio/ogg;codecs=opus',
        'audio/mp4',
        'audio/wav'
    ];

    for (const type of types) {
        if (MediaRecorder.isTypeSupported(type)) {
            return type;
        }
    }
    return '';  // Let browser choose
}

/**
 * Format seconds to MM:SS
 */
function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

/**
 * Start the recording timer
 */
function startTimer() {
    recordingStartTime = Date.now();
    timerInterval = setInterval(() => {
        const elapsed = (Date.now() - recordingStartTime) / 1000;
        if (onTimerUpdateCallback) {
            onTimerUpdateCallback(formatTime(elapsed), elapsed);
        }
    }, 100);
}

/**
 * Stop the recording timer
 */
function stopTimer() {
    if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
    }
}

/**
 * Check if currently recording
 */
export function isRecording() {
    return mediaRecorder && mediaRecorder.state === 'recording';
}

/**
 * Request microphone permission
 */
export async function requestMicrophonePermission() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        // Stop the stream immediately - we just wanted to check permission
        stream.getTracks().forEach(track => track.stop());
        return true;
    } catch (error) {
        console.error('[Recorder] Microphone permission denied:', error);
        return false;
    }
}

/**
 * Start recording
 */
export async function startRecording() {
    if (isRecording()) {
        console.warn('[Recorder] Already recording');
        return false;
    }

    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            audio: {
                echoCancellation: true,
                noiseSuppression: true,
                autoGainControl: true
            }
        });

        const mimeType = getPreferredMimeType();
        const options = mimeType ? { mimeType } : {};

        mediaRecorder = new MediaRecorder(stream, options);
        audioChunks = [];

        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                audioChunks.push(event.data);
            }
        };

        mediaRecorder.onstop = () => {
            // Stop all tracks
            stream.getTracks().forEach(track => track.stop());
            stopTimer();

            // Create blob from chunks
            const mimeType = recordedMimeType || 'audio/mp4';
            const audioBlob = new Blob(audioChunks, { type: mimeType });
            const duration = recordingStartTime ? (Date.now() - recordingStartTime) / 1000 : 0;

            if (onRecordingStopCallback) {
                onRecordingStopCallback(audioBlob, duration);
            }

            // Clean up
            mediaRecorder = null;
            audioChunks = [];
        };

        mediaRecorder.onerror = (event) => {
            console.error('[Recorder] Error:', event.error);
            stopTimer();
            if (onRecordingErrorCallback) {
                onRecordingErrorCallback(event.error);
            }
        };

        // Start recording without timeslice (iOS WebKit doesn't reliably support it)
        mediaRecorder.start();
        recordedMimeType = mediaRecorder.mimeType || '';
        startTimer();

        if (onRecordingStartCallback) {
            onRecordingStartCallback();
        }

        console.log('[Recorder] Recording started, MIME type:', mimeType || 'default');
        return true;

    } catch (error) {
        console.error('[Recorder] Failed to start recording:', error);
        if (onRecordingErrorCallback) {
            onRecordingErrorCallback(error);
        }
        return false;
    }
}

/**
 * Stop recording
 */
export function stopRecording() {
    if (!isRecording()) {
        console.warn('[Recorder] Not currently recording');
        return false;
    }
    mediaRecorder.stop();
    return true;
}

/**
 * Cancel recording without saving
 */
export function cancelRecording() {
    if (!mediaRecorder) return;

    // Clear the stop callback to prevent processing
    const originalCallback = onRecordingStopCallback;
    onRecordingStopCallback = null;

    if (mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
    }

    stopTimer();

    // Restore callback
    onRecordingStopCallback = originalCallback;

    // Clean up
    mediaRecorder = null;
    audioChunks = [];
}

/**
 * Set callback for when recording starts
 */
export function onRecordingStart(callback) {
    onRecordingStartCallback = callback;
}

/**
 * Set callback for when recording stops
 * Callback receives (audioBlob, durationSeconds)
 */
export function onRecordingStop(callback) {
    onRecordingStopCallback = callback;
}

/**
 * Set callback for recording errors
 */
export function onRecordingError(callback) {
    onRecordingErrorCallback = callback;
}

/**
 * Set callback for timer updates
 * Callback receives (formattedTime, seconds)
 */
export function onTimerUpdate(callback) {
    onTimerUpdateCallback = callback;
}

/**
 * Get file extension for the recorded audio
 */
export function getFileExtension() {
    const mimeType = recordedMimeType || getPreferredMimeType() || 'audio/mp4';
    if (mimeType.includes('webm')) return 'webm';
    if (mimeType.includes('ogg')) return 'ogg';
    if (mimeType.includes('mp4')) return 'm4a';
    if (mimeType.includes('wav')) return 'wav';
    return 'm4a';
}
