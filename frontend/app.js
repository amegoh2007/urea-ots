'use strict';

// ---------- WebSocket ----------
const WS_URL = `ws://${location.hostname || 'localhost'}:8000/ws`;
let ws;
let lastState = {};

function connect(){
  ws = new WebSocket(WS_URL);
  ws.onopen = () => Health.onOpen();
  ws.onmessage = e => {
    const s = JSON.parse(e.data);
    lastState = s;
    Health.onPacket(s);           // read _health + refresh watchdog BEFORE rendering
    ResetBtn.onPacket(s);         // confirm a pending reset actually took (t_sim dropped to ~0)
    render(s);
    render322(s);
    if(window.refreshF50) window.refreshF50(s);
    if(window.refreshF51) window.refreshF51(s);
    if(window.refreshMSP) window.refreshMSP(s);
    if(window.OV_apply) window.OV_apply(s);
    if(window.TrendWindow) window.TrendWindow.onPacket(s);
  };
  ws.onclose = () => { Health.onDisconnect(); setTimeout(connect, 1000); };
  ws.onerror = () => ws.close();
}
function send(msg){ if(ws && ws.readyState===1) ws.send(JSON.stringify(msg)); }

// ---------- Backend health / fault surface ----------
// Three fault classes the operator must be able to tell apart:
//   CRASH  - server sent a packet whose _health.ok===false (physics step raised).
//   HANG   - packets still arrive but _health.age_s keeps climbing (step wedged, no throw).
//   LINK   - no packets at all: WebSocket dropped, server process gone.
const Health = (function(){
  let lastPacketWall = Date.now();
  let linkUp = false;
  let lastHealth = null;
  let userDismissed = false;      // reset whenever a NEW/worse fault appears
  const STALE_MS = 3000;          // no packet for 3 s -> treat link as stale

  const $ = id => document.getElementById(id);
  function setLED(cls, txt){
    const led = $('sys-led'); if(!led) return;
    led.classList.remove('warn','err');
    if(cls) led.classList.add(cls);
    $('sys-led-txt').textContent = txt;
  }
  function showOverlay(title, cond, h){
    const ov = $('fault-overlay'); if(!ov) return;
    $('fault-title').textContent = title;
    $('fault-cond').textContent  = cond;
    $('fault-type').textContent  = (h && h.type)  || '—';
    $('fault-simt').textContent  = (h && h.sim_t!=null) ? Number(h.sim_t).toFixed(1) : '—';
    $('fault-age').textContent   = (h && h.age_s!=null) ? (Number(h.age_s).toFixed(1)+' s') : '—';
    $('fault-count').textContent = (h && h.count) ? h.count : '—';
    $('fault-msg').textContent   = (h && h.error) || cond;
    const tb = $('fault-tb');
    if(h && h.traceback){ tb.textContent = h.traceback; }
    else { tb.textContent=''; tb.classList.remove('show'); $('fault-tb-toggle').textContent='Show traceback'; }
    if(!userDismissed) ov.classList.add('show');
  }
  function hideOverlay(){ const ov=$('fault-overlay'); if(ov) ov.classList.remove('show'); }

  // Signature so we only re-force the overlay open when the fault CHANGES, not every 100ms tick.
  function sig(kind, h){ return kind+'|'+((h&&h.since)||'')+'|'+((h&&h.type)||''); }
  let lastSig = null;

  function evaluate(){
    const stale = (Date.now() - lastPacketWall) > STALE_MS;
    let kind, h = lastHealth;
    if(!linkUp || stale){
      kind = 'LINK';
    } else if(h && h.ok === false){
      kind = 'CRASH';
    } else if(h && h.age_s != null && h.age_s > 5){
      kind = 'HANG';
    } else {
      kind = 'OK';
    }

    if(kind === 'OK'){
      setLED('', 'BACKEND OK');
      hideOverlay(); userDismissed=false; lastSig=null;
      return;
    }

    const s = sig(kind, h);
    if(s !== lastSig){ userDismissed = false; lastSig = s; }  // new/changed fault -> re-alert

    if(kind === 'LINK'){
      setLED('err', 'NO SIGNAL');
      showOverlay('BACKEND UNREACHABLE',
        'No data from the backend. The server process may have crashed or the connection dropped.',
        h);
    } else if(kind === 'CRASH'){
      setLED('err', 'BACKEND ERROR');
      showOverlay('BACKEND ERROR',
        'A physics step raised an exception. The simulation is frozen; displayed values are stale.',
        h);
    } else if(kind === 'HANG'){
      setLED('warn', 'BACKEND STALLED');
      showOverlay('BACKEND STALLED',
        'The physics step has not completed for several seconds (no exception). The backend is hung.',
        h);
    }
  }

  return {
    onOpen(){ linkUp = true; lastPacketWall = Date.now(); },
    onDisconnect(){ linkUp = false; evaluate(); },
    onPacket(s){ linkUp = true; lastPacketWall = Date.now(); lastHealth = s && s._health || null; evaluate(); },
    dismiss(){ userDismissed = true; hideOverlay(); },
    // watchdog: catches the LINK/HANG cases where no packet arrives to drive evaluate()
    _tick(){ evaluate(); }
  };
})();
setInterval(()=>Health._tick(), 1000);

// ---------- Reset button (verifies the backend actually reset) ----------
// The button does NOT claim success on click: it sends reset_sim, then watches the plant
// clock. Only once a packet arrives with t_sim collapsed back toward 0 does it show "RESET ✓".
// If no such packet lands within the timeout, it shows "NO RESPONSE" -- the honest signal that
// the running backend ignored the command (e.g. a server started before the reset handler
// existed and never restarted). This is exactly the case that made a stale server look reset.
const ResetBtn = (function(){
  let pending = null;   // { prevTsim, deadline }
  const btn = ()=>document.getElementById('sys-reset');
  const txt = ()=>document.getElementById('sys-reset-txt');
  function set(cls, label){ const b=btn(), t=txt(); if(!b||!t) return;
    b.classList.remove('flash','nak'); if(cls) b.classList.add(cls); t.textContent=label; }
  function idleSoon(ms){ setTimeout(()=>{ if(!pending) set('', 'RESET'); }, ms); }
  return {
    fire(){
      if(!confirm('Reset the simulation?\n\nThe plant clock and all counters/totalizers return to zero and the run restarts from the fresh seed.')) return;
      const prev = (lastState && typeof lastState.t_sim==='number') ? lastState.t_sim : Infinity;
      pending = { prevTsim: prev, deadline: Date.now()+4000 };
      send({type:'reset_sim'});
      set('', 'RESETTING…');
    },
    onPacket(s){
      if(!pending || !s || typeof s.t_sim!=='number') return;
      // reset took if the clock fell far below where it was (or is essentially zero)
      if(s.t_sim < 5 || s.t_sim < pending.prevTsim*0.5){
        pending = null; set('flash', 'RESET ✓'); idleSoon(1400);
      }
    },
    _tick(){
      if(pending && Date.now() > pending.deadline){
        pending = null; set('nak', 'NO RESPONSE'); idleSoon(3000);
      }
    }
  };
})();
setInterval(()=>ResetBtn._tick(), 500);

document.addEventListener('DOMContentLoaded', ()=>{
  const on=(id,fn)=>{ const el=document.getElementById(id); if(el) el.addEventListener('click',fn); };
  on('sys-led', ()=>document.getElementById('fault-overlay').classList.add('show'));
  on('sys-trend', ()=>{ if(window.TrendWindow) window.TrendWindow.open(); });
  on('sys-reset', ()=>ResetBtn.fire());
  on('fault-dismiss', ()=>Health.dismiss());
  on('fault-reload', ()=>location.reload());
  on('fault-tb-toggle', ()=>{
    const tb=document.getElementById('fault-tb'), b=document.getElementById('fault-tb-toggle');
    const shown=tb.classList.toggle('show');
    b.textContent = shown ? 'Hide traceback' : 'Show traceback';
  });
});
window.otsSend = send;
window.openTrend = (tag)=>openTrend(tag);

// (pushHistory removed: the backend historian records all 914 packet paths from process
//  start, so the 25-tag browser-side ring buffer it maintained is redundant.)

// ---------- Render ----------
const MODE_LETTER = { MAN:'M', AUTO:'A', CAS:'C' };

