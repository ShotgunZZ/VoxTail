/**
 * Transcript rendering for VoxTail
 */

import { state, findSpeaker } from './state.js';
import { escapeHtml, formatTime } from './utils.js';
import { SPEAKER_COLORS, getSpeakerColor, getInitials } from './speaker-utils.js';

// DOM elements (set via init)
let transcriptEl;

/**
 * Initialize transcript module
 */
export function initTranscript({ transcriptElement }) {
    transcriptEl = transcriptElement;
}

/**
 * Render transcript with avatar circles
 */
export function renderTranscript() {
    // Build a speaker-to-color index
    const speakerIds = [...new Set(state.currentUtterances.map(u => u.speaker_id))];
    const speakerColorMap = {};
    speakerIds.forEach((sid, i) => {
        speakerColorMap[sid] = getSpeakerColor(i);
    });

    transcriptEl.innerHTML = state.currentUtterances.map(u => {
        const speaker = findSpeaker(u.speaker_id);
        const confidence = speaker ? speaker.confidence : 'low';
        const color = speakerColorMap[u.speaker_id] || SPEAKER_COLORS[0];

        let displayName;
        if (confidence === 'high' && speaker?.assigned_name) {
            displayName = escapeHtml(speaker.assigned_name);
        } else if (confidence === 'medium' && speaker?.candidates?.length > 0) {
            displayName = `Maybe ${escapeHtml(speaker.candidates[0].name)}?`;
        } else {
            displayName = escapeHtml(u.speaker_name);
        }

        const initials = getInitials(
            speaker?.assigned_name || (speaker?.candidates?.[0]?.name) || u.speaker_name || u.speaker_id
        );

        return `
            <div class="utterance" data-speaker-id="${escapeHtml(u.speaker_id)}">
                <div class="utterance-avatar" style="background:${color}">${escapeHtml(initials)}</div>
                <div class="utterance-body">
                    <div class="speaker">
                        <span class="speaker-name" style="color:${color}">${displayName}</span>
                        <span class="meta">${formatTime(u.start)}</span>
                    </div>
                    <div class="text">${escapeHtml(u.text)}</div>
                </div>
            </div>
        `;
    }).join('');
}

/**
 * Render meeting info card on Results screen
 */
export function renderMeetingInfo() {
    const infoEl = document.getElementById('meetingInfo');
    if (!infoEl) return;

    const speakerCount = state.currentSpeakers.length;
    const now = new Date();
    const dateStr = now.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

    infoEl.innerHTML = `
        <div class="meeting-info-row">
            <span class="meeting-info-title">Meeting Recording</span>
        </div>
        <div class="meeting-info-detail">${dateStr} &middot; ${speakerCount} speaker${speakerCount !== 1 ? 's' : ''}</div>
    `;
}
