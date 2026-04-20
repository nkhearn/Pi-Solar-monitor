// Minimal Service Worker for PWA installation support.
// Offline capabilities are explicitly disabled as per requirements.

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(clients.claim());
});

self.addEventListener('fetch', (event) => {
  // Pass-through fetch without any caching
  event.respondWith(fetch(event.request));
});
