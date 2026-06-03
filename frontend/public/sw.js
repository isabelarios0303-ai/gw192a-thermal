/* ThermoBaby service worker — offline app shell + push notifications. */
const CACHE = 'thermobaby-v1';
const SHELL = ['/', '/manifest.webmanifest'];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  // Never cache API or websocket traffic; network-first for everything else.
  if (request.url.includes('/api/') || request.url.startsWith('ws')) return;
  event.respondWith(
    fetch(request)
      .then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(request, copy)).catch(() => {});
        return res;
      })
      .catch(() => caches.match(request).then((r) => r || caches.match('/')))
  );
});

// Push notifications for critical alerts.
self.addEventListener('push', (event) => {
  const data = (() => {
    try { return event.data ? event.data.json() : {}; } catch { return {}; }
  })();
  const title = data.title || 'ThermoBaby — Alerta';
  event.waitUntil(
    self.registration.showNotification(title, {
      body: data.body || 'Evento de temperatura detectado',
      tag: data.tag || 'thermobaby-alert',
      requireInteraction: data.level === 'critical',
      vibrate: data.level === 'critical' ? [300, 120, 300, 120, 300] : [200, 100, 200],
    })
  );
});