function fmt(v){
  if(v==null||isNaN(v)) return '--';
  if(Math.abs(v)>=1000) return Number(v).toFixed(2);
  return Number(v).toFixed(1);
}
// ---------- Faceplate value fields: click to expand to 3 decimal places ----------
// A faceplate rounds for readability (fmt -> 1 or 2 dp), which is right for a glance and wrong
// when an operator is checking whether a value has actually moved.  Clicking a value field
// swaps it to the shared 3-decimal form and back.  The expansion is per FIELD and survives the
// live re-fill each tick, so an expanded PV keeps tracking at 3 dp instead of snapping back.
const FPX = new Set();                                   // ids of fields currently expanded
function fpxDisplay(v){                                  // 3-dp form, shared with the registry
  return (window.IndicatorFaceplate ? window.IndicatorFaceplate.display(v)
                                    : (v==null||isNaN(v) ? '—' : Number(v).toFixed(3)));
}
function fpxBind(el){                                    // make one read-only field expandable
  if(!el || el.dataset.fpxBound) return;
  el.dataset.fpxBound = '1';
  el.classList.add('fpx');
  el.title = 'click to expand to 3 decimal places';
  el.addEventListener('click', ()=>{
    if(FPX.has(el.id)) FPX.delete(el.id); else FPX.add(el.id);
    fpxPaint(el);
  });
}
function fpxPaint(el){
  if(!el) return;
  const raw = el.dataset.fpxRaw;
  const expanded = FPX.has(el.id);
  el.classList.toggle('expanded', expanded);
  if(raw == null){ return; }
  const n = parseFloat(raw);
  el.value = (expanded && raw !== '' && !isNaN(n)) ? fpxDisplay(n) + (el.dataset.fpxSuf||'') : raw;
}
function fpxSet(el, text, numeric, suffix){              // write a value through the expander
  if(!el) return;
  el.dataset.fpxRaw = (text == null) ? '' : String(text);
  el.dataset.fpxSuf = suffix || '';
  if(numeric != null && !isNaN(numeric)) el.dataset.fpxNum = String(numeric);
  fpxBind(el);
  fpxPaint(el);
}
function setPI(tag,val,unit,alarm){
  if(window.IndicatorFaceplate) window.IndicatorFaceplate.publish(tag, val, unit || '');
  document.querySelectorAll(`.pi[data-tag="${tag}"]`).forEach(el=>{
    const u = unit || (el.querySelector('.u')?.textContent||'');
    el.innerHTML = `${fmt(val)} <span class="u">${u}</span>`;
    el.classList.toggle('alarm', !!alarm);
  });
}
function setXV(id,open){
  const el=document.getElementById(id); if(!el) return;
  el.classList.toggle('closed',!open);
  el.firstChild.textContent = open?'OPEN':'CLOSED';
}
function setModeTag(elId, letter){
  const mt=document.getElementById(elId); if(!mt) return;
  mt.textContent = letter;
  mt.classList.toggle('auto', letter==='A');
  mt.classList.toggle('cas',  letter==='C');
}

function render(s){
  setPI('FI_321401', s.FI_321401, 'T/H', false);
  setPI('TI_top1', s.TI_top1, 'C', false);
  setPI('TI_top2', s.TI_top2, 'C', false);
  setPI('PI_top1', s.PI_top1, 'BAR G', false);
  setPI('PI_top2', s.PI_top2, 'BAR G', false);
  setPI('PI_header', s.PI_header, 'BAR G', false);
  setPI('totalizer', s.totalizer, 'T', false);
  setPI('PI_321201', s.PI_321201, 'BAR G', s.PI_321201_alarm);
  setPI('PI_321202', s.PI_321202, 'BAR G', s.PI_321202_alarm);
  setPI('PY_321201', s.PY_321201 - 1.01325, 'BAR G', false);   // barg = bara - 1 atm
  setPI('PY_321202', s.PY_321202 - 1.01325, 'BAR G', false);
  setPI('PDY_321203', s.PDY_321203, 'BAR', s.PDY_321203_alarm);
  setPI('PDY_321204', s.PDY_321204, 'BAR', s.PDY_321204_alarm);
  setPI('PI_disch', s.PI_disch, 'BAR G', false);
  setPI('TI_321020', s.TI_321020, 'C', false);

  if(s.pumpA){
    setPI('PA_current', s.pumpA.current, 'A', false);
    setPI('PA_speed',   s.pumpA.speed,   'RPM', false);
    const btn=document.getElementById('pa-btn');
    btn.classList.toggle('on', s.pumpA.on); btn.classList.toggle('off', !s.pumpA.on);
    btn.firstChild.textContent = '321P002A '+(s.pumpA.on?'ON':'OFF');
    const ic=document.getElementById('pa-icon'); ic.classList.toggle('on',s.pumpA.on); ic.classList.toggle('off',!s.pumpA.on);
    setModeTag('pa-mode', s.pumpA.mode||'M');
  }
  if(s.pumpB){
    setPI('PB_current', s.pumpB.current, 'A', false);
    setPI('PB_speed',   s.pumpB.speed,   'RPM', false);
    const btn=document.getElementById('pb-btn');
    btn.classList.toggle('on', s.pumpB.on); btn.classList.toggle('off', !s.pumpB.on);
    btn.firstChild.textContent = '321P002B '+(s.pumpB.on?'ON':'OFF');
    const ic=document.getElementById('pb-icon'); ic.classList.toggle('on',s.pumpB.on); ic.classList.toggle('off',!s.pumpB.on);
    setModeTag('pb-mode', s.pumpB.mode||'M');
  }

  setXV('xv-321901', !!s.XV_321901);
  setXV('xv-322901', !!s.XV_322901);

  // tank level badge tracks level
  const tl=document.getElementById('tankL');
  if(tl && s.LI_321501!=null){
    const lvl=Math.max(0,Math.min(100,s.LI_321501));
    tl.style.top=(300 - lvl/100*160)+'px';
  }

  const lsl=document.querySelector('[data-tag="LSL_321501"]');
  if(lsl && s.LSL_321501!=null){
    lsl.textContent = s.LSL_321501 ? 'LO' : 'OK';
    lsl.classList.toggle('alarm', !!s.LSL_321501);
  }

  if(s.ratio){
    const sp=document.getElementById('ratioSP');
    if(document.activeElement!==sp) sp.value = s.ratio.SP.toFixed(3);
    document.getElementById('ratioBal').value = s.ratio.bal.toFixed(3);
    if(s.ratio.NC_A!=null) document.getElementById('ncA').value = s.ratio.NC_A.toFixed(3);
    if(s.ratio.NC_B!=null) document.getElementById('ncB').value = s.ratio.NC_B.toFixed(3);
  }
  const ext=document.getElementById('extOverride');
  ext.querySelector('.lamp').style.background = s.ext_override? '#22ff22':'#444';
}

// ---------- Click handlers (toggle style) ----------
// The 321P002 A/B button and icon on the home screen go to the SAME pump faceplate the overlay
// pumps use -- a click anywhere on a pump opens the faceplate, it never commands the machine.
const PUMP_FP = { A: {id:'A', bind:'pumpA', tag:'321P002A'},
                  B: {id:'B', bind:'pumpB', tag:'321P002B'} };
const openPumpFace = id => { if(window.OTS_FACE && window.OTS_FACE.pump) window.OTS_FACE.pump(PUMP_FP[id]); };
document.getElementById('pa-btn').onclick  = ()=> openPumpFace('A');
document.getElementById('pb-btn').onclick  = ()=> openPumpFace('B');
document.getElementById('pa-icon').onclick = ()=> openPumpFace('A');
document.getElementById('pb-icon').onclick = ()=> openPumpFace('B');
document.getElementById('xv-321901').onclick = ()=> send({type:'xv_toggle',id:'321901'});
document.getElementById('xv-322901').onclick = ()=> send({type:'xv_toggle',id:'322901'});
document.getElementById('extOverride').onclick = ()=> send({type:'ext_override',value:!lastState.ext_override});
document.getElementById('ratioSP').addEventListener('change', e=>{
  const v=parseFloat(e.target.value); if(!isNaN(v)) send({type:'ratio_set',sp:v});
});
// ENTER confirms the N/C ratio setpoint (ratioSP lives in the always-visible panel, not a .modal).
// Without it the next ~10Hz telemetry packet overwrites the un-committed field and the entry appears to revert.
document.getElementById('ratioSP').addEventListener('keydown', e=>{
  if(e.key==='Enter'){ const v=parseFloat(e.target.value); if(!isNaN(v)) send({type:'ratio_set',sp:v}); }
});

// ---------- Global: ENTER in any open faceplate input confirms (clicks that faceplate's SET button) ----------
// Operators expect ENTER to commit the value they typed. On faceplates with no Enter handler the keypress
// does nothing, so the next telemetry packet overwrites the field and the entry appears to "revert to 0".
// One handler covers every faceplate modal; the SET button is each modal's single primary button.
const FACEPLATE_MODALS = '#hicModal,#picModal,#hic2Modal,#ctlModal,#f50,#f51,#mspModal';
document.addEventListener('keydown', e=>{
  if(e.key!=='Enter') return;
  const ae=document.activeElement;
  if(!ae || ae.tagName!=='INPUT') return;
  const modal=ae.closest(FACEPLATE_MODALS);
  if(!modal || !modal.classList.contains('show')) return;
  const setBtn=modal.querySelector('button.primary');
  // ENTER records the change (clicks SET) AND closes the faceplate — applies to every controller faceplate.
  if(setBtn && !setBtn.disabled){ e.preventDefault(); setBtn.click(); modal.classList.remove('show'); }
});

// ---------- Faceplate routing (SIC controllers -> dedicated REST modals) ----------
const FP_MAP = {
  PA_speed:'SIC_321950', PA_current:'SIC_321950',
  PB_speed:'SIC_321951', PB_current:'SIC_321951'
};
const $ = id => document.getElementById(id);

// ---------- Indicators: left=faceplate, right=trend menu ----------
document.querySelectorAll('.pi[data-tag]').forEach(el=>{
  const tag = el.dataset.tag;
  el.addEventListener('click', ()=>{
    const fp = FP_MAP[tag];
    if(fp==='SIC_321950') { if(window.openF50) window.openF50(); }        // SIC_321950 REST faceplate
    else if(fp==='SIC_321951') { if(window.openF51) window.openF51(); }   // SIC_321951 REST faceplate
  });
  el.addEventListener('contextmenu', e=>{ e.preventDefault(); openCtxMenu(e.pageX,e.pageY,tag); });
});

