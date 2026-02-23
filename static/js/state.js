/**
 * Global state management for Speaker Recognition UI
 */

// Application state
export const state = {
    enrollFileSelected: null,
    identifyFileSelected: null,
    currentMeetingId: null,
    currentSpeakers: [],
    currentUtterances: []
};

/**
 * Reset meeting-related state
 */
export function resetMeetingState() {
    state.currentMeetingId = null;
    state.currentSpeakers = [];
    state.currentUtterances = [];
}

/**
 * Update meeting state after identification
 * @param {string} meetingId - Meeting ID
 * @param {Array} speakers - Speaker data
 * @param {Array} utterances - Utterance data
 */
export function setMeetingState(meetingId, speakers, utterances, audioDuration) {
    state.currentMeetingId = meetingId;
    state.currentSpeakers = speakers;
    state.currentUtterances = utterances;
    state.currentAudioDuration = audioDuration || 0;
}

/**
 * Find a speaker by ID in current meeting
 * @param {string} speakerId - Speaker ID to find
 * @returns {Object|undefined} Speaker object or undefined
 */
export function findSpeaker(speakerId) {
    return state.currentSpeakers.find(s => s.meeting_speaker_id === speakerId);
}

/**
 * Update a speaker's data
 * @param {string} speakerId - Speaker ID to update
 * @param {Object} updates - Properties to update
 */
export function updateSpeaker(speakerId, updates) {
    const speaker = findSpeaker(speakerId);
    if (speaker) {
        Object.assign(speaker, updates);
    }
}
