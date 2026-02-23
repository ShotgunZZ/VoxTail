/**
 * Enrollment UI component for Speaker Recognition
 */

import { state } from './state.js';
import { enrollSpeaker, listSpeakers, deleteSpeaker } from './api-client.js';
import { escapeHtml } from './utils.js';

// DOM Elements
let enrollDropZone, enrollFileInput, enrollFileInfo, enrollBtn, enrollStatus, speakerNameInput, speakersList;

/**
 * Initialize enrollment UI
 */
export function initEnrollment() {
    enrollDropZone = document.getElementById('enrollDropZone');
    enrollFileInput = document.getElementById('enrollFile');
    enrollFileInfo = document.getElementById('enrollFileInfo');
    enrollBtn = document.getElementById('enrollBtn');
    enrollStatus = document.getElementById('enrollStatus');
    speakerNameInput = document.getElementById('speakerName');
    speakersList = document.getElementById('speakersList');

    setupDropZone();
    speakerNameInput.addEventListener('input', updateEnrollButton);
    enrollBtn.addEventListener('click', handleEnroll);

    // Initial load
    loadSpeakers();
}

/**
 * Setup drop zone for audio file selection
 */
function setupDropZone() {
    enrollDropZone.addEventListener('click', () => enrollFileInput.click());

    enrollDropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        enrollDropZone.classList.add('drag-over');
    });

    enrollDropZone.addEventListener('dragleave', () => {
        enrollDropZone.classList.remove('drag-over');
    });

    enrollDropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        enrollDropZone.classList.remove('drag-over');
        const file = e.dataTransfer.files[0];
        if (file) handleFileSelect(file);
    });

    enrollFileInput.addEventListener('change', () => {
        const file = enrollFileInput.files[0];
        if (file) handleFileSelect(file);
    });
}

/**
 * Handle file selection
 * @param {File} file - Selected file
 */
function handleFileSelect(file) {
    state.enrollFileSelected = file;
    enrollFileInfo.textContent = `Selected: ${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`;
    enrollFileInfo.style.display = 'block';
    updateEnrollButton();
}

/**
 * Update enroll button state
 */
function updateEnrollButton() {
    enrollBtn.disabled = !state.enrollFileSelected || !speakerNameInput.value.trim();
}

/**
 * Handle enroll button click
 */
async function handleEnroll() {
    const name = speakerNameInput.value.trim();
    if (!name || !state.enrollFileSelected) return;

    enrollBtn.disabled = true;
    enrollStatus.className = 'status loading';
    enrollStatus.innerHTML = '<span class="loading-spinner"></span>Extracting voice fingerprint...';

    try {
        const data = await enrollSpeaker(name, state.enrollFileSelected);

        let statusMsg = `Enrolled ${escapeHtml(data.speaker)} (${data.total_samples} sample${data.total_samples > 1 ? 's' : ''})`;
        if (data.warning) {
            enrollStatus.className = 'status loading'; // Yellow background for warning
            statusMsg += ` Warning: ${escapeHtml(data.warning)}`;
        } else {
            enrollStatus.className = 'status success';
        }
        enrollStatus.textContent = statusMsg;

        // Reset form
        speakerNameInput.value = '';
        state.enrollFileSelected = null;
        enrollFileInfo.style.display = 'none';
        enrollFileInput.value = '';
        loadSpeakers();
    } catch (error) {
        enrollStatus.className = 'status error';
        enrollStatus.textContent = error.message;
    }
    updateEnrollButton();
}

/**
 * Load and display enrolled speakers
 */
export async function loadSpeakers() {
    try {
        const data = await listSpeakers();

        if (data.speakers.length === 0) {
            speakersList.innerHTML = '<em style="color: #999;">No speakers enrolled yet</em>';
        } else {
            speakersList.innerHTML = data.speakers.map(s => `
                <div class="speaker-tag">
                    <span class="name">${escapeHtml(s.name)}</span>
                    <span class="count">(${s.samples} sample${s.samples > 1 ? 's' : ''})</span>
                    <span class="delete" data-name="${escapeHtml(s.name)}">&times;</span>
                </div>
            `).join('');

            // Add delete event listeners
            speakersList.querySelectorAll('.delete').forEach(el => {
                el.addEventListener('click', () => handleDeleteSpeaker(el.dataset.name));
            });
        }
    } catch (error) {
        console.error('Failed to load speakers:', error);
    }
}

/**
 * Handle speaker deletion
 * @param {string} name - Speaker name to delete
 */
async function handleDeleteSpeaker(name) {
    if (!confirm(`Delete speaker "${name}"?`)) return;

    try {
        const response = await deleteSpeaker(name);
        if (response.ok) {
            loadSpeakers();
        }
    } catch (error) {
        console.error('Failed to delete speaker:', error);
    }
}
