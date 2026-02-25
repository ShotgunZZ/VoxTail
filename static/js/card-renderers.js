/**
 * Speaker card rendering functions
 */

import { state } from './state.js';
import { escapeHtml } from './utils.js';
import { getInitials } from './speaker-utils.js';
import { hasPendingDecision, getPendingDecision } from './pending-decisions.js';

/**
 * Get first utterance text for a speaker
 */
function getLongestUtterance(speakerId) {
    const utts = state.currentUtterances.filter(u => u.speaker_id === speakerId);
    if (!utts.length) return '';
    const longest = utts.reduce((a, b) => (b.end - b.start) > (a.end - a.start) ? b : a);
    const text = longest.text || '';
    return text.length > 80 ? text.slice(0, 80) + '...' : text;
}

/**
 * Render a high-confidence speaker card
 */
export function renderHighCard(s) {
    const escapedId = escapeHtml(s.meeting_speaker_id);
    const name = escapeHtml(s.assigned_name || `Speaker ${escapedId}`);
    const initials = getInitials(s.assigned_name);
    const score = Math.round((s.top_score || 0) * 100);
    const quote = getLongestUtterance(s.meeting_speaker_id);

    return `
        <div class="speaker-card high" id="card-${escapedId}">
            <div class="card-top">
                <div class="speaker-avatar green">${escapeHtml(initials)}</div>
                <div class="card-info">
                    <div class="card-name-row">
                        <span class="card-name">${name}</span>
                        <span class="confidence-badge high"><span class="badge-icon">&#10003;</span> ${score}%</span>
                    </div>
                    ${quote ? `<div class="card-quote">"${escapeHtml(quote)}"</div>` : ''}
                </div>
                <span class="card-check">&#10003;</span>
            </div>
        </div>
    `;
}

/**
 * Render a decided (pending confirmation) speaker card with undo
 */
export function renderDecidedCard(s) {
    const escapedId = escapeHtml(s.meeting_speaker_id);
    const name = escapeHtml(s.assigned_name || `Speaker ${escapedId}`);
    const initials = getInitials(s.assigned_name);
    const decision = getPendingDecision(s.meeting_speaker_id);
    const actionLabel = decision.action === 'confirm' ? 'Confirmed' : 'Enrolled';

    return `
        <div class="speaker-card high decided" id="card-${escapedId}">
            <div class="card-top">
                <div class="speaker-avatar green">${escapeHtml(initials)}</div>
                <div class="card-info">
                    <div class="card-name-row">
                        <span class="card-name">${name}</span>
                        <span class="confidence-badge high"><span class="badge-icon">&#10003;</span> ${actionLabel}</span>
                    </div>
                </div>
                <button class="undo-btn" data-speaker-id="${escapedId}">Undo</button>
            </div>
        </div>
    `;
}

/**
 * Render a medium-confidence speaker card
 */
export function renderMediumCard(s) {
    const escapedId = escapeHtml(s.meeting_speaker_id);
    const score = Math.round((s.top_score || 0) * 100);
    const quote = getLongestUtterance(s.meeting_speaker_id);
    const candidateName = s.candidates?.[0]?.name || '';
    const initials = getInitials(candidateName);
    const clipUrl = `/api/meeting/${encodeURIComponent(state.currentMeetingId)}/speaker/${encodeURIComponent(s.meeting_speaker_id)}/clip`;

    // Check if audio is long enough for playback (2 seconds minimum)
    const canPlay = (s.longest_utterance_ms || 0) >= 2000;

    let candidateButtons = '';
    if (s.candidates && s.candidates.length > 0) {
        candidateButtons = s.candidates.map(c =>
            `<button class="confirm-btn" data-speaker-id="${escapedId}" data-candidate-name="${escapeHtml(c.name)}">${escapeHtml(c.name)}</button>`
        ).join('');
    }

    return `
        <div class="speaker-card medium" id="card-${escapedId}">
            <div class="card-top">
                <div class="speaker-avatar orange">${escapeHtml(initials || '?')}</div>
                <div class="card-info">
                    <div class="card-name-row">
                        <span class="card-name">Speaker ${escapedId}</span>
                        <span class="confidence-badge medium"><span class="badge-icon">&#9888;</span> ${score}%</span>
                    </div>
                    ${quote ? `<div class="card-quote">"${escapeHtml(quote)}"</div>` : ''}
                    ${s.low_speech_quality ? `<div class="card-warning">&#9888; Low audio quality — match may be less reliable</div>` : ''}
                </div>
                ${canPlay
                    ? `<button class="play-btn orange" data-clip-url="${escapeHtml(clipUrl)}">&#9654;</button>`
                    : `<span class="audio-too-short">Audio too short</span>`
                }
            </div>
            <div class="card-suggestion">
                <p>Best match from voiceprint library:</p>
                <div class="suggestion-buttons">
                    ${candidateButtons}
                    ${!s.low_speech_quality ? `<button class="rename-btn" data-speaker-id="${escapedId}">&#9998; New Name</button>` : ''}
                </div>
            </div>
            ${!s.low_speech_quality ? `
            <div class="add-sample-row hidden">
                <span>Add this sample to strengthen voiceprint</span>
                <label class="toggle-switch">
                    <input type="checkbox" id="enroll-cb-${escapedId}" checked>
                    <span class="toggle-slider"></span>
                </label>
            </div>
            ` : ''}
            <div class="card-confirm-action hidden">
                <button class="final-confirm-btn" data-speaker-id="${escapedId}">Confirm</button>
            </div>
        </div>
    `;
}

/**
 * Render a low-confidence / unidentified speaker card
 */
export function renderLowCard(s) {
    const escapedId = escapeHtml(s.meeting_speaker_id);
    const quote = getLongestUtterance(s.meeting_speaker_id);
    const clipUrl = `/api/meeting/${encodeURIComponent(state.currentMeetingId)}/speaker/${encodeURIComponent(s.meeting_speaker_id)}/clip`;

    // Check if audio is long enough for playback and enrollment (2 seconds minimum)
    const canPlay = (s.longest_utterance_ms || 0) >= 2000;

    return `
        <div class="speaker-card low" id="card-${escapedId}">
            <div class="card-top">
                <div class="speaker-avatar gray">&#128100;</div>
                <div class="card-info">
                    <div class="card-name-row">
                        <span class="card-name">Speaker ${escapedId}</span>
                    </div>
                    ${quote ? `<div class="card-quote">"${escapeHtml(quote)}"</div>` : ''}
                    ${s.low_speech_quality ? `<div class="card-warning">&#9888; Low audio quality — match may be less reliable</div>` : ''}
                </div>
                ${canPlay
                    ? `<button class="play-btn gray" data-clip-url="${escapeHtml(clipUrl)}">&#9654;</button>`
                    : `<span class="audio-too-short">Audio too short</span>`
                }
            </div>
            ${canPlay && !s.low_speech_quality ? `
                <div class="card-name-input">
                    <div class="name-input-group">
                        <input type="text" id="name-${escapedId}" placeholder="Enter speaker name...">
                        <button class="enroll-btn" data-speaker-id="${escapedId}">Save</button>
                    </div>
                </div>
                <div class="enroll-row" data-speaker-id="${escapedId}">
                    <span class="fp-icon">&#128274;</span>
                    <span>Save voice sample to library</span>
                </div>
            ` : `
                <div class="audio-insufficient">
                    <span>${s.low_speech_quality
                        ? 'Not enough speech for voiceprint registration'
                        : 'Insufficient audio for voiceprint registration'}</span>
                </div>
            `}
        </div>
    `;
}
