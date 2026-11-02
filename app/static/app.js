// ARK — small progressive enhancements. Everything works without JS; this adds polish.
(function () {
  "use strict";
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));
  const store = {
    get(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} },
  };
  // Live calculator helper: re-runs fn(values) on every input change, remembers inputs.
  function calc(formSel, fn) {
    const form = $(formSel);
    if (!form) return;
    const key = "calc:" + location.pathname + formSel;
    const saved = store.get(key, {});
    $$("input, select", form).forEach(el => {
      if (el.name && saved[el.name] !== undefined && el.type !== "button") {
        if (el.type === "checkbox") el.checked = saved[el.name]; else el.value = saved[el.name];
      }
    });
    const run = () => {
      const v = {}, raw = {};
      $$("input, select", form).forEach(el => {
        if (!el.name) return;
        raw[el.name] = el.type === "checkbox" ? el.checked : el.value;
        v[el.name] = el.type === "checkbox" ? el.checked : (el.type === "number" ? parseFloat(el.value) : el.value);
      });
      store.set(key, raw);
      try { fn(v, form); } catch (e) { console.error(e); }
    };
    form.addEventListener("input", run);
    form.addEventListener("change", run);
    form.addEventListener("submit", e => e.preventDefault());
    run();
    return run;
  }
  const fmt = (n, d = 1) => isFinite(n) ? Number(n).toLocaleString(undefined, { maximumFractionDigits: d, minimumFractionDigits: 0 }) : "-";
  const out = (id, val) => { const el = document.getElementById(id); if (el) el.innerHTML = val; };
  const beep = (freq = 880, ms = 200, vol = 0.3) => {
    try {
      const ctx = beep.ctx || (beep.ctx = new (window.AudioContext || window.webkitAudioContext)());
      const o = ctx.createOscillator(), g = ctx.createGain();
      o.frequency.value = freq; g.gain.value = vol; o.connect(g); g.connect(ctx.destination);
      o.start(); o.stop(ctx.currentTime + ms / 1000);
    } catch (e) {}
  };
  window.ARK = { $, $$, store, calc, fmt, out, beep };

  // ---- Theme switcher
  const root = document.documentElement;
  function setTheme(t) {
    root.dataset.theme = t;
    try { localStorage.setItem("theme", t); } catch (e) {}
    $$("[data-set-theme]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.setTheme === t)));
    document.dispatchEvent(new CustomEvent("ark:theme", { detail: t }));
  }
  $$("[data-set-theme]").forEach(b => b.addEventListener("click", () => setTheme(b.dataset.setTheme)));
  setTheme(root.dataset.theme || "dark");


  // ---- Wrap wide tables so they scroll instead of breaking layout
  $$(".prose table").forEach(t => {
    if (t.parentElement.classList.contains("table-wrap")) return;
    const w = document.createElement("div"); w.className = "table-wrap";
    t.parentNode.insertBefore(w, t); w.appendChild(t);
  });

  // ---- Live clock on home
  const clock = $("#clock");
  if (clock) {
    const tick = () => { clock.textContent = new Date().toLocaleString([], { weekday: "short", hour: "2-digit", minute: "2-digit" }); };
    tick(); setInterval(tick, 15000);
  }

  // ---- Client-side list filter
  $$("[data-filter]").forEach(inp => {
    inp.addEventListener("input", () => {
      const q = inp.value.toLowerCase();
      $$(inp.dataset.filter).forEach(el => { el.hidden = q && !el.textContent.toLowerCase().includes(q); });
    });
  });

  // ---- Highlight search terms in results
  const hl = $("[data-highlight]");
  if (hl && hl.dataset.highlight) {
    const terms = hl.dataset.highlight.split(/\s+/).filter(t => t.length > 1).map(t => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
    if (terms.length) {
      const re = new RegExp("(" + terms.join("|") + ")", "gi");
      $$(".row-title, .result-snippet", hl).forEach(el => {
        el.innerHTML = el.textContent.replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[c]).replace(re, "<mark>$1</mark>");
      });
    }
  }

  // ---- Recipes: checkable ingredients, numbered steps, wake lock
  const recipe = $("[data-recipe]");
  if (recipe) {
    const key = "checks:" + recipe.dataset.recipe;
    const saved = new Set(store.get(key, []));
    const items = $$(".recipe-card li", recipe);
    items.forEach((li, i) => {
      if (saved.has(i)) li.classList.add("done");
      li.addEventListener("click", e => {
        e.stopPropagation();
        li.classList.toggle("done");
        store.set(key, items.map((x, j) => x.classList.contains("done") ? j : -1).filter(j => j >= 0));
      });
    });
    const reset = $("#reset-checks");
    reset && reset.addEventListener("click", () => { items.forEach(li => li.classList.remove("done")); store.set(key, []); });

    // Turn "### 1. Preheat" style headings into numbered step blocks.
    const steps = $(".recipe-steps", recipe) || recipe;
    $$("h3", steps).forEach(h => {
      const m = h.textContent.match(/^\s*(\d+)\.\s*(.*)$/);
      if (!m) return;
      const block = document.createElement("div"); block.className = "step";
      const body = document.createElement("div"); body.className = "step-body";
      h.innerHTML = '<span class="step-num">' + m[1] + "</span><span>" + h.innerHTML.replace(/^\s*\d+\.\s*/, "") + "</span>";
      h.parentNode.insertBefore(block, h);
      block.appendChild(h);
      while (block.nextSibling && !/^H[23]$/.test(block.nextSibling.nodeName)) body.appendChild(block.nextSibling);
      block.appendChild(body);
    });
  }

  const wakeBtn = $("#wake-btn");
  if (wakeBtn) {
    let lock = null;
    if (!("wakeLock" in navigator)) { wakeBtn.title = "Screen wake lock needs HTTPS or localhost in most browsers"; }
    wakeBtn.addEventListener("click", async () => {
      try {
        if (lock) { await lock.release(); lock = null; wakeBtn.classList.remove("wake-on"); return; }
        lock = await navigator.wakeLock.request("screen");
        wakeBtn.classList.add("wake-on");
        lock.addEventListener("release", () => { lock = null; wakeBtn.classList.remove("wake-on"); });
      } catch (e) {
        wakeBtn.textContent = "Not supported here";
      }
    });
  }
})();

