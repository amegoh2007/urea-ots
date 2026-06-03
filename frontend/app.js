'use strict';

// ---------- WebSocket ----------
const WS_URL = `ws://${location.hostname || 'localhost'}:8000/ws`;
let ws;
let lastState = {};
let history = {};
const HIST_MAX = 3600;

function connect(){
  ws = new WebSocket(WS_URL);
  ws.onmessage = e => {
    const s = JSON.parse(e.data);
    lastState = s;
    pushHistory(s);
    render(s);
    render322(s);
    refreshFaceplate(s);
    if(window.OV_apply) window.OV_apply(s);
  };
  ws.onclose = () => setTimeout(connect, 1000);
  ws.onerror = () => ws.close();
}
function send(msg){ if(ws && ws.readyState===1) ws.send(JSON.stringify(msg)); }
window.otsSend = send;
window.openTrend = (tag)=>openTrend(tag);
window.openFaceplate = (id)=>openFaceplate(id);

function pushHistory(s){
  const tnow = s.t || (Date.now()/1000);
  const tags = {
    FI_321401:s.FI_321401, TI_top1:s.TI_top1, TI_top2:s.TI_top2,
    PI_top1:s.PI_top1, PI_top2:s.PI_top2, PI_header:s.PI_header, totalizer:s.totalizer,
    PI_321201:s.PI_321201, PI_321202:s.PI_321202,
    PY_321201:s.PY_321201, PY_321202:s.PY_321202,
    PDY_321203:s.PDY_321203, PDY_321204:s.PDY_321204,
    PA_current:s.pumpA?.current, PA_speed:s.pumpA?.speed,
    PB_current:s.pumpB?.current, PB_speed:s.pumpB?.speed,
    PI_disch:s.PI_disch, TI_321020:s.TI_321020
  };
  const _ej=s.EJ_322F001;
  if(_ej){ Object.assign(tags,{
    EJ_motive:_ej.motive_kgh, EJ_suction:_ej.suction_kgh, EJ_mu:_ej.mu,
    TT_322012:_ej.TT_322012, EJ_Pdisch:_ej.PI_disch, EJ_total:_ej.total_th,
    EJ_MW:_ej.MW, HIC_322602:_ej.HIC_322602 }); }
  for(const k in tags){
    if(tags[k]===undefined||tags[k]===null) continue;
    if(!history[k]) history[k]=[];
    history[k].push({t:tnow,v:Number(tags[k])});
    if(history[k].length>HIST_MAX) history[k].shift();
  }
}

// ---------- Render ----------
const MODE_LETTER = { MAN:'M', AUTO:'A', CAS:'C' };