// ---------- Stream popups ----------
document.querySelectorAll('.stream-click').forEach(p=>{
  p.addEventListener('click', ()=> openStreamPopup(p.dataset.stream));
});

// ---------- Context menu / Trend ----------
const ctx=document.getElementById('ctxmenu');
let ctxTag=null;
function openCtxMenu(x,y,tag){ ctxTag=tag; ctx.style.display='block'; ctx.style.left=x+'px'; ctx.style.top=y+'px'; }
document.addEventListener('click',()=> ctx.style.display='none');
document.getElementById('ctx-trend').onclick = ()=>{ if(ctxTag) openTrend(ctxTag); };

// Trending now lives in trend.js: a persistent multi-pen window backfilled from the backend
// historian. The old single-tag #trendModal plotted `history[tag]`, which only ever matched
// on the legacy .pi screen — every overlay screen passes a P&ID tag ('TT-321001') while this
// dict is keyed by packet key ('TI_top1'), so those charts always came up empty.
function openTrend(tag){
  if(window.TrendWindow){ window.TrendWindow.open(); window.TrendWindow.addTag(tag, null); }
}

// ---------- Stream popup (generic renderer over packet STREAMS) ----------
const COMP_LBL = {CO2:'CO₂',CH4:'CH₄',H2:'H₂',H2O:'H₂O',N2:'N₂',
                  NH3:'NH₃',O2:'O₂',Urea:'Urea',Biuret:'Biuret'};
const fStrm = (v,d)=> (v==null ? '—' : (+v).toFixed(d));
function renderStream(s, compositionOnly = false){
  if (compositionOnly) {
    const rows = [['Composition', 'mol %  |  mass %']];
    Object.keys(COMP_LBL).forEach(k=>{
      const mo = (s.mol_pct&&s.mol_pct[k])||0, ma = (s.mass_pct&&s.mass_pct[k])||0;
      if(mo>0 || ma>0) rows.push([COMP_LBL[k], fStrm(mo,3)+'  |  '+fStrm(ma,3)]);
    });
    return rows;
  }
  const rows = [
    ['Route', s.src+' → '+s.dst], ['Phase', s.phase],
    ['Temperature', fStrm(s.T_C,1)+' °C'], ['Pressure', fStrm(s.P_bara,1)+' bar a'],
    ['Mass flow', fStrm(s.mass_th,2)+' t/h ('+fStrm(s.mass_kgh,0)+' kg/h)'],
    ['Molar flow', fStrm(s.mol_kmolh,1)+' kmol/h'], ['Avg MW', fStrm(s.MW,2)+' kg/kmol'],
    ['Specific enthalpy', s.enthalpy_kJkg!=null ? fStrm(s.enthalpy_kJkg,2)+' kJ/kg' : '— (not modelled)'],
    ['Enthalpy flow', s.enthalpy_flow_kW!=null ? fStrm(s.enthalpy_flow_kW,2)+' kW' : '— (not modelled)'],
    ['Enthalpy basis', s.enthalpy_basis ? (s.enthalpy_basis.startsWith('H0') ? 'H0 (ideal solution)' : s.enthalpy_basis.startsWith('H1') ? 'H1 (with mixing)' : 'H2 (plant reconciled)') : '—'],
    ['Density', s.rho!=null ? fStrm(s.rho,1)+' kg/m³' : '—'],
    ['Volum. flow', s.vol_m3h!=null ? fStrm(s.vol_m3h,1)+' m³/h' : '—'],
    ['', ''], ['Composition', 'mol %  |  mass %'],
  ];
  Object.keys(COMP_LBL).forEach(k=>{
    const mo = (s.mol_pct&&s.mol_pct[k])||0, ma = (s.mass_pct&&s.mass_pct[k])||0;
    if(mo>0 || ma>0) rows.push([COMP_LBL[k], fStrm(mo,3)+'  |  '+fStrm(ma,3)]);
  });
  return rows;
}
function openStreamPopup(id, compositionOnly = false){
  const s = (lastState.STREAMS||{})[id]; if(!s) return;
  document.getElementById('stream-title').textContent = s.name;
  document.getElementById('stream-table').innerHTML =
    renderStream(s, compositionOnly).map(r=>`<tr><td>${r[0]}</td><td>${r[1]}</td></tr>`).join('');
  document.getElementById('streamModal').classList.add('show');
}
document.getElementById('s-close').onclick = ()=> document.getElementById('streamModal').classList.remove('show');

// ---------- Hover tag tooltips (ui_guidelines rule 9) ----------
// Map internal packet keys -> P&ID tag numbers. Loop/level/pressure tags are
// real; tank-top, discharge, current/ratio/override tags are assigned for the OTS.
const TAG_MAP = {
  FI_321401:'FT-321401', totalizer:'FQI-321401',
  TI_top1:'TT-321001', TI_top2:'TT-321002', PI_top1:'PI-321001', PI_top2:'PI-321002', PI_header:'PI-321003',
  PI_321201:'PT-321201', PI_321202:'PT-321202',
  PY_321201:'PY-321201', PY_321202:'PY-321202',
  PDY_321203:'PDY-321203', PDY_321204:'PDY-321204',
  PA_current:'IT-321961', PA_speed:'SIC-321950',
  PB_current:'IT-321962', PB_speed:'SIC-321951',
  TI_321020:'TT-321020', PI_disch:'PI-321203',
  EJ_motive:'FI-322012', EJ_suction:'FI-329201', EJ_mu:'ENTRAINMENT μ',
  TT_322012:'TT-322012', EJ_Pdisch:'PI-322012', EJ_total:'FI-322013',
  EJ_MW:'MW DISCHARGE', TI_322002:'TI-322002', PI_329201:'PI-329201',
  HIC_322602:'HIC-322602'
};
const STREAM_TAG = {
  NH3_FEED:'NH3 EX 309E005', PUMP_SUCT:'NH3 SUCTION HDR',
  HP_DISCH:'NH3 HP DISCHARGE', CARB_RECYCLE:'CARBAMATE EX 322E003',
  EJ_DISCH:'CARB. LIQ. → 322E002', CO2_FEED:'CO2 FEED GAS',
  STRIP_TOP:'STRIP TOP GAS', STRIP_BOT:'STRIP BOTTOM SOLN',
  HPCC_PROD:'HPCC PRODUCT → 322R001', HPCC_STEAM:'LP STEAM 4.4 BARA',
  HPCC_COND:'BFW/COND → 322E002',
  REACT_OVERFLOW:'OVERFLOW → 322E001', REACT_OFFGAS:'REACTOR GAS → 322E003',
  SCRUB_OFFGAS:'SCRUBBER OFF-GAS → HV-322604', SCRUB_OFFGAS_LP:'OFF-GAS LP → 322C001',
  CCW_SUPPLY:'CCW SUPPLY → 322E003', CCW_RETURN:'CCW RETURN → 329P006 A/B'
};
function tagOf(el){
  if(el.dataset && el.dataset.tip) return el.dataset.tip;
  if(el.id==='tankL') return 'LI-321501';
  if(el.id==='extOverride') return 'HS-321002';
  if(el.classList){
    if(el.classList.contains('tank'))        return '321D003';
    if(el.classList.contains('block'))        return el.textContent.trim();
  }
  if(el.dataset){
    if(el.dataset.stream) return STREAM_TAG[el.dataset.stream] || el.dataset.stream;
    if(el.dataset.id)     return 'XV-'+el.dataset.id;
    if(el.dataset.pump)   return '321P002'+el.dataset.pump;
    if(el.dataset.tag)    return TAG_MAP[el.dataset.tag] || el.dataset.tag.replace(/_/g,'-');
  }
  return null;
}
const TIP_SEL = '.pi[data-tag],[data-id],[data-pump],.block,.tank,#tankL,#extOverride,.stream-click,[data-tip]';
const tip = document.createElement('div');
tip.id = 'tag-tip';
tip.style.cssText =
  'position:fixed;z-index:500;pointer-events:none;display:none;'+
  'background:#000;color:#ffd000;border:1px solid #ffd000;'+
  'font:11px Consolas,monospace;padding:2px 6px;white-space:nowrap;letter-spacing:0.5px;';
document.body.appendChild(tip);
const _stage = document.getElementById('stage');
_stage.addEventListener('mousemove', e=>{
  const host = e.target.closest ? e.target.closest(TIP_SEL) : null;
  const tag  = host ? tagOf(host) : null;
  if(!tag){ tip.style.display='none'; return; }
  tip.textContent  = tag;
  tip.style.display= 'block';
  tip.style.left   = (e.clientX + 12) + 'px';
  tip.style.top    = (e.clientY + 14) + 'px';
});
_stage.addEventListener('mouseleave', ()=> tip.style.display='none');

