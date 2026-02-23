/**
 * API client for Speaker Recognition backend
 */

/**
 * Get common headers for API requests
 */
export function getCommonHeaders() {
    const headers = {};
    const deviceId = localStorage.getItem('voxtail_device_id');
    if (deviceId) headers['X-Device-ID'] = deviceId;
    return headers;
}

/**
 * Enroll a new speaker
 * @param {string} name - Speaker name
 * @param {File} audioFile - Audio file
 * @returns {Promise<Object>} Response data
 */
export async function enrollSpeaker(name, audioFile) {
    const formData = new FormData();
    formData.append('name', name);
    formData.append('audio', audioFile);

    const response = await fetch('/api/enroll', {
        method: 'POST',
        headers: getCommonHeaders(),
        body: formData
    });
    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.detail || 'Enrollment failed');
    }
    return data;
}

/**
 * Identify speakers in an audio file (returns raw Response for SSE streaming)
 * @param {File} audioFile - Audio file
 * @returns {Promise<Response>} Raw fetch Response (SSE stream)
 */
export async function identifySpeakers(audioFile) {
    const formData = new FormData();
    formData.append('audio', audioFile);

    const response = await fetch('/api/identify', {
        method: 'POST',
        headers: getCommonHeaders(),
        body: formData
    });

    if (!response.ok) {
        // Non-SSE error (e.g. 401, 422)
        const data = await response.json();
        throw new Error(data.detail || 'Identification failed');
    }
    return response;
}

/**
 * List all enrolled speakers
 * @returns {Promise<Object>} Response with speakers array
 */
export async function listSpeakers() {
    const response = await fetch('/api/speakers', { headers: getCommonHeaders() });
    return response.json();
}

/**
 * Delete a speaker
 * @param {string} name - Speaker name to delete
 * @returns {Promise<Response>} Fetch response
 */
export async function deleteSpeaker(name) {
    return fetch(`/api/speakers/${encodeURIComponent(name)}`, {
        method: 'DELETE',
        headers: getCommonHeaders()
    });
}

/**
 * Confirm a speaker match
 * @param {string} meetingId - Meeting ID
 * @param {string} speakerId - Speaker ID
 * @param {string} confirmedName - Confirmed speaker name
 * @param {boolean} shouldEnroll - Whether to enroll the speaker
 * @returns {Promise<Object>} Response data
 */
export async function confirmSpeaker(meetingId, speakerId, confirmedName, shouldEnroll) {
    const formData = new FormData();
    formData.append('meeting_id', meetingId);
    formData.append('speaker_id', speakerId);
    formData.append('confirmed_name', confirmedName);
    formData.append('enroll', shouldEnroll);

    const response = await fetch('/api/confirm-speaker', {
        method: 'POST',
        headers: getCommonHeaders(),
        body: formData
    });
    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.detail || 'Confirmation failed');
    }
    return data;
}

/**
 * Enroll a speaker from meeting audio
 * @param {string} meetingId - Meeting ID
 * @param {string} speakerId - Speaker ID
 * @param {string} speakerName - Name to assign
 * @returns {Promise<Object>} Response data
 */
export async function enrollFromMeeting(meetingId, speakerId, speakerName) {
    const formData = new FormData();
    formData.append('meeting_id', meetingId);
    formData.append('speaker_id', speakerId);
    formData.append('speaker_name', speakerName);

    const response = await fetch('/api/enroll-from-meeting', {
        method: 'POST',
        headers: getCommonHeaders(),
        body: formData
    });
    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.detail || 'Enrollment failed');
    }
    return data;
}

/**
 * Generate AI summary for a meeting
 * @param {string} meetingId - Meeting ID
 * @returns {Promise<Object>} Response with summary data
 */
export async function generateSummary(meetingId) {
    const response = await fetch(`/api/meeting/${meetingId}/summary`, {
        method: 'POST',
        headers: getCommonHeaders()
    });
    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.detail || 'Summary generation failed');
    }
    return data;
}

