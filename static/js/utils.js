/**
 * Utility functions for Speaker Recognition UI
 */

/**
 * Escape HTML special characters to prevent XSS attacks.
 * @param {string} text - Text to escape
 * @returns {string} Escaped text safe for HTML insertion
 */
export function escapeHtml(text) {
    if (typeof text !== 'string') {
        return text;
    }
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Format duration in milliseconds to human-readable format.
 * @param {number} ms - Duration in milliseconds
 * @returns {string} Formatted duration (e.g., "2m 30s" or "45s")
 */
export function formatDuration(ms) {
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return minutes > 0 ? `${minutes}m ${secs}s` : `${secs}s`;
}

/**
 * Format time in milliseconds to MM:SS format.
 * @param {number} ms - Time in milliseconds
 * @returns {string} Formatted time (e.g., "2:05")
 */
export function formatTime(ms) {
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
}