// ---------- Screen 322-2 render (HP ejector path) ----------
function render322(s){
  const e=s.EJ_322F001; if(!e) return;
  setPI('EJ_motive',  e.motive_kgh, 'KG/H', false);
  setPI('EJ_suction', e.suction_kgh,'KG/H', false);
  setPI('EJ_mu',      e.mu,         'μ', false);
  setPI('TT_322012',  e.TT_322012,  'C',     false);
  setPI('EJ_Pdisch',  e.PI_disch - 1.01325,   'BAR G', false);   // barg = bara - 1 atm
  setPI('EJ_total',   e.total_th,   'T/H',   false);
  setPI('EJ_MW',      e.MW,         'KG/KMOL', false);
  setPI('TI_322002',  178.8,        'C',     false);   // design suction temp (322E003 boundary)
  setPI('PI_329201',  e.PI_disch - 1.01325,   'BAR G', false);   // HP loop pressure (barg = bara - 1 atm)
  setPI('HIC_322602', e.HIC_322602, '%',     false);
  const hv=document.getElementById('hv-op'); if(hv) hv.textContent = fmt(e.HIC_322602)+' %';
  if(window.OTS_FACE && window.OTS_FACE.hicSync) window.OTS_FACE.hicSync();   // keep the open HV faceplate's field live (any hand valve)
  if(window.OTS_FACE && window.OTS_FACE.hsSync) window.OTS_FACE.hsSync();     // keep the open HS faceplate's status live
  if(window.OTS_FACE && window.OTS_FACE.pumpSync) window.OTS_FACE.pumpSync(); // keep the open pump faceplate's START/STOP enabling live
  if(window.OTS_FACE && window.OTS_FACE.indicatorSync) window.OTS_FACE.indicatorSync();  // keep the open indicator faceplate's value live
  const xb=document.getElementById('xv-322901b');
  if(xb) xb.classList.toggle('closed', !s.XV_322901);   // bowtie: green=open, red=closed (CSS)
}

// ---------- Hand-valve faceplate (opening-only) — HV-322602 reference; SHARED by every hand valve ----------
// Every HV (HIC/HV-322602, -322605, -322604, and any future hand valve) opens THIS one opening-only faceplate:
// a single "Opening %" field, no MAN/AUTO/CAS (a hand valve has no controller mode). Overlays route here via
// face:'hic'. To add a future HV: one CMD row below + face:'hic' on its overlay record — nothing else.
(function(){
  const inp=document.getElementById('hic-inp'), btn=document.getElementById('hic-set-btn'),
        box=document.getElementById('hic-box'), m=document.getElementById('hicModal'),
        cl=document.getElementById('hic-close'), ttl=document.getElementById('hic-title'),
        note=document.getElementById('hic-note');
  if(!inp||!btn) return;
  const gp=(o,p)=> p.split('.').reduce((a,k)=> (a==null?a:a[k]), o);   // dotted live-packet path
  // tag (HIC or HV form) -> backend command + payload field. Hand-valve setpoint = opening only.
  const CMD={ 'HIC-322602':{t:'hic_set',   f:'value'}, 'HV-322602':{t:'hic_set',   f:'value'},
              'HIC-322605':{t:'hic605_set',f:'op'},    'HV-322605':{t:'hic605_set',f:'op'},
              'HIC-322604':{t:'hic604_set',f:'op'},    'HV-322604':{t:'hic604_set',f:'op'},
              'HIC-329601':{t:'steam_hpvent_set',f:'op'}, 'HV-329601':{t:'steam_hpvent_set',f:'op'},
              'HIC-329602':{t:'hic329602_set',   f:'op'}, 'HV-329602':{t:'hic329602_set',   f:'op'},   // hand valve HV-329602, driven ONLY by HIC-329602 (NOT the PIC-329207C steam_963_set valve)
              'HIC-329605':{t:'hic9605_set',      f:'value'}, 'HV-329605':{t:'hic9605_set',      f:'value'},
              'HIC-329606':{t:'hic9606_set',      f:'value'}, 'HV-329606':{t:'hic9606_set',      f:'value'},
              'HIC-323605':{t:'hic323605_set',      f:'value'}, 'HV-323605':{t:'hic323605_set',      f:'value'},
              'FT-322404':{t:'cpl_set', f:'value'} };                          // 954 condensate feed -> 322C001 (kg/h, not a %-opening)
  const NOTE={ '322602':'↓ opening ⇒ ↑ 322E003 suction (↑ μ)',
               '323605':'↓ opening ⇒ ↑ 323F010 pressure (↓ vacuum)',
               '329605':'↑ opening ⇒ ↑ 324F002 vacuum (↓ 324E002 pressure)',
               '329606':'↑ opening ⇒ ↑ 324F004/F005 vacuum (↓ 324F003 pressure)',
               '322404':'operator sets 954 condensate feed (kg/h) ⇒ ↑322C001 sump ⇒ LIC-322502 opens ⇒ ↑756 draw ⇒ make dilutes' };
  const TTL ={ '322404':'FT-322404  CONDENSATE 954 → 322C001 (MANUAL, kg/h)' };  // honest title: this is a flow inject, not a HV
  let cur=null;   // overlay currently shown -> drives the SET command + live prefill
  const apply=()=>{ const v=parseFloat(inp.value); if(isNaN(v)) return;
    const c=(cur&&CMD[cur.tag])||CMD['HV-322602'];          // default = HV-322602 (panel %-box / direct open)
    send({type:c.t, [c.f]:v}); };
  btn.onclick=apply;
  inp.addEventListener('change',apply);
  const open=(o)=>{ cur=o||null;
    const num=((cur&&cur.tag.match(/\d+/))||[''])[0];
    if(ttl)  ttl.textContent  = TTL[num] || (num ? ('HIC-'+num+' → HV-'+num+' (MANUAL)') : 'HV (MANUAL)');
    if(note) note.textContent = NOTE[num] || 'Hand valve — operator sets opening directly (no controller mode).';
    const v=(cur&&cur.bind)? gp(window.OTS_LAST||{}, cur.bind) : null;   // prefill from THIS valve's live opening
    if(v!=null && document.activeElement!==inp) inp.value=fmt(v);
    if(m) m.classList.add('show'); };
  window.OTS_FACE = Object.assign(window.OTS_FACE||{}, { hic: open,
    hicSync: ()=>{ if(!m||!m.classList.contains('show')||!cur||!cur.bind||document.activeElement===inp) return;
                   const v=gp(window.OTS_LAST||{}, cur.bind); if(v!=null) inp.value=fmt(v); } });   // per-tick live field
  if(box) box.addEventListener('click', ()=>open(null));
  const pibox=document.querySelector('.pi[data-tag="HIC_322602"]'); if(pibox) pibox.addEventListener('click', ()=>open(null));
  if(cl&&m) cl.onclick=()=> m.classList.remove('show');
  if(m) m.addEventListener('click', e=>{ if(e.target===m) m.classList.remove('show'); });
})();

// ---------- Pump faceplate — START / STOP, one live button ------------------------------------
// No pump anywhere in the OTS starts or stops on a click: a click opens this, and the command is
// issued from here.  Exactly one of the two buttons is ever live -- START while the pump is
// stopped, STOP while it runs -- and the other is colourless and dead, so the operator cannot
// command the state the plant is already in.  The buttons send an EXPLICIT on/off rather than a
// toggle, so a faceplate rendered a tick behind the engine cannot invert the intent.
(function(){
  const m=document.getElementById('pumpModal'); if(!m) return;
  const ttl=document.getElementById('pump-title'), tagf=document.getElementById('pump-tag'),
        status=document.getElementById('pump-status'), ilk=document.getElementById('pump-ilk'),
        bStart=document.getElementById('pump-start-btn'), bStop=document.getElementById('pump-stop-btn'),
        cl=document.getElementById('pump-close');
  if(!bStart||!bStop) return;
  let cur=null;                                   // {id, bind, tag} of the pump being commanded
  const gp=(o,p)=> p.split('.').reduce((a,k)=> (a==null?a:a[k]), o);
  const isOn=()=>{ if(!cur||!cur.bind) return false;
                   const p=gp(window.OTS_LAST||{}, cur.bind); return !!(p&&p.on); };
  // 321P002 A/B restart gating, mirroring handle_cmd: a latch whose live cause has recovered is
  // auto-acknowledged by the START click itself; a latch over a still-live cause blocks it.
  const interlock=()=>{
    if(!cur || (cur.id!=='A' && cur.id!=='B')) return '';          // 329P006 A/B carry no latch
    const S=window.OTS_LAST||{}, L=S.trip_latched||{}, T=S.trips||{};
    const keys=['21_2','21_4','22_2', cur.id==='A'?'21_8':'21_10'];
    const live=keys.filter(k=>L[k]&&T[k]), held=keys.filter(k=>L[k]&&!T[k]);
    if(live.length) return 'TRIP '+live.join(', ').replace(/_/g,'.')+' ACTIVE';
    if(held.length) return 'TRIP '+held.join(', ').replace(/_/g,'.')+' LATCHED (clears on START)';
    return 'CLEAR';
  };
  const paint=()=>{ const on=isOn();
    if(status) status.value = on ? 'RUNNING' : 'STOPPED';
    if(ilk)    ilk.value    = interlock() || 'n/a';
    bStart.disabled = on;   bStart.classList.toggle('primary', !on);
    bStop.disabled  = !on;  bStop.classList.toggle('primary',  on);
  };
  const open=(o)=>{ cur=o||null;
    if(ttl && cur)  ttl.textContent = cur.tag || cur.id || 'PUMP';
    if(tagf && cur) tagf.value = cur.tag || cur.id || '';
    paint(); m.classList.add('show'); };
  bStart.onclick=()=>{ if(bStart.disabled||!cur) return; send({type:'pump_toggle', id:cur.id, on:true}); };
  bStop .onclick=()=>{ if(bStop.disabled ||!cur) return; send({type:'pump_toggle', id:cur.id, on:false}); };
  window.OTS_FACE = Object.assign(window.OTS_FACE||{}, { pump: open,
    pumpSync: ()=>{ if(m.classList.contains('show') && cur) paint(); } });
  if(cl) cl.onclick=()=> m.classList.remove('show');
  m.addEventListener('click', e=>{ if(e.target===m) m.classList.remove('show'); });
})();

