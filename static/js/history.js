/**
 * Meeting history — IndexedDB persistence and UI rendering for VoxTail
 */

import { escapeHtml, formatDuration } from './utils.js';

const DB_NAME = 'voxtail-history';
const DB_VERSION = 1;
const STORE_NAME = 'meetings';
const MAX_ENTRIES = 50;

/** @type {IDBDatabase|null} */
let db = null;

/**
 * Open (or create) the IndexedDB database.
 * @returns {Promise<IDBDatabase>}
 */
function openDB() {
    if (db) return Promise.resolve(db);
    return new Promise((resolve, reject) => {
        const req = indexedDB.open(DB_NAME, DB_VERSION);
        req.onupgradeneeded = () => {
            const store = req.result.createObjectStore(STORE_NAME, { keyPath: 'id' });
            store.createIndex('date', 'date');
        };
        req.onsuccess = () => { db = req.result; resolve(db); };
        req.onerror = () => reject(req.error);
    });
}

/**
 * Save a meeting summary to history.
 * Auto-prunes to MAX_ENTRIES most recent.
 */
export async function saveToHistory({ meetingId, date, duration, speakers, summary }) {
    const database = await openDB();
    const title = summary.executive_summary
        ? summary.executive_summary.slice(0, 60).replace(/\s+\S*$/, '...')
        : `Meeting — ${new Date(date).toLocaleDateString()}`;

    const record = {
        id: meetingId,
        date,
        duration,
        speakers,
        speakerCount: speakers.length,
        summary,
        title,
    };

    return new Promise((resolve, reject) => {
        const tx = database.transaction(STORE_NAME, 'readwrite');
        const store = tx.objectStore(STORE_NAME);
        store.put(record);
        tx.oncomplete = async () => {
            await pruneOldEntries();
            resolve();
        };
        tx.onerror = () => reject(tx.error);
    });
}

/**
 * Get all meetings sorted by date (newest first).
 * @returns {Promise<Array>}
 */
export async function getHistory() {
    const database = await openDB();
    return new Promise((resolve, reject) => {
        const tx = database.transaction(STORE_NAME, 'readonly');
        const store = tx.objectStore(STORE_NAME);
        const req = store.getAll();
        req.onsuccess = () => {
            const results = req.result.sort((a, b) => new Date(b.date) - new Date(a.date));
            resolve(results);
        };
        req.onerror = () => reject(req.error);
    });
}

/**
 * Delete a single meeting from history.
 */
export async function deleteFromHistory(meetingId) {
    const database = await openDB();
    return new Promise((resolve, reject) => {
        const tx = database.transaction(STORE_NAME, 'readwrite');
        tx.objectStore(STORE_NAME).delete(meetingId);
        tx.oncomplete = () => resolve();
        tx.onerror = () => reject(tx.error);
    });
}

/**
 * Clear all history.
 */
export async function clearHistory() {
    const database = await openDB();
    return new Promise((resolve, reject) => {
        const tx = database.transaction(STORE_NAME, 'readwrite');
        tx.objectStore(STORE_NAME).clear();
        tx.oncomplete = () => resolve();
        tx.onerror = () => reject(tx.error);
    });
}

/**
 * Keep only the MAX_ENTRIES most recent meetings.
 */
async function pruneOldEntries() {
    const all = await getHistory();
    if (all.length <= MAX_ENTRIES) return;

    const toRemove = all.slice(MAX_ENTRIES);
    const database = await openDB();
    const tx = database.transaction(STORE_NAME, 'readwrite');
    const store = tx.objectStore(STORE_NAME);
    for (const entry of toRemove) {
        store.delete(entry.id);
    }
}

/**
 * Render the history list into the given container element.
 * @param {HTMLElement} container
 */
export async function renderHistory(container) {
    const meetings = await getHistory();

    if (meetings.length === 0) {
        container.innerHTML = `
            <div class="history-empty">
                <p>Your meeting summaries will appear here after processing.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = meetings.map(m => {
        const dateStr = new Date(m.date).toLocaleDateString(undefined, {
            month: 'short', day: 'numeric', year: 'numeric',
            hour: 'numeric', minute: '2-digit'
        });
        const durationStr = formatDuration(m.duration * 1000);
        const speakerNames = m.speakers.map(s => escapeHtml(s)).join(', ');

        const actionItems = m.summary.action_items || [];
        const decisions = m.summary.key_decisions || [];
        const topics = m.summary.topics_discussed || [];

        return `
            <div class="history-card collapsed" data-meeting-id="${escapeHtml(m.id)}">
                <div class="history-card-header">
                    <div class="history-card-info">
                        <h4 class="history-title">${escapeHtml(m.title)}</h4>
                        <span class="history-meta">${dateStr} &middot; ${durationStr} &middot; ${m.speakerCount} speaker${m.speakerCount !== 1 ? 's' : ''}</span>
                    </div>
                    <span class="accordion-chevron">&#9660;</span>
                </div>
                <div class="history-card-content">
                    <div class="history-speakers">
                        <strong>Speakers:</strong> ${speakerNames}
                    </div>
                    <div class="history-summary-section">
                        <h5>Executive Summary</h5>
                        <p>${escapeHtml(m.summary.executive_summary || '')}</p>
                    </div>
                    ${actionItems.length > 0 ? `
                        <div class="history-summary-section">
                            <h5>Action Items (${actionItems.length})</h5>
                            <ul>${actionItems.map(a => `<li>${a.assignee ? `<strong class="assignee">${escapeHtml(a.assignee)}:</strong> ` : ''}${escapeHtml(a.task)}</li>`).join('')}</ul>
                        </div>
                    ` : ''}
                    ${decisions.length > 0 ? `
                        <div class="history-summary-section">
                            <h5>Key Decisions (${decisions.length})</h5>
                            <ul>${decisions.map(d => `<li>${escapeHtml(d)}</li>`).join('')}</ul>
                        </div>
                    ` : ''}
                    ${topics.length > 0 ? `
                        <div class="history-summary-section">
                            <h5>Topics (${topics.length})</h5>
                            <ul>${topics.map(t => `<li>${escapeHtml(t)}</li>`).join('')}</ul>
                        </div>
                    ` : ''}
                    <div class="history-actions">
                        <button class="history-delete-btn" data-meeting-id="${escapeHtml(m.id)}">Delete</button>
                    </div>
                </div>
            </div>
        `;
    }).join('');

    // Accordion toggle
    container.querySelectorAll('.history-card-header').forEach(header => {
        header.addEventListener('click', () => {
            header.closest('.history-card').classList.toggle('collapsed');
        });
    });

    // Delete buttons
    container.querySelectorAll('.history-delete-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const id = btn.dataset.meetingId;
            await deleteFromHistory(id);
            renderHistory(container);
        });
    });
}
