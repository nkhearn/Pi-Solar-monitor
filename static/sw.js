const CACHE_NAME = 'pi-solar-v1';
const ASSETS = [
  '/',
  '/index.html',
  '/charts.html',
  '/manifest.json',
  '/icon.svg',
  '/js/chart.js'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  // Use a Cache-First strategy for static assets, falling back to network
  // and updating the cache if needed.
  event.respondWith(
    caches.match(event.request)
      .then((response) => {
        if (response) {
          return response;
        }
        return fetch(event.request).then((fetchResponse) => {
          // Don't cache API calls or WebSocket upgrades
          if (!fetchResponse || fetchResponse.status !== 200 || fetchResponse.type !== 'basic') {
            return fetchResponse;
          }

          // Optional: Cache new static assets on the fly
          // const responseToCache = fetchResponse.clone();
          // caches.open(CACHE_NAME).then((cache) => {
          //   cache.put(event.request, responseToCache);
          // });

          return fetchResponse;
        });
      })
  );
});
