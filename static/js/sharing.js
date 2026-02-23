/**
 * Sharing integrations for VoxTail (Slack, Google Drive)
 */

import { state } from './state.js';
import { shareToSlack, shareToGDrive } from './api-client.js';

/**
 * Initialize sharing buttons (admin-only feature)
 */
export function initSharing(isAdmin = false) {
    const shareActions = document.querySelector('.share-actions');
    if (shareActions && !isAdmin) {
        shareActions.style.display = 'none';
        return;
    }

    const slackBtn = document.getElementById('shareSlackBtn');
    if (slackBtn) {
        slackBtn.addEventListener('click', () => handleShare(slackBtn, 'slack'));
    }

    const gdriveBtn = document.getElementById('shareGDriveBtn');
    if (gdriveBtn) {
        gdriveBtn.addEventListener('click', () => handleShare(gdriveBtn, 'gdrive'));
    }
}

/**
 * Handle share button click with loading/success/error states
 */
async function handleShare(btn, type) {
    if (!state.currentMeetingId || !state.currentSummary) return;
    if (btn.disabled) return;

    const label = btn.querySelector('.share-btn-label');
    const originalText = label.textContent;

    // Loading state
    btn.disabled = true;
    btn.classList.add('loading');
    label.textContent = type === 'slack' ? 'Sending...' : 'Uploading...';

    try {
        let result;
        if (type === 'slack') {
            result = await shareToSlack(state.currentMeetingId);
        } else {
            result = await shareToGDrive(state.currentMeetingId);
        }

        // Success state
        btn.classList.remove('loading');
        btn.classList.add('success');
        label.textContent = type === 'slack' ? 'Sent!' : 'Saved!';

        // Open Google Doc in new tab
        if (type === 'gdrive' && result.url) {
            window.open(result.url, '_blank');
        }

        setTimeout(() => {
            btn.classList.remove('success');
            btn.disabled = false;
            label.textContent = originalText;
        }, 3000);

    } catch (error) {
        // Error state
        btn.classList.remove('loading');
        btn.classList.add('error');
        label.textContent = error.message.length > 30
            ? 'Failed \u2014 try again'
            : error.message;

        setTimeout(() => {
            btn.classList.remove('error');
            btn.disabled = false;
            label.textContent = originalText;
        }, 3000);
    }
}
