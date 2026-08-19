// Minimal service worker whose only job is to keep the installed
// (home-screen / standalone) app from ever serving a stale index.html.
// iOS web-clips can reuse a cached WKWebView across app switches without
// revalidating past the server's Cache-Control TTL — this forces every
// navigation to go to the network, bypassing HTTP cache entirely.

self.addEventListener('install', () => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (event) => {
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request, { cache: 'no-store' }).catch(() => fetch(event.request))
    );
  }
  // Everything else (data/*.json, icons, etc.) passes through untouched —
  // the JSON fetches already cache-bust themselves with a ?v= query param.
});
