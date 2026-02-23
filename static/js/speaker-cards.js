/**
 * Speaker card orchestrator for VoxTail
 * Coordinates rendering and event handling for speaker identification cards
 */

import { state } from './state.js';
import { escapeHtml } from './utils.js';
import { getCommonHeaders } from './api-client.js';

// Re-export utilities for backwards compatibility
export { SPEAKER_COLORS, getSpeakerColor, getInitials } from './speaker-utils.js';
export { commitPendingDecisions, resetHandledCount } from './pending-decisions.js';

import {
    initPendingDecisions,
    setOriginalNonHighCount,
    hasPendingDecision,
    updateProgress,
    handleConfirmSpeaker,
    handleEnrollFromMeeting,
    handleUndo
} from './pending-decisions.js';

import {
    renderHighCard,
    renderDecidedCard,
    renderMediumCard,
    renderLowCard
} from './card-renderers.js';

// DOM elements (set via init)
let speakerSummary = null;

// Callbacks for cross-module coordination
let onSpeakerChanged = null;

/**
 * Initialize speaker cards module
 */
export function initSpeakerCards({ speakerSummaryEl, progressBarEl, progressTextEl, confirmSpeakersBtnEl }, callbacks = {}) {
    speakerSummary = speakerSummaryEl;
    onSpeakerChanged = callbacks.onSpeakerChanged || null;

    // Initialize pending decisions with DOM elements and callback
    initPendingDecisions(
        { progressBarEl, progressTextEl, confirmSpeakersBtnEl },
        { onDecisionChanged: renderSpeakerSummary }
    );
}

/**
 * Render speaker summary grouped by confidence tier
 */
export function renderSpeakerSummary() {
    const speakers = state.currentSpeakers;

    // Snapshot the original non-high count on first render
    const nonHighCount = speakers.filter(s => s.confidence !== 'high').length;
    setOriginalNonHighCount(nonHighCount);

    const high = speakers.filter(s => s.confidence === 'high');
    const medium = speakers.filter(s => s.confidence === 'medium');
    const low = speakers.filter(s => s.confidence === 'low');

    // Split high-confidence into originally-high and decided (pending undo)
    const originalHigh = high.filter(s => !hasPendingDecision(s.meeting_speaker_id));
    const decided = high.filter(s => hasPendingDecision(s.meeting_speaker_id));

    let html = '';

    // Decided tier (pending confirmation - show with undo)
    if (decided.length > 0) {
        html += `<div class="tier-header high"><span class="tier-dot"></span>Decided - Pending Confirmation</div>`;
        html += decided.map(s => renderDecidedCard(s)).join('');
    }

    // High confidence tier (originally high)
    if (originalHigh.length > 0) {
        html += `<div class="tier-header high"><span class="tier-dot"></span>High Confidence - Auto-Identified</div>`;
        html += originalHigh.map(s => renderHighCard(s)).join('');
    }

    // Medium confidence tier
    if (medium.length > 0) {
        html += `<div class="tier-header medium"><span class="tier-dot"></span>Medium Confidence - Verify Match</div>`;
        html += medium.map(s => renderMediumCard(s)).join('');
    }

    // Low / unidentified tier
    if (low.length > 0) {
        html += `<div class="tier-header low"><span class="tier-dot"></span>Unidentified - Enter Name</div>`;
        html += low.map(s => renderLowCard(s)).join('');
    }

    speakerSummary.innerHTML = html;

    // Update progress
    updateProgress();

    // Bind event listeners
    bindSpeakerCardEvents();
}

/**
 * Bind event listeners to speaker card elements
 */
