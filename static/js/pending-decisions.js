/**
 * Pending speaker decisions management for deferred commit
 */

import { state, findSpeaker, updateSpeaker } from './state.js';
import { confirmSpeaker, enrollFromMeeting } from './api-client.js';
import { loadSpeakers } from './enrollment.js';

// Track progress for speaker confirmation
let originalNonHighCount = 0;
const pendingDecisions = new Map(); // speakerId -> { name, action, originalData }

// DOM elements (set via init)
let progressBar = null;
let progressText = null;
let confirmSpeakersBtn = null;

// Callback for re-render
let onDecisionChanged = null;

/**
 * Initialize pending decisions module
 */
export function initPendingDecisions({ progressBarEl, progressTextEl, confirmSpeakersBtnEl }, callbacks = {}) {
    progressBar = progressBarEl;
    progressText = progressTextEl;
    confirmSpeakersBtn = confirmSpeakersBtnEl;
    onDecisionChanged = callbacks.onDecisionChanged || null;
}

/**
 * Reset progress tracking (call when new meeting is loaded)
 */
export function resetHandledCount() {
    originalNonHighCount = 0;
    pendingDecisions.clear();
}

/**
 * Set the original non-high count (called during first render)
 */
export function setOriginalNonHighCount(count) {
    if (originalNonHighCount === 0 && pendingDecisions.size === 0) {
        originalNonHighCount = count;
    }
}

/**
 * Check if a speaker has a pending decision
 */
export function hasPendingDecision(speakerId) {
    return pendingDecisions.has(speakerId);
}

/**
 * Get a pending decision for a speaker
 */
export function getPendingDecision(speakerId) {
    return pendingDecisions.get(speakerId);
}

/**
 * Update progress bar
 */
export function updateProgress() {
    // If all speakers are high confidence, keep button enabled
    if (originalNonHighCount === 0) {
        if (confirmSpeakersBtn) confirmSpeakersBtn.disabled = false;
        return;
    }

    const decided = pendingDecisions.size;
    const pct = Math.round((decided / originalNonHighCount) * 100);
    if (progressBar) {
        // Ensure there's a fill element
        let fill = progressBar.querySelector('.progress-bar-fill');
        if (!fill) {
            fill = document.createElement('div');
            fill.className = 'progress-bar-fill';
            progressBar.appendChild(fill);
        }
        fill.style.width = `${pct}%`;
    }
    if (progressText) {
        progressText.textContent = `${decided}/${originalNonHighCount}`;
    }
    if (confirmSpeakersBtn) {
        confirmSpeakersBtn.disabled = (decided < originalNonHighCount);
    }
}

/**
 * Locally decide a MEDIUM confidence speaker (deferred to commit)
 */
export function handleConfirmSpeaker(speakerId, confirmedName, shouldEnroll, onSpeakerChanged) {
    const speaker = findSpeaker(speakerId);
    if (!speaker) return;

    // Save original state for undo
    pendingDecisions.set(speakerId, {
        name: confirmedName,
        action: 'confirm',
        enroll: shouldEnroll,
        originalData: { assigned_name: speaker.assigned_name, confidence: speaker.confidence }
    });

    // Update local state for visual feedback
    updateSpeaker(speakerId, { assigned_name: confirmedName, confidence: 'high' });
    if (onDecisionChanged) onDecisionChanged();
    if (onSpeakerChanged) onSpeakerChanged();
}

/**
 * Locally decide an unknown speaker for enrollment (deferred to commit)
 */
export function handleEnrollFromMeeting(speakerId, name, onSpeakerChanged) {
    if (!name) {
        alert('Please enter a name for the speaker');
        return false;
    }

    const speaker = findSpeaker(speakerId);
    if (!speaker) return false;

    // Save original state for undo
    pendingDecisions.set(speakerId, {
        name,
        action: 'enroll',
        originalData: { assigned_name: speaker.assigned_name, confidence: speaker.confidence }
    });

    // Update local state for visual feedback
    updateSpeaker(speakerId, { assigned_name: name, confidence: 'high' });
    if (onDecisionChanged) onDecisionChanged();
    if (onSpeakerChanged) onSpeakerChanged();
    return true;
}

/**
 * Undo a pending decision
 */
export function handleUndo(speakerId, onSpeakerChanged) {
    const decision = pendingDecisions.get(speakerId);
    if (!decision) return;

    // Restore original state
    updateSpeaker(speakerId, decision.originalData);
    pendingDecisions.delete(speakerId);

    if (onDecisionChanged) onDecisionChanged();
    if (onSpeakerChanged) onSpeakerChanged();
}

/**
 * Commit all pending decisions to the backend
 */
export async function commitPendingDecisions() {
    const errors = [];

    for (const [speakerId, decision] of pendingDecisions) {
        try {
            if (decision.action === 'confirm') {
                await confirmSpeaker(state.currentMeetingId, speakerId, decision.name, decision.enroll);
            } else {
                await enrollFromMeeting(state.currentMeetingId, speakerId, decision.name);
            }
        } catch (error) {
            console.error(`Failed to commit decision for speaker ${speakerId}:`, error);
            errors.push(`Speaker ${speakerId}: ${error.message}`);
        }
    }

    pendingDecisions.clear();
    loadSpeakers();

    if (errors.length > 0) {
        throw new Error(`Some speakers failed to save:\n${errors.join('\n')}`);
    }
}
