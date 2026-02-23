// Service Worker for Speaker Recognition PWA
const CACHE_NAME = 'voiceid-v32';
const STATIC_ASSETS = [
  '/',
  '/static/index.html',
  '/static/css/tokens.css',
  '/static/css/base.css',
  '/static/css/speaker-cards.css',
  '/static/css/transcript.css',
  '/static/css/summary.css',
  '/static/css/history.css',
  '/static/css/layout.css',
  '/static/js/main.js',
  '/static/js/api-client.js',
  '/static/js/state.js',
  '/static/js/enrollment.js',
  '/static/js/identification.js',
  '/static/js/speaker-cards.js',
  '/static/js/speaker-utils.js',
  '/static/js/card-renderers.js',
  '/static/js/pending-decisions.js',
  '/static/js/transcript.js',
  '/static/js/summary.js',
  '/static/js/recorder.js',
  '/static/js/history.js',
  '/static/js/utils.js',
  '/static/manifest.json',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png'
];

// Install event - cache static assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('[SW] Caching static assets');
        return cache.addAll(STATIC_ASSETS);
      })
      .then(() => self.skipWaiting())
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((cacheNames) => {
        return Promise.all(
          cacheNames
            .filter((name) => name !== CACHE_NAME)
            .map((name) => {
              console.log('[SW] Deleting old cache:', name);
              return caches.delete(name);
            })
        );
      })
      .then(() => self.clients.claim())
  );
});

// Fetch event - network first for API, cache first for static
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Skip non-GET requests
  if (event.request.method !== 'GET') {
    return;
  }

  // API requests - network only (don't cache)
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(fetch(event.request));
    return;
  }

  // Static assets - cache first, then network
  event.respondWith(
    caches.match(event.request)
      .then((cachedResponse) => {
        if (cachedResponse) {
          // Return cached version, but also update cache in background
          event.waitUntil(
            fetch(event.request)
              .then((networkResponse) => {
                if (networkResponse.ok) {
                  caches.open(CACHE_NAME)
                    .then((cache) => cache.put(event.request, networkResponse));
                }
              })
              .catch(() => {/* ignore network errors */})
          );
          return cachedResponse;
        }

        // Not in cache - fetch from network
        return fetch(event.request)
          .then((networkResponse) => {
            // Cache successful responses for static files
            if (networkResponse.ok && url.pathname.startsWith('/static/')) {
              const responseClone = networkResponse.clone();
              caches.open(CACHE_NAME)
                .then((cache) => cache.put(event.request, responseClone));
            }
            return networkResponse;
          });
      })
  );
});

// Handle messages from clients
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});