// ---------- Hand Switch faceplate (HS-321901, HS-322901) — opens/closes XV on command ----------
(function(){
  const m=document.getElementById('hsModal'); if(!m) return;
  const xv=document.getElementById('hs-xv'), status=document.getElementById('hs-status'),
        btn=document.getElementById('hs-on-btn'), cl=document.getElementById('hs-close'),
        ttl=document.getElementById('hs-title');
  if(!btn) return;
  let cur=null;   // overlay currently shown
  const gp=(o,p)=> p.split('.').reduce((a,k)=> (a==null?a:a[k]), o);
  const open=(o)=>{ cur=o||null;
    if(ttl && cur) ttl.textContent = cur.tag;
    if(xv && cur && cur.xv) xv.value = cur.xv.replace('_','-');
    const isOpen = (cur&&cur.xv)? gp(window.OTS_LAST||{}, cur.xv) : null;
    if(status) status.value = (isOpen ? 'OPEN' : 'CLOSED');
    if(btn) btn.textContent = (isOpen ? 'CLOSE' : 'OPEN');
    if(m) m.classList.add('show');
  };
  btn.onclick=()=>{ if(cur&&cur.cmd) send({type:'xv_toggle', id:cur.cmd}); };
  window.OTS_FACE = Object.assign(window.OTS_FACE||{}, { hs: open,
    hsSync: ()=>{ if(!m||!m.classList.contains('show')||!cur||!cur.xv) return;
                  const isOpen=gp(window.OTS_LAST||{}, cur.xv);
                  if(status) status.value=(isOpen?'OPEN':'CLOSED');
                  if(btn) btn.textContent=(isOpen?'CLOSE':'OPEN'); } });
  if(cl&&m) cl.onclick=()=> m.classList.remove('show');
  if(m) m.addEventListener('click', e=>{ if(e.target===m) m.classList.remove('show'); });
})();

// ---------- PIC-322203 CO2 feed line pressure -> PV-322203 (faceplate) ----------
(function(){
  const m=document.getElementById('picModal'); if(!m) return;
  const pv=document.getElementById('pic-pv'), sp=document.getElementById('pic-sp'),
        op=document.getElementById('pic-op'), btn=document.getElementById('pic-set-btn'),
        cl=document.getElementById('pic-close'),
        mMan=document.getElementById('pic-man'), mAuto=document.getElementById('pic-auto');
  let mode='AUTO';
  const setMode=v=>{ mode=v;
    mMan.classList.toggle('active',v==='MAN'); mAuto.classList.toggle('active',v==='AUTO');
    if(pv) pv.readOnly = true;            // PV = measured pressure, always read-only
    if(op) op.readOnly = (v!=='MAN');     // MAN: only valve-opening (OP) editable
    if(sp) sp.readOnly = (v!=='AUTO');    // AUTO: only setpoint (SP) editable
  };
  mMan.onclick=()=>setMode('MAN');
  mAuto.onclick=()=>{ if(mode!=='AUTO' && pv && pv.value!=='') sp.value = parseFloat(pv.value); setMode('AUTO'); };  // bumpless: SP<-PV on MAN->AUTO (mirrors backend snap)
  const open=()=>{ const c=(window.OTS_LAST||{}).CO2_FEED||{};
    if(pv) fpxSet(pv, c.PIC_322203!=null ? (c.PIC_322203 - 1.01325) : '',
                  c.PIC_322203!=null ? (c.PIC_322203 - 1.01325) : null);   // barg = bara - 1 atm; click -> 3 dp
    if(sp) sp.value = c.PIC_sp!=null ? (c.PIC_sp - 1.01325) : (c.PIC_322203!=null ? (c.PIC_322203 - 1.01325) : '');
    if(op) op.value = c.PIC_op!=null ? c.PIC_op : '';
    setMode(c.PIC_mode||'AUTO'); m.classList.add('show'); };
  const apply=()=>{ const o=parseFloat(op.value), p=parseFloat(sp.value);
    const msg={type:'pic_set', mode};
    if(mode==='MAN'  && !isNaN(o)) msg.op=o;             // MAN: send valve opening only
    if(mode==='AUTO' && !isNaN(p)) msg.sp=p + 1.01325;   // AUTO: send setpoint (barg entry -> bara for engine)
    send(msg); };
  btn.onclick=apply;
  window.OTS_FACE = Object.assign(window.OTS_FACE||{}, { pic: open });   // overlay PIC-322203 left-click -> faceplate
  if(cl) cl.onclick=()=> m.classList.remove('show');
  m.addEventListener('click', e=>{ if(e.target===m) m.classList.remove('show'); });
})();

// ---------- HIC-322203 minimum opening of PV-322203 (faceplate) ----------
(function(){
  const m=document.getElementById('hic2Modal'); if(!m) return;
  const inp=document.getElementById('hic2-inp'), btn=document.getElementById('hic2-set-btn'),
        cl=document.getElementById('hic2-close');
  const open=()=>{ const c=(window.OTS_LAST||{}).CO2_FEED||{};
    if(inp&&c.HIC_322203!=null) inp.value=c.HIC_322203; m.classList.add('show'); };
  const apply=()=>{ const v=parseFloat(inp.value); if(!isNaN(v)) send({type:'hic2_set',value:v}); };
  btn.onclick=apply; inp.addEventListener('change',apply);
  window.OTS_FACE = Object.assign(window.OTS_FACE||{}, { hic2: open });   // overlay HIC-322203 left-click -> faceplate
  if(cl) cl.onclick=()=> m.classList.remove('show');
  m.addEventListener('click', e=>{ if(e.target===m) m.classList.remove('show'); });
})();

