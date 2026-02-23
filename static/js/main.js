/**
 * Main entry point for VoxTail UI
 */

import { initEnrollment } from './enrollment.js';
import { initIdentification } from './identification.js';
import { renderHistory, clearHistory } from './history.js';

/**
 * Navigate to a screen by ID.
 */
export function navigateTo(screenId) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    const target = document.getElementById(screenId);
    if (target) {
        target.classList.add('active');
    }

    // Update tab bar active state
    document.querySelectorAll('.tab-bar-item').forEach(item => {
        item.classList.toggle('active', item.dataset.screen === screenId);
    });
}

/**
 * Initialize tab bar navigation
 */
function initTabBar() {
    document.querySelectorAll('.tab-bar-item').forEach(item => {
        item.addEventListener('click', () => {
            const screen = item.dataset.screen;
            if (screen === 'settings') {
                navigateTo('screenSettings');
                const historyList = document.getElementById('historyList');
                if (historyList) renderHistory(historyList);
                return;
            }
            navigateTo(screen);
        });
    });
}

/**
 * Initialize back buttons
 */
function initBackButtons() {
    document.querySelectorAll('.back-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            navigateTo(btn.dataset.target);
        });
    });
}

/**
 * Initialize upload toggle on home screen
 */
function initUploadToggle() {
    const toggleBtn = document.getElementById('showUploadBtn');
    const uploadSection = document.getElementById('uploadSection');
    if (toggleBtn && uploadSection) {
        toggleBtn.addEventListener('click', (e) => {
            e.preventDefault();
            uploadSection.classList.toggle('hidden');
            toggleBtn.textContent = uploadSection.classList.contains('hidden')
                ? 'Upload file instead'
                : 'Hide upload';
        });
    }
}

/**
 * Initialize tab switcher (Transcript / AI Summary)
 */
function initTabSwitcher() {
    const switcher = document.getElementById('tabSwitcher');
    if (!switcher) return;

    switcher.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tabName = btn.dataset.tab;

            // Update button active state
            switcher.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Show corresponding content
            document.getElementById('tabTranscript').classList.toggle('active', tabName === 'transcript');
            document.getElementById('tabSummary').classList.toggle('active', tabName === 'summary');
        });
    });
}

/**
 * Initialize accordion behavior for summary cards
 */
function initAccordions() {
    document.querySelectorAll('.summary-card-header').forEach(header => {
        header.addEventListener('click', () => {
            const card = header.closest('.summary-card');
            if (card) {
                card.classList.toggle('collapsed');
            }
        });
    });
}

/**
 * Show a toast notification
 */
function showToast(message) {
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    toast.style.cssText = `
        position: fixed;
        bottom: 100px;
        left: 50%;
        transform: translateX(-50%);
        background: rgba(26,25,24,0.9);
        color: white;
        padding: 10px 20px;
        border-radius: 20px;
        font-size: 14px;
        z-index: 200;
        font-family: var(--mm-font);
    `;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 2000);
}

/**
 * Register service worker for PWA support
 */
function registerServiceWorker() {
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/static/sw.js')
            .then((registration) => {
                console.log('[PWA] Service worker registered:', registration.scope);

                registration.addEventListener('updatefound', () => {
                    const newWorker = registration.installing;
                    newWorker.addEventListener('statechange', () => {
                        if (newWorker.state === 'activated') {
                            console.log('[PWA] New version activated, reloading...');
                            window.location.reload();
                        }
                    });
                });
            })
            .catch((error) => {
                console.error('[PWA] Service worker registration failed:', error);
            });
    }
}

/**
 * Initialize the main app
 */
function initApp() {
    document.body.classList.add('app-ready');
    document.getElementById('screenHome').classList.add('active');

    initTabBar();
    initBackButtons();
    initUploadToggle();
    initTabSwitcher();
    initAccordions();
    initEnrollment();
    initIdentification();

    // Initialize history
    const historyList = document.getElementById('historyList');
    if (historyList) renderHistory(historyList);

    const clearHistoryBtn = document.getElementById('clearHistoryBtn');
    if (clearHistoryBtn) {
        clearHistoryBtn.addEventListener('click', async () => {
            if (confirm('Delete all meeting history?')) {
                await clearHistory();
                renderHistory(historyList);
            }
        });
    }
}

/**
 * Initialize application
 */
async function init() {
    registerServiceWorker();

    // Generate anonymous device ID for analytics (persists across sessions)
    if (!localStorage.getItem('voxtail_device_id')) {
        localStorage.setItem('voxtail_device_id', crypto.randomUUID());
    }

    initApp();
}

// Wait for DOM to be ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
