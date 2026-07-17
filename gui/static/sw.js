/* Chronos PWA v6 — multi-page shell + offline API + mutation flush support */
const CACHE = "chronos-shell-v6";
const PRECACHE = [
  "/",
  "/login",
  "/my-schedule",
  "/my-week",
  "/open-shifts",
  "/time-off",
  "/timecards",
  "/time-punch",
  "/notifications",
  "/bidding",
  "/ops-desk",
  "/live-schedule",
  "/dashboard",
  "/static/chronos.css",
  "/static/fonts.css",
  "/static/manifest.webmanifest",
  "/static/chronos_logo.png",
  "/static/sw.js",
  "/static/offline.html",
  "/static/offline-cache.js",
  "/api/offline/snapshot",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((cache) =>
        Promise.all(PRECACHE.map((u) => cache.add(u).catch(() => undefined)))
      )
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  let url;
  try {
    url = new URL(req.url);
  } catch (e) {
    return;
  }
  if (url.origin !== self.location.origin) return;

  // Mutation apply: network only (never serve cached POST)
  if (req.method === "POST" && url.pathname === "/api/offline/mutations") {
    event.respondWith(
      fetch(req).catch(
        () =>
          new Response(
            JSON.stringify({
              success: false,
              offline: true,
              message: "Still offline — mutations remain queued",
            }),
            { headers: { "Content-Type": "application/json" }, status: 503 }
          )
      )
    );
    return;
  }

  if (req.method !== "GET") return;

  // Offline API snapshot: network-first → cache
  if (url.pathname === "/api/offline/snapshot" || url.pathname.startsWith("/api/offline/")) {
    event.respondWith(
      fetch(req)
        .then((res) => {
          if (res && res.ok) {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(req, copy));
          }
          return res;
        })
        .catch(() =>
          caches.match(req).then(
            (h) =>
              h ||
              new Response(
                JSON.stringify({
                  success: false,
                  offline: true,
                  message: "Offline — no cached API snapshot",
                }),
                { headers: { "Content-Type": "application/json" }, status: 503 }
              )
          )
        )
    );
    return;
  }

  // Shell: cache-first for static + navigations
  if (
    url.pathname.startsWith("/static/") ||
    PRECACHE.indexOf(url.pathname) >= 0 ||
    req.mode === "navigate"
  ) {
    event.respondWith(
      caches.match(req).then((cached) => {
        const net = fetch(req)
          .then((res) => {
            if (res && res.ok) {
              const copy = res.clone();
              caches.open(CACHE).then((c) => c.put(req, copy));
            }
            return res;
          })
          .catch(() => cached || caches.match("/static/offline.html"));
        return cached || net;
      })
    );
  }
});