// ---------- Generic controller faceplate (any *IC-3* without a dedicated model) ----------
(function(){
  const m=document.getElementById('ctlModal'); if(!m) return;
  const ttl=document.getElementById('ctl-title'), pv=document.getElementById('ctl-pv'),
        sp=document.getElementById('ctl-sp'), op=document.getElementById('ctl-op'),
        note=document.getElementById('ctl-note'), cl=document.getElementById('ctl-close');
  const btn=document.getElementById('ctl-set-btn'),
        bMan=document.getElementById('ctl-man'), bAuto=document.getElementById('ctl-auto'), bCas=document.getElementById('ctl-cas');
  const gp=(o,p)=> p.split('.').reduce((a,k)=> (a==null?a:a[k]), o);   // dotted packet path
  const CK='ots_ctl_v1';                                               // local mode/SP/OP store (unmodelled loops)
  const load=()=>{ try{ return JSON.parse(localStorage.getItem(CK))||{}; }catch(e){ return {}; } };
  const save=st=>{ try{ localStorage.setItem(CK, JSON.stringify(st)); }catch(e){} };
  let cur=null, curPV=null, mode='AUTO';
  // Cascade SP authority: a slave in CAS does NOT own its setpoint — the master writes it every
  // tick, so the operator must enter the SP on the MASTER's faceplate instead.  `sp.readOnly`
  // below already blocks the field in CAS and apply() only ever sends `sp` in AUTO, so the write
  // path is safe; this map exists so the note NAMES the owning master rather than saying
  // "a linked parameter" and leaving the operator to guess where to go.
  // Every entry mirrors a real `cas_sp=` wiring in main.py's step_sim.
  const CAS_MASTER={
    'PIC-329202':'TIC-323007',   // 323C003 steam pressure  <- shell temp master
    'PIC-329208':'TIC-323012',   // 323F010 recirc heater   <- outlet temp master
    'PIC-329203':'TIC-324001',   // 324E001 chest steam-P   <- melt temp master
    'PIC-329212':'TIC-324002',   // 324E003 chest steam-P   <- melt temp master
    'FIC-324401':'LIC-323507',   // 324E001 carbamate feed  <- 323D002 Comp-I level master
    'FIC-329401':'FFIC-329401',  // 328C004 LP-steam 931    <- steam/feed ratio master (T/M3)
    'FIC-335405':'FFIC-335406',  // 335 UF85 injection      <- UF85-to-product ratio master
    'FIC-328404':'TIC-328008',   // 328D001 775 carbamate reflux <- offgas H2O master (PFD 737)
  };
  // Declared in the control narrative but NOT wired in main.py: the loop is seeded CAS yet its
  // _fic_flow call passes no cas_sp, so CAS behaves as AUTO at the seeded SP.  Say so plainly
  // rather than name a master that is not actually driving anything.  Tracked as TD-004.
  // Seeded CAS in the backend but with NO cas_sp wired in step_sim, so CAS silently holds the
  // seeded SP (behaves as AUTO). The faceplate says so plainly rather than naming a phantom master.
  // (TIC-328008 -> FIC-328404 is NOT here: that cascade IS wired, see CAS_MASTER.)
  const CAS_UNWIRED={
    'TIC-323013':'no master is wired to it',                 // 323 tempered-water; boots CAS, no cas_sp
    'FIC-329402':'its intended master TIC-328012 is not wired yet',   // 328C003 MP steam
  };
  const applyMode=v=>{                                                 // MAN=set opening, AUTO=set SP, CAS=linked param
    mode=v;
    bMan.classList.toggle('active', v==='MAN');
    bAuto.classList.toggle('active', v==='AUTO');
    bCas.classList.toggle('active', v==='CAS');
    op.readOnly = (v!=='MAN');                                         // MAN: operator edits valve opening
    sp.readOnly = (v!=='AUTO');                                        // AUTO: operator edits setpoint
    const tag=cur&&cur.tag, mst=tag&&CAS_MASTER[tag], unw=tag&&CAS_UNWIRED[tag];
    note.textContent =
      v==='MAN'  ? 'MAN — operator sets valve opening directly.' :
      v==='AUTO' ? 'AUTO — controller drives opening to hold SP.' :
      mst        ? ('CAS — SP is written by ' + mst + '. To change it, open the ' + mst + ' faceplate; this field is read-only.') :
      unw        ? ('CAS — inactive here: ' + unw + ', so CAS just holds the seeded SP (behaves as AUTO).') :
                   'CAS — opening driven by a linked (cascade) parameter.';
    if(cur && cur.note) note.textContent += '  ·  ' + cur.note;   // per-loop cause->effect physics note
  };
  const open=(o)=>{
    cur=o; ttl.textContent=o.tag;
    if(bCas) bCas.style.display = o.cas ? '' : 'none';   // CAS button only for cascade slaves (o.cas)
    const v = o.bind ? gp(window.OTS_LAST||{}, o.bind) : null;
    fpxSet(pv, (v==null||v==='') ? '—' : (v + (o.u?(' '+o.u):'')),
           (v==null||v==='') ? null : parseFloat(v), o.u?(' '+o.u):'');   // click the PV -> 3 dp
    curPV = (v==null||v==='') ? null : parseFloat(v);
    // authoritative telemetry: modelled loops expose a sibling {pv,sp,op,mode} block (bind ends in .pv)
    const blk = (o.bind && o.bind.endsWith('.pv')) ? gp(window.OTS_LAST||{}, o.bind.slice(0,-3)) : null;
    if(blk && typeof blk==='object' && blk.mode!=null){     // backend-authoritative loop -> live sp/op/mode
      sp.value = blk.sp!=null ? blk.sp : '';
      op.value = blk.op!=null ? blk.op : '';
      applyMode(blk.mode||'AUTO');
    } else {                                                // unmodelled loop -> local mode/SP/OP store
      const st=load()[o.tag]||{};
      sp.value = st.sp!=null ? st.sp : '';
      op.value = st.op!=null ? st.op : '';
      applyMode(st.mode||'AUTO');
    }
    m.classList.add('show');
  };
  bMan.onclick =()=>applyMode('MAN');
  bAuto.onclick=()=>{ if(mode!=='AUTO' && curPV!=null) sp.value = curPV; applyMode('AUTO'); };  // bumpless: SP<-PV on MAN->AUTO
  if(bCas) bCas.onclick=()=>applyMode('CAS');   // cascade slaves (o.cas) enable CAS -> master-driven SP
  const apply=()=>{
    if(!cur) return;
    const st=load(), o=parseFloat(op.value), p=parseFloat(sp.value);
    st[cur.tag]={ mode, op:isNaN(o)?null:o, sp:isNaN(p)?null:p };
    save(st);
    const T={ 'LIC-322501':'lic_set', 'HIC-322605':'hic605_set', 'HIC-322604':'hic604_set', 'FIC-329409':'fic_set', 'TIC-329005':'tic_set', 'PIC-329204':'pic329204_set', 'PIC-329205':'pic329205_set', 'PIC-329207':'pic329207_set', 'HIC-329601':'steam_hpvent_set', 'LIC-329502':'lic329502_set', 'LIC-329503':'lic329503_set', 'LIC-329504':'lic329504_set' };     // loops with a bespoke backend handler
    // Inline I-PD faceplates served by the generic `r323_ctrl_set` handler.  MUST mirror
    // main.py's R323_CTRL_MODES whitelist: a tag missing here falls through to
    // `controller_set`, whose getattr(state, 'FIC-323401') misses and SILENTLY no-ops, so the
    // faceplate looks alive but every mode/SP/OP write is discarded.  The backend re-checks the
    // whitelist (and the per-loop legal mode tuple), so an extra tag here is inert, not unsafe.
    const R323=new Set(['TIC-323007','PIC-329202','LIC-323501','LIC-323505','TIC-323012','PIC-329208','LIC-323507','FIC-324401','TIC-323013',
                        'PIC-323202','PIC-323203','LIC-323502','SIC-323901','SIC-323902','LIC-323503','FIC-323401','FIC-323402','FIC-328405','FIC-323418',
                        'LIC-328501','PIC-328202','TIC-328002','FIC-328404','FIC-329402','PIC-328203','FFIC-329401','FIC-329401','TIC-328008','TIC-328012',
                        'LIC-328503','LIC-328504','LIC-328505','FIC-328402','FIC-328406','PIC-322201','LIC-322502',
                        // G7: 324/335 evaporation-train dict controllers, previously mis-routed to
                        // controller_set and silently discarded. Must mirror R323_CTRL_MODES in main.py.
                        'TIC-324001','PIC-329203','PIC-324202','TIC-324002','PIC-329212','PIC-324203','LIC-324501','FFIC-335406','FIC-335405']);
    const msg={type:T[cur.tag] || (R323.has(cur.tag) ? 'r323_ctrl_set' : 'controller_set'), id:cur.tag, mode};
    if(mode==='MAN'  && !isNaN(o)) msg.op=o;
    if(mode==='AUTO' && !isNaN(p)) msg.sp=p;
    send(msg);
  };
  btn.onclick=apply;
  window.OTS_FACE = Object.assign(window.OTS_FACE||{}, { ctl: open });   // overlay *IC-3* left-click -> generic faceplate
  if(cl) cl.onclick=()=> m.classList.remove('show');
  m.addEventListener('click', e=>{ if(e.target===m) m.classList.remove('show'); });
})();

// ---------- Indicator faceplate (any indicator / valve opening with no dedicated loop) ----------
// Every bound value on a screen is now readable: overlays route an indicator, a bargraph, a
// valve-opening or a hand-switch button here whenever it has no loop faceplate of its own, so a
// left-click always opens something instead of silently doing nothing.  Read-only by design --
// these tags have no operator handle; the value, its unit and where it comes from are the content.
// Clicking the value expands it to 3 decimal places (fpxBind), which is the point of opening it.
(function(){
  const m=document.getElementById('indicatorModal'); if(!m) return;
  const ttl=document.getElementById('ind-title'), val=document.getElementById('ind-val'),
        unit=document.getElementById('ind-unit'), src=document.getElementById('ind-src'),
        cl=document.getElementById('ind-close');
  const gp=(o,p)=> p.split('.').reduce((a,k)=> (a==null?a:a[k]), o);
  let cur=null;
  const paint=()=>{
    if(!cur) return;
    let v = cur.bind ? gp(window.OTS_LAST||{}, cur.bind) : null;
    let u = cur.u || '';
    if(u==='BAR A' && typeof v==='number'){ v = v - 1.01325; u = 'BARG'; }   // Domain 1a: PT/PIC read gauge
    if(window.IndicatorFaceplate) window.IndicatorFaceplate.publish(cur.tag, v, u);
    const shown = (v==null||v==='') ? '—'
                : (typeof v==='number' ? fmt(v) : String(v));
    fpxSet(val, shown, typeof v==='number' ? v : null);
    if(unit) unit.value = u || '—';
    if(src)  src.value  = cur.bind || 'unbound';
  };
  const open=(o)=>{ cur=o||null; if(ttl&&cur) ttl.textContent=cur.tag||''; paint(); m.classList.add('show'); };
  window.OTS_FACE = Object.assign(window.OTS_FACE||{}, { indicator: open,
    indicatorSync: ()=>{ if(m.classList.contains('show')) paint(); } });
  if(cl) cl.onclick=()=> m.classList.remove('show');
  m.addEventListener('click', e=>{ if(e.target===m) m.classList.remove('show'); });
})();