function fmt(v){
  if(v==null||isNaN(v)) return '--';
  if(Math.abs(v)>=1000) return Number(v).toFixed(2);
  return Number(v).toFixed(1);
}
function setPI(tag,val,unit,alarm){
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
  setPI('PY_321201', s.PY_321201, 'BAR A', false);
  setPI('PY_321202', s.PY_321202, 'BAR A', false);
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
document.getElementById('pa-btn').onclick  = ()=> send({type:'pump_toggle',id:'A'});
document.getElementById('pb-btn').onclick  = ()=> send({type:'pump_toggle',id:'B'});
document.getElementById('pa-icon').onclick = ()=> send({type:'pump_toggle',id:'A'});
document.getElementById('pb-icon').onclick = ()=> send({type:'pump_toggle',id:'B'});
document.getElementById('xv-321901').onclick = ()=> send({type:'xv_toggle',id:'321901'});
document.getElementById('xv-322901').onclick = ()=> send({type:'xv_toggle',id:'322901'});
document.getElementById('extOverride').onclick = ()=> send({type:'ext_override',value:!lastState.ext_override});
document.getElementById('ratioSP').addEventListener('change', e=>{
  const v=parseFloat(e.target.value); if(!isNaN(v)) send({type:'ratio_set',sp:v});
});

// ---------- Faceplate (SIC) ----------
const FP_MAP = {
  PA_speed:'SIC_321950', PA_current:'SIC_321950',
  PB_speed:'SIC_321951', PB_current:'SIC_321951'
};
let fpTag=null;
const $ = id => document.getElementById(id);

// MAN -> PV active | AUTO -> SP active | CAS -> N/C active (PV & MV inactive)
function fpEnable(mode){
  const m = {
    MAN: {pv:true, sp:false, nc:false},
    AUTO:{pv:false,sp:true, nc:false},
    CAS: {pv:false,sp:false,nc:true }
  }[mode] || {};
  $('fp-pv').disabled = !m.pv;
  $('fp-sp').disabled = !m.sp;
  $('fp-mv').disabled = true;     // MV = output, always read-only
  $('fp-nc').disabled = !m.nc;
  fpRelabelSP(mode);
}
// AUTO setpoint is entered/displayed in RPM; MAN/CAS keep % opening
function fpRelabelSP(mode){
  const auto = (mode==='AUTO');
  $('fp-sp-label').textContent = auto ? 'SP (RPM)' : 'SP (%)';
  const d = (fpTag && lastState[fpTag]) || {};
  if(document.activeElement!==$('fp-sp'))
    $('fp-sp').value = auto ? fmt(d.sp_rpm) : fmt(d.sp);
}
function openFaceplate(id){
  fpTag=id;
  const s = lastState[id] || {};
  $('fp-title').textContent = id.replace('_','-')+' FACEPLATE';
  $('fp-pv').value = fmt(s.pv);
  $('fp-sp').value = fmt(s.sp);
  $('fp-mv').value = fmt(s.mv);
  $('fp-nc').value = fmt(s.nc);
  ['MAN','AUTO','CAS'].forEach(m=>{
    $('fp-'+m.toLowerCase()).classList.toggle('active', (s.mode||'MAN')===m);
  });
  fpEnable(s.mode||'MAN');
  $('faceplate').classList.add('show');
}
function fpActiveMode(){
  return ['MAN','AUTO','CAS'].find(m=>$('fp-'+m.toLowerCase()).classList.contains('active')) || 'MAN';
}
function refreshFaceplate(s){
  if(!$('faceplate').classList.contains('show') || !fpTag) return;
  const d=s[fpTag]; if(!d) return;
  if(document.activeElement!==$('fp-mv')) $('fp-mv').value = fmt(d.mv);
  if($('fp-pv').disabled && document.activeElement!==$('fp-pv')) $('fp-pv').value = fmt(d.pv);
  if($('fp-sp').disabled && document.activeElement!==$('fp-sp'))
    $('fp-sp').value = (fpActiveMode()==='AUTO') ? fmt(d.sp_rpm) : fmt(d.sp);
}
document.querySelectorAll('.mode-group button').forEach(b=>{
  b.onclick = ()=>{
    document.querySelectorAll('.mode-group button').forEach(x=>x.classList.remove('active'));
    b.classList.add('active');
    fpEnable(b.dataset.mode);
  };
});
$('fp-apply').onclick = ()=>{
  if(!fpTag) return;
  const mode = fpActiveMode();
  const msg = {type:'controller_set', id:fpTag, mode};
  if(mode==='MAN'){ const v=parseFloat($('fp-pv').value); if(!isNaN(v)) msg.op=v; }   // PV entry = direct opening
  if(mode==='AUTO'){ const v=parseFloat($('fp-sp').value); if(!isNaN(v)) msg.sp_rpm=v; }   // AUTO SP in RPM
  if(mode==='CAS'){ const v=parseFloat($('fp-nc').value); if(!isNaN(v)) msg.nc=v; }
  send(msg);
};
$('fp-close').onclick = ()=>{ $('faceplate').classList.remove('show'); fpTag=null; };

// ---------- Indicators: left=faceplate, right=trend menu ----------
document.querySelectorAll('.pi[data-tag]').forEach(el=>{
  const tag = el.dataset.tag;
  el.addEventListener('click', ()=>{ if(FP_MAP[tag]) openFaceplate(FP_MAP[tag]); });
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

let trendChart=null, trendSpan=60, trendInterval=null;
const TREND_SPANS=[10,30,60,120,300,600,1800,3600];
function openTrend(tag){
  document.getElementById('trend-title').textContent = `Trend — ${tag}`;
  document.getElementById('trendModal').classList.add('show');
  updateTrend(tag);
  document.getElementById('t-inc').onclick = ()=>{ let i=TREND_SPANS.indexOf(trendSpan); if(i<TREND_SPANS.length-1){trendSpan=TREND_SPANS[i+1]; updateTrend(tag);} };
  document.getElementById('t-dec').onclick = ()=>{ let i=TREND_SPANS.indexOf(trendSpan); if(i>0){trendSpan=TREND_SPANS[i-1]; updateTrend(tag);} };
  document.getElementById('t-close').onclick = ()=> { document.getElementById('trendModal').classList.remove('show'); if(trendInterval) clearInterval(trendInterval); };
  if(trendInterval) clearInterval(trendInterval);
  trendInterval = setInterval(()=> updateTrend(tag), 500);
}
function updateTrend(tag){
  document.getElementById('t-span').textContent = trendSpan+' s';
  const arr = history[tag]||[];
  const t1 = (lastState.t || Date.now()/1000);
  const pts = arr.filter(p=>p.t>=t1-trendSpan).map(p=>({x:Number((p.t-t1).toFixed(1)),y:p.v}));
  const ctxc = document.getElementById('trendChart').getContext('2d');
  if(trendChart) trendChart.destroy();
  trendChart = new Chart(ctxc,{
    type:'line',
    data:{datasets:[{label:tag,data:pts,parsing:false,borderColor:'#22ff22',backgroundColor:'rgba(34,255,34,0.1)',pointRadius:0,tension:0.2}]},
    options:{ animation:false,responsive:false,
      scales:{ x:{type:'linear',ticks:{color:'#fff'},grid:{color:'#333'},title:{display:true,text:'t (s)',color:'#fff'}},
               y:{ticks:{color:'#fff'},grid:{color:'#333'}} },
      plugins:{legend:{labels:{color:'#fff'}}} }
  });
}

// ---------- Stream popup (generic renderer over packet STREAMS) ----------
const COMP_LBL = {CO2:'CO₂',CH4:'CH₄',H2:'H₂',H2O:'H₂O',N2:'N₂',
                  NH3:'NH₃',O2:'O₂',Urea:'Urea',Biuret:'Biuret'};
const fStrm = (v,d)=> (v==null ? '—' : (+v).toFixed(d));
function renderStream(s){
  const rows = [
    ['Route', s.src+' → '+s.dst], ['Phase', s.phase],
    ['Temperature', fStrm(s.T_C,1)+' °C'], ['Pressure', fStrm(s.P_bara,1)+' bar a'],
    ['Mass flow', fStrm(s.mass_th,2)+' t/h ('+fStrm(s.mass_kgh,0)+' kg/h)'],
    ['Molar flow', fStrm(s.mol_kmolh,1)+' kmol/h'], ['Avg MW', fStrm(s.MW,2)+' kg/kmol'],
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
function openStreamPopup(id){
  const s = (lastState.STREAMS||{})[id]; if(!s) return;
  document.getElementById('stream-title').textContent = s.name;
  document.getElementById('stream-table').innerHTML =
    renderStream(s).map(r=>`<tr><td>${r[0]}</td><td>${r[1]}</td></tr>`).join('');
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
  HPCC_COND:'BFW/COND → 322E002'
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
  setPI('EJ_Pdisch',  e.PI_disch,   'BAR A', false);
  setPI('EJ_total',   e.total_th,   'T/H',   false);
  setPI('EJ_MW',      e.MW,         'KG/KMOL', false);
  setPI('TI_322002',  178.8,        'C',     false);   // design suction temp (322E003 boundary)
  setPI('PI_329201',  e.PI_disch,   'BAR A', false);   // HP loop pressure
  setPI('HIC_322602', e.HIC_322602, '%',     false);
  const hv=document.getElementById('hv-op'); if(hv) hv.textContent = fmt(e.HIC_322602)+' %';
  const inp=document.getElementById('hic-inp');
  if(inp && document.activeElement!==inp) inp.value = fmt(e.HIC_322602);
  const xb=document.getElementById('xv-322901b');
  if(xb) xb.classList.toggle('closed', !s.XV_322901);   // bowtie: green=open, red=closed (CSS)
}

// ---------- HIC-322602 hand controller -> HV-322602 opening (faceplate popup) ----------
(function(){
  const inp=document.getElementById('hic-inp'), btn=document.getElementById('hic-set-btn'),
        box=document.getElementById('hic-box'), m=document.getElementById('hicModal'),
        cl=document.getElementById('hic-close');
  if(!inp||!btn) return;
  const apply=()=>{ const v=parseFloat(inp.value); if(!isNaN(v)) send({type:'hic_set',value:v}); };
  btn.onclick=apply;
  inp.addEventListener('change',apply);
  // open faceplate from HIC-322602 tag or its % box (rule 6 controller)
  const open=()=>{ if(m) m.classList.add('show'); };
  window.OTS_FACE = Object.assign(window.OTS_FACE||{}, { hic: open });   // overlay h602 left-click -> faceplate
  if(box) box.addEventListener('click',open);
  const pibox=document.querySelector('.pi[data-tag="HIC_322602"]'); if(pibox) pibox.addEventListener('click',open);
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
  mMan.onclick=()=>setMode('MAN'); mAuto.onclick=()=>setMode('AUTO');
  const open=()=>{ const c=(window.OTS_LAST||{}).CO2_FEED||{};
    if(pv) pv.value = c.PIC_322203!=null ? c.PIC_322203 : '';
    if(sp) sp.value = c.PIC_sp!=null ? c.PIC_sp : (c.PIC_322203!=null ? c.PIC_322203 : '');
    if(op) op.value = c.PIC_op!=null ? c.PIC_op : '';
    setMode(c.PIC_mode||'AUTO'); m.classList.add('show'); };
  const apply=()=>{ const o=parseFloat(op.value), p=parseFloat(sp.value);
    const msg={type:'pic_set', mode};
    if(mode==='MAN'  && !isNaN(o)) msg.op=o;   // MAN: send valve opening only
    if(mode==='AUTO' && !isNaN(p)) msg.sp=p;   // AUTO: send setpoint only
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
  let cur=null, mode='AUTO';
  const applyMode=v=>{                                                 // MAN=set opening, AUTO=set SP, CAS=linked param
    mode=v;
    bMan.classList.toggle('active', v==='MAN');
    bAuto.classList.toggle('active', v==='AUTO');
    bCas.classList.toggle('active', v==='CAS');
    op.readOnly = (v!=='MAN');                                         // MAN: operator edits valve opening
    sp.readOnly = (v!=='AUTO');                                        // AUTO: operator edits setpoint
    note.textContent =
      v==='MAN'  ? 'MAN — operator sets valve opening directly.' :
      v==='AUTO' ? 'AUTO — controller drives opening to hold SP.' :
                   'CAS — opening driven by a linked (cascade) parameter.';
  };
  const open=(o)=>{
    cur=o; ttl.textContent=o.tag;
    const v = o.bind ? gp(window.OTS_LAST||{}, o.bind) : null;
    pv.value = (v==null||v==='') ? '—' : (v + (o.u?(' '+o.u):''));
    const st=load()[o.tag]||{};
    sp.value = st.sp!=null ? st.sp : '';
    op.value = st.op!=null ? st.op : '';
    applyMode(st.mode||'AUTO');
    m.classList.add('show');
  };
  bMan.onclick =()=>applyMode('MAN');
  bAuto.onclick=()=>applyMode('AUTO');
  bCas.onclick =()=>applyMode('CAS');
  const apply=()=>{
    if(!cur) return;
    const st=load(), o=parseFloat(op.value), p=parseFloat(sp.value);
    st[cur.tag]={ mode, op:isNaN(o)?null:o, sp:isNaN(p)?null:p };
    save(st);
    const T={ 'LIC-322501':'lic_set', 'HIC-322605':'hic605_set' };     // modelled loops -> real backend handler; unmodelled tags stay controller_set (no-op until modelled)
    const msg={type:T[cur.tag]||'controller_set', id:cur.tag, mode};
    if(mode==='MAN'  && !isNaN(o)) msg.op=o;
    if(mode==='AUTO' && !isNaN(p)) msg.sp=p;
    send(msg);
  };
  btn.onclick=apply;
  window.OTS_FACE = Object.assign(window.OTS_FACE||{}, { ctl: open });   // overlay *IC-3* left-click -> generic faceplate
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