// ---- PWA: register service worker (needs HTTPS or localhost) and show connection state
(function () {
  if ("serviceWorker" in navigator && window.isSecureContext) {
    navigator.serviceWorker.register("/sw.js", { scope: "/" }).then(reg => {
      const ask = () => reg.active && reg.active.postMessage("cache-status");
      navigator.serviceWorker.addEventListener("message", e => {
        if (e.data && e.data.type === "cache-status") {
          const el = document.getElementById("net-status");
          if (el) el.textContent = `${navigator.onLine ? "connected" : "offline mode"} · ${e.data.count} items saved on this device`;
        }
      });
      navigator.serviceWorker.ready.then(ask);
    }).catch(() => {});
  }
  const flag = () => document.documentElement.classList.toggle("is-offline", !navigator.onLine);
  addEventListener("online", flag); addEventListener("offline", flag); flag();
})();

// ---- Topics dropdown: position under its button (the nav scrolls sideways), close on outside click / Esc
(function () {
  document.querySelectorAll(".nav-drop").forEach(d => {
    d.addEventListener("toggle", () => {
      if (!d.open) return;
      // Positioned by CSS under the Topics button.
    });
  });
  document.addEventListener("click", e => document.querySelectorAll(".nav-drop[open]").forEach(d => { if (!d.contains(e.target)) d.open = false; }));
  document.addEventListener("keydown", e => { if (e.key === "Escape") document.querySelectorAll(".nav-drop[open]").forEach(d => d.open = false); });
  addEventListener("scroll", () => document.querySelectorAll(".nav-drop[open]").forEach(d => d.open = false), { passive: true });
})();

// ---- Header v2: search drawer, menu sheet
(function () {
  const drawer = document.getElementById("search-drawer"), sBtn = document.getElementById("search-toggle");
  const sheet = document.getElementById("menu-sheet"), mBtn = document.getElementById("menu-toggle");
  const openSearch = () => { drawer.hidden = false; const i = document.getElementById("global-search"); i && i.focus(); };
  sBtn && sBtn.addEventListener("click", () => { if (drawer.hidden) openSearch(); else drawer.hidden = true; });
  function setMenu(open) {
    sheet.hidden = !open; mBtn.setAttribute("aria-expanded", String(open)); document.body.classList.toggle("menu-open", open);
  }
  mBtn && mBtn.addEventListener("click", () => setMenu(sheet.hidden));
  sheet && sheet.addEventListener("click", e => { if (e.target === sheet || e.target.closest("a")) setMenu(false); });
  document.addEventListener("keydown", e => {
    if (e.key === "Escape") { setMenu(false); if (drawer && !document.getElementById("global-search").value) drawer.hidden = true; }
    if (e.key === "/" && !/input|textarea|select/i.test(document.activeElement.tagName)) { e.preventDefault(); openSearch(); }
  });
})();
