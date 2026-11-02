// ARK·π service worker — keeps the knowledge base usable on this device with no connection.
//  • App shell + every article + every tool page are pre-cached on install.
//  • Pages: network first (fresh when the server is reachable), cache fallback.
//  • Static assets: cache first.
//  • Map tiles and manuals are NOT pre-cached (gigabytes); manuals you open are kept.
const VERSION = "__VERSION__";
const SHELL = `ark-shell-${VERSION}`;
const PAGES = "ark-pages";
const MANUALS = "ark-manuals";

self.addEventListener("install", event => {
  event.waitUntil((async () => {
    const cache = await caches.open(SHELL);
    let urls = [];
    try { urls = await (await fetch("/api/precache", { cache: "no-store" })).json(); } catch (e) {}
    // Add individually so one failure doesn't abort the whole install.
    await Promise.all(urls.map(u => cache.add(new Request(u, { cache: "reload" })).catch(() => {})));
    self.skipWaiting();
  })());
});

self.addEventListener("activate", event => {
  event.waitUntil((async () => {
    for (const key of await caches.keys()) {
      if (key.startsWith("ark-shell-") && key !== SHELL) await caches.delete(key);
    }
    await self.clients.claim();
  })());
});

async function fromCache(req) {
  return (await caches.match(req, { ignoreSearch: req.mode === "navigate" })) || null;
}

self.addEventListener("fetch", event => {
  const req = event.request;
  const url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== location.origin) return;
  if (url.pathname.startsWith("/maps/") || url.pathname.startsWith("/kiwix") || url.pathname.startsWith("/media/file/") || req.headers.has("range")) return;   // big/streamed content: straight to server

  // Immutable static assets (fonts, images, vendor libs, ?v= versioned CSS/JS): cache first.
  // Anything else under /static falls through to network-first below, so a stale stylesheet
  // can never be paired with a newer page.
  const immutable = url.search.includes("v=") || /^\/static\/(fonts|img|vendor|data)\//.test(url.pathname) || url.pathname === "/static/favicon.svg";
  if (url.pathname.startsWith("/static/") && immutable) {
    event.respondWith((async () => {
      const hit = await fromCache(req);
      if (hit) return hit;
      const res = await fetch(req);
      if (res.ok) (await caches.open(SHELL)).put(req, res.clone());
      return res;
    })());
    return;
  }

  // Manuals: keep any you've opened
  if (url.pathname.startsWith("/manual/")) {
    event.respondWith((async () => {
      const hit = await caches.match(req);
      if (hit) return hit;
      const res = await fetch(req);
      if (res.ok && res.status === 200) (await caches.open(MANUALS)).put(req, res.clone());
      return res;
    })());
    return;
  }

  // Pages + API reads: network first, fall back to cache, then offline page
  event.respondWith((async () => {
    try {
      const res = await fetch(req);
      if (res.ok) (await caches.open(url.pathname.startsWith("/api/") ? PAGES : SHELL)).put(req, res.clone());
      return res;
    } catch (e) {
      const hit = await fromCache(req);
      if (hit) return hit;
      if (req.mode === "navigate") return (await caches.match("/offline")) || new Response("Offline", { status: 503 });
      return new Response(JSON.stringify([]), { status: 503, headers: { "Content-Type": "application/json" } });
    }
  })());
});

self.addEventListener("message", event => {
  if (event.data === "cache-status") {
    (async () => {
      let n = 0;
      for (const key of await caches.keys()) n += (await (await caches.open(key)).keys()).length;
      event.source.postMessage({ type: "cache-status", count: n, version: VERSION });
    })();
  }
});
