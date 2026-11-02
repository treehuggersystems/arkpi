// ARK·π offline map: stacked PMTiles layers, pins & waypoints, measuring, GPS.
(function () {
  "use strict";
  const { $, store } = window.ARK;
  const LAYERS = window.ARK_MAP_LAYERS || [];
  const KINDS = {
    point:   { label: "Point",        color: "#e3a33b" },
    rally:   { label: "Rally point",  color: "#73b86d" },
    water:   { label: "Water",        color: "#4aa3df" },
    cache:   { label: "Cache",        color: "#c27ddb" },
    shelter: { label: "Shelter",      color: "#d9c9a3" },
    danger:  { label: "Hazard",       color: "#e5573f" },
  };
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const wrapLng = lng => L.Util.wrapNum(lng, [-180, 180], true);

  const saved = store.get("map:view", null);
  const map = L.map("map", { zoomControl: false, worldCopyJump: true, minZoom: 1, maxZoom: 18, doubleClickZoom: true })
    .setView(saved ? saved.c : [39.5, -98.35], saved ? saved.z : 6);
  L.control.zoom({ position: "topleft" }).addTo(map);
  L.control.scale({ imperial: true, metric: true }).addTo(map);
  window._m = map;  // handy from the console

  // ---- Base layers --------------------------------------------------------
  // World is always drawn; the most detailed overlay covering the view is drawn on top and the
  // world's labels are hidden under it. New layers are added before old ones are removed, and the
  // old ones only go once the new one has finished drawing, so switching never flashes blank.
  const flavorFor = t => t === "paper" ? "light" : t === "night" ? "black" : "dark";
  const bboxOf = l => l.bbox ? L.latLngBounds([l.bbox[1], l.bbox[0]], [l.bbox[3], l.bbox[2]]) : null;
  let built = [], active;

  function build() {
    built.forEach(b => { map.removeLayer(b.full); b.nolabel && map.removeLayer(b.nolabel); });
    built = [];
    if (!LAYERS.length) return;
    const probe = protomapsL.leafletLayer({ url: LAYERS[0].url, flavor: flavorFor(document.documentElement.dataset.theme), lang: "en" });
    const paint = probe.paintRules, labels = probe.labelRules, bg = probe.backgroundColor;
    map.getContainer().style.background = bg;
    LAYERS.forEach((cfg, i) => {
      const base = i === 0, bounds = bboxOf(cfg);
      const opts = { url: cfg.url, paintRules: paint, maxDataZoom: cfg.maxzoom, attribution: base ? undefined : "",
                     keepBuffer: 4, ...(base ? { backgroundColor: bg } : { minZoom: cfg.minzoom, bounds: bounds || undefined }) };
      built.push({ cfg, bounds, overlay: !base,
                   full: protomapsL.leafletLayer({ ...opts, labelRules: labels }),
                   nolabel: base ? protomapsL.leafletLayer({ ...opts, labelRules: [] }) : null });
    });
    active = undefined;
    refresh();
  }

  function swapIn(toAdd, toRemove) {
    const add = toAdd.filter(l => !map.hasLayer(l)), remove = toRemove.filter(l => map.hasLayer(l) && !toAdd.includes(l));
    add.forEach(l => l.addTo(map));
    if (!remove.length) return;
    const drop = () => remove.forEach(l => { if (!toAdd.includes(l)) map.removeLayer(l); });
    const newest = add[add.length - 1];
    if (!newest) return drop();
    let done = false;
    const finish = () => { if (!done) { done = true; drop(); } };
    newest.once("load", finish);
    setTimeout(finish, 2500);  // never leave both up for long
  }

  function refresh() {
    if (!built.length) return;
    const z = map.getZoom(), c = map.getCenter();
    let best = null;
    built.forEach(b => { if (b.overlay && z >= b.cfg.minzoom && (!b.bounds || b.bounds.contains(c))) best = b; });
    if (best !== active) {
      const base = built[0];
      const want = best ? [base.nolabel, best.full] : [base.full];
      const all = built.flatMap(b => [b.full, b.nolabel]).filter(Boolean);
      swapIn(want, all);
      active = best;
    }
    $("#zoom").textContent = z;
    $("#active-layer").textContent = (best || built[0] || { cfg: { name: "-" } }).cfg.name;
  }

  map.on("zoomend moveend", () => {
    refresh();
    store.set("map:view", { c: [map.getCenter().lat, map.getCenter().lng], z: map.getZoom() });
  });
  document.addEventListener("ark:theme", build);
  build();

  // ---- Coordinate readout ---------------------------------------------------
  // Shows the pin if one is dropped, else the cursor (desktop) or the map center (phones).
  let pin = null, pinLL = null, fromWp = null, hover = null;
  function showCoords(ll, label) {
    const lat = ll.lat, lng = wrapLng(ll.lng);
    $("#c-label").textContent = label;
    $("#c-dd").textContent = `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
    $("#c-dms").textContent = Geo.dms(lat, lng);
    $("#c-utm").textContent = Math.abs(lat) <= 84 ? Geo.utmString(lat, lng) : "-";
    $("#c-mgrs").textContent = Geo.toMGRS(lat, lng);
    if (fromWp) {
      const d = Geo.distance(fromWp.lat, fromWp.lng, lat, lng), b = Geo.bearing(fromWp.lat, fromWp.lng, lat, lng);
      $("#c-from").textContent = `${Geo.fmtDist(d)} @ ${b.toFixed(0)}° ${Geo.cardinal(b)}`;
    }
  }
  const refreshCoords = () => pinLL ? showCoords(pinLL, "Pin") : hover ? showCoords(hover, "Cursor") : showCoords(map.getCenter(), "Map center");
  map.on("mousemove", e => { hover = e.latlng; if (!pinLL) showCoords(e.latlng, "Cursor"); });
  map.on("mouseout", () => { hover = null; refreshCoords(); });
  map.on("move", () => { if (!pinLL && !hover) showCoords(map.getCenter(), "Map center"); });
  refreshCoords();

  // ---- Pins -------------------------------------------------------------------
  const pinIcon = L.divIcon({ className: "ark-dropped-pin", iconSize: [22, 22], iconAnchor: [11, 11],
    html: '<svg viewBox="0 0 22 22" width="22" height="22"><circle cx="11" cy="11" r="8" fill="none" stroke="#fff" stroke-width="3"/><circle cx="11" cy="11" r="8" fill="none" stroke="#e5573f" stroke-width="2"/><circle cx="11" cy="11" r="2" fill="#e5573f"/></svg>' });

  function pinPopup(ll) {
    const lat = ll.lat, lng = wrapLng(ll.lng);
    return `<div class="pin-pop">
      <div class="mono"><strong>${Geo.toMGRS(lat, lng)}</strong><br>${lat.toFixed(5)}, ${lng.toFixed(5)}</div>
      ${fromWp ? `<div class="hint">${esc(fromWp.name)} → ${Geo.fmtDist(Geo.distance(fromWp.lat, fromWp.lng, lat, lng))} @ ${Geo.bearing(fromWp.lat, fromWp.lng, lat, lng).toFixed(0)}°</div>` : ""}
      <div class="wp-actions">
        <button class="button small" data-act="save">＋ Save waypoint</button>
        <button class="button small ghost" data-act="measure">Measure from here</button>
        <button class="button small ghost" data-act="clear">Clear</button>
      </div></div>`;
  }

  function dropPin(ll, openPopup = true) {
    pinLL = ll;
    if (!pin) pin = L.marker(ll, { icon: pinIcon, draggable: true, keyboard: false }).addTo(map)
      .on("drag", e => { pinLL = e.target.getLatLng(); refreshCoords(); })
      .on("dragend", () => pin.setPopupContent(pinPopup(pinLL)).openPopup())
      .on("click", () => pin.openPopup());
    else pin.setLatLng(ll);
    pin.bindPopup(pinPopup(ll), { closeButton: true, autoPan: true, offset: [0, -6] });
    if (openPopup) pin.openPopup();
    refreshCoords();
  }
  function clearPin() { if (pin) { map.removeLayer(pin); pin = null; } pinLL = null; refreshCoords(); }

  map.on("popupopen", e => {
    const el = e.popup.getElement();
    el.querySelectorAll("[data-act]").forEach(btn => btn.addEventListener("click", () => {
      const act = btn.dataset.act;
      if (act === "save") openWaypointForm({ lat: pinLL.lat, lng: wrapLng(pinLL.lng), name: "", kind: "point" });
      if (act === "measure") { const ll = pinLL; clearPin(); map.closePopup(); startMeasure(ll); }
      if (act === "clear") { map.closePopup(); clearPin(); }
      if (act === "edit") openWaypointForm(waypoints.find(w => w.id === btn.dataset.id));
      if (act === "from") { setFrom(waypoints.find(w => w.id === btn.dataset.id)); map.closePopup(); }
    }));
    bindForm(el);
  });

  // ---- Waypoints ----------------------------------------------------------------
  let waypoints = [];
  const markers = L.layerGroup().addTo(map);

  function wpIcon(kind) {
    const c = (KINDS[kind] || KINDS.point).color;
    return L.divIcon({ className: "ark-pin", iconSize: [26, 34], iconAnchor: [13, 33], popupAnchor: [0, -30],
      html: `<svg viewBox="0 0 26 34" width="26" height="34"><path d="M13 33S2 21 2 12.5a11 11 0 0 1 22 0C24 21 13 33 13 33z" fill="${c}" stroke="#000" stroke-opacity=".5"/><circle cx="13" cy="12.5" r="4" fill="#000" fill-opacity=".55"/></svg>` });
  }
  const kindOptions = sel => Object.entries(KINDS).map(([k, v]) => `<option value="${k}" ${k === sel ? "selected" : ""}>${v.label}</option>`).join("");

  function formHtml(wp) {
    return `<form class="wp-form" data-id="${esc(wp.id || "")}" data-lat="${wp.lat}" data-lng="${wp.lng}">
      <strong>${wp.id ? "Edit waypoint" : "New waypoint"}</strong>
      <input name="name" value="${esc(wp.name)}" placeholder="Name (e.g. Rally point 1)" required autofocus>
      <select name="kind">${kindOptions(wp.kind || "point")}</select>
      <input name="notes" value="${esc(wp.notes)}" placeholder="Notes">
      <div class="mono hint">${Geo.toMGRS(wp.lat, wp.lng)}</div>
      <div class="wp-actions"><button class="button small" type="submit">Save</button>
      ${wp.id ? '<button class="button small ghost" type="button" data-del>Delete</button>' : ""}</div></form>`;
  }
  function openWaypointForm(wp) {
    if (!wp) return;
    L.popup({ offset: [0, wp.id ? -30 : -6] }).setLatLng([wp.lat, wp.lng]).setContent(formHtml(wp)).openOn(map);
  }
  function bindForm(el) {
    const form = el.querySelector(".wp-form");
    if (!form) return;
    const input = form.querySelector("input[name=name]"); setTimeout(() => input && input.focus(), 50);
    form.addEventListener("submit", async e => {
      e.preventDefault();
      const fd = new FormData(form);
      const body = { id: form.dataset.id || undefined, lat: +form.dataset.lat, lng: +form.dataset.lng,
                     name: fd.get("name"), kind: fd.get("kind"), notes: fd.get("notes") };
      await fetch("/api/waypoints", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      map.closePopup(); clearPin(); load();
    });
    const del = form.querySelector("[data-del]");
    del && del.addEventListener("click", async () => {
      if (del.dataset.confirm !== "1") { del.dataset.confirm = "1"; del.textContent = "Really delete?"; return; }
      await fetch("/api/waypoints/" + encodeURIComponent(form.dataset.id), { method: "DELETE" });
      if (fromWp && fromWp.id === form.dataset.id) setFrom(null);
      map.closePopup(); load();
    });
  }

  function wpPopup(w) {
    return `<div class="pin-pop"><strong>${esc(w.name)}</strong> <span class="hint">${esc((KINDS[w.kind] || KINDS.point).label)}</span>
      ${w.notes ? `<div>${esc(w.notes)}</div>` : ""}
      <div class="mono hint">${Geo.toMGRS(w.lat, w.lng)}<br>${w.lat.toFixed(5)}, ${w.lng.toFixed(5)}</div>
      <div class="wp-actions"><button class="button small ghost" data-act="from" data-id="${esc(w.id)}">Distance from here</button>
      <button class="button small ghost" data-act="edit" data-id="${esc(w.id)}">Edit</button></div></div>`;
  }

  function setFrom(wp) {
    fromWp = wp;
    $("#c-from-name").textContent = wp ? wp.name : "-";
    if (!wp) $("#c-from").textContent = "Choose a waypoint (⌖)";
    renderList(); refreshCoords();
  }

  function renderList() {
    const list = $("#wp-list");
    $("#wp-count").textContent = waypoints.length ? `(${waypoints.length})` : "";
    if (!waypoints.length) { list.innerHTML = '<p class="hint">No waypoints yet. Tap the map, then “Save waypoint”.</p>'; return; }
    list.innerHTML = waypoints.map(w => `
      <div class="wp ${fromWp && fromWp.id === w.id ? "from" : ""}" data-id="${esc(w.id)}">
        <span class="wp-dot" style="background:${(KINDS[w.kind] || KINDS.point).color}"></span>
        <button type="button" class="wp-name" data-go>${esc(w.name)}<small>${esc((KINDS[w.kind] || KINDS.point).label)} · ${Geo.toMGRS(w.lat, w.lng, 4)}</small></button>
        <button type="button" class="wp-from" data-from title="Measure distance and bearing from here">⌖</button>
      </div>`).join("");
    list.querySelectorAll(".wp").forEach(el => {
      const w = waypoints.find(x => x.id === el.dataset.id);
      el.querySelector("[data-go]").addEventListener("click", () => { map.setView([w.lat, w.lng], Math.max(map.getZoom(), 14)); w._marker && w._marker.openPopup(); });
      el.querySelector("[data-from]").addEventListener("click", () => setFrom(fromWp && fromWp.id === w.id ? null : w));
    });
  }

  async function load() {
    try { waypoints = await (await fetch("/api/waypoints")).json(); } catch (e) { waypoints = []; }
    waypoints.sort((a, b) => a.name.localeCompare(b.name));
    markers.clearLayers();
    waypoints.forEach(w => {
      w._marker = L.marker([w.lat, w.lng], { icon: wpIcon(w.kind), title: w.name })
        .bindTooltip(esc(w.name), { direction: "top", offset: [0, -30] })
        .bindPopup(wpPopup(w), { offset: [0, 0] })
        .addTo(markers);
    });
    if (fromWp) fromWp = waypoints.find(w => w.id === fromWp.id) || null;
    renderList();
  }
  load();

  // ---- Measure tool ---------------------------------------------------------------
  let measuring = false, mPts = [], mLine = null, mDots = L.layerGroup().addTo(map);
  function startMeasure(first) {
    measuring = true; mPts = []; mDots.clearLayers();
    if (mLine) { map.removeLayer(mLine); mLine = null; }
    document.body.classList.add("measuring");
    $("#measure-box").hidden = false; $("#btn-measure").classList.add("on");
    if (first) addMeasurePoint(first);
    updateMeasure();
  }
  function stopMeasure() {
    measuring = false; document.body.classList.remove("measuring");
    $("#btn-measure").classList.remove("on");
  }
  function clearMeasure() { stopMeasure(); mPts = []; mDots.clearLayers(); if (mLine) map.removeLayer(mLine); mLine = null; $("#measure-box").hidden = true; }
  function addMeasurePoint(ll) {
    mPts.push(L.latLng(ll.lat, wrapLng(ll.lng)));
    L.circleMarker(ll, { radius: 5, color: "#fff", weight: 2, fillColor: "#e3a33b", fillOpacity: 1 }).addTo(mDots);
    if (!mLine) mLine = L.polyline(mPts, { color: "#e3a33b", weight: 3, dashArray: "6 6" }).addTo(map);
    else mLine.setLatLngs(mPts);
    updateMeasure();
  }
  function updateMeasure() {
    let total = 0;
    const legs = [];
    for (let i = 1; i < mPts.length; i++) {
      const a = mPts[i - 1], b = mPts[i];
      const d = Geo.distance(a.lat, a.lng, b.lat, b.lng), brg = Geo.bearing(a.lat, a.lng, b.lat, b.lng);
      total += d; legs.push(`<li>${Geo.fmtDist(d)} @ ${brg.toFixed(0)}° ${Geo.cardinal(brg)}</li>`);
    }
    $("#measure-total").textContent = mPts.length > 1 ? Geo.fmtDist(total) : (mPts.length ? "Tap the next point…" : "Tap the map to start…");
    $("#measure-legs").innerHTML = legs.join("");
    // walking time at ~3 mph on level ground (Naismith)
    $("#measure-time").textContent = total ? `≈ ${Math.round(total / 1609.344 / 3 * 60)} min walking (3 mph, level)` : "";
  }
  $("#btn-measure").addEventListener("click", () => measuring ? stopMeasure() : startMeasure());
  $("#measure-undo").addEventListener("click", () => {
    mPts.pop(); const dots = mDots.getLayers(); if (dots.length) mDots.removeLayer(dots[dots.length - 1]);
    if (mLine) mLine.setLatLngs(mPts); updateMeasure();
  });
  $("#measure-clear").addEventListener("click", clearMeasure);
  document.addEventListener("keydown", e => { if (e.key === "Escape") { map.closePopup(); measuring ? stopMeasure() : clearPin(); } });

  // ---- Map clicks: measure point, or drop/move the pin --------------------------------
  map.on("click", e => {
    if (measuring) return addMeasurePoint(e.latlng);
    dropPin(e.latlng);
  });

  // ---- Locate me (GPS needs HTTPS or localhost) ------------------------------------------
  let gpsWatch = null, gpsDot = null, gpsCircle = null, firstFix = true;
  $("#btn-locate").addEventListener("click", () => {
    const btn = $("#btn-locate");
    if (!window.isSecureContext || !("geolocation" in navigator)) {
      flash(`GPS needs the secure address: https://${location.hostname}/map`); return;
    }
    if (gpsWatch !== null) {
      navigator.geolocation.clearWatch(gpsWatch); gpsWatch = null; btn.classList.remove("on");
      [gpsDot, gpsCircle].forEach(l => l && map.removeLayer(l)); gpsDot = gpsCircle = null; return;
    }
    btn.classList.add("on"); firstFix = true; flash("Finding your location…");
    gpsWatch = navigator.geolocation.watchPosition(p => {
      const ll = [p.coords.latitude, p.coords.longitude];
      if (!gpsDot) {
        gpsCircle = L.circle(ll, { radius: p.coords.accuracy, color: "#4aa3df", weight: 1, fillOpacity: 0.12 }).addTo(map);
        gpsDot = L.circleMarker(ll, { radius: 7, color: "#fff", weight: 2, fillColor: "#4aa3df", fillOpacity: 1 }).addTo(map)
          .bindTooltip("You are here");
      } else { gpsDot.setLatLng(ll); gpsCircle.setLatLng(ll).setRadius(p.coords.accuracy); }
      if (firstFix) { map.setView(ll, Math.max(map.getZoom(), 15)); firstFix = false; flash(`Located (±${Math.round(p.coords.accuracy)} m)`); }
    }, err => { flash("Location unavailable: " + err.message); btn.classList.remove("on"); gpsWatch = null; },
    { enableHighAccuracy: true, maximumAge: 5000, timeout: 20000 });
  });

  // ---- Fullscreen ---------------------------------------------------------------------
  $("#btn-full").addEventListener("click", () => {
    document.body.classList.toggle("map-full");
    $("#btn-full").classList.toggle("on");
    setTimeout(() => map.invalidateSize(), 200);
  });

  // ---- Go to: "lat, lon", MGRS-free text, or waypoint name --------------------------------
  $("#goto").addEventListener("submit", e => {
    e.preventDefault();
    const q = $("#goto-q").value.trim();
    const m = q.match(/^(-?\d+(?:\.\d+)?)[,\s]+(-?\d+(?:\.\d+)?)$/);
    if (m) { const ll = L.latLng(+m[1], +m[2]); map.setView(ll, Math.max(map.getZoom(), 13)); dropPin(ll); return; }
    const w = waypoints.find(x => x.name.toLowerCase().includes(q.toLowerCase()));
    if (w) { map.setView([w.lat, w.lng], Math.max(map.getZoom(), 14)); w._marker.openPopup(); }
    else flash("No waypoint matches “" + q + "”");
  });

  // ---- Tiny toast -----------------------------------------------------------------------
  let toastT;
  function flash(msg) {
    const t = $("#map-toast"); t.textContent = msg; t.hidden = false;
    clearTimeout(toastT); toastT = setTimeout(() => { t.hidden = true; }, 4000);
  }
})();
