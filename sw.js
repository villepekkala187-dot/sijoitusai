const CACHE = "sijoitusai-v11";
const ASSETS = [
  "/index.html",
  "/manifest.json",
  // CDN-resurssit offline-tukea varten
  "https://cdnjs.cloudflare.com/ajax/libs/react/18.2.0/umd/react.production.min.js",
  "https://cdnjs.cloudflare.com/ajax/libs/react-dom/18.2.0/umd/react-dom.production.min.js",
  "https://cdnjs.cloudflare.com/ajax/libs/babel-standalone/7.23.5/babel.min.js",
];

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
  const url = e.request.url;

  // API-kutsut ja Worker-kutsut aina verkosta, ei cachesta
  if (
    url.includes("anthropic.com") ||
    url.includes("workers.dev") ||
    url.includes("yahoo") ||
    url.includes("alphavantage.co")
  ) {
    return;
  }

  // Google Fonts — cache on first use (stale-while-revalidate)
  if (url.includes("fonts.googleapis.com") || url.includes("fonts.gstatic.com")) {
    e.respondWith(
      caches.match(e.request).then(cached => {
        const fetchPromise = fetch(e.request).then(response => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE).then(cache => cache.put(e.request, clone));
          }
          return response;
        }).catch(() => cached);
        return cached || fetchPromise;
      })
    );
    return;
  }

  // Muut resurssit: cache-first, fallback verkkoon
  e.respondWith(
    caches.match(e.request).then(cached => cached || fetch(e.request))
  );
});
