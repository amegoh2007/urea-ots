'use strict';
// Globally persistent multi-pen trend window.
//
// The window is appended to <body>, OUTSIDE #stage, so screen navigation cannot affect it:
// the screens are sibling divs that toggle .active, and nothing here lives inside them.
// It closes only via the X button, per requirement.
//
// Data path: backend historian (/api/hist) supplies history from process start; the live
// WebSocket packet extends each pen forward. Both are keyed to the PLANT clock (t_sim), so
// a "1 hour" span is one hour of plant behaviour whether the sim runs at 1x or 60x.
//
// Tag -> packet path resolution goes through window.OV_BINDS (overlays.js BIND_MAP). The
// legacy .pi screen is not consulted: those elements live inside .screen.shot and are
// hidden by `.screen.shot > *:not(.ov-layer){display:none;}`.
(function () {
  const LSK = 'ots_trend_v1';
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

  // Pen palette: ui_guidelines §10 tokens first, then distinct additions. No pair relies on
  // red/green discrimination alone.
  const PENS = ['#22ff22', '#7fd0d8', '#ffd000', '#ff9a3c', '#ff00ff',
                '#5fe08f', '#e06f6f', '#9bbabb', '#c78fff', '#ffffff'];

  // Engineering ranges by unit, used to normalise every pen onto a shared 0-100 grid.
  // An explicit rng:[lo,hi] on the OV entry wins; anything unmatched auto-scales.
  const UNIT_RANGE = {
    '%': [0, 100], 'C': [0, 250], 'BAR G': [0, 200], 'BARG': [0, 200], 'BAR A': [0, 200],
    'T/H': [0, 100], 'RPM': [0, 3000], 'A': [0, 200], 'NM3/H': [0, 40000],
    'KG/H': [0, 50000], 'M3/H': [0, 500], 'KW': [0, 5000], '': [0, 1],
  };

  const gp = (o, path) => path ? path.split('.').reduce((a, k) => (a == null ? undefined : a[k]), o) : undefined;
  const clamp = (v, lo, hi) => v < lo ? lo : v > hi ? hi : v;
  const pad2 = n => (n < 10 ? '0' : '') + n;

  function hms(sec) {                                  // plant clock: elapsed since program init
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
  const Registry = {
    entry(tag) {
      const b = (window.OV_BINDS || {})[tag];
      if (!b || !b.bind) return null;
      let u = (b.u || '').toUpperCase();
      let rng = b.rng || UNIT_RANGE[u] || null;
      // Domain 1a: BAR A tags are displayed as gauge pressure, so trend the same quantity.
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
  let selected = 0;
  let chart = null, win = null, lastPacket = null;
  let cursorT = null;                  // ruler position, absolute plant seconds (null = no ruler)
  // Right edge of the plot, absolute plant seconds. null = live (tracks now). Absolute rather
  // than an offset from now, so a scrolled-back view stays on the instant it was parked at
  // instead of drifting forward with every packet.
  let viewEndT = null;
  const PAN_FRACTION = 0.25;           // arrows step a quarter window, as DCS trends do
  let nowSim = 0, nowWall = 0;
  let timeMap = [];                    // [t_sim, t_wall] pairs for the desktop tick row
  let dirty = false, redrawTimer = null;
  let histOK = true;

  function saved() {
    try { return JSON.parse(localStorage.getItem(LSK)) || {}; } catch (e) { return {}; }
  }
  function save() {
    const st = saved();
    st.span = span; st.sel = selected;
    st.tags = slots.map(s => s && s.tag);
    // Only operator-set ranges are persisted; auto-scaled pens re-derive theirs from data.
    st.ranges = slots.map(s => (s && !s.auto) ? [s.lo, s.hi] : null);
    if (win) {
      st.open = win.style.display !== 'none';
      st.x = win.style.left; st.y = win.style.top;
      st.w = win.style.width; st.h = win.style.height;
    }
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
  function wallAt(tSim) {               // interpolate desktop time for a plant time
    if (!timeMap.length) return nowWall;
    // Before the first observed pair there is no honest desktop time to report; clamping
    // would print the page-load clock against instants that preceded it.
    if (tSim < timeMap[0][0]) return null;
    if (tSim === timeMap[0][0]) return timeMap[0][1];
    for (let i = timeMap.length - 1; i >= 0; i--) {
      if (timeMap[i][0] <= tSim) {
        const a = timeMap[i], b = timeMap[i + 1];
        if (!b) return a[1] + (tSim - a[0]);         // extrapolate at 1x past the newest pair
        const f = (tSim - a[0]) / Math.max(1e-9, b[0] - a[0]);
        return a[1] + f * (b[1] - a[1]);
      }
    }
    return nowWall;
  }

  // Right edge of the visible window in absolute plant seconds.
  function viewEnd() { return viewEndT == null ? nowSim : viewEndT; }
  function isLive() { return viewEndT == null; }
  // How far back history can be scrolled: never before program start, never past retention.
  function maxPanBack() { return Math.max(0, Math.min(nowSim, 28800) - span); }

  function backfill(slot) {
    if (!slot) return Promise.resolve();
    if (typeof fetch !== 'function') return Promise.resolve();   // headless test context
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
      // History first, then whatever the live feed already collected past its end.
      const edge = pts.length ? pts[pts.length - 1].t : -Infinity;
      slot.pts = pts.concat(slot.pts.filter(p => p.t > edge));
      dirty = true;
    }).catch(() => { histOK = false; markHist(); });
  }

  // ================= chart =================
  function norm(slot, v) {
    const lo = slot.lo, hi = slot.hi;
    if (hi - lo < 1e-12) return 50;
    return (v - lo) / (hi - lo) * 100;
  }
  function rescale(slot) {              // auto-range pens with no declared engineering range
    if (!slot.auto) return;
    let lo = Infinity, hi = -Infinity;
    const ve = viewEnd(), cut = ve - span;
    for (const p of slot.pts) {
      if (p.t < cut || p.t > ve) continue;
      if (p.v < lo) lo = p.v;
      if (p.v > hi) hi = p.v;
    }
    if (!isFinite(lo) || !isFinite(hi)) { slot.lo = 0; slot.hi = 1; return; }
    if (hi - lo < 1e-9) { lo -= 0.5; hi += 0.5; }
    const pad = (hi - lo) * 0.05;
    slot.lo = lo - pad; slot.hi = hi + pad;
  }

  // Value a pen held at the ruler instant. Hold semantics (last sample at or before), which
  // is what a DCS cursor reports and the only correct reading for a stepped digital pen.
  function valueAt(slot, t) {
    if (t == null || !slot || !slot.pts.length) return null;
    let best = null;
    for (const p of slot.pts) {
      if (p.t > t) break;
      best = p;
    }
    return best ? best.v : null;
  }

  // Vertical ruler. A plugin rather than a DOM overlay so it draws inside the chart bitmap and
  // is therefore captured by the PNG export without any extra work.
  const rulerPlugin = {
    id: 'otsRuler',
    afterDatasetsDraw(ch) {
      if (cursorT == null) return;
      const area = ch.chartArea;
      const x = ch.scales.x.getPixelForValue(cursorT - viewEnd());
      if (!(x >= area.left && x <= area.right)) return;
      const g = ch.ctx;
      g.save();
      g.strokeStyle = '#ffd000';
      g.lineWidth = 1;
      g.setLineDash([4, 3]);
      g.beginPath();
      g.moveTo(x, area.top);
      g.lineTo(x, area.bottom);
      g.stroke();
      g.setLineDash([]);
      const w = wallAt(cursorT);
      const label = hms(cursorT) + (w == null ? '' : '  ' + deskClock(w));
      g.font = 'bold 10px Consolas, monospace';
      const bw = g.measureText(label).width + 10;
      const bx = clamp(x - bw / 2, area.left, Math.max(area.left, area.right - bw));
      g.fillStyle = '#ffd000';
      g.fillRect(bx, area.top, bw, 14);
      g.fillStyle = '#241f00';
      g.fillText(label, bx + 5, area.top + 10);
      g.restore();
    },
  };

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
                     // blank the region that precedes program start rather than stacking 00:00:00
                     callback: v => (viewEnd() + v) < 0 ? '' : hms(viewEnd() + v) },
            title: { display: true, text: 'PLANT CLOCK', color: '#5fe08f',
                     font: { size: 10, weight: 'bold' } },
          },
          x2: {
            type: 'linear', position: 'bottom', min: -span, max: 0, display: true,
            grid: { drawOnChartArea: false, color: '#16292c' },
            ticks: { color: '#7f9ba8', maxTicksLimit: 8, font: { size: 10 },
                     callback: v => { const w = wallAt(viewEnd() + v); return w == null ? '' : deskClock(w); } },
            title: { display: true, text: 'DESKTOP CLOCK', color: '#7f9ba8',
                     font: { size: 10 } },
          },
          y: {
            min: -2, max: 102,
            grid: { color: '#1e3a34' },
            ticks: { color: '#d6f3e4', font: { size: 10 }, stepSize: 20,
                     callback: pct => {
                       // -2..102 gives the pens headroom; label only the real 0-100 % band so
                       // the axis never prints a value outside the pen's engineering range.
                       if (pct < -0.001 || pct > 100.001) return '';
                       const s = slots[selected];
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
    if (!chart || !win || win.style.display === 'none') return;
    const ve = viewEnd(), cut = ve - span;
    // Once the ruler leaves the visible window its readings sit against an invisible line;
    // drop it rather than leave a column of numbers with nothing to point at.
    if (cursorT != null && (cursorT < cut || cursorT > ve)) setCursor(null);
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
      ds.borderWidth = (i === selected) ? 2.4 : 1.4;
    }
    chart.update('none');
    renderRows();
    win.querySelector('#tw-plant').textContent = hms(nowSim);
    win.querySelector('#tw-desk').textContent = deskClock(nowWall);
    win.querySelector('#tw-rul-plant').textContent = cursorT == null ? '--:--:--' : hms(cursorT);
    const rw = cursorT == null ? null : wallAt(cursorT);
    win.querySelector('#tw-rul-desk').textContent = rw == null ? '--:--:--' : deskClock(rw);
    win.querySelector('#tw-ruler-box').classList.toggle('set', cursorT != null);
    win.querySelector('#tw-live').classList.toggle('hist', !isLive());
    win.querySelector('#tw-live').textContent = isLive() ? 'LIVE' : 'HISTORY';
    win.querySelector('#tw-fwd').disabled = isLive();
    win.querySelector('#tw-back').disabled = (nowSim - viewEnd()) >= maxPanBack() - 1e-6;
  }

  // Scroll the window through history. Steps a quarter span per press and re-backfills, so
  // scrolling past what the browser has buffered still shows real recorded data.
  function pan(dir) {
    const step = span * PAN_FRACTION * dir;
    let target = viewEnd() + step;
    const oldest = nowSim - maxPanBack();
    if (target >= nowSim) viewEndT = null;                 // caught up: resume live
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

  function setCursor(t) {
    cursorT = t;
    dirty = true;
    if (win && chart) redraw();
  }
  function scheduleRedraw() {
    if (redrawTimer) return;
    redrawTimer = setTimeout(() => { redrawTimer = null; if (dirty) { dirty = false; redraw(); } }, REDRAW_MS);
  }

  // ================= pen table =================
  function renderRows() {
    if (!win) return;
    const tb = win.querySelector('#tw-rows');
    for (let i = 0; i < SLOTS; i++) {
      const tr = tb.children[i], slot = slots[i];
      tr.className = (i === selected ? 'sel ' : '') + (slot ? 'full' : 'empty');
      const cells = tr.children;
      const loI = cells[6].firstChild, hiI = cells[7].firstChild;
      cells[0].textContent = i + 1;
      cells[1].firstChild.style.background = PENS[i];
      if (!slot) {
        cells[2].textContent = '-- drop indicator here --';
        cells[3].textContent = ''; cells[4].textContent = ''; cells[5].textContent = '';
        loI.value = ''; hiI.value = '';
        loI.disabled = hiI.disabled = true;
        cells[8].textContent = '';
        continue;
      }
      const last = slot.pts.length ? slot.pts[slot.pts.length - 1] : null;
      const stale = last && (nowSim - last.t) > 30;
      cells[2].textContent = slot.tag;
      cells[3].textContent = last ? last.v.toFixed(slot.entry.dec) : '--';
      const at = valueAt(slot, cursorT);
      cells[4].textContent = cursorT == null ? '' : (at == null ? '--' : at.toFixed(slot.entry.dec));
      cells[5].textContent = stale ? 'STALE' : slot.entry.unit;
      loI.disabled = hiI.disabled = false;
      // Never overwrite the field the operator is typing into — the 4 Hz redraw would
      // otherwise wipe a half-entered number, the same failure the faceplates guard against.
      if (document.activeElement !== loI) loI.value = slot.lo.toFixed(slot.entry.dec);
      if (document.activeElement !== hiI) hiI.value = slot.hi.toFixed(slot.entry.dec);
      loI.classList.toggle('auto', slot.auto);
      hiI.classList.toggle('auto', slot.auto);
      cells[8].textContent = 'x';
    }
  }

  // Operator-set display range. Blanking a field hands the pen back to auto-scaling.
  function commitRange(i, which, inp) {
    const slot = slots[i];
    if (!slot) { inp.value = ''; return; }
    if (inp.value.trim() === '') {
      slot.auto = true;
      dirty = true; redraw(); save();
      return;
    }
    const v = Number(inp.value);
    const lo = which === 'lo' ? v : slot.lo;
    const hi = which === 'hi' ? v : slot.hi;
    if (!isFinite(v) || hi - lo <= 0) {     // an inverted or zero span cannot be plotted
      renderRows();
      flash(i, 'BAD RANGE');
      return;
    }
    slot.lo = lo; slot.hi = hi; slot.auto = false;
    dirty = true; redraw(); save();
  }
  function markHist() {
    if (!win) return;
    const chip = win.querySelector('#tw-hist');
    chip.style.display = histOK ? 'none' : 'inline-block';
  }

  // ================= slot operations =================
  function addTag(tag, index) {
    const e = Registry.entry(tag);
    if (!e) { flash(index, 'NOT BOUND'); return false; }
    const existing = slots.findIndex(s => s && s.tag === tag);
    if (existing >= 0 && (index == null || index === existing)) { selected = existing; dirty = true; scheduleRedraw(); return true; }
    let i = index;
    if (i == null) i = slots.findIndex(s => !s);
    if (i == null || i < 0) { flash(null, 'SLOTS FULL'); return false; }
    const rng = e.range;
    slots[i] = { tag: tag, entry: e, pts: [], colour: PENS[i],
                 lo: rng ? rng[0] : 0, hi: rng ? rng[1] : 1, auto: !rng };
    selected = i;
    backfill(slots[i]).then(() => { dirty = true; scheduleRedraw(); });
    dirty = true; scheduleRedraw(); save();
    return true;
  }
  function removeSlot(i) { slots[i] = null; dirty = true; scheduleRedraw(); save(); }
  function flash(index, msg) {
    if (!win) return;
    const el = win.querySelector('#tw-flash');
    el.textContent = msg;
    el.style.opacity = '1';
    setTimeout(() => { el.style.opacity = '0'; }, 1400);
  }

  function setSpan(s) {
    span = s;
    win.querySelectorAll('#tw-spans button').forEach(b =>
      b.classList.toggle('on', Number(b.dataset.span) === s));
    Promise.all(slots.filter(Boolean).map(backfill)).then(() => { dirty = true; redraw(); });
    save();
  }

  // ================= export =================
  function exportPNG() {
    const cv = win.querySelector('#tw-canvas');
    const W = cv.width, headH = 58, rowH = 18;
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
               (cursorT == null ? '' : '    RULER ' + hms(cursorT)), 12, 44);

    c.drawImage(cv, 0, headH);

    let y = headH + cv.height + 24;
    c.font = 'bold 11px Consolas, monospace'; c.fillStyle = '#82b3a3';
    const ruler = cursorT != null;
    c.fillText('#   TAG                     VALUE' + (ruler ? '   @ RULER' : '') +
               '      UNIT          LOW         HIGH', 12, y);
    c.font = '11px Consolas, monospace';
    live.forEach((s) => {
      y += rowH;
      const i = slots.indexOf(s);
      const last = s.pts.length ? s.pts[s.pts.length - 1] : null;
      const at = valueAt(s, cursorT);
      c.fillStyle = PENS[i]; c.fillRect(12, y - 8, 10, 8);
      c.fillStyle = '#d6f3e4';
      c.fillText(String(i + 1).padEnd(4) + s.tag.padEnd(24) +
                 (last ? last.v.toFixed(s.entry.dec) : '--').padStart(9) + '  ' +
                 (ruler ? (at == null ? '--' : at.toFixed(s.entry.dec)).padStart(9) + '  ' : '') +
                 s.entry.unit.padEnd(8) +
                 s.lo.toFixed(s.entry.dec).padStart(11) + '  ' +
                 s.hi.toFixed(s.entry.dec).padStart(11) +
                 (s.auto ? '  (auto)' : ''), 28, y);
    });

    const name = 'Trend_Report_' + stamp(d) + '.png';
    out.toBlob(blob => {
      if (window.showSaveFilePicker) {
        window.showSaveFilePicker({
          suggestedName: name,
          types: [{ description: 'PNG image', accept: { 'image/png': ['.png'] } }],
        }).then(h => h.createWritable())
          .then(w => w.write(blob).then(() => w.close()))
          .catch(() => { /* operator cancelled the dialog */ });
      } else {
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = name;
        a.click();
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
#trendwin{position:fixed;z-index:400;display:none;background:#13202c;border:1px solid #4aa587;
  box-shadow:0 8px 28px rgba(0,0,0,.6);color:#cfe;font:13px "Segoe UI",system-ui;
  min-width:520px;min-height:360px;resize:both;overflow:hidden;}
#tw-head{display:flex;align-items:center;gap:8px;padding:6px 8px;background:#0f1a24;
  border-bottom:1px solid #2a4a44;cursor:move;user-select:none;}
#tw-close{width:20px;height:20px;line-height:18px;text-align:center;cursor:pointer;
  background:#3a0d0d;border:1px solid #ff3030;color:#ff8a8a;font-weight:bold;border-radius:3px;}
#tw-close:hover{background:#5a1414;}
#tw-title{font-weight:bold;letter-spacing:1px;}
#tw-hist{display:none;font:10px Consolas,monospace;background:#3a2a08;border:1px solid #b3892f;
  color:#ffd27f;padding:1px 5px;border-radius:3px;}
#tw-plot canvas{cursor:crosshair;}
#tw-bar{display:flex;align-items:center;gap:8px;padding:4px 8px;background:#0f1a24;
  border-top:1px solid #2a4a44;border-bottom:1px solid #2a4a44;}
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
#tw-bar .twb span{font:bold 12px Consolas,monospace;font-variant-numeric:tabular-nums;
  color:#5fe08f;}
#tw-bar .twb span+span{color:#7f9ba8;font-weight:normal;}
#tw-ruler-box span{color:#54706c;}
#tw-ruler-box.set{border-color:#ffd000;}
#tw-ruler-box.set span{color:#ffd000;}
#tw-ruler-box.set span+span{color:#c9a83c;font-weight:normal;}
#tw-ruler{cursor:pointer;color:#e06f6f !important;font-weight:bold;}
#tw-ruler:hover{color:#ff3030 !important;}
#tw-spans{margin-left:auto;display:flex;gap:2px;}
#tw-spans button{font:bold 11px Arial;background:#1b2a30;color:#9bbabb;border:1px solid #2a4a44;
  padding:3px 7px;cursor:pointer;border-radius:3px;}
#tw-spans button.on{background:#0aa64d;border-color:#22ff22;color:#fff;}
#tw-save{font:bold 11px Arial;background:#1b2a30;color:#7fd0d8;border:1px solid #4aa587;
  padding:3px 9px;cursor:pointer;border-radius:3px;}
#tw-save:hover{background:#22424a;}
#tw-plot{position:relative;height:calc(100% - 34px - 30px - 250px);min-height:140px;padding:4px 6px 0;}
#tw-flash{position:absolute;top:8px;left:50%;transform:translateX(-50%);opacity:0;
  transition:opacity .25s;background:#3a0d0d;border:1px solid #ff3030;color:#ff8a8a;
  font:bold 11px Consolas,monospace;padding:3px 10px;border-radius:3px;pointer-events:none;z-index:2;}
#tw-table{height:250px;overflow:auto;}
#tw-table table{width:100%;border-collapse:collapse;font:11px Consolas,monospace;
  font-variant-numeric:tabular-nums;}
#tw-table td{padding:2px 6px;border-bottom:1px solid #16292c;white-space:nowrap;}
#tw-table tr{cursor:pointer;}
#tw-table tr.empty td{color:#54706c;font-style:italic;}
#tw-table tr.sel{background:#16323a;outline:1px solid #7fd0d8;}
#tw-table tr.drop{background:#1d4d52;}
#tw-table td.c-n{width:22px;color:#82b3a3;}
#tw-table td.c-k{width:16px;}
#tw-table td.c-k i{display:block;width:11px;height:9px;}
#tw-table td.c-v{text-align:right;width:88px;color:#fff;font-weight:bold;}
#tw-table td.c-cur{text-align:right;width:88px;color:#ffd000;font-weight:bold;}
#tw-table th.h-cur{color:#ffd000;}
#tw-table td.c-u{width:64px;color:#82b3a3;}
#tw-table th{position:sticky;top:0;background:#0f1a24;color:#82b3a3;text-align:left;
  font:bold 10px "Segoe UI",system-ui;letter-spacing:.5px;padding:3px 6px;
  border-bottom:1px solid #2a4a44;}
#tw-table td.c-lo,#tw-table td.c-hi{width:78px;}
#tw-table td.c-lo input,#tw-table td.c-hi input{width:70px;background:#0b1a16;color:#d6f3e4;
  border:1px solid #2a4a44;font:11px Consolas,monospace;font-variant-numeric:tabular-nums;
  padding:1px 3px;text-align:right;}
#tw-table td.c-lo input:focus,#tw-table td.c-hi input:focus{outline:none;border-color:#7fd0d8;
  background:#0f2a24;}
#tw-table td.c-lo input.auto,#tw-table td.c-hi input.auto{color:#54706c;font-style:italic;}
#tw-table td.c-lo input:disabled,#tw-table td.c-hi input:disabled{background:transparent;
  border-color:#16292c;}
#tw-table td.c-x{width:18px;text-align:center;color:#e06f6f;font-weight:bold;}
#tw-table td.c-x:hover{color:#ff3030;}
.ov[draggable="true"]{cursor:grab;}
#tw-menu{position:absolute;z-index:420;background:#222;border:1px solid #ccc;color:#fff;
  font:12px Arial;min-width:150px;display:none;}