// ---------- Screen navigation (ui_guidelines rule 10) ----------
function switchScreen(id){
  document.querySelectorAll('.screen').forEach(sc=> sc.classList.toggle('active', sc.id===id));
  document.querySelectorAll('#tabbar button').forEach(b=> b.classList.toggle('active', b.dataset.go===id));
}
window.otsSwitchScreen = switchScreen;   // overlay nav hotspots call this
// top tab bar: one button per screen; label = screen NUMBER only (drop descriptive name)
function buildTabs(){
  const bar=document.getElementById('tabbar'); if(!bar) return;
  const cur=document.querySelector('.screen.active');
  const num=sc=> (sc.dataset.label||sc.id).split(' ')[0];   // "322-2 HP SCRUBBER" -> "322-2"
  bar.innerHTML=[...document.querySelectorAll('.screen')]
    .sort((a,b)=> num(a).localeCompare(num(b), undefined, {numeric:true}))   // tabs sorted alphabetically/naturally
    .map(sc=> `<button data-go="${sc.id}"${sc===cur?' class="active"':''}>${num(sc)}</button>`).join('');
  bar.querySelectorAll('button').forEach(b=> b.onclick=()=> switchScreen(b.dataset.go));
}
buildTabs();
const scmenu=document.getElementById('screenmenu');
function openScreenMenu(x,y){
  const screens=[...document.querySelectorAll('.screen')];
  const cur=document.querySelector('.screen.active');
  scmenu.innerHTML='<div class="hd">GO TO SCREEN</div>'+screens.map(sc=>
    `<div class="item${sc===cur?' cur':''}" data-go="${sc.id}">${sc.dataset.label||sc.id}</div>`).join('');
  scmenu.querySelectorAll('.item').forEach(it=>{
    it.onclick=()=>{ switchScreen(it.dataset.go); scmenu.style.display='none'; };
  });
  scmenu.style.display='block'; scmenu.style.left=x+'px'; scmenu.style.top=y+'px';
}
document.addEventListener('click', ()=> scmenu.style.display='none');
// right-click empty stage area (not on an asset/indicator) -> screen dropdown
const NAV_ASSET_SEL='.pi[data-tag],[data-id],[data-pump],.block,.tank,.pump,.pump-btn,#tabbar,'+
  '.ratio-panel,.ext-override,.stream-click,.hic-panel,.avalve,.ejector,[data-tip],.mode-tag,.badge-l';
// bound on document (not _stage) so the body margins beside the centered stage are covered too
document.addEventListener('contextmenu', e=>{
  if(e.target.closest('.pi[data-tag]')) return;   // indicator: its own Trend menu (handler already ran)
  e.preventDefault();                              // suppress native browser menu everywhere else
  ctx.style.display='none';
  if(e.target.closest(NAV_ASSET_SEL)) return;      // other asset: no nav menu (rule 10 = empty space only)
  openScreenMenu(e.pageX, e.pageY);
});
// equipment-tag buttons jump to the screen hosting that equipment
document.querySelectorAll('[data-goto]').forEach(el=>{
  el.addEventListener('click', ()=> switchScreen(el.dataset.goto));
});

connect();

// ---------- SIC_321951 faceplate: REST /api/ctrl write + controllers WS read ----------
// Single source of truth = backend. Buttons POST commands; WS controllers block renders state.
// Gating mirrors backend transition rules: SP editable AUTO-only, MV editable MAN-only,
// N/C bias editable CAS-only, nothing editable OOS.
(function(){
  const TAG = 'SIC_321951';
  const URL = '/api/ctrl/' + TAG;
  const f = id => document.getElementById(id);
  const modal = f('f51');
  if(!modal) return;

  // mode -> which REST verb the SET button issues (null = SET disabled)
  const VERB = { MAN:'set_op', AUTO:'set_sp', CAS:'set_bias', OOS:null };
  // mode -> which input element backs the active verb
  const INPUT = { set_op:'f51-mv', set_sp:'f51-sp', set_bias:'f51-bias' };
  let curMode = 'MAN';

  const cdata = s => (s && s.controllers && s.controllers[TAG]) || null;

  function setMsg(txt, ok){
    const el = f('f51-msg');
    el.textContent = txt || '';
    el.style.color = ok ? '#7fffae' : '#ff7f7f';
  }

  // toggle disabled/active state of inputs + mode buttons for a mode
  function applyGates(mode){
    curMode = mode;
    f('f51-sp').disabled   = (mode !== 'AUTO');   // SP: AUTO only
    f('f51-mv').disabled   = (mode !== 'MAN');    // MV: MAN only
    f('f51-bias').disabled = (mode !== 'CAS');    // CAS bias (SP offset): CAS only
    f('f51-set').disabled  = (VERB[mode] == null);
    ['MAN','AUTO','CAS','OOS'].forEach(m =>
      f('f51-' + m.toLowerCase()).classList.toggle('active', m === mode));
    const mt = f('f51-mode');
    mt.textContent = mode;
    mt.className = 'f51mode ' + mode.toLowerCase();
  }

  // write field values from a controller packet, respecting focus (don't clobber typing)
  function fillFields(d){
    const ae = document.activeElement;
    fpxSet(f('f51-pv'), fmt(d.pv), d.pv);                            // PV: read-only/live; click -> 3 dp
    // N/C readout.  The row below it is the CAS BIAS -- an operator offset on the cascade
    // setpoint, correctly 0.0 at design -- which read as "the N/C" while it was labelled that
    // way.  These two rows are the actual loop N/C the ratio master is holding (design 2.023),
    // taken from the same `ratio` block the home screen shows.
    {
      const r = (lastState && lastState.ratio) || {};
      fpxSet(f('f51-ncsp'), r.SP!=null ? Number(r.SP).toFixed(3) : '—', r.SP);
      fpxSet(f('f51-ncpv'), r.PV!=null ? Number(r.PV).toFixed(3) : '—', r.PV);
    }
    if(ae !== f('f51-mv'))   f('f51-mv').value   = fmt(d.mv);
    if(ae !== f('f51-sp'))   f('f51-sp').value   = fmt(d.sp);
    if(ae !== f('f51-bias')) f('f51-bias').value = fmt(d.bias);
    const st = d.status || {};
    const flags = [];
    if(st.pv_bad)      flags.push('PV BAD');
    if(st.mv_hi_clamp) flags.push('MV @ HI');
    if(st.mv_lo_clamp) flags.push('MV @ LO');
    f('f51-status').textContent = flags.join('   ');
  }

  // authoritative GET (used after mode change to capture bumpless SP immediately)
  async function syncFromServer(){
    try{
      const r = await fetch(URL);
      if(!r.ok) return;
      const d = await r.json();
      applyGates(d.mode);
      fillFields(d);
    }catch(e){ /* WS refresh will catch up */ }
  }

  async function post(body){
    try{
      const r = await fetch(URL, {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify(body)
      });
      const j = await r.json().catch(() => ({}));
      if(!r.ok){
        const detail = (j && j.detail) || r.statusText || ('HTTP ' + r.status);
        setMsg(r.status + ': ' + detail, false);   // 404 tag / 422 mode / 409 illegal
        return null;
      }
      setMsg(j.reason === 'clamped' ? 'set (clamped to limit)' : 'OK', true);
      return j;
    }catch(err){
      setMsg('network error: ' + err.message, false);
      return null;
    }
  }

  function open(){
    const d = cdata(lastState);
    if(d){ applyGates(d.mode); fillFields(d); setMsg('', true); }
    else { setMsg('waiting for controller data...', false); }
    modal.classList.add('show');
    syncFromServer();
  }
  window.openF51 = open;

  // live render from WS controllers block (called every packet while open)
  window.refreshF51 = function(s){
    if(!modal.classList.contains('show')) return;
    const d = cdata(s);
    if(!d) return;
    if(d.mode !== curMode) applyGates(d.mode);   // backend-driven mode change (e.g. bad-PV -> MAN)
    fillFields(d);
  };

  // mode buttons -> POST set_mode, then pull authoritative state
  ['MAN','AUTO','CAS','OOS'].forEach(m => {
    f('f51-' + m.toLowerCase()).onclick = async () => {
      const j = await post({ set_mode: m });
      if(j){ applyGates(j.mode); syncFromServer(); }
    };
  });

  // SET -> POST the active mode's value
  f('f51-set').onclick = async () => {
    const verb = VERB[curMode];
    if(!verb) return;
    const v = parseFloat(f(INPUT[verb]).value);
    if(isNaN(v)){ setMsg('enter a numeric value', false); return; }
    await post({ [verb]: v });
  };

  // Enter-to-SET handled globally for all faceplates (see FACEPLATE_MODALS handler).

  f('f51-close').onclick = () => modal.classList.remove('show');
})();

