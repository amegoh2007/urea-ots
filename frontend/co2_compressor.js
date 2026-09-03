'use strict';
// =====================================================================================
//  322-1  COMPRESSOR SPEED widget  (CO2 feed load hand-station)
// -------------------------------------------------------------------------------------
//  Bottom-left panel on screen 322-1.  UP / DOWN nudge the 320K002 CO2 compressor feed
//  to the urea plant by +/-2 % of design in one step.  Design feed 54.618 t/h = 100 %
//  plant Load (main.py CO2_DES_KGH).  Hard ceiling 120 %.  Backend command:
//      { type:'co2_set', value:<t/h> }   ->  s.F_CO2_raw_th   (main.py handler)
//  raw_th is echoed back in CO2_FEED.raw_th, so the readout tracks the true commanded
//  value and re-syncs after a RESET or any external co2_set once the operator is idle.
//
//  Lives in a DEDICATED ov-layer sibling (class "co2-comp-layer") so overlays.js build()
//  -- which only ever clears the FIRST .ov-layer it finds -- can never wipe the widget.
//  render() also re-creates it if it ever goes missing (auto-heal).
// =====================================================================================
(function () {
  var CO2_DES_TH = 54.618;   // t/h raw CO2 feed = 100 % plant Load (main.py: CO2_DES_KGH/1000)
  var STEP = 2.0;            // % of design per button press
  var MIN = 0.0, MAX = 120.0;

  var pct = 100.0;           // commanded compressor speed (% of design CO2 feed)
  var lastClickT = -1e9;     // ms; suppress live-resync briefly after an operator press
  var elWidget = null, elPct = null, elUp = null, elDown = null;

  function now()   { return (window.performance && performance.now) ? performance.now() : Date.now(); }
  function clamp(v){ return Math.max(MIN, Math.min(MAX, v)); }
  function gp(o, p){ return p.split('.').reduce(function (a, k) { return a == null ? undefined : a[k]; }, o); }

  function injectCSS() {
    if (document.getElementById('co2-comp-css')) return;
    var s = document.createElement('style'); s.id = 'co2-comp-css';
    s.textContent =
      // The dedicated layer is a full-screen inset:0 sibling at the SAME z-index as the
      // overlays layer, so as the later sibling it wins hit-testing across the whole screen
      // and swallows every faceplate click on 322-1.  Make the layer click-through and let
      // only the widget itself take pointer events back.
      '.co2-comp-layer{pointer-events:none;}' +
      // Placed at the marker the 322-1 slide reserves for this widget (shape 227, centre
      // 96.7,421.5).  Pulled to the screen edge and 43 px up: the widget is 196 x 53 against the
      // marker's 63 x 54, and at the marker's own origin its right edge lands on the AT-322701
      // indicator (187..266) and its bottom on the AE-322801 chip (441..465).
      '.co2-comp{position:absolute;left:6px;top:352px;width:196px;z-index:6;pointer-events:auto;' +
        'background:var(--ratio,#2e8a8f);border:1px solid #99dadd;border-radius:3px;' +
        'padding:6px 8px 7px;box-shadow:0 2px 9px rgba(0,0,0,.45);user-select:none;}' +
      '.co2-comp .cc-hd{font:bold 10.5px Arial,Helvetica,sans-serif;letter-spacing:.7px;' +
        'color:#eaf7f8;margin:0 0 5px;text-align:center;text-transform:uppercase;}' +
      '.co2-comp .cc-row{display:flex;align-items:stretch;gap:6px;}' +
      '.co2-comp .cc-btn{flex:0 0 auto;min-width:48px;background:#1b4a4f;color:#cfeff1;' +
        'border:1px solid #2f6f75;border-radius:4px;font:bold 11px Arial,Helvetica,sans-serif;' +
        'letter-spacing:.3px;cursor:pointer;padding:4px 6px;line-height:1;white-space:nowrap;}' +
      '.co2-comp .cc-btn:hover{background:#27666d;color:#fff;border-color:#7fd0d8;}' +
      '.co2-comp .cc-btn:active{background:#0aa64d;border-color:#22ff22;color:#fff;}' +
      '.co2-comp .cc-btn:disabled{opacity:.32;cursor:not-allowed;background:#173a3e;color:#8fb3b5;border-color:#2f6f75;}' +
      '.co2-comp .cc-up .g{color:#22ff22;} .co2-comp .cc-down .g{color:#ffd000;}' +
      '.co2-comp .cc-btn:disabled .g{color:inherit;}' +
      '.co2-comp .cc-val{flex:1 1 auto;display:flex;align-items:center;justify-content:center;gap:3px;' +
        'background:#000;border:1px solid #fff;border-radius:2px;padding:0 2px;}' +
      '.co2-comp .cc-val b{font:bold 15px var(--val-font);font-variant-numeric:tabular-nums;color:#38f5b0;}' +
      '.co2-comp .cc-val .cc-u{font:normal 10px var(--val-font);color:#7fbfa8;}' +
      '.co2-comp.at-max .cc-val b{color:#ffd000;}' +
      '.co2-comp.at-max{border-color:#ffd000;box-shadow:0 0 8px rgba(255,208,0,.45);}';
    document.head.appendChild(s);
  }

  function ensure() {
    var scr = document.getElementById('screen-322-1');
    if (!scr) return false;
    if (document.getElementById('co2-comp-widget')) return true;   // already built
    injectCSS();
    // dedicated layer sibling -> survives overlays.js build() (which clears only the first .ov-layer)
    var layer = scr.querySelector('.co2-comp-layer');
    if (!layer) { layer = document.createElement('div'); layer.className = 'ov-layer co2-comp-layer'; scr.appendChild(layer); }
    var w = document.createElement('div');
    w.id = 'co2-comp-widget';
    w.className = 'co2-comp';
    w.title = '320K002 CO2 compressor feed to urea plant (100 % = 54.618 t/h design)';
    w.innerHTML =
      '<div class="cc-hd">Compressor Speed</div>' +
      '<div class="cc-row">' +
        '<button type="button" class="cc-btn cc-down" title="Decrease CO2 feed to urea plant by 2%">' +
          '<span class="g">&#9660;</span> DOWN</button>' +
        '<div class="cc-val"><b>100.0</b><span class="cc-u">%</span></div>' +
        '<button type="button" class="cc-btn cc-up" title="Increase CO2 feed to urea plant by 2% (max 120%)">' +
          '<span class="g">&#9650;</span> UP</button>' +
      '</div>';
    layer.appendChild(w);
    elWidget = w;
    elPct  = w.querySelector('.cc-val b');
    elUp   = w.querySelector('.cc-up');
    elDown = w.querySelector('.cc-down');
    elUp.addEventListener('click',  function (e) { e.stopPropagation(); step(+STEP); });
    elDown.addEventListener('click', function (e) { e.stopPropagation(); step(-STEP); });
    return true;
  }

  function livePct() {
    var raw = gp(window.OTS_LAST || {}, 'CO2_FEED.raw_th');
    return (typeof raw === 'number' && CO2_DES_TH > 0) ? raw / CO2_DES_TH * 100 : null;
  }

  function step(d) {
    // Nudge from the LOCAL commanded value, not the live packet: a burst of clicks fires
    // before any WS packet returns, so reading raw_th here would stall every press at +1 step.
    // render() re-syncs pct to the live value while the operator is idle (RESET / external set).
    pct = clamp(Math.round((pct + d) * 10) / 10);
    lastClickT = now();
    if (window.otsSend) window.otsSend({ type: 'co2_set', value: +(CO2_DES_TH * pct / 100).toFixed(3) });
    paint();
  }

  function render() {
    if (!ensure()) return;
    var lp = livePct();
    // Re-sync the readout to the live commanded value while the operator is idle so a
    // backend RESET / external co2_set is reflected; a fresh press owns the value for 1.5 s.
    if (lp != null && (now() - lastClickT) > 1500) pct = clamp(Math.round(lp * 10) / 10);
    paint();
  }

  function paint() {
    if (!elPct) return;
    elPct.textContent = pct.toFixed(1);
    var atMax = pct >= MAX - 1e-6, atMin = pct <= MIN + 1e-6;
    if (elWidget) elWidget.classList.toggle('at-max', atMax);
    if (elUp)   elUp.disabled   = atMax;
    if (elDown) elDown.disabled = atMin;
  }

  // Piggy-back the per-packet render loop without disturbing overlays.js.
  function hook() {
    var prev = window.OV_apply;
    if (typeof prev === 'function' && !prev.__cc) {
      var wrapped = function (s) { prev(s); try { render(); } catch (e) { /* keep DCS alive */ } };
      wrapped.__cc = true;
      window.OV_apply = wrapped;
    }
  }

  function boot() { ensure(); hook(); render(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
  // overlays.js may (re)assign OV_apply after us; re-hook a few times to be safe.
  var tries = 0, iv = setInterval(function () { hook(); if (++tries > 20) clearInterval(iv); }, 250);
})();