#tw-menu .hd{background:#0aa64d;padding:4px 10px;font-weight:bold;}
#tw-menu .it{padding:6px 10px;cursor:pointer;}
#tw-menu .it:hover{background:#444;}
#tw-menu .it.off{color:#777;cursor:default;}
#tw-menu .it.off:hover{background:transparent;}
#tw-menu .sub{max-height:210px;overflow:auto;border-top:1px solid #444;}`;
    document.head.appendChild(st);
  }

  function buildWindow() {
    injectCSS();
    win = document.createElement('div');
    win.id = 'trendwin';
    win.innerHTML =
      '<div id="tw-head">' +
        '<div id="tw-close" title="Close trend">X</div>' +
        '<div id="tw-title">TREND</div>' +
        '<span id="tw-hist">HISTORY UNAVAILABLE — LIVE ONLY</span>' +
        '<div id="tw-spans"></div>' +
        '<button id="tw-save" title="Save trend image">SAVE</button>' +
      '</div>' +
      '<div id="tw-plot"><div id="tw-flash"></div><canvas id="tw-canvas"></canvas></div>' +
      // Control strip between plot and pen table: scroll arrows, current time, ruler time.
      '<div id="tw-bar">' +
        '<button id="tw-back" title="Scroll back to older records">&#9664;</button>' +
        '<button id="tw-fwd" title="Scroll forward to newer records">&#9654;</button>' +
        '<span id="tw-live" title="Return to live">LIVE</span>' +
        '<div class="twb"><label>CURRENT</label>' +
          '<span id="tw-plant">00:00:00</span><span id="tw-desk">--:--:--</span></div>' +
        '<div class="twb" id="tw-ruler-box"><label>RULER</label>' +
          '<span id="tw-rul-plant">--:--:--</span><span id="tw-rul-desk">--:--:--</span>' +
          '<span id="tw-ruler" title="Clear the ruler">&#10005;</span></div>' +
      '</div>' +
      '<div id="tw-table"><table>' +
        '<thead><tr><th></th><th></th><th>TAG</th><th>VALUE</th><th class="h-cur">@ RULER</th>' +
        '<th>UNIT</th><th>LOW</th><th>HIGH</th><th></th></tr></thead>' +
        '<tbody id="tw-rows"></tbody></table></div>';
    document.body.appendChild(win);

    const sp = win.querySelector('#tw-spans');
    SPANS.forEach(x => {
      const b = document.createElement('button');
      b.textContent = x.lbl; b.dataset.span = x.s;
      b.onclick = () => setSpan(x.s);
      sp.appendChild(b);
    });

    const tb = win.querySelector('#tw-rows');
    for (let i = 0; i < SLOTS; i++) {
      const tr = document.createElement('tr');
      tr.innerHTML = '<td class="c-n"></td><td class="c-k"><i></i></td><td class="c-t"></td>' +
                     '<td class="c-v"></td><td class="c-cur"></td><td class="c-u"></td>' +
                     '<td class="c-lo"><input type="number" step="any" disabled ' +
                       'title="Display LOW for this pen. Blank the field to auto-scale."></td>' +
                     '<td class="c-hi"><input type="number" step="any" disabled ' +
                       'title="Display HIGH for this pen. Blank the field to auto-scale."></td>' +
                     '<td class="c-x"></td>';
      tr.onclick = ev => {
        if (ev.target.tagName === 'INPUT') { selected = i; dirty = true; redraw(); return; }
        if (ev.target.classList.contains('c-x')) { if (slots[i]) removeSlot(i); return; }
        selected = i; dirty = true; redraw(); save();
      };
      [['lo', '.c-lo input'], ['hi', '.c-hi input']].forEach(([which, sel]) => {
        const inp = tr.querySelector(sel);
        inp.addEventListener('change', () => commitRange(i, which, inp));
        inp.addEventListener('keydown', ev => {
          if (ev.key !== 'Enter') return;
          ev.preventDefault();                       // ENTER commits, per ui_guidelines §12
          commitRange(i, which, inp);
          inp.blur();
        });
        inp.addEventListener('mousedown', ev => ev.stopPropagation());
      });
      tr.addEventListener('dragover', ev => { ev.preventDefault(); tr.classList.add('drop'); });
      tr.addEventListener('dragleave', () => tr.classList.remove('drop'));
      tr.addEventListener('drop', ev => {
        ev.preventDefault(); tr.classList.remove('drop');
        const tag = ev.dataTransfer.getData('text/ots-tag') || ev.dataTransfer.getData('text/plain');
        if (tag) addTag(tag, i);
      });
      tb.appendChild(tr);
    }

    // Click anywhere on the plot to drop the ruler at that instant.
    win.querySelector('#tw-canvas').addEventListener('click', ev => {
      if (!chart) return;
      const rect = ev.currentTarget.getBoundingClientRect();
      const px = ev.clientX - rect.left;
      const area = chart.chartArea;
      if (px < area.left || px > area.right) return;
      setCursor(viewEnd() + chart.scales.x.getValueForPixel(px));
    });
    win.querySelector('#tw-ruler').onclick = () => setCursor(null);
    win.querySelector('#tw-back').onclick = () => pan(-1);
    win.querySelector('#tw-fwd').onclick = () => pan(+1);
    win.querySelector('#tw-live').onclick = goLive;

    const plot = win.querySelector('#tw-plot');
    plot.addEventListener('dragover', ev => ev.preventDefault());
    plot.addEventListener('drop', ev => {
      ev.preventDefault();
      const tag = ev.dataTransfer.getData('text/ots-tag') || ev.dataTransfer.getData('text/plain');
      if (tag) addTag(tag, null);
    });

    win.querySelector('#tw-close').onclick = () => {
      win.style.display = 'none';
      save();                                   // slot list is retained for the next open
    };
    win.querySelector('#tw-save').onclick = exportPNG;

    // title-bar drag
    const head = win.querySelector('#tw-head');
    head.addEventListener('mousedown', ev => {
      if (ev.button !== 0 || ev.target.id === 'tw-close') return;
      const sx = ev.clientX, sy = ev.clientY;
      const ox = parseFloat(win.style.left) || win.offsetLeft;
      const oy = parseFloat(win.style.top) || win.offsetTop;
      const mm = e => {
        win.style.left = clamp(ox + e.clientX - sx, 0, window.innerWidth - 120) + 'px';
        win.style.top  = clamp(oy + e.clientY - sy, 0, window.innerHeight - 40) + 'px';
      };
      const mu = () => {
        document.removeEventListener('mousemove', mm);
        document.removeEventListener('mouseup', mu);
        save();
      };
      document.addEventListener('mousemove', mm);
      document.addEventListener('mouseup', mu);
    });

    new ResizeObserver(() => { if (chart) chart.resize(); }).observe(win);
  }

  function open() {
    if (!win) buildWindow();
    const st = saved();
    if (win.style.display !== 'block') {
      win.style.display = 'block';
      win.style.left = st.x || '120px';
      win.style.top = st.y || '90px';
      win.style.width = st.w || '860px';
      win.style.height = st.h || '560px';
    }
    if (!chart) buildChart();
    win.querySelectorAll('#tw-spans button').forEach(b =>
      b.classList.toggle('on', Number(b.dataset.span) === span));
    markHist();
    dirty = true; redraw(); save();
  }

  // ================= context menu =================
  const HAS_DOM = (typeof document !== 'undefined');

  let menu = null;
  function closeMenu() { if (menu) menu.style.display = 'none'; }
  if (HAS_DOM) {
    // Styles up front, not lazily from buildWindow(): the context menu is reachable before the
    // window has ever been built, and unstyled it renders unpositioned below the fold.
    injectCSS();
    document.addEventListener('click', closeMenu);
    document.addEventListener('contextmenu', e => { if (!e.target.closest('#tw-menu')) closeMenu(); }, true);
  }

  function openMenu(ev, tag) {
    // The menu can be the very first thing an operator touches, before the window has ever been
    // built. Without this the styles are absent and it renders unpositioned below the fold, so
    // right-click looks like it does nothing. injectCSS is idempotent.
    injectCSS();
    if (!menu) {
      menu = document.createElement('div');
      menu.id = 'tw-menu';
      document.body.appendChild(menu);
    }
    const bound = Registry.bound(tag);
    let html = '<div class="hd">' + tag + '</div>';
    if (!bound) {
      html += '<div class="it off">Trend — not bound</div>';
    } else {
      html += '<div class="it" data-act="trend">Trend</div>';
      if (win && win.style.display === 'block') {
        html += '<div class="sub">';
        for (let i = 0; i < SLOTS; i++) {
          const s = slots[i];
          html += '<div class="it" data-act="slot" data-i="' + i + '">Slot ' + (i + 1) + ' — ' +
                  (s ? s.tag : 'empty') + '</div>';
        }
        html += '</div>';
      }
    }
    menu.innerHTML = html;
    menu.querySelectorAll('.it[data-act]').forEach(it => {
      it.onclick = () => {
        if (it.dataset.act === 'trend') { open(); addTag(tag, null); }
        else { open(); addTag(tag, Number(it.dataset.i)); }
        closeMenu();
      };
    });
    menu.style.display = 'block';
    menu.style.left = Math.min(ev.pageX, window.innerWidth - 170) + 'px';
    menu.style.top = Math.min(ev.pageY, window.innerHeight - 120) + 'px';
  }

  // ================= live feed =================
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
    dirty = true;
    scheduleRedraw();
  }

  // ================= restore =================
  function restore() {
    const st = saved();
    if (typeof st.span === 'number' && SPANS.some(x => x.s === st.span)) span = st.span;
    if (typeof st.sel === 'number') selected = clamp(st.sel, 0, SLOTS - 1);
    if (!st.open || !Array.isArray(st.tags)) return;
    open();
    st.tags.forEach((tag, i) => {
      if (!tag) return;
      addTag(tag, i);
      const r = st.ranges && st.ranges[i];
      if (slots[i] && Array.isArray(r) && r.length === 2 && r[1] > r[0]) {
        slots[i].lo = r[0]; slots[i].hi = r[1]; slots[i].auto = false;
      }
    });
  }
  // Restore after overlays.js has published OV_BINDS.
  if (HAS_DOM) {
    if (document.readyState === 'complete') setTimeout(restore, 0);
    else window.addEventListener('load', () => setTimeout(restore, 0));
  }

  const API = {
    open: open, onPacket: onPacket, addTag: addTag, openMenu: openMenu, removeSlot: removeSlot,
    setCursor: setCursor, cursor: () => cursorT, valueAt: valueAt,
    pan: pan, goLive: goLive, viewEnd: viewEnd, isLive: isLive,
    isBound: t => Registry.bound(t), isOpen: () => !!win && win.style.display === 'block',
  };
  if (typeof window !== 'undefined') {
    window.TrendWindow = API;
    // Preserved entry point: overlays.js and any legacy caller use window.openTrend(tag).
    window.openTrend = function (tag) { open(); addTag(tag, null); };
  }
  // Headless export so the pure logic is testable without a DOM (see test_trend.js).
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = Object.assign({}, API, {
      _internals: { hms, deskClock, stamp, norm, wallAt, noteTime, Registry, commitRange,
                    UNIT_RANGE, SPANS, SLOTS, PENS, slots,
                    setSpanValue: v => { span = v; }, getSpan: () => span,
                    maxPanBack: maxPanBack, setNow: t => { nowSim = t; },
                    getSelected: () => selected, save: save, saved: saved },
    });
  }
})();
