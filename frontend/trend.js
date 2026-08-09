'use strict';
// Multi-pen trend, hosted in a SEPARATE browser window (trend.html).
//
// Two runtime roles share this one file:
//   * POPUP  (trend.html sets window.__OTS_TREND_POPUP__) — builds the full-page trend UI,
//            opens its OWN WebSocket to /ws, backfills from /api/hist, and owns all rendering.
//   * LAUNCHER (the main DCS app) — never renders a trend inline; it opens/focuses the popup
//            window and hands tags across via a localStorage queue + BroadcastChannel. Native
//            drag from a main-screen indicator onto the popup is preserved with a dragend
//            screen-rect test, since HTML5 drag payloads do not cross window boundaries.
//
// Tag -> packet path resolution uses window.OV_BINDS in the main window; the popup reads the
// mirror overlays.js writes to localStorage('ots_ov_binds').
(function () {
  const POPUP = (typeof window !== 'undefined') && window.__OTS_TREND_POPUP__ === true;
  const HAS_DOM = (typeof document !== 'undefined');

  const LSK = 'ots_trend_v1';
  const BINDS_KEY = 'ots_ov_binds';
  const PENDING_KEY = 'ots_trend_pending';
  const CH_NAME = 'ots_trend';
  const POPUP_NAME = 'ots_trend_popup';
  const SLOTS = 10;
  const SPANS = [
    { s: 60,    lbl: '1m'  }, { s: 300,   lbl: '5m'  }, { s: 1800,  lbl: '30m' },
    { s: 3600,  lbl: '1h'  }, { s: 7200,  lbl: '2h'  }, { s: 14400, lbl: '4h'  },
    { s: 28800, lbl: '8h'  },
  ];
  const DEFAULT_SPAN = 3600;          // 1 h, per requirement
  const REDRAW_MS = 250;              // 4 Hz; packets arrive at 10 Hz
  const LIVE_MIN_DT = 1.0;            // plant-seconds between live samples (matches fast ring)
  const MAX_POINTS = 800;
  const RULERS_MAX = 10;
  // Ten distinct ruler colours, well separated on the dark canvas; labels carry R1..R10 so
  // identity never rests on colour alone.
  const RULER_COLORS = ['#ffd000', '#41e0ff', '#ff5db1', '#7CFC00', '#ff8c1a',
                        '#b47cff', '#ff4d4d', '#2ee6a6', '#f0f0f0', '#7aa5ff'];

  // Pen palette: ui_guidelines §10 tokens first, then distinct additions.
  const PENS = ['#22ff22', '#7fd0d8', '#ffd000', '#ff9a3c', '#ff00ff',
                '#5fe08f', '#e06f6f', '#9bbabb', '#c78fff', '#ffffff'];

  const UNIT_RANGE = {
    '%': [0, 100], 'C': [0, 250], 'BAR G': [0, 200], 'BARG': [0, 200], 'BAR A': [0, 200],
    'T/H': [0, 100], 'RPM': [0, 3000], 'A': [0, 200], 'NM3/H': [0, 40000],
    'KG/H': [0, 50000], 'M3/H': [0, 500], 'KW': [0, 5000], '': [0, 1],
  };

  const gp = (o, path) => path ? path.split('.').reduce((a, k) => (a == null ? undefined : a[k]), o) : undefined;
  const clamp = (v, lo, hi) => v < lo ? lo : v > hi ? hi : v;
  const pad2 = n => (n < 10 ? '0' : '') + n;

  function hms(sec) {
    sec = Math.max(0, Math.floor(sec));
    return pad2(Math.floor(sec / 3600)) + ':' + pad2(Math.floor(sec / 60) % 60) + ':' + pad2(sec % 60);
  }
  function deskClock(epoch) {
    if (epoch == null || !isFinite(epoch)) return '--:--:--';
    const d = new Date(epoch * 1000);
    return pad2(d.getHours()) + ':' + pad2(d.getMinutes()) + ':' + pad2(d.getSeconds());
  }
  function stamp(d) {
    return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate()) + '_' +
           pad2(d.getHours()) + '-' + pad2(d.getMinutes()) + '-' + pad2(d.getSeconds());
  }

  // ================= tag registry =================
  let _bindsCache = null;
  function binds() {
    if (typeof window !== 'undefined' && window.OV_BINDS) return window.OV_BINDS;   // main window: live map
    if (_bindsCache) return _bindsCache;                                            // popup: localStorage mirror
    try { _bindsCache = JSON.parse((typeof localStorage !== 'undefined' && localStorage.getItem(BINDS_KEY)) || 'null') || {}; }
    catch (e) { _bindsCache = {}; }
    return _bindsCache;
  }
  const Registry = {
    entry(tag) {
      const b = binds()[tag];
      if (!b || !b.bind) return null;
      let u = (b.u || '').toUpperCase();
      let rng = b.rng || UNIT_RANGE[u] || null;
      return { tag: tag, path: b.bind, unit: u === 'BAR A' ? 'BARG' : u, dec: b.dec == null ? 1 : b.dec,
               range: rng, gauge: u === 'BAR A' };
    },
    value(pkt, e) {
      let v = gp(pkt, e.path);
      if (typeof v === 'boolean') return v ? 1 : 0;
      if (typeof v !== 'number' || !isFinite(v)) return null;
      if (e.gauge) v = v - 1.01325;
      return v;
    },
    bound(tag) { return !!this.entry(tag); },
  };

  // ================= state =================
  const slots = [];                    // {tag, entry, pts:[{t,v}], colour, lo, hi, auto}
  for (let i = 0; i < SLOTS; i++) slots.push(null);
  let span = DEFAULT_SPAN;
  let highlights = new Set();        // slot indices whose trend is highlighted (checkbox-marked); empty = all full strength
  let axisPen = -1;                  // slot index whose engineering range labels the Y axis (last marked); -1 = percent grid
  let chart = null, win = null, lastPacket = null;
  let rulers = [];                     // absolute plant seconds; up to RULERS_MAX, coloured by index
  let dragRuler = -1, dragMoved = false; // index of the ruler being dragged; whether the pointer moved
  let viewEndT = null;                 // right edge (abs plant s); null = live
  const PAN_FRACTION = 0.25;
  let nowSim = 0, nowWall = 0;
  let timeMap = [];
  let dirty = false, redrawTimer = null;
  let histOK = true;

  function saved() {
    try { return JSON.parse(localStorage.getItem(LSK)) || {}; } catch (e) { return {}; }
  }
  function save() {
    const st = saved();
    st.span = span; st.hl = [...highlights]; st.axis = axisPen;
    st.tags = slots.map(s => s && s.tag);
    st.ranges = slots.map(s => (s && !s.auto) ? [s.lo, s.hi] : null);
    st.open = true;
    try { localStorage.setItem(LSK, JSON.stringify(st)); } catch (e) { /* quota: ignore */ }
  }

  // ================= history =================
  function noteTime(tSim, tWall) {
    if (tSim == null || tWall == null) return;
    const last = timeMap[timeMap.length - 1];
    if (last && tSim - last[0] < 1.0) return;
    timeMap.push([tSim, tWall]);
    const cut = tSim - 28800;
    while (timeMap.length > 2 && timeMap[0][0] < cut) timeMap.shift();
  }
  function wallAt(tSim) {
    if (!timeMap.length) return nowWall;
    if (tSim < timeMap[0][0]) return null;
    if (tSim === timeMap[0][0]) return timeMap[0][1];
    for (let i = timeMap.length - 1; i >= 0; i--) {
      if (timeMap[i][0] <= tSim) {
        const a = timeMap[i], b = timeMap[i + 1];
        if (!b) return a[1] + (tSim - a[0]);
        const f = (tSim - a[0]) / Math.max(1e-9, b[0] - a[0]);
        return a[1] + f * (b[1] - a[1]);
      }
    }
    return nowWall;
  }

  function viewEnd() { return viewEndT == null ? nowSim : viewEndT; }
  function isLive() { return viewEndT == null; }
  function maxPanBack() { return Math.max(0, Math.min(nowSim, 28800) - span); }

  function backfill(slot) {
    if (!slot) return Promise.resolve();
    if (typeof fetch !== 'function') return Promise.resolve();
    const url = '/api/hist?paths=' + encodeURIComponent(slot.entry.path) +
                '&span=' + span + '&max=' + MAX_POINTS +
                (isLive() ? '' : '&end=' + viewEndT.toFixed(3));
    return fetch(url).then(r => {
      if (!r.ok) throw new Error('hist ' + r.status);
      return r.json();
    }).then(j => {
      histOK = true;
      const vals = (j.series || {})[slot.entry.path];
      if (!vals) return;
      const pts = [];
      for (let i = 0; i < vals.length; i++) {
        const v = vals[i], t = j.t_sim[i];
        if (v == null || t == null) continue;
        pts.push({ t: t, v: slot.entry.gauge ? v - 1.01325 : v });
        noteTime(t, j.t_wall[i]);
      }
      const edge = pts.length ? pts[pts.length - 1].t : -Infinity;
      slot.pts = pts.concat(slot.pts.filter(p => p.t > edge));
      dirty = true;
    }).catch(() => { histOK = false; markHist(); });
  }

  // ================= scaling / readings =================
  function norm(slot, v) {
    const lo = slot.lo, hi = slot.hi;
    if (hi - lo < 1e-12) return 50;
    return (v - lo) / (hi - lo) * 100;
  }
  function rescale(slot) {
    if (!slot.auto) return;
    let lo = Infinity, hi = -Infinity;
    const ve = viewEnd(), cut = ve - span;
    for (const p of slot.pts) {
      if (p.t < cut || p.t > ve) continue;
      if (p.v < lo) lo = p.v;
      if (p.v > hi) hi = p.v;
    }
    if (!isFinite(lo) || !isFinite(hi)) return;      // no visible samples: keep the seeded range
    if (hi - lo < 1e-9) { lo -= 0.5; hi += 0.5; }    // flat trace: give it a readable band
    const pad = (hi - lo) * 0.05;                     // slightly below MIN, slightly above MAX
    slot.lo = lo - pad; slot.hi = hi + pad;
  }

  // Hold semantics: last sample at or before t. Correct for a DCS cursor and a stepped pen.
  function valueAt(slot, t) {
    if (t == null || !slot || !slot.pts.length) return null;
    let best = null;
    for (const p of slot.pts) {
      if (p.t > t) break;
      best = p;
    }
    return best ? best.v : null;
  }

  // MIN / MAX / AVG over the points currently in view [viewEnd-span, viewEnd].
  function windowStats(slot) {
    if (!slot || !slot.pts.length) return null;
    const ve = viewEnd(), cut = ve - span;
    let mn = Infinity, mx = -Infinity, sum = 0, n = 0;
    for (const p of slot.pts) {
      if (p.t < cut || p.t > ve) continue;
      if (p.v < mn) mn = p.v;
      if (p.v > mx) mx = p.v;
      sum += p.v; n++;
    }
    if (!n) return null;
    return { min: mn, max: mx, avg: sum / n, n: n };
  }

  // ================= rulers =================
  function addRuler(t) {
    if (t == null) return false;
    if (rulers.some(r => Math.abs(r - t) < 1e-6)) return false;    // no duplicate at the same instant
    if (rulers.length >= RULERS_MAX) { flash(null, 'MAX ' + RULERS_MAX + ' RULERS'); return false; }
    rulers.push(t);
    dirty = true; if (win && chart) redraw();
    return true;
  }
  function removeRuler(i) {
    if (i < 0 || i >= rulers.length) return;
    rulers.splice(i, 1);
    dirty = true; if (win && chart) redraw();
  }
  function clearRulers() { rulers = []; dirty = true; if (win && chart) redraw(); }
  // Slide an existing ruler to a new instant, clamped to the visible window. Drives the drag handler.
  function moveRuler(i, t) {
    if (i < 0 || i >= rulers.length || t == null) return false;
    const ve = viewEnd();
    rulers[i] = clamp(t, ve - span, ve);
    dirty = true; if (win && chart) redraw();
    return true;
  }
  // Backward-compatible single-ruler shims (kept for the earlier API + tests).
  function setCursor(t) { if (t == null) clearRulers(); else { rulers = [t]; dirty = true; if (win && chart) redraw(); } }

  // Vertical rulers as a Chart.js plugin: drawn inside the bitmap, so the PNG export gets them free.
  const rulerPlugin = {
    id: 'otsRulers',
    afterDatasetsDraw(ch) {
      if (!rulers.length) return;
      const area = ch.chartArea, g = ch.ctx, ve = viewEnd();
      rulers.forEach((t, i) => {
        const x = ch.scales.x.getPixelForValue(t - ve);
        if (!(x >= area.left && x <= area.right)) return;
        const col = RULER_COLORS[i % RULER_COLORS.length];
        g.save();
        g.strokeStyle = col; g.lineWidth = 1; g.setLineDash([4, 3]);
        g.beginPath(); g.moveTo(x, area.top); g.lineTo(x, area.bottom); g.stroke();
        g.setLineDash([]);
        const label = 'R' + (i + 1) + ' ' + hms(t);
        g.font = 'bold 10px Consolas, monospace';
        const bw = g.measureText(label).width + 8;
        const bx = clamp(x - bw / 2, area.left, Math.max(area.left, area.right - bw));
        const by = Math.min(area.top + i * 15, area.bottom - 13);  // stack labels, clamp inside the plot
        g.fillStyle = col; g.fillRect(bx, by, bw, 13);
        g.fillStyle = '#101010'; g.fillText(label, bx + 4, by + 9.5);
        g.restore();
      });
    },
  };

  // Pixel<->time helpers + ruler hit-testing, shared by click-to-add and drag-to-move.
  const RULER_HIT_PX = 6;                              // grab tolerance around a ruler line
  function pxToTime(px) { return viewEnd() + chart.scales.x.getValueForPixel(px); }
  function rulerNear(px) {
    let best = -1, bd = RULER_HIT_PX + 0.5;
    for (let i = 0; i < rulers.length; i++) {
      const d = Math.abs(chart.scales.x.getPixelForValue(rulers[i] - viewEnd()) - px);
      if (d < bd) { bd = d; best = i; }
    }
    return best;
  }

  function buildChart() {
    const cv = win.querySelector('#tw-canvas');
    chart = new Chart(cv.getContext('2d'), {
      plugins: [rulerPlugin],
      type: 'line',
      data: { datasets: slots.map((_, i) => ({
        label: 'slot' + i, data: [], parsing: false, borderColor: PENS[i],
        borderWidth: 1.4, pointRadius: 0, tension: 0, spanGaps: false, xAxisID: 'x',
      })) },
      options: {
        animation: false, responsive: true, maintainAspectRatio: false,
        interaction: { mode: 'nearest', axis: 'x', intersect: false },
        scales: {
          x: {
            type: 'linear', min: -span, max: 0,
            grid: { color: '#1e3a34' },
            ticks: { color: '#8fb3ab', maxTicksLimit: 8, font: { size: 10 },
                     callback: v => (viewEnd() + v) < 0 ? '' : hms(viewEnd() + v) },
            title: { display: true, text: 'PLANT CLOCK', color: '#5fe08f', font: { size: 10, weight: 'bold' } },
          },
          x2: {
            type: 'linear', position: 'bottom', min: -span, max: 0, display: true,
            grid: { drawOnChartArea: false, color: '#16292c' },
            ticks: { color: '#7f9ba8', maxTicksLimit: 8, font: { size: 10 },
                     callback: v => { const w = wallAt(viewEnd() + v); return w == null ? '' : deskClock(w); } },
            title: { display: true, text: 'DESKTOP CLOCK', color: '#7f9ba8', font: { size: 10 } },
          },
          y: {
            min: -2, max: 102,
            grid: { color: '#1e3a34' },
            ticks: { color: '#d6f3e4', font: { size: 10 }, stepSize: 20,
                     callback: pct => {
                       if (pct < -0.001 || pct > 100.001) return '';
                       const s = slots[axisPen];
                       if (!s) return pct + '%';
                       const v = s.lo + (pct / 100) * (s.hi - s.lo);
                       return v.toFixed(s.entry.dec);
                     } },
          },
        },
        plugins: { legend: { display: false }, tooltip: { enabled: false } },
      },
    });
  }

  function redraw() {
    if (!chart || !win) return;
    const ve = viewEnd(), cut = ve - span;
    // Drop any ruler that has scrolled out of view — its readings would point at nothing.
    for (let i = rulers.length - 1; i >= 0; i--) if (rulers[i] < cut || rulers[i] > ve) rulers.splice(i, 1);
    chart.options.scales.x.min = -span;
    chart.options.scales.x2.min = -span;
    for (let i = 0; i < SLOTS; i++) {
      const slot = slots[i], ds = chart.data.datasets[i];
      if (!slot) { ds.data = []; continue; }
      rescale(slot);
      const bool = slot.lo === 0 && slot.hi === 1 && slot.entry.unit === '';
      ds.stepped = bool ? 'before' : false;
      const pts = [];
      for (const p of slot.pts) {
        if (p.t < cut || p.t > ve) continue;
        pts.push({ x: p.t - ve, y: norm(slot, p.v) });
      }
      ds.data = pts;
      // Highlight every checkbox-marked pen: thicken it, keep full colour, and draw it last (on top);
      // fade the unmarked pens so the marked trends stand out. No marks = all pens keep full strength.
      const hi = highlights.has(i), fade = highlights.size > 0 && !hi;
      ds.borderWidth = hi ? 3.2 : 1.4;
      ds.borderColor = fade ? (PENS[i] + '40') : PENS[i];   // +40 = 25% alpha (8-digit hex)
      ds.order = hi ? 1 : 0;                                 // Chart.js draws higher order last -> marked pens on top
    }
    chart.update('none');
    renderRows();
    renderRulerChips();
    win.querySelector('#tw-plant').textContent = hms(nowSim);
    win.querySelector('#tw-desk').textContent = deskClock(nowWall);
    win.querySelector('#tw-live').classList.toggle('hist', !isLive());
    win.querySelector('#tw-live').textContent = isLive() ? 'LIVE' : 'HISTORY';
    win.querySelector('#tw-fwd').disabled = isLive();
    win.querySelector('#tw-back').disabled = (nowSim - viewEnd()) >= maxPanBack() - 1e-6;
  }

  function renderRulerChips() {
    const box = win.querySelector('#tw-rulers-list');
    if (!rulers.length) { box.innerHTML = '<span class="rnone">click plot to add · drag to move (up to ' + RULERS_MAX + ')</span>'; return; }
    box.innerHTML = rulers.map((t, i) => {
      const col = RULER_COLORS[i % RULER_COLORS.length];
      const w = wallAt(t);
      return '<span class="rchip" style="color:' + col + ';border-color:' + col + '">R' + (i + 1) + ' ' +
             hms(t) + (w == null ? '' : ' / ' + deskClock(w)) +
             ' <b data-ri="' + i + '">&#10005;</b></span>';
    }).join('');
  }

  function pan(dir) {
    const step = span * PAN_FRACTION * dir;
    let target = viewEnd() + step;
    const oldest = nowSim - maxPanBack();
    if (target >= nowSim) viewEndT = null;
    else viewEndT = Math.max(target, oldest);
    Promise.all(slots.filter(Boolean).map(backfill)).then(() => { dirty = true; redraw(); });
    dirty = true; redraw();
  }
  function goLive() {
    if (isLive()) return;
    viewEndT = null;
    Promise.all(slots.filter(Boolean).map(backfill)).then(() => { dirty = true; redraw(); });
    dirty = true; redraw();
  }
  function scheduleRedraw() {
    if (redrawTimer) return;
    redrawTimer = setTimeout(() => { redrawTimer = null; if (dirty) { dirty = false; redraw(); } }, REDRAW_MS);
  }

  // ================= pen table =================
  function renderRows() {
    if (!win) return;
    const tb = win.querySelector('#tw-rows');
    // ruler column headers/visibility
    const th = win.querySelectorAll('#tw-head-row .h-r');
    for (let r = 0; r < RULERS_MAX; r++) {
      const on = r < rulers.length;
      th[r].style.display = on ? '' : 'none';
      if (on) { th[r].textContent = 'R' + (r + 1); th[r].style.color = RULER_COLORS[r]; }
    }
    for (let i = 0; i < SLOTS; i++) {
      const tr = tb.children[i], slot = slots[i];
      tr.className = (highlights.has(i) ? 'sel ' : '') + (slot ? 'full' : 'empty');
      const q = sel => tr.querySelector(sel);
      const loI = q('.c-lo input'), hiI = q('.c-hi input');
      q('.c-n').textContent = i + 1;
      const cb = q('.c-hl input'); cb.checked = highlights.has(i); cb.disabled = !slot;
      q('.c-k i').style.background = PENS[i];
      const rc = tr.querySelectorAll('.c-r');
      if (!slot) {
        q('.c-t').textContent = '-- drop indicator here --';
        q('.c-v').textContent = ''; q('.c-min').textContent = ''; q('.c-max').textContent = '';
        q('.c-avg').textContent = ''; q('.c-u').textContent = '';
        rc.forEach(c => { c.textContent = ''; c.style.display = 'none'; });
        loI.value = ''; hiI.value = ''; loI.disabled = hiI.disabled = true;
        q('.c-x').textContent = '';
        continue;
      }
      const dec = slot.entry.dec;
      const last = slot.pts.length ? slot.pts[slot.pts.length - 1] : null;
      const stale = last && (nowSim - last.t) > 30;
      q('.c-t').textContent = slot.tag;
      q('.c-v').textContent = last ? last.v.toFixed(dec) : '--';
      const st = windowStats(slot);
      q('.c-min').textContent = st ? st.min.toFixed(dec) : '--';
      q('.c-max').textContent = st ? st.max.toFixed(dec) : '--';
      q('.c-avg').textContent = st ? st.avg.toFixed(dec) : '--';
      for (let r = 0; r < RULERS_MAX; r++) {
        const cell = rc[r], on = r < rulers.length;
        cell.style.display = on ? '' : 'none';
        if (!on) { cell.textContent = ''; continue; }
        const at = valueAt(slot, rulers[r]);
        cell.textContent = at == null ? '--' : at.toFixed(dec);
        cell.style.color = RULER_COLORS[r];
      }
      q('.c-u').textContent = stale ? 'STALE' : slot.entry.unit;
      loI.disabled = hiI.disabled = false;
      if (document.activeElement !== loI) loI.value = slot.lo.toFixed(dec);
      if (document.activeElement !== hiI) hiI.value = slot.hi.toFixed(dec);
      loI.classList.toggle('auto', slot.auto);
      hiI.classList.toggle('auto', slot.auto);
      q('.c-x').textContent = 'x';
    }
  }

  function commitRange(i, which, inp) {
    const slot = slots[i];
    if (!slot) { inp.value = ''; return; }
    if (inp.value.trim() === '') { slot.auto = true; dirty = true; redraw(); save(); return; }
    const v = Number(inp.value);
    const lo = which === 'lo' ? v : slot.lo;
    const hi = which === 'hi' ? v : slot.hi;
    if (!isFinite(v) || hi - lo <= 0) { renderRows(); flash(i, 'BAD RANGE'); return; }
    slot.lo = lo; slot.hi = hi; slot.auto = false;
    dirty = true; redraw(); save();
  }
  function markHist() {
    if (!win) return;
    win.querySelector('#tw-hist').style.display = histOK ? 'none' : 'inline-block';
  }

  // ================= slot operations (core) =================
  function coreAddTag(tag, index) {
    const e = Registry.entry(tag);
    if (!e) { flash(index, 'NOT BOUND'); return false; }
    const existing = slots.findIndex(s => s && s.tag === tag);
    if (existing >= 0 && (index == null || index === existing)) { dirty = true; scheduleRedraw(); return true; }
    let i = index;
    if (i == null) i = slots.findIndex(s => !s);
    if (i == null || i < 0) { flash(null, 'SLOTS FULL'); return false; }
    const rng = e.range;
    // Analog pens auto-scale off the displayed data by default; digital on/off pens (no unit)
    // stay pinned to 0..1 so their stepped trace keeps full-scale height. The declared range
    // just seeds lo/hi until the first samples arrive.
    const digital = e.unit === '';
    slots[i] = { tag: tag, entry: e, pts: [], colour: PENS[i],
                 lo: rng ? rng[0] : 0, hi: rng ? rng[1] : 1, auto: !digital };
    backfill(slots[i]).then(() => { dirty = true; scheduleRedraw(); });
    dirty = true; scheduleRedraw(); save();
    return true;
  }
  function removeSlot(i) {
    slots[i] = null;
    highlights.delete(i);
    if (axisPen === i) axisPen = highlights.size ? [...highlights][highlights.size - 1] : -1;
    dirty = true; scheduleRedraw(); save();
  }
  // Highlight control: mark/unmark a pen's trend via its row tickbox. Multiple pens can be marked at
  // once; every marked trend is thickened and drawn on top while the unmarked pens fade. The most
  // recently marked pen also drives the Y-axis engineering scale (axisPen).
  function setHighlight(i, on) {
    if (i == null || i < 0 || i >= SLOTS) return false;
    if (!slots[i]) on = false;
    if (on) { highlights.add(i); axisPen = i; }
    else {
      highlights.delete(i);
      if (axisPen === i) axisPen = highlights.size ? [...highlights][highlights.size - 1] : -1;
    }
    dirty = true; redraw(); save();
    return highlights.has(i);
  }
  function toggleHighlight(i) { return setHighlight(i, !highlights.has(i)); }
  function flash(index, msg) {
    if (!win) return;
    const el = win.querySelector('#tw-flash');
    el.textContent = msg; el.style.opacity = '1';
    setTimeout(() => { el.style.opacity = '0'; }, 1400);
  }
  // Parse a user-typed span string: "30s" → 30, "10m" → 600, "3h" → 10800.
  // Returns null if unparseable or out of the 5 s – 24 h range.
  function parseSpan(str) {
    const m = (str || '').trim().match(/^(\d+(?:\.\d+)?)\s*([smh]?)$/i);
    if (!m) return null;
    const n = parseFloat(m[1]);
    const unit = (m[2] || 's').toLowerCase();
    const s = unit === 'h' ? n * 3600 : unit === 'm' ? n * 60 : n;
    return (isFinite(s) && s >= 5 && s <= 86400) ? Math.round(s) : null;
  }
  function applyCustomSpan(inp) {
    const s = parseSpan(inp.value);
    if (s == null) { flash(null, 'BAD SPAN (e.g. 30s 10m 3h)'); inp.classList.remove('on'); return; }
    setSpan(s);
  }
  function setSpan(s) {
    span = s;
    win.querySelectorAll('#tw-spans button').forEach(b => b.classList.toggle('on', Number(b.dataset.span) === s));
    const ci = win.querySelector('#tw-spans .cust-inp');
    if (ci) ci.classList.toggle('on', !SPANS.some(x => x.s === s) && parseSpan(ci.value) === s);
    Promise.all(slots.filter(Boolean).map(backfill)).then(() => { dirty = true; redraw(); });
    save();
  }

  // ================= export =================
  function exportPNG() {
    const cv = win.querySelector('#tw-canvas');
    const W = Math.max(cv.width, 900), headH = 58, rowH = 18;
    const live = slots.filter(Boolean);
    const H = headH + cv.height + 10 + (live.length + 1) * rowH + 12;
    const out = document.createElement('canvas');
    out.width = W; out.height = H;
    const c = out.getContext('2d');
    c.fillStyle = '#0a1416'; c.fillRect(0, 0, W, H);
    c.fillStyle = '#13202c'; c.fillRect(0, 0, W, headH);
    c.fillStyle = '#cfe'; c.font = 'bold 16px "Segoe UI", system-ui';
    c.fillText('UREA OTS — TREND REPORT', 12, 24);
    c.font = '12px Consolas, monospace'; c.fillStyle = '#8fb3ab';
    const d = new Date();
    c.fillText('PLANT ' + hms(nowSim) + '    DESKTOP ' + d.toLocaleString() +
               '    SPAN ' + (SPANS.find(x => x.s === span) || {}).lbl +
               (rulers.length ? '    RULERS ' + rulers.map(t => hms(t)).join(', ') : ''), 12, 44);
    c.drawImage(cv, 0, headH);

    let y = headH + cv.height + 24;
    const pad = (s, n) => String(s).padStart(n);
    const rhdr = rulers.map((_, i) => pad('R' + (i + 1), 10)).join('');
    c.font = 'bold 11px Consolas, monospace'; c.fillStyle = '#82b3a3';
    c.fillText('#  TAG                 ' + pad('VALUE', 9) + pad('MIN', 9) + pad('MAX', 9) + pad('AVG', 9) +
               rhdr + '  UNIT      ' + pad('LOW', 10) + pad('HIGH', 10), 12, y);
    c.font = '11px Consolas, monospace';
    live.forEach((s) => {
      y += rowH;
      const i = slots.indexOf(s), dec = s.entry.dec;
      const last = s.pts.length ? s.pts[s.pts.length - 1] : null;
      const st = windowStats(s);
      c.fillStyle = PENS[i]; c.fillRect(12, y - 8, 10, 8);
      c.fillStyle = '#d6f3e4';
      let line = pad(i + 1, 2) + ' ' + s.tag.padEnd(20) +
        pad(last ? last.v.toFixed(dec) : '--', 9) +
        pad(st ? st.min.toFixed(dec) : '--', 9) +
        pad(st ? st.max.toFixed(dec) : '--', 9) +
        pad(st ? st.avg.toFixed(dec) : '--', 9);
      rulers.forEach(t => { const at = valueAt(s, t); line += pad(at == null ? '--' : at.toFixed(dec), 10); });
      line += '  ' + s.entry.unit.padEnd(8) + pad(s.lo.toFixed(dec), 10) + pad(s.hi.toFixed(dec), 10) + (s.auto ? ' (auto)' : '');
      c.fillText(line, 28, y);
    });

    const name = 'Trend_Report_' + stamp(d) + '.png';
    out.toBlob(blob => {
      if (window.showSaveFilePicker) {
        window.showSaveFilePicker({ suggestedName: name, types: [{ description: 'PNG image', accept: { 'image/png': ['.png'] } }] })
          .then(h => h.createWritable()).then(w => w.write(blob).then(() => w.close())).catch(() => {});
      } else {
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob); a.download = name; a.click();
        setTimeout(() => URL.revokeObjectURL(a.href), 5000);
      }
    }, 'image/png');
  }

  // ================= DOM =================
  function injectCSS() {
    if (document.getElementById('tw-css')) return;
    const st = document.createElement('style');
    st.id = 'tw-css';
    st.textContent = `
body.tw-popup{margin:0;background:#0a1416;overflow:hidden;}
.tw-popup #trendwin{position:static;width:100vw;height:100vh;min-width:0;min-height:0;border:none;
  resize:none;display:block;box-shadow:none;}
#trendwin{position:fixed;z-index:400;display:none;background:#13202c;border:1px solid #4aa587;
  box-shadow:0 8px 28px rgba(0,0,0,.6);color:#cfe;font:13px "Segoe UI",system-ui;
  min-width:520px;min-height:360px;overflow:hidden;}
#tw-head{display:flex;align-items:center;gap:8px;padding:6px 8px;background:#0f1a24;
  border-bottom:1px solid #2a4a44;user-select:none;}
#tw-close{width:20px;height:20px;line-height:18px;text-align:center;cursor:pointer;
  background:#3a0d0d;border:1px solid #ff3030;color:#ff8a8a;font-weight:bold;border-radius:3px;}
#tw-close:hover{background:#5a1414;}
#tw-title{font-weight:bold;letter-spacing:1px;}
#tw-hist{display:none;font:10px Consolas,monospace;background:#3a2a08;border:1px solid #b3892f;
  color:#ffd27f;padding:1px 5px;border-radius:3px;}
#tw-plot canvas{cursor:crosshair;}
#tw-bar{display:flex;align-items:center;gap:8px;padding:4px 8px;background:#0f1a24;
  border-top:1px solid #2a4a44;border-bottom:1px solid #2a4a44;flex-wrap:wrap;}
#tw-back,#tw-fwd{font:12px Arial;line-height:1;background:#1b2a30;color:#7fd0d8;
  border:1px solid #4aa587;padding:3px 10px;cursor:pointer;border-radius:3px;}
#tw-back:hover:not(:disabled),#tw-fwd:hover:not(:disabled){background:#22424a;}
#tw-back:disabled,#tw-fwd:disabled{color:#3d5a56;border-color:#22363a;cursor:default;}
#tw-live{font:bold 10px Consolas,monospace;letter-spacing:.5px;padding:2px 7px;border-radius:3px;
  background:#0b2b1a;border:1px solid #22ff22;color:#5fe08f;cursor:default;}
#tw-live.hist{background:#3a2f08;border-color:#ffd000;color:#ffd000;cursor:pointer;}
#tw-bar .twb{display:flex;align-items:center;gap:6px;padding:2px 8px;border-radius:3px;
  background:#0b1a16;border:1px solid #22363a;}
#tw-bar .twb label{font:bold 9px "Segoe UI",system-ui;letter-spacing:.6px;color:#82b3a3;}
#tw-bar .twb span{font:bold 12px Consolas,monospace;font-variant-numeric:tabular-nums;color:#5fe08f;}
#tw-bar .twb span+span{color:#7f9ba8;font-weight:normal;}
#tw-rulers{flex:1 1 260px;min-width:180px;}
#tw-rulers-list{display:inline-flex;flex-wrap:wrap;gap:4px;}
#tw-rulers-list .rnone{font:italic 11px Consolas,monospace;color:#54706c;}
.rchip{font:bold 10px Consolas,monospace;font-variant-numeric:tabular-nums;border:1px solid;
  border-radius:3px;padding:1px 5px;}
.rchip b{cursor:pointer;margin-left:3px;opacity:.8;}
.rchip b:hover{opacity:1;}
#tw-spans{margin-left:auto;display:flex;gap:2px;align-items:center;}
#tw-spans button{font:bold 11px Arial;background:#1b2a30;color:#9bbabb;border:1px solid #2a4a44;
  padding:3px 7px;cursor:pointer;border-radius:3px;}
#tw-spans button.on{background:#0aa64d;border-color:#22ff22;color:#fff;}
#tw-spans .cust-inp{width:56px;font:bold 11px Arial;background:#1b2a30;color:#9bbabb;
  border:1px solid #2a4a44;padding:3px 5px;border-radius:3px;text-align:center;}
#tw-spans .cust-inp:focus{outline:none;border-color:#7fd0d8;color:#d6f3e4;}
#tw-spans .cust-inp.on{background:#0aa64d;border-color:#22ff22;color:#fff;}
#tw-spans .cust-inp::placeholder{color:#3d5a56;font-weight:normal;font-style:italic;}
#tw-save{font:bold 11px Arial;background:#1b2a30;color:#7fd0d8;border:1px solid #4aa587;
  padding:3px 9px;cursor:pointer;border-radius:3px;}
#tw-save:hover{background:#22424a;}
#tw-plot{position:relative;height:calc(100% - 34px - 34px - 250px);min-height:140px;padding:4px 6px 0;}
#tw-flash{position:absolute;top:8px;left:50%;transform:translateX(-50%);opacity:0;
  transition:opacity .25s;background:#3a0d0d;border:1px solid #ff3030;color:#ff8a8a;
  font:bold 11px Consolas,monospace;padding:3px 10px;border-radius:3px;pointer-events:none;z-index:2;}
#tw-table{height:290px;overflow:auto;}
#tw-table table{width:100%;border-collapse:collapse;font:13px Consolas,monospace;font-variant-numeric:tabular-nums;}
#tw-table td{padding:3px 7px;border-bottom:1px solid #16292c;white-space:nowrap;}
#tw-table tr{cursor:pointer;}
#tw-table tr.empty td{color:#54706c;font-style:italic;}
#tw-table tr.sel{background:#16323a;outline:1px solid #7fd0d8;}
#tw-table tr.drop{background:#1d4d52;}
#tw-table th{position:sticky;top:0;background:#0f1a24;color:#82b3a3;text-align:left;
  font:bold 11px "Segoe UI",system-ui;letter-spacing:.5px;padding:4px 7px;border-bottom:1px solid #2a4a44;}
#tw-table td.c-n{width:26px;color:#82b3a3;}
#tw-table td.c-hl{width:24px;text-align:center;}
#tw-table td.c-hl input{cursor:pointer;margin:0;vertical-align:middle;accent-color:#4aa587;}
#tw-table th.h-hl{width:24px;text-align:center;color:#4aa587;}
#tw-table td.c-k{width:19px;}
#tw-table td.c-k i{display:block;width:13px;height:10px;}
#tw-table td.c-v{text-align:right;width:92px;color:#fff;font-weight:bold;}
#tw-table td.c-min{text-align:right;width:84px;color:#7fd0d8;}
#tw-table td.c-max{text-align:right;width:84px;color:#ff9a3c;}
#tw-table td.c-avg{text-align:right;width:84px;color:#cfe;}
#tw-table th.h-min{color:#7fd0d8;} #tw-table th.h-max{color:#ff9a3c;} #tw-table th.h-avg{color:#cfe;}
#tw-table td.c-r{text-align:right;width:88px;font-weight:bold;}
#tw-table td.c-u{width:72px;color:#82b3a3;}
#tw-table td.c-lo,#tw-table td.c-hi{width:92px;}
#tw-table td.c-lo input,#tw-table td.c-hi input{width:83px;background:#0b1a16;color:#d6f3e4;
  border:1px solid #2a4a44;font:13px Consolas,monospace;font-variant-numeric:tabular-nums;padding:1px 4px;text-align:right;}
#tw-table td.c-lo input:focus,#tw-table td.c-hi input:focus{outline:none;border-color:#7fd0d8;background:#0f2a24;}
#tw-table td.c-lo input.auto,#tw-table td.c-hi input.auto{color:#54706c;font-style:italic;}
#tw-table td.c-lo input:disabled,#tw-table td.c-hi input:disabled{background:transparent;border-color:#16292c;}
#tw-table td.c-x{width:22px;text-align:center;color:#e06f6f;font-weight:bold;}
#tw-table td.c-x:hover{color:#ff3030;}
.ov[draggable="true"]{cursor:grab;}
#tw-menu{position:absolute;z-index:420;background:#222;border:1px solid #ccc;color:#fff;font:12px Arial;min-width:150px;display:none;}
#tw-menu .hd{background:#0aa64d;padding:4px 10px;font-weight:bold;}
#tw-menu .it{padding:6px 10px;cursor:pointer;}
#tw-menu .it:hover{background:#444;}
#tw-menu .it.off{color:#777;cursor:default;}
#tw-menu .it.off:hover{background:transparent;}`;
    document.head.appendChild(st);
  }

  function buildWindow() {
    injectCSS();
    win = document.createElement('div');
    win.id = 'trendwin';
    let rth = '';                                   // ruler column headers (hidden until placed)
    for (let r = 0; r < RULERS_MAX; r++) rth += '<th class="h-r" style="display:none"></th>';
    let rtd = '';
    for (let r = 0; r < RULERS_MAX; r++) rtd += '<td class="c-r" style="display:none"></td>';
    win.innerHTML =
      '<div id="tw-head">' +
        '<div id="tw-close" title="Close trend window">X</div>' +
        '<div id="tw-title">TREND</div>' +
        '<span id="tw-hist">HISTORY UNAVAILABLE — LIVE ONLY</span>' +
        '<div id="tw-spans"></div>' +
        '<button id="tw-save" title="Save trend image">SAVE</button>' +
      '</div>' +
      '<div id="tw-plot"><div id="tw-flash"></div><canvas id="tw-canvas"></canvas></div>' +
      '<div id="tw-bar">' +
        '<button id="tw-back" title="Scroll back to older records">&#9664;</button>' +
        '<button id="tw-fwd" title="Scroll forward to newer records">&#9654;</button>' +
        '<span id="tw-live" title="Return to live">LIVE</span>' +
        '<div class="twb"><label>CURRENT</label>' +
          '<span id="tw-plant">00:00:00</span><span id="tw-desk">--:--:--</span></div>' +
        '<div class="twb" id="tw-rulers"><label>RULERS</label><span id="tw-rulers-list"></span></div>' +
      '</div>' +
      '<div id="tw-table"><table>' +
        '<thead><tr id="tw-head-row"><th></th><th class="h-hl" title="Tick to highlight this trend">&#10003;</th><th></th><th>TAG</th><th>VALUE</th>' +
        '<th class="h-min">MIN</th><th class="h-max">MAX</th><th class="h-avg">AVG</th>' +
        rth + '<th>UNIT</th><th>LOW</th><th>HIGH</th><th></th></tr></thead>' +
        '<tbody id="tw-rows"></tbody></table></div>';
    document.body.appendChild(win);

    const sp = win.querySelector('#tw-spans');
    SPANS.forEach(x => {
      const b = document.createElement('button');
      b.textContent = x.lbl; b.dataset.span = x.s;
      b.onclick = () => setSpan(x.s);
      sp.appendChild(b);
    });
    const custInp = document.createElement('input');
    custInp.type = 'text';
    custInp.className = 'cust-inp';
    custInp.placeholder = 'e.g. 30s';
    custInp.title = 'Custom span — type a value like 30s, 10m, 3h, then press Enter';
    custInp.addEventListener('keydown', ev => {
      if (ev.key === 'Enter') { ev.preventDefault(); ev.stopPropagation(); applyCustomSpan(custInp); custInp.blur(); }
    });
    custInp.addEventListener('mousedown', ev => ev.stopPropagation());
    sp.appendChild(custInp);

    const tb = win.querySelector('#tw-rows');
    for (let i = 0; i < SLOTS; i++) {
      const tr = document.createElement('tr');
      tr.innerHTML = '<td class="c-n"></td><td class="c-hl"><input type="checkbox" title="Highlight this trend"></td>' +
        '<td class="c-k"><i></i></td><td class="c-t"></td>' +
        '<td class="c-v"></td><td class="c-min"></td><td class="c-max"></td><td class="c-avg"></td>' +
        rtd + '<td class="c-u"></td>' +
        '<td class="c-lo"><input type="number" step="any" disabled title="Display LOW — blank to auto-scale"></td>' +
        '<td class="c-hi"><input type="number" step="any" disabled title="Display HIGH — blank to auto-scale"></td>' +
        '<td class="c-x"></td>';
      tr.onclick = ev => {
        if (ev.target.tagName === 'INPUT') return;   // the tickbox + LOW/HIGH fields own their own clicks
        if (ev.target.classList.contains('c-x')) { if (slots[i]) removeSlot(i); return; }
        toggleHighlight(i);   // clicking anywhere on the row marks/unmarks its trend (same as the tickbox)
      };
      tr.querySelector('.c-hl input').addEventListener('change', ev => setHighlight(i, ev.target.checked));
      [['lo', '.c-lo input'], ['hi', '.c-hi input']].forEach(([which, sel]) => {
        const inp = tr.querySelector(sel);
        inp.addEventListener('change', () => commitRange(i, which, inp));
        inp.addEventListener('keydown', ev => { if (ev.key === 'Enter') { ev.preventDefault(); commitRange(i, which, inp); inp.blur(); } });
        inp.addEventListener('mousedown', ev => ev.stopPropagation());
      });
      tr.addEventListener('dragover', ev => { ev.preventDefault(); tr.classList.add('drop'); });
      tr.addEventListener('dragleave', () => tr.classList.remove('drop'));
      tr.addEventListener('drop', ev => {
        ev.preventDefault(); tr.classList.remove('drop');
        const tag = ev.dataTransfer.getData('text/ots-tag') || ev.dataTransfer.getData('text/plain');
        if (tag) coreAddTag(tag, i);
      });
      tb.appendChild(tr);
    }

    // Plot pointer: grab a ruler within RULER_HIT_PX and drag it along the time axis; a plain
    // click on empty plot still drops a new ruler at that instant.
    const cv = win.querySelector('#tw-canvas');
    cv.addEventListener('pointerdown', ev => {
      if (!chart) return;
      const rect = cv.getBoundingClientRect();
      const px = ev.clientX - rect.left, area = chart.chartArea;
      if (px < area.left || px > area.right) return;
      dragMoved = false;
      dragRuler = rulerNear(px);
      if (dragRuler >= 0) {
        try { cv.setPointerCapture(ev.pointerId); } catch (e) {}
        cv.style.cursor = 'ew-resize';
        ev.preventDefault();
      }
    });
    cv.addEventListener('pointermove', ev => {
      if (!chart) return;
      const rect = cv.getBoundingClientRect();
      const px = ev.clientX - rect.left, area = chart.chartArea;
      if (dragRuler >= 0) {
        moveRuler(dragRuler, pxToTime(clamp(px, area.left, area.right)));
        dragMoved = true;
      } else if (px >= area.left && px <= area.right) {
        cv.style.cursor = rulerNear(px) >= 0 ? 'ew-resize' : 'crosshair';
      }
    });
    function endDrag(ev) {
      if (dragRuler < 0) return false;
      try { cv.releasePointerCapture(ev.pointerId); } catch (e) {}
      dragRuler = -1; cv.style.cursor = 'crosshair';
      return true;
    }
    cv.addEventListener('pointerup', ev => {
      if (!chart) return;
      if (endDrag(ev)) return;
      const rect = cv.getBoundingClientRect();
      const px = ev.clientX - rect.left, area = chart.chartArea;
      if (!dragMoved && px >= area.left && px <= area.right) addRuler(pxToTime(px));
    });
    cv.addEventListener('pointercancel', endDrag);
    win.querySelector('#tw-rulers-list').addEventListener('click', ev => {
      const b = ev.target.closest('b[data-ri]');
      if (b) removeRuler(Number(b.dataset.ri));
    });
    win.querySelector('#tw-back').onclick = () => pan(-1);
    win.querySelector('#tw-fwd').onclick = () => pan(+1);
    win.querySelector('#tw-live').onclick = goLive;
    win.querySelector('#tw-save').onclick = exportPNG;
    win.querySelector('#tw-close').onclick = () => { if (POPUP) window.close(); else win.style.display = 'none'; };

    const plot = win.querySelector('#tw-plot');
    plot.addEventListener('dragover', ev => ev.preventDefault());
    plot.addEventListener('drop', ev => {
      ev.preventDefault();
      const tag = ev.dataTransfer.getData('text/ots-tag') || ev.dataTransfer.getData('text/plain');
      if (tag) coreAddTag(tag, null);
    });

    new ResizeObserver(() => { if (chart) chart.resize(); }).observe(win);
  }

  function coreOpen() {
    if (!win) buildWindow();
    win.style.display = 'block';
    if (!chart) buildChart();
    win.querySelectorAll('#tw-spans button').forEach(b => b.classList.toggle('on', Number(b.dataset.span) === span));
    const _ci = win.querySelector('#tw-spans .cust-inp');
    if (_ci) _ci.classList.toggle('on', !SPANS.some(x => x.s === span) && parseSpan(_ci.value) === span);
    markHist();
    dirty = true; redraw();
  }

  // ================= live feed (packet -> pens) =================
  function onPacket(s) {
    lastPacket = s;
    if (typeof s.t_sim === 'number') nowSim = s.t_sim;
    if (typeof s.t === 'number') nowWall = s.t;
    noteTime(nowSim, nowWall);
    for (const slot of slots) {
      if (!slot) continue;
      const v = Registry.value(s, slot.entry);
      if (v == null) continue;
      const last = slot.pts[slot.pts.length - 1];
      if (last && nowSim - last.t < LIVE_MIN_DT) { last.v = v; continue; }
      slot.pts.push({ t: nowSim, v: v });
      const cut = nowSim - 28800;
      if (slot.pts.length > 4 && slot.pts[0].t < cut) {
        let k = 0; while (k < slot.pts.length && slot.pts[k].t < cut) k++;
        slot.pts.splice(0, k);
      }
    }
    dirty = true; scheduleRedraw();
  }

  // ================= cross-window handoff =================
  // Browser-only: a BroadcastChannel open in headless Node keeps the event loop alive and
  // hangs `node --test`.
  let bc = null;
  try { if (HAS_DOM && typeof BroadcastChannel !== 'undefined') bc = new BroadcastChannel(CH_NAME); } catch (e) {}
  function readPending() { try { return JSON.parse(localStorage.getItem(PENDING_KEY) || '[]') || []; } catch (e) { return []; } }
  function enqueueAdd(tag) {
    const q = readPending(); q.push(tag);
    try { localStorage.setItem(PENDING_KEY, JSON.stringify(q)); } catch (e) {}
    if (bc) bc.postMessage({ cmd: 'add' });
  }
  function drainPending() {
    _bindsCache = null;                       // refresh the bind mirror before resolving new tags
    const q = readPending();
    try { localStorage.setItem(PENDING_KEY, '[]'); } catch (e) {}
    q.forEach(tag => coreAddTag(tag, null));
    if (q.length) { coreOpen(); }
  }

  // ================= role wiring =================
  if (POPUP) {
    // --- popup window: own the UI + a private WebSocket feed ---
    function connectWS() {
      const url = (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws';
      (function c() {
        let ws;
        try { ws = new WebSocket(url); } catch (e) { setTimeout(c, 1000); return; }
        ws.onmessage = e => { try { onPacket(JSON.parse(e.data)); } catch (_) {} };
        ws.onclose = () => setTimeout(c, 1000);
        ws.onerror = () => { try { ws.close(); } catch (_) {} };
      })();
    }
    function popupInit() {
      document.body.classList.add('tw-popup');
      buildWindow(); buildChart();
      const st = saved();
      if (typeof st.span === 'number' && st.span > 0) span = st.span;
      if (Array.isArray(st.hl)) highlights = new Set(st.hl.filter(n => Number.isInteger(n) && n >= 0 && n < SLOTS));
      else if (typeof st.sel === 'number' && st.sel >= 0) highlights.add(clamp(st.sel, 0, SLOTS - 1)); // migrate old single-select
      if (typeof st.axis === 'number') axisPen = st.axis < 0 ? -1 : clamp(st.axis, 0, SLOTS - 1);
      if (Array.isArray(st.tags)) st.tags.forEach((tag, i) => {
        if (!tag) return;
        coreAddTag(tag, i);
        const r = st.ranges && st.ranges[i];
        if (slots[i] && Array.isArray(r) && r.length === 2 && r[1] > r[0]) { slots[i].lo = r[0]; slots[i].hi = r[1]; slots[i].auto = false; }
      });
      highlights.forEach(n => { if (!slots[n]) highlights.delete(n); });   // drop marks for slots that did not restore
      if (axisPen >= 0 && !slots[axisPen]) axisPen = highlights.size ? [...highlights][highlights.size - 1] : -1;
      win.style.display = 'block';
      win.querySelectorAll('#tw-spans button').forEach(b => b.classList.toggle('on', Number(b.dataset.span) === span));
      if (!SPANS.some(x => x.s === span)) {
        const ci2 = win.querySelector('#tw-spans .cust-inp');
        if (ci2) {
          ci2.value = span % 3600 === 0 ? (span / 3600) + 'h' : span % 60 === 0 ? (span / 60) + 'm' : span + 's';
          ci2.classList.add('on');
        }
      }
      drainPending();
      connectWS();
      markHist(); redraw();
      document.title = 'Trend — Urea OTS';
    }
    if (bc) bc.onmessage = e => { if (e.data && e.data.cmd === 'add') drainPending(); };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', popupInit);
    else popupInit();

    window.TrendWindow = {
      open: coreOpen, onPacket: onPacket, addTag: coreAddTag, removeSlot: removeSlot,
      setCursor: setCursor, cursor: () => (rulers.length ? rulers[0] : null),
      addRuler: addRuler, removeRuler: removeRuler, moveRuler: moveRuler, clearRulers: clearRulers, rulers: () => rulers.slice(),
      valueAt: valueAt, windowStats: windowStats, pan: pan, goLive: goLive, viewEnd: viewEnd, isLive: isLive,
      isBound: t => Registry.bound(t), isOpen: () => true,
    };
    window.openTrend = tag => { coreOpen(); coreAddTag(tag, null); };

  } else if (HAS_DOM) {
    // --- main DCS app: launcher only, no inline trend ---
    let popup = null;
    function openPopup() {
      if (popup && !popup.closed) { try { popup.focus(); } catch (e) {} return popup; }
      popup = window.open('trend.html', POPUP_NAME, 'width=1040,height=720');
      if (!popup) { flashMain('Allow pop-ups to open the trend window'); }
      return popup;
    }
    function launcherAdd(tag) {
      if (!Registry.bound(tag)) return false;
      enqueueAdd(tag);
      openPopup();
      return true;
    }
    function flashMain(msg) {
      let el = document.getElementById('tw-launch-msg');
      if (!el) {
        el = document.createElement('div'); el.id = 'tw-launch-msg';
        el.style.cssText = 'position:fixed;top:8px;left:50%;transform:translateX(-50%);z-index:700;' +
          'background:#3a2f08;border:1px solid #ffd000;color:#ffd000;font:bold 12px Consolas,monospace;' +
          'padding:5px 12px;border-radius:4px;';
        document.body.appendChild(el);
      }
      el.textContent = msg; el.style.display = 'block';
      setTimeout(() => { el.style.display = 'none'; }, 3000);
    }

    // Context menu (right-click an indicator/controller/valve).
    injectCSS();
    let menu = null;
    function closeMenu() { if (menu) menu.style.display = 'none'; }
    document.addEventListener('click', closeMenu);
    document.addEventListener('contextmenu', e => { if (!e.target.closest('#tw-menu')) closeMenu(); }, true);
    function openMenu(ev, tag) {
      injectCSS();
      if (!menu) { menu = document.createElement('div'); menu.id = 'tw-menu'; document.body.appendChild(menu); }
      const bound = Registry.bound(tag);
      menu.innerHTML = '<div class="hd">' + tag + '</div>' +
        (bound ? '<div class="it" data-act="trend">Trend &#8599;</div>' : '<div class="it off">Trend — not bound</div>');
      const it = menu.querySelector('.it[data-act]');
      if (it) it.onclick = () => { launcherAdd(tag); closeMenu(); };
      menu.style.display = 'block';
      menu.style.left = Math.min(ev.pageX, window.innerWidth - 170) + 'px';
      menu.style.top = Math.min(ev.pageY, window.innerHeight - 90) + 'px';
    }

    // Preserve native drag from a main-screen indicator onto the popup: the payload cannot cross
    // windows, so on dragend we test whether the pointer landed inside the popup's screen rect.
    document.addEventListener('dragend', e => {
      const tag = window.__ots_drag_tag; window.__ots_drag_tag = null;
      if (!tag || !popup || popup.closed) return;
      const sx = e.screenX, sy = e.screenY;
      try {
        if (sx >= popup.screenX && sx <= popup.screenX + popup.outerWidth &&
            sy >= popup.screenY && sy <= popup.screenY + popup.outerHeight) launcherAdd(tag);
      } catch (err) {}
    });

    window.TrendWindow = {
      open: openPopup, addTag: launcherAdd, openMenu: openMenu, onPacket: function () {},
      isBound: t => Registry.bound(t), isOpen: () => !!(popup && !popup.closed),
      setCursor: function () {}, removeSlot: function () {},
    };
    window.openTrend = tag => launcherAdd(tag);
  }

  // Headless export for the test suite (no DOM); exposes the core logic.
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
      open: coreOpen, onPacket: onPacket, addTag: coreAddTag, removeSlot: removeSlot,
      setCursor: setCursor, cursor: () => (rulers.length ? rulers[0] : null),
      addRuler: addRuler, removeRuler: removeRuler, moveRuler: moveRuler, clearRulers: clearRulers, rulers: () => rulers.slice(),
      valueAt: valueAt, windowStats: windowStats, pan: pan, goLive: goLive, viewEnd: viewEnd, isLive: isLive,
      isBound: t => Registry.bound(t),
      _internals: { hms, deskClock, stamp, norm, rescale, wallAt, noteTime, Registry, commitRange, windowStats,
                    UNIT_RANGE, SPANS, SLOTS, PENS, RULER_COLORS, RULERS_MAX, slots,
                    setSpanValue: v => { span = v; }, getSpan: () => span, maxPanBack: maxPanBack,
                    setNow: t => { nowSim = t; }, getHighlights: () => [...highlights], getAxisPen: () => axisPen,
                    setHighlight: setHighlight, toggleHighlight: toggleHighlight, save: save, saved: saved,
                    getRulers: () => rulers, parseSpan: parseSpan },
    };
  }
})();
