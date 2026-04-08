const CACHE = "sijoitusai-v8";
const ASSETS = ["/index.html", "/manifest.json"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)));
  self.skipWaiting();
});

self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(keys =>
    Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
  ));
  self.clients.claim();
});

self.addEventListener("fetch", e => {
  // API-kutsut aina verkosta, ei cachesta
  if (
    e.request.url.includes("anthropic.com") ||
    e.request.url.includes("alphavantage.co") ||
    e.request.url.includes("workers.dev")
  ) {
    return;
  }
  e.respondWith(
    caches.match(e.request).then(cached => cached || fetch(e.request))
  );
});
