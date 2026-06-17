{% load static %}/* LAI PWA service worker — served from root scope (/). */

const CACHE_VERSION = "lai-v1";
const OFFLINE_URL = "{% url 'core:offline' %}";

// App-shell assets safe to precache (own-origin, rarely change).
const PRECACHE_URLS = [
  OFFLINE_URL,
  "{% static 'icons/icon-192.png' %}",
  "{% static 'icons/icon-512.png' %}",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((k) => k !== CACHE_VERSION).map((k) => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // Only handle GET on our own origin. Let everything else hit the network
  // untouched: POST uploads, cross-origin CDNs (Chart.js/HTMX), media, admin.
  if (req.method !== "GET" || url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/admin/") ||
      url.pathname.startsWith("/media/") ||
      url.pathname.startsWith("/api/")) return;

  // Navigations: network-first, fall back to cached offline page when offline.
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req).catch(() => caches.match(OFFLINE_URL))
    );
    return;
  }

  // Static assets (/static/...): cache-first, then populate cache.
  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.match(req).then((cached) =>
        cached ||
        fetch(req).then((res) => {
          const copy = res.clone();
          caches.open(CACHE_VERSION).then((c) => c.put(req, copy));
          return res;
        })
      )
    );
  }
});
