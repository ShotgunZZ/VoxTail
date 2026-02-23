/**
 * AI Summary UI for VoxTail
 */

import { state } from './state.js';
import { generateSummary } from './api-client.js';
import { escapeHtml } from './utils.js';
import { saveToHistory } from './history.js';

// DOM elements (set via init)
let generateSummaryBtn, summaryStatus, summaryContent;

/**
 * Initialize summary module
 */
export function initSummary({ generateSummaryBtnEl, summaryStatusEl, summaryContentEl }) {
    generateSummaryBtn = generateSummaryBtnEl;
    summaryStatus = summaryStatusEl;
    summaryContent = summaryContentEl;

    if (!generateSummaryBtn) return;

    generateSummaryBtn.addEventListener('click', handleGenerateSummary);

    document.querySelectorAll('.copy-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const targetId = btn.dataset.target;
            const targetEl = document.getElementById(targetId);
            if (targetEl) {
                copyToClipboard(targetEl.innerText, btn);
            }
        });
    });

    const copyAllBtn = document.getElementById('copyAllSummary');
    if (copyAllBtn) {
        copyAllBtn.addEventListener('click', () => {
            const fullSummary = formatFullSummary();
            copyToClipboard(fullSummary, copyAllBtn);
        });
    }
}

/**
 * Handle generate summary button click
 */
export async function handleGenerateSummary() {
    if (!state.currentMeetingId) {
        summaryStatus.className = 'status error';
        summaryStatus.textContent = 'No meeting data available';
        return;
    }

    if (generateSummaryBtn) generateSummaryBtn.classList.add('hidden');
    summaryStatus.className = 'status loading';
    summaryStatus.innerHTML = '<span class="loading-spinner"></span>Generating AI summary...';
    summaryContent.classList.add('hidden');

    try {
        const data = await generateSummary(state.currentMeetingId);
        const summary = data.summary;

        state.currentSummary = summary;

        // Persist to local history
        const speakerNames = (state.currentSpeakers || []).map(
            s => s.assigned_name || s.meeting_speaker_id
        );
        saveToHistory({
            meetingId: state.currentMeetingId,
            date: new Date().toISOString(),
            duration: state.currentAudioDuration || 0,
            speakers: speakerNames,
            summary: summary,
        }).catch(err => console.warn('Failed to save to history:', err));

        document.getElementById('executiveSummary').textContent = summary.executive_summary;

        const actionItemsEl = document.getElementById('actionItems');
        const actionItemsCount = summary.action_items?.length || 0;
        updateSectionCount('actionItemsCount', actionItemsCount);
        if (actionItemsCount > 0) {
            actionItemsEl.innerHTML = summary.action_items.map(item => `
                <li>
                    ${item.assignee ? `<strong class="assignee">${escapeHtml(item.assignee)}:</strong> ` : ''}${escapeHtml(item.task)}${item.context ? ` <span class="context">(${escapeHtml(item.context)})</span>` : ''}
                </li>
            `).join('');
        } else {
            actionItemsEl.innerHTML = '<li class="empty">No action items identified</li>';
        }

        const decisionsEl = document.getElementById('keyDecisions');
        const decisionsCount = summary.key_decisions?.length || 0;
        updateSectionCount('keyDecisionsCount', decisionsCount);
        if (decisionsCount > 0) {
            decisionsEl.innerHTML = summary.key_decisions.map(d => `<li>${escapeHtml(d)}</li>`).join('');
        } else {
            decisionsEl.innerHTML = '<li class="empty">No key decisions identified</li>';
        }

        const topicsEl = document.getElementById('topicsDiscussed');
        const topicsCount = summary.topics_discussed?.length || 0;
        updateSectionCount('topicsDiscussedCount', topicsCount);
        if (topicsCount > 0) {
            topicsEl.innerHTML = summary.topics_discussed.map(t => `<li>${escapeHtml(t)}</li>`).join('');
        } else {
            topicsEl.innerHTML = '<li class="empty">No topics identified</li>';
        }

        summaryStatus.className = 'status success';
        summaryStatus.textContent = 'Summary generated successfully!';
        summaryContent.classList.remove('hidden');

        // Switch to AI Summary tab
        const summaryTabBtn = document.querySelector('.tab-btn[data-tab="summary"]');
        if (summaryTabBtn) summaryTabBtn.click();

    } catch (error) {
        summaryStatus.className = 'status error';
        summaryStatus.textContent = error.message;
        // Show button again so user can retry manually
        if (generateSummaryBtn) {
            generateSummaryBtn.classList.remove('hidden');
            generateSummaryBtn.disabled = false;
        }
    }
}

/**
 * Update section count badges
 */
function updateSectionCount(sectionId, count) {
    const countEl = document.getElementById(sectionId);
    if (countEl) {
        countEl.textContent = count > 0 ? `(${count})` : '';
    }
}

/**
 * Format full summary for copying
 */
function formatFullSummary() {
    const summary = state.currentSummary;
    if (!summary) return '';

    let text = `MEETING SUMMARY\n${'='.repeat(50)}\n\n`;
    text += `EXECUTIVE SUMMARY:\n${summary.executive_summary}\n\n`;

    text += `ACTION ITEMS:\n`;
    if (summary.action_items && summary.action_items.length > 0) {
        summary.action_items.forEach(item => {
            text += `- ${item.task}`;
            if (item.assignee) text += ` (${item.assignee})`;
            text += '\n';
        });
    } else {
        text += '- None identified\n';
    }
    text += '\n';

    text += `KEY DECISIONS:\n`;
    if (summary.key_decisions && summary.key_decisions.length > 0) {
        summary.key_decisions.forEach(d => text += `- ${d}\n`);
    } else {
        text += '- None identified\n';
    }
    text += '\n';

    text += `TOPICS DISCUSSED:\n`;
    if (summary.topics_discussed && summary.topics_discussed.length > 0) {
        summary.topics_discussed.forEach(t => text += `- ${t}\n`);
    } else {
        text += '- None identified\n';
    }

    return text;
}

/**
 * Copy text to clipboard
 */
async function copyToClipboard(text, btn) {
    try {
        await navigator.clipboard.writeText(text);
        const originalText = btn.textContent;
        btn.textContent = 'Copied!';
        btn.classList.add('copied');
        setTimeout(() => {
            btn.textContent = originalText;
            btn.classList.remove('copied');
        }, 2000);
    } catch (err) {
        console.error('Failed to copy:', err);
        alert('Failed to copy to clipboard');
    }
}