// ---------- SIC_321950 faceplate: REST /api/ctrl write + controllers WS read ----------
// Single source of truth = backend. Buttons POST commands; WS controllers block renders state.
// Gating mirrors backend transition rules: SP editable AUTO-only, MV editable MAN-only,
// N/C bias editable CAS-only, nothing editable OOS.
(function(){
  const TAG = 'SIC_321950';
  const URL = '/api/ctrl/' + TAG;
  const f = id => document.getElementById(id);
  const modal = f('f50');
  if(!modal) return;

  const VERB = { MAN:'set_op', AUTO:'set_sp', CAS:'set_bias', OOS:null };
  const INPUT = { set_op:'f50-mv', set_sp:'f50-sp', set_bias:'f50-bias' };
  let curMode = 'MAN';

  const cdata = s => (s && s.controllers && s.controllers[TAG]) || null;

  function setMsg(txt, ok){
    const el = f('f50-msg');
    el.textContent = txt || '';
    el.style.color = ok ? '#7fffae' : '#ff7f7f';
  }

  function applyGates(mode){
    curMode = mode;
    f('f50-sp').disabled   = (mode !== 'AUTO');   // SP: AUTO only
    f('f50-mv').disabled   = (mode !== 'MAN');    // MV: MAN only
    f('f50-bias').disabled = (mode !== 'CAS');    // CAS bias (SP offset): CAS only
    f('f50-set').disabled  = (VERB[mode] == null);
    ['MAN','AUTO','CAS','OOS'].forEach(m =>
      f('f50-' + m.toLowerCase()).classList.toggle('active', m === mode));
    const mt = f('f50-mode');
    mt.textContent = mode;
    mt.className = 'f50mode ' + mode.toLowerCase();
  }

  function fillFields(d){
    const ae = document.activeElement;
    fpxSet(f('f50-pv'), fmt(d.pv), d.pv);                            // PV: read-only/live; click -> 3 dp
    // N/C readout.  The row below it is the CAS BIAS -- an operator offset on the cascade
    // setpoint, correctly 0.0 at design -- which read as "the N/C" while it was labelled that
    // way.  These two rows are the actual loop N/C the ratio master is holding (design 2.023),
    // taken from the same `ratio` block the home screen shows.
    {
      const r = (lastState && lastState.ratio) || {};
      fpxSet(f('f50-ncsp'), r.SP!=null ? Number(r.SP).toFixed(3) : '—', r.SP);
      fpxSet(f('f50-ncpv'), r.PV!=null ? Number(r.PV).toFixed(3) : '—', r.PV);
    }
    if(ae !== f('f50-mv'))   f('f50-mv').value   = fmt(d.mv);
    if(ae !== f('f50-sp'))   f('f50-sp').value   = fmt(d.sp);
    if(ae !== f('f50-bias')) f('f50-bias').value = fmt(d.bias);
    const st = d.status || {};
    const flags = [];
    if(st.pv_bad)      flags.push('PV BAD');
    if(st.mv_hi_clamp) flags.push('MV @ HI');
    if(st.mv_lo_clamp) flags.push('MV @ LO');
    f('f50-status').textContent = flags.join('   ');
  }

  async function syncFromServer(){
    try{
      const r = await fetch(URL);
      if(!r.ok) return;
      const d = await r.json();
      applyGates(d.mode);
      fillFields(d);
    }catch(e){ /* WS refresh will catch up */ }
  }

  async function post(body){
    try{
      const r = await fetch(URL, {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify(body)
      });
      const j = await r.json().catch(() => ({}));
      if(!r.ok){
        const detail = (j && j.detail) || r.statusText || ('HTTP ' + r.status);
        setMsg(r.status + ': ' + detail, false);   // 404 tag / 422 mode / 409 illegal
        return null;
      }
      setMsg(j.reason === 'clamped' ? 'set (clamped to limit)' : 'OK', true);
      return j;
    }catch(err){
      setMsg('network error: ' + err.message, false);
      return null;
    }
  }

  function open(){
    const d = cdata(lastState);
    if(d){ applyGates(d.mode); fillFields(d); setMsg('', true); }
    else { setMsg('waiting for controller data...', false); }
    modal.classList.add('show');
    syncFromServer();
  }
  window.openF50 = open;

  // live render from WS controllers block (called every packet while open)
  window.refreshF50 = function(s){
    if(!modal.classList.contains('show')) return;
    const d = cdata(s);
    if(!d) return;
    if(d.mode !== curMode) applyGates(d.mode);   // backend-driven mode change (e.g. bad-PV -> MAN)
    fillFields(d);
  };

  // mode buttons -> POST set_mode, then pull authoritative state
  ['MAN','AUTO','CAS','OOS'].forEach(m => {
    f('f50-' + m.toLowerCase()).onclick = async () => {
      const j = await post({ set_mode: m });
      if(j){ applyGates(j.mode); syncFromServer(); }
    };
  });

  // SET -> POST the active mode's value
  f('f50-set').onclick = async () => {
    const verb = VERB[curMode];
    if(!verb) return;
    const v = parseFloat(f(INPUT[verb]).value);
    if(isNaN(v)){ setMsg('enter a numeric value', false); return; }
    await post({ [verb]: v });
  };

  // Enter-to-SET handled globally for all faceplates (see FACEPLATE_MODALS handler).

  f('f50-close').onclick = () => modal.classList.remove('show');
})();

// ---------- MASTER SP faceplate: 4-bar steam header ON/OFF cascade over PIC-329207A/B/C ----------
// Source of truth = backend STEAM_SYSTEM telemetry; commands go over WS via send().
//   ON  : one MASTER SP fans out & locks the trio  (A=SP+0.1 vent / B=SP turbine / C=SP-0.1 admit).
//   OFF : the three sub-controllers are independent (operator sets each SP / mode / MAN opening).
(function(){
  const f = id => document.getElementById(id);
  const modal = f('mspModal');
  if(!modal) return;
  const LEGS = ['a','b','c'];
  const CMD  = { a:'pic329207a_set', b:'pic329207b_set', c:'pic329207c_set' };
  const KEY  = { a:'PIC_329207A', b:'PIC_329207B', c:'PIC_329207C' };
  const modeOf = {};                       // last-seen per-leg mode (drives OP-input gating)
  let masterOn = false;

  const ss  = s => (s && s.STEAM_SYSTEM) || null;
  const num = v => (typeof v === 'number' && isFinite(v)) ? v : NaN;
  const bg  = v => { const n = num(v); return isFinite(n) ? n - 1.01325 : v; };   // absolute bara -> gauge barg for display

  function setMsg(txt, ok){
    const el = f('msp-msg');
    el.textContent = txt || '';
    el.style.color = ok ? '#7fffae' : '#ff7f7f';
  }

  // enable/disable inputs & buttons per ON/OFF and per-leg mode
  function applyGates(){
    const chip = f('msp-mode');
    chip.textContent = masterOn ? 'ON' : 'OFF';
    chip.className   = 'mspmode' + (masterOn ? ' on' : '');
    f('msp-on').classList.toggle('active', masterOn);
    f('msp-off').classList.toggle('active', !masterOn);
    f('msp-sp').disabled = !masterOn;                       // master SP editable only when ON
    LEGS.forEach(L => {
      const man = (modeOf[L] === 'MAN');
      f('msp-'+L+'-sp').disabled = masterOn;                // sub SP editable only when OFF
      f('msp-'+L+'-op').disabled = masterOn || !man;        // OP editable only OFF & MAN
      f('msp-'+L+'-auto').disabled = masterOn;
      f('msp-'+L+'-man').disabled  = masterOn;
      f('msp-'+L+'-auto').classList.toggle('active', modeOf[L] === 'AUTO');
      f('msp-'+L+'-man').classList.toggle('active', man);
    });
  }

  function fill(s){
    const S = ss(s); if(!S) return;
    const m = S.MASTER_SP_329207 || {};
    const ae = document.activeElement;
    masterOn = !!m.on;
    if(ae !== f('msp-pv')) f('msp-pv').value = fmt(bg(m.pv));
    if(ae !== f('msp-sp')) f('msp-sp').value = fmt(bg(m.sp));
    LEGS.forEach(L => {
      const d = S[KEY[L]] || {};
      modeOf[L] = d.mode || modeOf[L] || 'AUTO';
      if(ae !== f('msp-'+L+'-sp')) f('msp-'+L+'-sp').value = fmt(bg(d.sp));
      if(ae !== f('msp-'+L+'-op')) f('msp-'+L+'-op').value = fmt(d.op);
    });
    applyGates();
    f('msp-note').textContent = masterOn
      ? 'MASTER ON: A=SP+0.1 (vent) / B=SP (turbine) / C=SP-0.1 (BL admit) — locked to AUTO.'
      : 'MASTER OFF: PIC-329207A/B/C independent — set each SP / mode (OP in MAN).';
  }

  function open(){
    if(lastState) fill(lastState); else setMsg('waiting for telemetry...', false);
    modal.classList.add('show');
  }
  window.OTS_FACE = window.OTS_FACE || {};
  window.OTS_FACE.msp = open;

  // live render from WS while open
  window.refreshMSP = function(s){
    if(!modal.classList.contains('show')) return;
    fill(s);
  };

  // ON / OFF cascade toggle -> immediate command
  f('msp-on').onclick  = () => { send({type:'master207_set', on:true});  setMsg('MASTER ON', true); };
  f('msp-off').onclick = () => { send({type:'master207_set', on:false}); setMsg('MASTER OFF', true); };

  // per-leg mode buttons (honored backend-side only when MASTER OFF)
  LEGS.forEach(L => {
    ['auto','man'].forEach(md => {
      f('msp-'+L+'-'+md).onclick = () => {
        if(masterOn) return;
        modeOf[L] = md.toUpperCase();
        send({type:CMD[L], mode:modeOf[L]});
        applyGates();
      };
    });
  });

  // SET -> ON: master SP ; OFF: each leg's SP (+ OP when that leg is MAN)
  f('msp-set').onclick = () => {
    if(masterOn){
      const v = parseFloat(f('msp-sp').value);
      if(isNaN(v)){ setMsg('enter a numeric MASTER SP', false); return; }
      send({type:'master207_set', sp:v + 1.01325});   // barg entry -> bara for engine
      setMsg('MASTER SP set', true);
      return;
    }
    let n = 0;
    LEGS.forEach(L => {
      const sp = parseFloat(f('msp-'+L+'-sp').value);
      const msg = {type:CMD[L]};
      if(!isNaN(sp)){ msg.sp = sp + 1.01325; n++; }   // barg entry -> bara for engine
      if(modeOf[L] === 'MAN'){
        const op = parseFloat(f('msp-'+L+'-op').value);
        if(!isNaN(op)){ msg.op = op; n++; }
      }
      if(msg.sp !== undefined || msg.op !== undefined) send(msg);
    });
    setMsg(n ? 'sub-controllers set' : 'nothing to set', n > 0);
  };

  f('msp-close').onclick = () => modal.classList.remove('show');
})();