function bindSpeakerCardEvents() {
    // Confirm buttons (medium confidence) - step 1: select candidate
    speakerSummary.querySelectorAll('.confirm-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const speakerId = btn.dataset.speakerId;
            const card = document.getElementById(`card-${speakerId}`);
            if (!card) return;

            // Deselect other candidates in this card
            card.querySelectorAll('.confirm-btn').forEach(b => b.classList.remove('selected'));
            // Highlight selected candidate
            btn.classList.add('selected');

            // Hide name input if it was open from "New Name"
            const nameInput = card.querySelector('.card-name-input');
            if (nameInput) nameInput.classList.add('hidden');

            // Show add-sample toggle and confirm action button
            const sampleRow = card.querySelector('.add-sample-row');
            if (sampleRow) sampleRow.classList.remove('hidden');
            const confirmAction = card.querySelector('.card-confirm-action');
            if (confirmAction) confirmAction.classList.remove('hidden');

            // Store selected name on the confirm action button
            const finalBtn = card.querySelector('.final-confirm-btn');
            if (finalBtn) finalBtn.dataset.candidateName = btn.dataset.candidateName;
        });
    });

    // Final confirm buttons (medium confidence) - step 2: commit selection
    speakerSummary.querySelectorAll('.final-confirm-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const speakerId = btn.dataset.speakerId;
            const candidateName = btn.dataset.candidateName;
            if (candidateName) {
                const enrollCheckbox = document.getElementById(`enroll-cb-${speakerId}`);
                const shouldEnroll = enrollCheckbox ? enrollCheckbox.checked : true;
                handleConfirmSpeaker(speakerId, candidateName, shouldEnroll, onSpeakerChanged);
            }
        });
    });

    // Rename / new name buttons (medium confidence)
    speakerSummary.querySelectorAll('.rename-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const speakerId = btn.dataset.speakerId;
            const card = document.getElementById(`card-${speakerId}`);
            if (!card) return;

            // Deselect any selected candidate
            card.querySelectorAll('.confirm-btn').forEach(b => b.classList.remove('selected'));

            // Hide add-sample toggle and confirm action (enrollment is automatic for new speakers)
            const sampleRow = card.querySelector('.add-sample-row');
            if (sampleRow) sampleRow.classList.add('hidden');
            const confirmAction = card.querySelector('.card-confirm-action');
            if (confirmAction) confirmAction.classList.add('hidden');

            let inputSection = card.querySelector('.card-name-input');
            if (!inputSection) {
                // Create inline input for medium cards
                inputSection = document.createElement('div');
                inputSection.className = 'card-name-input';
                inputSection.innerHTML = `
                    <div class="name-input-group">
                        <input type="text" id="name-${escapeHtml(speakerId)}" placeholder="Enter new name...">
                        <button class="enroll-btn" data-speaker-id="${escapeHtml(speakerId)}">Save</button>
                    </div>
                `;
                card.querySelector('.card-suggestion').after(inputSection);

                // Bind the new enroll button
                inputSection.querySelector('.enroll-btn').addEventListener('click', () => {
                    const nameInput = document.getElementById(`name-${speakerId}`);
                    const name = nameInput?.value.trim();
                    handleEnrollFromMeeting(speakerId, name, onSpeakerChanged);
                });
            } else {
                inputSection.classList.remove('hidden');
            }
            inputSection.querySelector('input')?.focus();
        });
    });

    // Enroll buttons (low confidence)
    speakerSummary.querySelectorAll('.enroll-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const speakerId = btn.dataset.speakerId;
            const nameInput = document.getElementById(`name-${speakerId}`);
            const name = nameInput?.value.trim();
            handleEnrollFromMeeting(speakerId, name, onSpeakerChanged);
        });
    });

    // Undo buttons (decided cards)
    speakerSummary.querySelectorAll('.undo-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            handleUndo(btn.dataset.speakerId, onSpeakerChanged);
        });
    });

    // Play buttons
    speakerSummary.querySelectorAll('.play-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            playClip(btn);
        });
    });
}

/**
 * Play audio clip from speaker.
 * On iOS, audio.play() may be blocked if the gesture context expired during fetch.
 * We retain the loaded audio so a second tap plays immediately (within fresh gesture).
 */
async function playClip(btn) {
    const url = btn.dataset.clipUrl;
    if (!url) return;

    // Prevent duplicate fetches from rapid taps
    if (btn._loading) return;

    // If already playing, stop
    if (btn._audio && !btn._audio.paused) {
        btn._audio.pause();
        btn._audio.currentTime = 0;
        btn.innerHTML = '&#9654;';
        return;
    }

    // If audio already loaded (e.g. previous play was blocked by iOS), retry immediately
    if (btn._audio && btn._audio.readyState >= 2) {
        btn.innerHTML = '&#9724;';
        btn._audio.play().catch(() => {
            btn.innerHTML = '&#9654;';
        });
        return;
    }

    btn._loading = true;
    btn.classList.add('loading');
    btn.innerHTML = '&#8943;';

    try {
        // Clean up any previous audio for this button
        if (btn._blobUrl) {
            URL.revokeObjectURL(btn._blobUrl);
            btn._blobUrl = null;
        }
        btn._audio = null;

        const response = await fetch(url, { headers: getCommonHeaders() });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const blob = await response.blob();
        const blobUrl = URL.createObjectURL(blob);

        const audio = new Audio(blobUrl);
        btn._audio = audio;
        btn._blobUrl = blobUrl;

        audio.addEventListener('canplay', () => {
            btn._loading = false;
            btn.classList.remove('loading');
            btn.innerHTML = '&#9724;';
            audio.play().catch(() => {
                // iOS blocked autoplay — reset icon, user can tap again (instant next time)
                btn.innerHTML = '&#9654;';
            });
        }, { once: true });

        audio.addEventListener('ended', () => {
            btn.innerHTML = '&#9654;';
        });

        audio.addEventListener('error', () => {
            btn._loading = false;
            btn.classList.remove('loading');
            btn.innerHTML = '&#9654;';
            URL.revokeObjectURL(blobUrl);
            btn._blobUrl = null;
            btn._audio = null;
        });

        audio.load();
    } catch (err) {
        console.error('Failed to load audio clip:', err);
        btn._loading = false;
        btn.classList.remove('loading');
        btn.innerHTML = '&#9654;';
    }
}
