'use strict';
// Rev2 image-backed UI — live overlay layer driven by the tagged DCS screenshots.
// Opaque divs sit on top of the cleaned screenshot and cover ("crop") the static
// symbols/values baked into the image, replacing them with LIVE sim data:
//   type 'ind'  -> black indicator box, live value + unit (or empty slot if unbound)
//   type 'pump' -> dynamic ON/OFF icon  (green = ON, grey = OFF)
//   type 'xv'   -> dynamic OPEN/CLOSED bowtie (green = OPEN, red = CLOSED)
//   type 'bar'  -> vertical level bargraph, fill height = bound level 0-100 %
//   type 'nav'  -> transparent screen-jump hotspot
// Click "Edit Layout" to drag any element — positions persist to localStorage.
//
// All ten screens are now seeded from the PowerPoint equipment drawings rather than from
// screenshots: 321-1 / 322-1 / 322-2 off the 2026-08 deck, the other seven off the 2026-09
// deck. Each seed coordinate is a shape centre mapped 12192000x6858000 EMU -> 1366x720
// stage, and the background PNG is that same slide with exactly those shapes deleted, so an
// overlay always lands in the hole its own symbol left. The mapping is anisotropic
// (1366/12192000 across, 720/6858000 down); rotated icons are re-squared by sizeIcon's
// scaleX(SLIDE_RX) rotate(deg) so a 90-deg pump reads as a pump, not an ellipse.
//
// A tag drawn on a screen whose unit the backend does not model yet is a WHITE-FRAME empty
// slot (tag text only) — chiefly the Unit-335 finishing side on 324-1b. It picks up a live
// value the moment some screen binds the same tag (see BIND_MAP / eff()).
(function () {
  const STAGE_W = 1366, STAGE_H = 720;
  const LSK = 'ots_ov_pos_v6';   // v6: the remaining seven screens were re-seeded from the 2026-09
                                 // slide deck, so every coord on them moved -- and their element keys
                                 // changed too (k is now derived from the tag).  Stale drag positions
                                 // are dropped for those seven and carried across for 321-1 / 322-1 /
                                 // 322-2, which this migration did not touch.  Same rule as v5.
  const REMAPPED = ['screen-323-1', 'screen-323-2', 'screen-324-1', 'screen-324-1b',
                    'screen-328-1', 'screen-328-2', 'screen-329-1'];
  function carryOver(newKey, oldKey) {
    let cur = null;
    try { cur = JSON.parse(localStorage.getItem(newKey) || 'null'); } catch (e) { cur = null; }
    if (cur) return cur;
    let prev = {};
    try { prev = JSON.parse(localStorage.getItem(oldKey) || '{}') || {}; } catch (e) { prev = {}; }
    const kept = {};
    for (const k in prev) if (!REMAPPED.some(sid => k.indexOf(sid + '|') === 0 || k === sid)) kept[k] = prev[k];
    localStorage.setItem(newKey, JSON.stringify(kept));
    return kept;
  }

  // bind = dot-path into the ws packet ('FI_321401', 'pumpA.current', 'SIC_321950.pv').
  // dec  = decimals. fp = controller id for left-click faceplate. No bind => empty slot.
  const OV = {
    // ---------------------------------------------------------------------------------
    //  Seed coordinates below are the shape centres of the 321-1 slide
    //  (UI Pages/321-1.pptx), mapped 12192000x6858000 EMU -> 1366x720 stage.  The
    //  background PNG is that same slide with these shapes deleted, so an overlay always
    //  lands exactly where its symbol was drawn.
    // ---------------------------------------------------------------------------------
    'screen-321-1': [
      // ---- indicators (all bound: active unit) ----
      { k: 'tt1',  t: 'ind', x: 242,  y: 225, tag: 'TT-321001', bind: 'TI_top1',     u: 'C',     dec: 1 },
      { k: 'tt2',  t: 'ind', x: 465,  y: 217, tag: 'TT-321002', bind: 'TI_top2',     u: 'C',     dec: 1 },
      { k: 'py2',  t: 'ind', x: 623,  y: 133, tag: 'PY-321202', bind: 'PY_321202',   u: 'BAR G', dec: 1 },
      { k: 'py1',  t: 'ind', x: 628,  y: 202, tag: 'PY-321201', bind: 'PY_321201',   u: 'BAR G', dec: 1 },
      { k: 'pd3',  t: 'ind', x: 694,  y: 246, tag: 'PDY-321203',bind: 'PDY_321203',  u: 'BAR G', dec: 1 },
      { k: 'pd4',  t: 'ind', x: 973,  y: 247, tag: 'PDY-321204',bind: 'PDY_321204',  u: 'BAR G', dec: 1 },
      { k: 'tt20', t: 'ind', x: 1011, y: 310, tag: 'TT-321020', bind: 'TI_321020',   u: 'C',     dec: 1 },
      { k: 'ft',   t: 'ind', x: 211,  y: 353, tag: 'FT-321401', bind: 'FI_321401',   u: 'T/H',   dec: 2 },
      { k: 'pt1',  t: 'ind', x: 582,  y: 373, tag: 'PT-321201', bind: 'PI_321201',   u: 'BAR G', dec: 1 },
      { k: 'pt2',  t: 'ind', x: 794,  y: 396, tag: 'PT-321202', bind: 'PI_321202',   u: 'BAR G', dec: 1 },
      { k: 'fqi',  t: 'ind', x: 210,  y: 424, tag: 'FQT-321401', bind: 'totalizer', u: 'T', dec: 1 },   // s.totalizer_t, NH3 delivered this run
      // Feed-ratio panel rows A/B: the per-pump NH3/CO2 molar ratio.  Left-click opens that
      // pump's speed faceplate, which is where the N/C bias is editable (CAS only).
      { k: 'ffa',  t: 'ind', x: 159,  y: 547, tag: 'FFIC-321404A', bind: 'ratio.PV', u: 'N/C', dec: 3, fp: 'SIC_321950' },
      { k: 'ffb',  t: 'ind', x: 158,  y: 593, tag: 'FFIC-321404B', bind: 'ratio.PV', u: 'N/C', dec: 3, fp: 'SIC_321951' },
      { k: 'i61',  t: 'ind', x: 619,  y: 592, tag: 'IT-321961', bind: 'pumpA.current',u: 'A',    dec: 1 },
      { k: 'i62',  t: 'ind', x: 841,  y: 604, tag: 'IT-321962', bind: 'pumpB.current',u: 'A',    dec: 1 },
      { k: 's50',  t: 'ind', x: 570,  y: 642, tag: 'SIC-321950',bind: 'controllers.SIC_321950.pv',u: 'RPM',  dec: 1, fp: 'SIC_321950', mode: 'controllers.SIC_321950.mode' },
      { k: 's51',  t: 'ind', x: 770,  y: 648, tag: 'SIC-321951',bind: 'controllers.SIC_321951.pv',u: 'RPM',  dec: 1, fp: 'SIC_321951', mode: 'controllers.SIC_321951.mode' },
      // ---- pumps (slide Picture 27 / 67) ----
      { k: 'pa',  t: 'pump', x: 621.8,  y: 521.7, w: 75.86, h: 65.64, rot: 0,   bind: 'pumpA', id: 'A', tag: '321P002A' },
      { k: 'pb',  t: 'pump', x: 839.9,  y: 516.8, w: 75.86, h: 65.64, rot: 0,   bind: 'pumpB', id: 'B', tag: '321P002B' },
      // ---- XVs (slide Picture 156 / 158) ----
      { k: 'xva', t: 'xv',   x: 457.5,  y: 324.9, w: 68.84, h: 32.00, rot: 0,   bind: 'XV_321901', cmd: '321901', tag: 'XV-321901' },
      { k: 'xvb', t: 'xv',   x: 1129.1, y: 359.7, w: 68.84, h: 32.00, rot: 0,   bind: 'XV_322901', cmd: '322901', tag: 'XV-322901' },
      // ---- hand switches: the green square inside each "Open XV-..." panel (slide 165 / 167) ----
      { k: 'hs321901', t: 'hs', x: 555,  y: 280, w: 26, h: 20, xv: 'XV_321901', cmd: '321901', tag: 'HS-321901' },
      { k: 'hs322901', t: 'hs', x: 1167, y: 416, w: 26, h: 20, xv: 'XV_322901', cmd: '322901', tag: 'HS-322901' },
      // ---- navigation links (slide comment "Link to page ...") ----
      { k: 'nav-322f001',t: 'nav', x: 1277, y: 359, w: 103, h: 32, tag: '322F001 -> 322-2',   goto: 'screen-322-2' },
      { k: 'nav-ft403',  t: 'nav', x: 70,   y: 426, w: 113, h: 38, tag: 'FT-322402 -> 322-1', goto: 'screen-322-1' },
      { k: 'nav-bl',     t: 'nav', x: 61,   y: 265, w: 78,  h: 28, tag: 'BL -> (external)',   goto: 'screen-321-1' },  // BL = Battery Limits - no screen yet
    ],
    // ---------------------------------------------------------------------------------
    //  Seed coordinates are the shape centres of the 322-2 slide (UI Pages/322-2.pptx),
    //  mapped 12192000x6858000 EMU -> 1366x720 stage.
    // ---------------------------------------------------------------------------------
    'screen-322-2': [
      // ===== 322E003 HP SCRUBBER =====
      { k: 'tt11',   t: 'ind', x: 552,  y: 112, tag: 'TT-322011', bind: 'SCRUB_322E003.TT_322011', u: 'C', dec: 1 },
      { k: 'h604',   t: 'ind', x: 1070, y: 78,  tag: 'HIC-322604', bind: 'SCRUB_322E003.HIC_322604', u: '%', dec: 1, face: 'hic' },
      { k: 'hv604',  t: 'ind', x: 1068, y: 164, tag: 'HV-322604',  bind: 'SCRUB_322E003.HV_322604',  u: '%', dec: 1, face: 'hic' },
      { k: 'lt9501', t: 'ind', x: 359,  y: 408, tag: 'LT-329501',  bind: 'SCRUB_322E003.LT_329501',  u: '%', dec: 1 },
      { k: 'bar9501',t: 'bar', x: 422,  y: 411, w: 22, h: 79, tag: 'LT-329501', bind: 'SCRUB_322E003.LT_329501' },
      { k: 'tt9',    t: 'ind', x: 245,  y: 216, tag: 'TT-322009', bind: 'REACT_322R001.TT_322009', u: 'C', dec: 1 },
      // ===== 322F001 HP EJECTOR =====
      { k: 'tt12',   t: 'ind', x: 210,  y: 270, tag: 'TT-322012', bind: 'EJ_322F001.TT_322012', u: 'C', dec: 1 },
      { k: 'pt9201', t: 'ind', x: 392,  y: 332, tag: 'PT-329201', bind: 'EJ_322F001.PI_329201', u: 'BAR A', dec: 1 },
      { k: 'tt2',    t: 'ind', x: 374,  y: 357, tag: 'TT-322002', bind: 'EJ_322F001.TI_322002', u: 'C', dec: 1 },
      { k: 'h602',   t: 'ind', x: 214,  y: 452, tag: 'HIC-322602', bind: 'EJ_322F001.HIC_322602', u: '%', dec: 1, face: 'hic' },
      { k: 'hv602',  t: 'ind', x: 212,  y: 481, tag: 'HV-322602',  bind: 'EJ_322F001.HIC_322602', u: '%', dec: 1, face: 'hic' },
      { k: 'tt1020', t: 'ind', x: 174,  y: 625, tag: 'TT-321020',  bind: 'TI_321020', u: 'C', dec: 1 },
      // ===== SHELL-SIDE CCW LOOP (329P006 A/B + 329E004 cooler) =====
      { k: 'tic05',  t: 'ind', x: 666,  y: 404, tag: 'TIC-329005', bind: 'SCRUB_322E003.ccw.TIC_329005.pv', u: 'C', dec: 1, mode: 'SCRUB_322E003.ccw.TIC_329005.mode' },
      { k: 'tv05',   t: 'ind', x: 831,  y: 350, tag: 'TV-329005',  bind: 'SCRUB_322E003.ccw.TIC_329005.op', u: '%', dec: 1 },
      { k: 'tdy25',  t: 'ind', x: 609,  y: 470, tag: 'TDY-329125', bind: 'SCRUB_322E003.ccw.TDY_329125', u: 'C', dec: 1 },
      { k: 'fic09',  t: 'ind', x: 682,  y: 465, tag: 'FIC-329409', bind: 'SCRUB_322E003.ccw.FIC_329409.pv', u: 'T/H', dec: 1, mode: 'SCRUB_322E003.ccw.FIC_329409.mode' },
      { k: 'fv09',   t: 'ind', x: 834,  y: 446, tag: 'FV-329409',  bind: 'SCRUB_322E003.ccw.FIC_329409.op', u: '%', dec: 1 },
      { k: 'tt25',   t: 'ind', x: 944,  y: 543, tag: 'TT-329125',  bind: 'SCRUB_322E003.ccw.TT_329125', u: 'C', dec: 1 },
      // 329P006 A/B tempered-water circulation pumps -- A duty, B standby, both operator
      // startable/stoppable.  They are the CCW loop's only motive source: stop both and
      // FIC-329409 falls to 0, the shell-side exotherm stops being removed and PT-329201 climbs.
      // The slide draws both rotated 180 deg (suction on the right).
      { k: 'pca',    t: 'pump', x: 997.7,  y: 386.5, w: 43.72, h: 37.83, rot: 180, bind: 'SCRUB_322E003.ccw.P329P006A', id: '329P006A', tag: '329P006A' },
      { k: 'pcb',    t: 'pump', x: 1001.9, y: 458.1, w: 43.72, h: 37.83, rot: 180, bind: 'SCRUB_322E003.ccw.P329P006B', id: '329P006B', tag: '329P006B' },
      // ===== 322C001 / 323 BOUNDARY =====
      { k: 'pic201', t: 'ind', x: 1240, y: 93,  tag: 'PIC-322201', bind: 'ABSORB_328.C001.PIC_322201.pv', u: 'BAR A', dec: 2, mode: 'ABSORB_328.C001.PIC_322201.mode' },
      { k: 'tt3010', t: 'ind', x: 1237, y: 115, tag: 'TT-323010',  bind: 'RECIRC_323.F010.TT_323010', u: 'C', dec: 1 },
      // ===== XVs + hand switches =====
      { k: 'xv901',  t: 'xv', x: 278.3, y: 535.8, w: 41.57, h: 24.04, rot: 90, bind: 'XV_322901', cmd: '322901', tag: 'XV-322901' },
      { k: 'xv903',  t: 'xv', x: 348.4, y: 467.6, w: 41.57, h: 24.04, rot: 0,  bind: 'EJ_322F001.XV_322903', cmd: '322903', tag: 'XV-322903' },
      { k: 'hs903',  t: 'hs', x: 411, y: 522, w: 26, h: 20, xv: 'EJ_322F001.XV_322903', cmd: '322903', tag: 'HS-322903' },
      // ===== STREAM-INSPECTOR HOTSPOTS =====
      { k: 'strm-soffg', t: 'strm', stream: 'SCRUB_OFFGAS',    tag: 'SCRUBBER OFF-GAS -> HV-322604', x: 620,  y: 139, w: 250, h: 16 },
      { k: 'strm-soglp', t: 'strm', stream: 'SCRUB_OFFGAS_LP', tag: 'OFF-GAS LP -> 322C001',         x: 1150, y: 139, w: 100, h: 16 },
      { k: 'strm-ccws',  t: 'strm', stream: 'CCW_SUPPLY',      tag: 'CCW SUPPLY -> 322E003',         x: 800,  y: 426, w: 200, h: 14 },
      { k: 'strm-ccwr',  t: 'strm', stream: 'CCW_RETURN',      tag: 'CCW RETURN -> 329P006 A/B',     x: 1000, y: 516, w: 200, h: 14 },
      // ===== NAVIGATION (slide comment "Link to page ...") =====
      { k: 'nav-r001', t: 'nav', x: 82,   y: 187, w: 92,  h: 21, tag: '322R001 -> 322-1',    goto: 'screen-322-1' },
      { k: 'nav-e002', t: 'nav', x: 86,   y: 243, w: 92,  h: 21, tag: '322E002 -> 322-1',    goto: 'screen-322-1' },
      { k: 'nav-p002', t: 'nav', x: 82,   y: 599, w: 100, h: 21, tag: '321P002A/B -> 321-1', goto: 'screen-321-1' },
      { k: 'nav-c001', t: 'nav', x: 1235, y: 141, w: 92,  h: 21, tag: '322C001 -> 328-2',    goto: 'screen-328-2' },
      { k: 'nav-p001', t: 'nav', x: 1235, y: 211, w: 98,  h: 21, tag: '323P001A/B -> 323-2', goto: 'screen-323-2' },
    ],
    // ---------------------------------------------------------------------------------
    //  Seed coordinates are the shape centres of the 322-1 slide (UI Pages/322-1.pptx),
    //  mapped 12192000x6858000 EMU -> 1366x720 stage.
    // ---------------------------------------------------------------------------------
    'screen-322-1': [
      // ===== 322R001 REACTOR =====
      { k: 'tt9',   t: 'ind', x: 405,  y: 114, tag: 'TT-322009', bind: 'REACT_322R001.TT_322009', u: 'C', dec: 1 },
      { k: 'tt5',   t: 'ind', x: 387,  y: 200, tag: 'TT-322005', bind: 'REACT_322R001.TT_322005', u: 'C', dec: 1 },
      { k: 'tt6',   t: 'ind', x: 387,  y: 247, tag: 'TT-322006', bind: 'REACT_322R001.TT_322006', u: 'C', dec: 1 },
      { k: 'tt7',   t: 'ind', x: 387,  y: 293, tag: 'TT-322007', bind: 'REACT_322R001.TT_322007', u: 'C', dec: 1 },
      { k: 'tt8',   t: 'ind', x: 387,  y: 347, tag: 'TT-322008', bind: 'REACT_322R001.TT_322008', u: 'C', dec: 1 },
      { k: 'lt504', t: 'ind', x: 171,  y: 247, tag: 'LT-322504', bind: 'REACT_322R001.LT_322504', u: '%', dec: 1 },
      { k: 'bar504',t: 'bar', x: 243,  y: 285, w: 12, h: 125, tag: 'LT-322504', bind: 'REACT_322R001.LT_322504' },
      { k: 'at701', t: 'ind', x: 226,  y: 424, tag: 'AT-322701', bind: 'REACT_322R001.AT_322701', u: 'N/C', dec: 3 },
      { k: 'ae801', t: 'ae',  x: 217,  y: 453, tag: 'AE-322801', stream: 'REACT_OVERFLOW', note: 'Solution composition: 322R001 -> HV-322605' },
      { k: 'h605',  t: 'ind', x: 711,  y: 446, tag: 'HIC-322605', bind: 'REACT_322R001.HIC_322605', u: '%', dec: 1, face: 'hic' },
      { k: 'hv605', t: 'ind', x: 710,  y: 503, tag: 'HV-322605',  bind: 'REACT_322R001.HV_322605',  u: '%', dec: 1, face: 'hic' },
      // ===== 322E002 HP CARBAMATE CONDENSER =====
      { k: 'tt12',  t: 'ind', x: 634,  y: 210, tag: 'TT-322012', bind: 'EJ_322F001.TT_322012',   u: 'C', dec: 1 },
      { k: 'tt10',  t: 'ind', x: 444,  y: 442, tag: 'TT-322010', bind: 'HPCC_322E002.TT_322010', u: 'C', dec: 1 },
      { k: 'tt2900',t: 'ind', x: 755,  y: 355, tag: 'TT-329001', bind: 'HPCC_322E002.TT_329001', u: 'C', dec: 1 },
      // ===== 322E001 HP STRIPPER =====
      { k: 'tt13',  t: 'ind', x: 1018, y: 258, tag: 'TT-322013', bind: 'STRIP_322E001.TT_322013', u: 'C', dec: 1 },
      { k: 'tt14',  t: 'ind', x: 455,  y: 508, tag: 'TT-322014', bind: 'STRIP_322E001.TT_322014', u: 'C', dec: 1 },
      { k: 'tt4',   t: 'ind', x: 905,  y: 559, tag: 'TT-322004', bind: 'STRIP_322E001.TT_322004', u: 'C', dec: 1 },
      { k: 'lic501',t: 'ind', x: 864,  y: 478, tag: 'LIC-322501', bind: 'STRIP_322E001.LIC_322501.pv', u: '%', dec: 1, mode: 'STRIP_322E001.LIC_322501.mode' },
      { k: 'bar501',t: 'bar', x: 976,  y: 474, w: 12, h: 68, tag: 'LIC-322501', bind: 'STRIP_322E001.LIC_322501.pv' },
      { k: 'lv501', t: 'ind', x: 1051, y: 590, tag: 'LV-322501', bind: 'STRIP_322E001.LV_322501', u: '%', dec: 1 },
      { k: 'ae802', t: 'ae',  x: 986,  y: 602, tag: 'AE-322802', stream: 'STRIP_BOT', note: 'Solution composition: 322E001 -> LV-322501' },
      { k: 'pt3201',t: 'ind', x: 1115, y: 599, tag: 'PT-323201', bind: 'RECIRC_323.C003.P_bara', u: 'BAR A', dec: 2 },
      // ===== CO2 FEED LINE (320K002 -> XV-322902 -> 322E001) =====
      { k: 'pic203',t: 'ind',    x: 118, y: 561, tag: 'PIC-322203', bind: 'CO2_FEED.PIC_322203', u: 'BAR A', dec: 1, face: 'pic', mode: 'CO2_FEED.PIC_mode' },
      { k: 'pv203', t: 'avalve', x: 242, y: 522, tag: 'PV-322203',  bind: 'CO2_FEED.PV_322203',  u: '%',     dec: 1, face: 'hic2' },   // left-click = HIC-322203 forced-minimum faceplate
      { k: 'hs203', t: 'btn',    x: 141, y: 498, w: 74, h: 19, tag: 'HS-322203', face: 'hic2', bind: 'CO2_FEED.HIC_322203', u: '%', dec: 1 },   // slide-drawn button -> HIC-322203 station (bind is for the trend pen only; the button draws no value)
      { k: 'fy403', t: 'ind',    x: 362, y: 523, tag: 'FY-322403',  bind: 'CO2_FEED.FY_322403',  u: 'T/H',   dec: 2 },
      { k: 'ft403', t: 'ind',    x: 363, y: 559, tag: 'FT-322403',  bind: 'CO2_FEED.FT_322403',  u: 'NM3/H', dec: 0 },
      { k: 'tt17',  t: 'ind',    x: 290, y: 597, tag: 'TT-322017',  bind: 'CO2_FEED.TI_322017',  u: 'C',     dec: 1 },
      { k: 'xv902', t: 'xv',     x: 700.1, y: 578.3, w: 44.58, h: 20.72, rot: 0, bind: 'CO2_FEED.XV_322902', cmd: '322902', tag: 'XV-322902' },
      { k: 'hs902', t: 'hs',     x: 734, y: 634, w: 26, h: 20, xv: 'CO2_FEED.XV_322902', cmd: '322902', tag: 'HS-322902' },
      { k: 'load',  t: 'ind',    x: 1201,y: 648, tag: 'LOAD', bind: 'CO2_FEED.Load', u: '%', dec: 1, fs: 14 },   // panel label is left-aligned; value takes the right half
      // ===== FEED-RATIO / PUMP-SPEED PANEL (mirrors the 321-1 panel; editable via faceplate) =====
      { k: 'ffa',   t: 'ind', x: 402, y: 640, tag: 'FFIC-321404A', bind: 'ratio.PV', u: 'N/C', dec: 3, fp: 'SIC_321950' },
      { k: 'ffb',   t: 'ind', x: 399, y: 660, tag: 'FFIC-321404B', bind: 'ratio.PV', u: 'N/C', dec: 3, fp: 'SIC_321951' },
      { k: 's50',   t: 'ind', x: 528, y: 640, tag: 'SIC-321950', bind: 'controllers.SIC_321950.pv', u: 'RPM', dec: 1, fp: 'SIC_321950', mode: 'controllers.SIC_321950.mode' },
      { k: 's51',   t: 'ind', x: 528, y: 660, tag: 'SIC-321951', bind: 'controllers.SIC_321951.pv', u: 'RPM', dec: 1, fp: 'SIC_321951', mode: 'controllers.SIC_321951.mode' },
      // ===== 329 STEAM BOUNDARY =====
      { k: 'pt9201',t: 'ind', x: 1125, y: 45,  tag: 'PT-329201', bind: 'EJ_322F001.PI_329201', u: 'BAR A', dec: 1, fs: 18 },
      { k: 'msp',   t: 'ind', x: 1146, y: 236, tag: 'MASTER-SP', bind: 'STEAM_SYSTEM.MASTER_SP_329207.sp', u: 'BAR A', dec: 2, fp: 'MASTER_SP_329207' },
      { k: 'pt9207',t: 'ind', x: 1148, y: 256, tag: 'PT-329207', bind: 'STEAM_SYSTEM.LP.P_bara', u: 'BAR A', dec: 2 },
      { k: 'pic204',t: 'ind', x: 1080, y: 400, tag: 'PIC-329204', bind: 'STEAM_SYSTEM.PIC_329204.pv', u: 'BAR A', dec: 2, mode: 'STEAM_SYSTEM.PIC_329204.mode' },
      { k: 'h9601', t: 'ind', x: 1126, y: 448, tag: 'HIC-329601', bind: 'STEAM_SYSTEM.HP_VENT.pct', u: '%', dec: 1, face: 'hic' },
      { k: 'ft9403',t: 'ind', x: 1130, y: 471, tag: 'FT-329403',  bind: 'STEAM_SYSTEM.FT_329403_th', u: 'T/H', dec: 2 },
      // ===== STREAM-INSPECTOR HOTSPOTS (each sits on the drawn line its tags measure) =====
      { k: 'strm-rog',   t: 'strm', stream: 'REACT_OFFGAS',   tag: 'REACTOR GAS -> 322E003',  x: 850,  y: 93,  w: 280, h: 16 },
      { k: 'strm-ejd',   t: 'strm', stream: 'EJ_DISCH',       tag: 'CARB. LIQ. -> 322E002',   x: 900,  y: 193, w: 280, h: 16 },
      { k: 'strm-stm',   t: 'strm', stream: 'HPCC_STEAM',     tag: 'LP STEAM -> 322D001',     x: 900,  y: 294, w: 200, h: 14 },
      { k: 'strm-cond',  t: 'strm', stream: 'HPCC_COND',      tag: 'BFW/COND -> 322E002',     x: 900,  y: 329, w: 200, h: 14 },
      { k: 'strm-stop',  t: 'strm', stream: 'STRIP_TOP',      tag: 'STRIP TOP GAS',           x: 960,  y: 320, w: 14,  h: 120 },
      { k: 'strm-rov',   t: 'strm', stream: 'REACT_OVERFLOW', tag: 'OVERFLOW -> 322E001',     x: 560,  y: 483, w: 200, h: 16 },
      { k: 'strm-co2',   t: 'strm', stream: 'CO2_FEED',       tag: 'CO2 FEED GAS',            x: 500,  y: 578, w: 280, h: 16 },
      { k: 'strm-sbot',  t: 'strm', stream: 'STRIP_BOT',      tag: 'STRIP BOTTOM SOLN',       x: 1150, y: 574, w: 110, h: 16 },
      // ===== NAVIGATION (slide comment "Link to page ...") =====
      { k: 'nav-e003',  t: 'nav', x: 1220, y: 95,  w: 92,  h: 21, tag: '322E003 -> 322-2',  goto: 'screen-322-2' },
      { k: 'nav-f001',  t: 'nav', x: 1220, y: 195, w: 92,  h: 21, tag: '322F001 -> 322-2',  goto: 'screen-322-2' },
      { k: 'nav-msp',   t: 'nav', x: 1229, y: 249, w: 74,  h: 41, tag: 'MASTER SP -> 329-1', goto: 'screen-329-1' },
      { k: 'nav-d001a', t: 'nav', x: 1224, y: 293, w: 92,  h: 21, tag: '322D001 -> 329-1',  goto: 'screen-329-1' },
      { k: 'nav-d001b', t: 'nav', x: 1224, y: 330, w: 92,  h: 21, tag: '322D001 -> 329-1',  goto: 'screen-329-1' },
      { k: 'nav-vent',  t: 'nav', x: 1231, y: 449, w: 101, h: 21, tag: 'VENT VALVE -> 329-1', goto: 'screen-329-1' },
      { k: 'nav-extr',  t: 'nav', x: 1231, y: 472, w: 101, h: 21, tag: 'EXTR STEAM -> 329-1', goto: 'screen-329-1' },
      { k: 'nav-c003',  t: 'nav', x: 1220, y: 572, w: 92,  h: 21, tag: '323C003 -> 323-1',  goto: 'screen-323-1' },
    ],
    // ============================ 329-1  UREA STEAM SYSTEM  (25 bar BL / 329D005 / 329D009 / 322D001A/B 4 bar) ============================
    // Seed geometry = the shape centres of UI Pages/329-1.pptx, 12192000x6858000 EMU -> 1366x720
    // stage.  The background PNG is that slide with exactly these shapes deleted, so every
    // overlay lands in the hole its own symbol left.  root STEAM_SYSTEM; every 322E00x consumer links back to 322-1.
    'screen-329-1': [
      // ---- indicators, controllers and modulating-valve openings ----
      { k: 'pic329207b', t: 'ind', x: 1116, y: 57, tag: 'PIC-329207B', bind: 'STEAM_SYSTEM.PIC_329207B.pv', u: 'BAR A', dec: 2, mode: 'STEAM_SYSTEM.PIC_329207B.mode', fp: 'MASTER_SP_329207' },
      { k: 'mastersp', t: 'ind', x: 94, y: 78, tag: 'MASTER-SP', bind: 'STEAM_SYSTEM.MASTER_SP_329207.sp', u: 'BAR A', dec: 2, fp: 'MASTER_SP_329207', note: '4-bar header master setpoint; the A/B/C legs track it at +0.1 / 0 / -0.1' },
      { k: 'pic329207a', t: 'ind', x: 1046, y: 83, tag: 'PIC-329207A', bind: 'STEAM_SYSTEM.PIC_329207A.pv', u: 'BAR A', dec: 2, mode: 'STEAM_SYSTEM.PIC_329207A.mode', fp: 'MASTER_SP_329207' },
      { k: 'pic329207c', t: 'ind', x: 368, y: 144, tag: 'PIC-329207C', bind: 'STEAM_SYSTEM.PIC_329207C.pv', u: 'BAR A', dec: 2, mode: 'STEAM_SYSTEM.PIC_329207C.mode', fp: 'MASTER_SP_329207' },
      { k: 'pt329207', t: 'ind', x: 691, y: 144, tag: 'PT-329207', bind: 'STEAM_SYSTEM.LP.P_bara', u: 'BAR A', dec: 2 },
      { k: 'ft329407', t: 'ind', x: 1187, y: 145, tag: 'FT-329407', bind: 'STEAM_SYSTEM.FT_329407_th', u: 'T/H', dec: 2 },
      { k: 'lic329504', t: 'ind', x: 419, y: 202, tag: 'LIC-329504', bind: 'STEAM_SYSTEM.LIC_329504.pv', u: '%', dec: 1, mode: 'STEAM_SYSTEM.LIC_329504.mode', note: 'reverse-acting: AUTO holds 322D001A/B level via LV-329504 make-up from 329P001A/B pumps; MAN sets LV-329504 opening directly' },
      { k: 'tt329001', t: 'ind', x: 651, y: 257, tag: 'TT-329001', bind: 'HPCC_322E002.TT_329001', u: 'C', dec: 1 },
      { k: 'hic329602', t: 'ind', x: 364, y: 336, tag: 'HIC-329602', bind: 'STEAM_SYSTEM.LP_MAKEUP.HV_329602', u: '%', dec: 1, face: 'hic' },
      { k: 'pic329205', t: 'ind', x: 721, y: 363, tag: 'PIC-329205', bind: 'STEAM_SYSTEM.PIC_329205.pv', u: 'BAR A', dec: 2, mode: 'STEAM_SYSTEM.PIC_329205.mode', note: 'up P9 => PV-329205B let-down (9->4 bar) opens; down P9 => PV-329205A admits 25-bar BL steam' },
      { k: 'hv329601', t: 'ind', x: 171, y: 383, tag: 'HV-329601', bind: 'STEAM_SYSTEM.HP_VENT.pct', u: '%', dec: 1, face: 'hic' },
      { k: 'hic329601', t: 'ind', x: 271, y: 383, tag: 'HIC-329601', bind: 'STEAM_SYSTEM.HP_VENT.pct', u: '%', dec: 1, face: 'hic' },
      { k: 'hv329602', t: 'ind', x: 366, y: 392, tag: 'HV-329602', bind: 'STEAM_SYSTEM.LP_MAKEUP.HV_329602', u: '%', dec: 1, face: 'hic' },
      { k: 'lic329503', t: 'ind', x: 1071, y: 404, tag: 'LIC-329503', bind: 'STEAM_SYSTEM.LIC_329503.pv', u: '%', dec: 1, mode: 'STEAM_SYSTEM.LIC_329503.mode', note: 'AUTO holds 329D009 level via LV-329503 drain to 322D001A/B; MAN sets LV-329503 opening directly' },
      { k: 'pic329204', t: 'ind', x: 396, y: 510, tag: 'PIC-329204', bind: 'STEAM_SYSTEM.PIC_329204.pv', u: 'BAR A', dec: 2, mode: 'STEAM_SYSTEM.PIC_329204.mode', note: 'AUTO holds 329D005 at SP via PV-329204; MAN sets PV-329204 opening directly' },
      { k: 'fic329401', t: 'ind', x: 256, y: 526, tag: 'FIC-329401', bind: 'DESORB_328.C004.FIC_329401.pv', u: 'KG/H', dec: 1, mode: 'DESORB_328.C004.FIC_329401.mode', cas: true, note: 'slave: CAS follows FFIC-329401 ratio on the FIC-328402 feed; LP steam via FV-329401' },
      { k: 'lic329502', t: 'ind', x: 794, y: 564, tag: 'LIC-329502', bind: 'STEAM_SYSTEM.LIC_329502.pv', u: '%', dec: 1, mode: 'STEAM_SYSTEM.LIC_329502.mode', note: 'AUTO holds 329D005 level via LV-329502 drain to 329D009; MAN sets LV-329502 opening directly' },
      { k: 'pt329251', t: 'ind', x: 216, y: 593, tag: 'PT-329251', bind: 'STEAM_SYSTEM.SUPPLY_25BAR.P_bara', u: 'BAR A', dec: 2 },
      { k: 'ft329403', t: 'ind', x: 164, y: 643, tag: 'FT-329403', bind: 'STEAM_SYSTEM.FT_329403_th', u: 'T/H', dec: 2 },
      { k: 'tt329101', t: 'ind', x: 264, y: 643, tag: 'TT-329101', bind: 'STEAM_SYSTEM.SUPPLY_25BAR.TI_sat', u: 'C', dec: 1 },
      { k: 'pv329207a', t: 'avalve', x: 854, y: 133, tag: 'PV-329207A', bind: 'STEAM_SYSTEM.PIC_329207A.op', u: '%', dec: 1 },
      { k: 'pv329207b', t: 'avalve', x: 1120, y: 192, tag: 'PV-329207B', bind: 'STEAM_SYSTEM.PIC_329207B.op', u: '%', dec: 1 },
      { k: 'lv329504', t: 'avalve', x: 214, y: 247, tag: 'LV-329504', bind: 'STEAM_SYSTEM.LIC_329504.op', u: '%', dec: 1 },
      { k: 'pv329205b', t: 'avalve', x: 903, y: 280, tag: 'PV-329205B', bind: 'STEAM_SYSTEM.DRUM_9BAR.letdown_pct', u: '%', dec: 1 },
      { k: 'pv329207c', t: 'avalve', x: 368, y: 284, tag: 'PV-329207C', bind: 'STEAM_SYSTEM.PIC_329207C.op', u: '%', dec: 1 },
      { k: 'pv329205a', t: 'avalve', x: 671, y: 446, tag: 'PV-329205A', bind: 'STEAM_SYSTEM.DRUM_9BAR.admit_pct', u: '%', dec: 1 },
      { k: 'lv329503', t: 'avalve', x: 1074, y: 517, tag: 'LV-329503', bind: 'STEAM_SYSTEM.LIC_329503.op', u: '%', dec: 1 },
      { k: 'pv329204', t: 'avalve', x: 395, y: 633, tag: 'PV-329204', bind: 'STEAM_SYSTEM.MP.supply_pct', u: '%', dec: 1 },
      { k: 'lv329502', t: 'avalve', x: 792, y: 666, tag: 'LV-329502', bind: 'STEAM_SYSTEM.LIC_329502.op', u: '%', dec: 1 },
      // ---- level bargraphs (fill height = bound level, 0-100 %) ----
      { k: 'barlic329504', t: 'bar', x: 496, y: 215, w: 19, h: 69, tag: 'LIC-329504', bind: 'STEAM_SYSTEM.LIC_329504.pv' },
      { k: 'barlic329503', t: 'bar', x: 961, y: 389, w: 23, h: 81, tag: 'LIC-329503', bind: 'STEAM_SYSTEM.LIC_329503.pv' },
      { k: 'barlic329502', t: 'bar', x: 702, y: 573, w: 16, h: 81, tag: 'LIC-329502', bind: 'STEAM_SYSTEM.LIC_329502.pv' },
      // ---- screen-nav hotspots (slide comment "LINK TO PAGE ...") ----
      { k: 'nav3221322e002', t: 'nav', x: 81, y: 173, w: 92, h: 21, tag: '322E002 -> 322-1', goto: 'screen-322-1' },
      { k: 'nav3221322e0022', t: 'nav', x: 81, y: 311, w: 92, h: 21, tag: '322E002 -> 322-1', goto: 'screen-322-1' },
      { k: 'nav3241b324e003', t: 'nav', x: 1282, y: 381, w: 92, h: 21, tag: '324E003 -> 324-1b', goto: 'screen-324-1b' },
      { k: 'nav3221322e001', t: 'nav', x: 81, y: 412, w: 92, h: 21, tag: '322E001 -> 322-1', goto: 'screen-322-1' },
      { k: 'nav3221322e0012', t: 'nav', x: 81, y: 458, w: 92, h: 21, tag: '322E001 -> 322-1', goto: 'screen-322-1' },
      { k: 'nav3281328c003', t: 'nav', x: 81, y: 547, w: 92, h: 21, tag: '328C003 -> 328-1', goto: 'screen-328-1' },
    ],
    // ============================ 323-1  LP RECIRCULATION & PRE-EVAPORATION ============================
    // Seed geometry = the shape centres of UI Pages/323-1.pptx, 12192000x6858000 EMU -> 1366x720
    // stage.  The background PNG is that slide with exactly these shapes deleted, so every
    // overlay lands in the hole its own symbol left.  roots RECIRC_323 (323C003 rect. column / 323F004 flash / 323F010 pre-evap / 323D002 tank).
    'screen-323-1': [
      // ---- indicators, controllers and modulating-valve openings ----
      { k: 'hic323605', t: 'ind', x: 1021, y: 139, tag: 'HIC-323605', bind: 'RECIRC_323.F010.HV_323605', u: '%', dec: 1, face: 'hic' },
      { k: 'pic323203', t: 'ind', x: 704, y: 144, tag: 'PIC-323203', bind: 'LPCC_3232.E011.PIC_323203.pv', u: 'BAR A', dec: 2, mode: 'LPCC_3232.E011.PIC_323203.mode', note: '323E011/D011 LP node P; flash vapour 701 (LV-323501 -> 323F004) accumulates it. AUTO holds SP via PV-323203; MAN lets P ramp' },
      { k: 'tt323001', t: 'ind', x: 225, y: 175, tag: 'TT-323001', bind: 'RECIRC_323.C003.feed_T', u: 'C', dec: 1 },
      { k: 'pt323201', t: 'ind', x: 442, y: 191, tag: 'PT-323201', bind: 'RECIRC_323.C003.P_bara', u: 'BAR A', dec: 2 },
      { k: 'hv323605', t: 'ind', x: 1017, y: 202, tag: 'HV-323605', bind: 'RECIRC_323.F010.HV_323605', u: '%', dec: 1, face: 'hic' },
      { k: 'pt323204', t: 'ind', x: 988, y: 240, tag: 'PT-323204', bind: 'RECIRC_323.F010.P_bara', u: 'BAR A', dec: 2 },
      { k: 'lic323501', t: 'ind', x: 442, y: 250, tag: 'LIC-323501', bind: 'RECIRC_323.C003.LIC_323501.pv', u: '%', dec: 1, mode: 'RECIRC_323.C003.LIC_323501.mode', note: 'holds 323C003 level via LV-323501 bottoms drain to 323F004' },
      { k: 'lic323505', t: 'ind', x: 757, y: 263, tag: 'LIC-323505', bind: 'RECIRC_323.F004.LIC_323505.pv', u: '%', dec: 1, mode: 'RECIRC_323.F004.LIC_323505.mode', note: 'holds 323F004 level via LV-323505 drain to 323F010 pre-evaporator' },
      { k: 'pic329202', t: 'ind', x: 228, y: 285, tag: 'PIC-329202', bind: 'RECIRC_323.C003.PIC_329202.pv', u: 'BAR A', dec: 2, mode: 'RECIRC_323.C003.PIC_329202.mode', cas: true, note: 'slave: CAS follows TIC-323007; drives PV-329202 steam to 323E002' },
      { k: 'pic329208', t: 'ind', x: 1058, y: 340, tag: 'PIC-329208', bind: 'RECIRC_323.F010.PIC_329208.pv', u: 'BAR A', dec: 2, mode: 'RECIRC_323.F010.PIC_329208.mode', cas: true, note: 'slave: CAS follows TIC-323012; drives PV-329208 steam to 323E010' },
      { k: 'tic323007', t: 'ind', x: 422, y: 385, tag: 'TIC-323007', bind: 'RECIRC_323.C003.TIC_323007.pv', u: 'C', dec: 1, mode: 'RECIRC_323.C003.TIC_323007.mode', note: 'master: cascades PIC-329202 steam-P to 323E002 to hold 135 C' },
      { k: 'tic323012', t: 'ind', x: 1012, y: 417, tag: 'TIC-323012', bind: 'RECIRC_323.F010.TIC_323012.pv', u: 'C', dec: 1, mode: 'RECIRC_323.F010.TIC_323012.mode', note: 'master: cascades PIC-329208 steam-P to 323E010 to hold 99 C' },
      { k: 'tt323002', t: 'ind', x: 301, y: 467, tag: 'TT-323002', bind: 'RECIRC_323.C003.TT_323002', u: 'C', dec: 1 },
      { k: 'lic322501', t: 'ind', x: 145, y: 542, tag: 'LIC-322501', bind: 'STRIP_322E001.LIC_322501.pv', u: '%', dec: 1, mode: 'STRIP_322E001.LIC_322501.mode' },
      { k: 'lt323504', t: 'ind', x: 844, y: 601, tag: 'LT-323504', bind: 'RECIRC_323.D002.LI_323504', u: '%', dec: 1, note: '323D002 passive compartment II - indication and alarms only, normally 0 %' },
      { k: 'lic323507', t: 'ind', x: 1138, y: 607, tag: 'LIC-323507', bind: 'RECIRC_323.D002.LIC_323507.pv', u: '%', dec: 1, mode: 'RECIRC_323.D002.LIC_323507.mode', note: 'master: active compartment I level cascades FIC-324401 product flow' },
      { k: 'fic335407', t: 'ind', x: 660, y: 653, tag: 'FIC-335407' },
      { k: 'tt323008', t: 'ind', x: 1128, y: 669, tag: 'TT-323008', bind: 'RECIRC_323.D002.TI_323008', u: 'C', dec: 1, note: '323D002 Comp-I bulk temperature (TAL: a falling tank walks the 80 % liquor toward crystallisation and blocks the 323P003 suction)' },
      { k: 'pv329202', t: 'avalve', x: 135, y: 349, tag: 'PV-329202', bind: 'RECIRC_323.C003.PIC_329202.op', u: '%', dec: 1 },
      { k: 'lv323501', t: 'avalve', x: 476, y: 361, tag: 'LV-323501', bind: 'RECIRC_323.C003.LIC_323501.op', u: '%', dec: 1 },
      { k: 'pv329208', t: 'avalve', x: 1116, y: 390, tag: 'PV-329208', bind: 'RECIRC_323.F010.PIC_329208.op', u: '%', dec: 1 },
      { k: 'lv323505', t: 'avalve', x: 750, y: 551, tag: 'LV-323505', bind: 'RECIRC_323.F004.LIC_323505.op', u: '%', dec: 1 },
      { k: 'lv322501', t: 'avalve', x: 143, y: 607, tag: 'LV-322501', bind: 'STRIP_322E001.LV_322501', u: '%', dec: 1 },
      { k: 'fv335407', t: 'avalve', x: 762, y: 698, tag: 'FV-335407' },
      // ---- level bargraphs (fill height = bound level, 0-100 %) ----
      { k: 'barlic323501', t: 'bar', x: 343, y: 247, w: 15, h: 56, tag: 'LIC-323501', bind: 'RECIRC_323.C003.LIC_323501.pv' },
      { k: 'barlic323505', t: 'bar', x: 647, y: 263, w: 24, h: 86, tag: 'LIC-323505', bind: 'RECIRC_323.F004.LIC_323505.pv' },
      { k: 'barlt323504', t: 'bar', x: 929, y: 628, w: 20, h: 70, tag: 'LT-323504', bind: 'RECIRC_323.D002.LI_323504' },
      { k: 'barlic323507', t: 'bar', x: 1055, y: 628, w: 22, h: 70, tag: 'LIC-323507', bind: 'RECIRC_323.D002.LIC_323507.pv' },
      // ---- screen-nav hotspots (slide comment "LINK TO PAGE ...") ----
      { k: 'nav3232323e003', t: 'nav', x: 1264, y: 62, w: 92, h: 21, tag: '323E003 -> 323-2', goto: 'screen-323-2' },
      { k: 'nav3232323e011', t: 'nav', x: 1264, y: 112, w: 92, h: 21, tag: '323E011 -> 323-2', goto: 'screen-323-2' },
      { k: 'nav3241324e002', t: 'nav', x: 1265, y: 180, w: 92, h: 21, tag: '324E002 -> 324-1', goto: 'screen-324-1' },
      { k: 'nav3291322d001ab2', t: 'nav', x: 54, y: 326, w: 92, h: 37, tag: '322D001 A/B -> 329-1', goto: 'screen-329-1' },
      { k: 'nav3291322d001ab', t: 'nav', x: 1257, y: 380, w: 92, h: 33, tag: '322D001 A/B -> 329-1', goto: 'screen-329-1' },
      { k: 'nav3221322e001', t: 'nav', x: 52, y: 587, w: 92, h: 21, tag: '322E001 -> 322-1', goto: 'screen-322-1' },
      { k: 'nav3241323p003ab', t: 'nav', x: 1260, y: 641, w: 100, h: 21, tag: '323P003A/B -> 324-1', goto: 'screen-324-1' },
    ],
    // ============================ 323-2  LP RECIRCULATION 2  (323D001 / 323E003 / 323E011 / 323C005) ============================
    // Seed geometry = the shape centres of UI Pages/323-2.pptx, 12192000x6858000 EMU -> 1366x720
    // stage.  The background PNG is that slide with exactly these shapes deleted, so every
    // overlay lands in the hole its own symbol left.  root LPCC_3232, with DESORB_328.D001 and 328C002 cross-refs drawn on this screen.
    'screen-323-2': [
      // ---- indicators, controllers and modulating-valve openings ----
      { k: 'pic323203', t: 'ind', x: 1183, y: 38, tag: 'PIC-323203', bind: 'LPCC_3232.E011.PIC_323203.pv', u: 'BAR A', dec: 2, mode: 'LPCC_3232.E011.PIC_323203.mode', note: '323E011/D011 LP node P; flash vapour 701 (LV-323501 -> 323F004) accumulates it. AUTO holds SP via PV-323203; MAN lets P ramp' },
      { k: 'pic328202', t: 'ind', x: 705, y: 86, tag: 'PIC-328202', bind: 'DESORB_328.D001.PIC_328202.pv', u: 'BAR A', dec: 2, mode: 'DESORB_328.D001.PIC_328202.mode', note: '323F004/328D001 reflux drum pressure via PV-328202' },
      { k: 'tt323005', t: 'ind', x: 50, y: 213, tag: 'TT-323005', bind: 'RECIRC_323.F004.TT_323005', u: 'C', dec: 1 },
      { k: 'tt323015', t: 'ind', x: 496, y: 238, tag: 'TT-323015', bind: 'LPCC_3232.E003.TT_323015', u: 'C', dec: 1 },
      { k: 'tt329007', t: 'ind', x: 853, y: 258, tag: 'TT-329007', bind: 'DESORB_328.D001.TT_329007', u: 'C', dec: 1 },
      { k: 'fic323402', t: 'ind', x: 1263, y: 313, tag: 'FIC-323402', bind: 'LPCC_3232.E011.FIC_323402.pv', u: 'M3/H', dec: 2, mode: 'LPCC_3232.E011.FIC_323402.mode', note: '328D003 Comp-I wash to 323E011, PFD stream 791, via FV-323402' },
      { k: 'lic328501', t: 'ind', x: 504, y: 316, tag: 'LIC-328501', bind: 'DESORB_328.D001.LIC_328501.pv', u: '%', dec: 1, mode: 'DESORB_328.D001.LIC_328501.mode', note: 'holds 328D001 level via LV-328501' },
      { k: 'pic323202', t: 'ind', x: 195, y: 319, tag: 'PIC-323202', bind: 'LPCC_3232.E003.PIC_323202.pv', u: 'BAR A', dec: 2, mode: 'LPCC_3232.E003.PIC_323202.mode', note: 'holds 323D001 off-gas pressure via PV-323202 vent to GCB' },
      { k: 'tic323013', t: 'ind', x: 322, y: 332, tag: 'TIC-323013', bind: 'LPCC_3232.E003.TIC_323013.pv', u: 'C', dec: 1, mode: 'LPCC_3232.E003.TIC_323013.mode', note: 'holds 323E003 tempered-water supply temp (55 C) via the TV-323013A/B split range' },
      { k: 'fic328405', t: 'ind', x: 902, y: 357, tag: 'FIC-328405', bind: 'LPCC_3232.C005.FIC_328405.pv', u: 'M3/H', dec: 2, mode: 'LPCC_3232.C005.FIC_328405.mode', note: 'Ammonia-water stream 793, normally-closed spare off the 328D003 Comp-I discharge header, via FV-328405; loop PV/SP are VOLUMETRIC (PFD des 0 m3/h = 0 kg/h; full stroke 1.55 m3/h = 1534 kg/h at rho 992.4)' },
      { k: 'tic328002', t: 'ind', x: 661, y: 368, tag: 'TIC-328002', bind: 'DESORB_328.D001.TIC_328002.pv', u: 'C', dec: 1, mode: 'DESORB_328.D001.TIC_328002.mode', note: '328D001 reflux temp via TV-328002' },
      { k: 'lt323502', t: 'ind', x: 94, y: 400, tag: 'LT-323502', bind: 'LPCC_3232.E003.LI_323502', u: '%', dec: 1 },
      { k: 'tt323006', t: 'ind', x: 290, y: 412, tag: 'TT-323006', bind: 'LPCC_3232.E003.TT_323006', u: 'C', dec: 1 },
      { k: 'ft328401', t: 'ind', x: 580, y: 494, tag: 'FT-328401', bind: 'DESORB_328.D001.flow776_m3h', u: 'M3/H', dec: 1, note: '328D001 bottoms draw (stream 776) via LV-328501, des 7.6 m3/h' },
      { k: 'lic323503', t: 'ind', x: 1014, y: 517, tag: 'LIC-323503', bind: 'LPCC_3232.C005.LIC_323503.pv', u: '%', dec: 1, mode: 'LPCC_3232.C005.LIC_323503.mode', note: 'holds 323C005 bottoms level via LV-323503 drain' },
      { k: 'tt323011', t: 'ind', x: 988, y: 553, tag: 'TT-323011', bind: 'LPCC_3232.E011.TT_323011', u: 'C', dec: 1 },
      { k: 'fic323418', t: 'ind', x: 625, y: 555, tag: 'FIC-323418', bind: 'LPCC_3232.C005.FIC_323418.pv', u: 'M3/H', dec: 2, mode: 'LPCC_3232.C005.FIC_323418.mode', note: '718B carbamate slipstream, 323C005 bottoms to 323E003; loop PV/SP are VOLUMETRIC (des 3.34 m3/h = 3560.4 kg/h at rho 1065)' },
      { k: 'sic323901', t: 'ind', x: 120, y: 578, tag: 'SIC-323901', bind: 'LPCC_3232.E003.SIC_323901.pv', u: 'RPM', dec: 0, mode: 'LPCC_3232.E003.SIC_323901.mode', note: '323P001A pump speed; MAN/AUTO/CAS' },
      { k: 'sic323902', t: 'ind', x: 266, y: 578, tag: 'SIC-323902', bind: 'LPCC_3232.E003.SIC_323902.pv', u: 'RPM', dec: 0, mode: 'LPCC_3232.E003.SIC_323902.mode', note: '323P001B pump speed; MAN/AUTO/CAS' },
      { k: 'fic328404', t: 'ind', x: 1099, y: 642, tag: 'FIC-328404', bind: 'DESORB_328.D001.FIC_328404.pv', u: 'M3/H', dec: 2, mode: 'DESORB_328.D001.FIC_328404.mode', cas: true, note: 'CAS slave of TIC-328008 (offgas H2O): FV-328404 strokes the 775 reflux to hold it; PFD stream 775' },
      { k: 'fic323401', t: 'ind', x: 556, y: 653, tag: 'FIC-323401', bind: 'LPCC_3232.E011.FIC_323401.pv', u: 'M3/H', dec: 2, mode: 'LPCC_3232.E011.FIC_323401.mode', note: '323E011 draw / PFD 401 flush via FV-323401; loop PV/SP are VOLUMETRIC (des 0.83 m3/h = 823 kg/h at rho 992.4)' },
      { k: 'pv323203', t: 'avalve', x: 1106, y: 92, tag: 'PV-323203', bind: 'LPCC_3232.E011.PIC_323203.op', u: '%', dec: 1 },
      { k: 'pv323202', t: 'avalve', x: 48, y: 173, tag: 'PV-323202', bind: 'LPCC_3232.E003.PIC_323202.op', u: '%', dec: 1 },
      { k: 'pv328202', t: 'avalve', x: 563, y: 178, tag: 'PV-328202', bind: 'DESORB_328.D001.PIC_328202.op', u: '%', dec: 1 },
      { k: 'tv328002', t: 'avalve', x: 840, y: 218, tag: 'TV-328002', bind: 'DESORB_328.D001.TIC_328002.op', u: '%', dec: 1 },
      { k: 'tv323013a', t: 'avalve', x: 320, y: 228, tag: 'TV-323013A', bind: 'LPCC_3232.E003.TV_323013A', u: '%', dec: 1 },
      { k: 'tv323013b', t: 'avalve', x: 328, y: 259, tag: 'TV-323013B', bind: 'LPCC_3232.E003.TV_323013B', u: '%', dec: 1 },
      { k: 'fv323402', t: 'avalve', x: 1190, y: 291, tag: 'FV-323402', bind: 'LPCC_3232.E011.FIC_323402.op', u: '%', dec: 1 },
      { k: 'fv328405', t: 'avalve', x: 902, y: 407, tag: 'FV-328405', bind: 'LPCC_3232.C005.FIC_328405.op', u: '%', dec: 1 },
      { k: 'lv328501', t: 'avalve', x: 510, y: 491, tag: 'LV-328501', bind: 'DESORB_328.D001.LIC_328501.op', u: '%', dec: 1 },
      { k: 'lv323503', t: 'avalve', x: 810, y: 497, tag: 'LV-323503', bind: 'LPCC_3232.C005.LIC_323503.op', u: '%', dec: 1 },
      { k: 'fv323418', t: 'avalve', x: 582, y: 596, tag: 'FV-323418', bind: 'LPCC_3232.C005.FIC_323418.op', u: '%', dec: 1 },
      { k: 'fv323401', t: 'avalve', x: 518, y: 690, tag: 'FV-323401', bind: 'LPCC_3232.E011.FIC_323401.op', u: '%', dec: 1 },
      // ---- level bargraphs (fill height = bound level, 0-100 %) ----
      { k: 'barlic328501', t: 'bar', x: 572, y: 295, w: 16, h: 58, tag: 'LIC-328501', bind: 'DESORB_328.D001.LIC_328501.pv' },
      { k: 'barlt323502', t: 'bar', x: 169, y: 416, w: 17, h: 83, tag: 'LT-323502', bind: 'LPCC_3232.E003.LI_323502' },
      { k: 'barlic323503', t: 'bar', x: 901, y: 493, w: 14, h: 52, tag: 'LIC-323503', bind: 'LPCC_3232.C005.LIC_323503.pv' },
      // ---- pumps: A duty (drawn running), B installed standby (drawn stopped) ----
      { k: 'p329p003a', t: 'pump', x: 387.4, y: 124.8, w: 37.8, h: 32.7, rot: 180, tag: '329P003A' },
      { k: 'p329p003b', t: 'pump', x: 387.1, y: 189.3, w: 37.8, h: 32.7, rot: 180, tag: '329P003B', def: false },
      { k: 'p328p002a', t: 'pump', x: 561, y: 417.4, w: 37.8, h: 32.7, rot: 90, tag: '328P002A' },
      { k: 'p328p002b', t: 'pump', x: 628.5, y: 417.4, w: 37.8, h: 32.7, rot: 90, tag: '328P002B', def: false },
      { k: 'p323p001a', t: 'pump', x: 160.7, y: 551, w: 37.8, h: 32.7, rot: 90, tag: '323P001A' },
      { k: 'p323p001b', t: 'pump', x: 228.2, y: 551, w: 37.8, h: 32.7, rot: 90, tag: '323P001B', def: false },
      { k: 'p323p008a', t: 'pump', x: 888.7, y: 585.5, w: 37.8, h: 32.7, rot: 90, tag: '323P008A' },
      { k: 'p323p008b', t: 'pump', x: 955.1, y: 585.9, w: 37.8, h: 32.7, rot: 90, tag: '323P008B', def: false },
      // ---- screen-nav hotspots (slide comment "LINK TO PAGE ...") ----
      { k: 'nav3231323f004', t: 'nav', x: 1276, y: 37, w: 92, h: 21, tag: '323F004 -> 323-1', goto: 'screen-323-1' },
      { k: 'nav3231323c003', t: 'nav', x: 58, y: 68, w: 92, h: 21, tag: '323C003 -> 323-1', goto: 'screen-323-1' },
      { k: 'nav3282323c005', t: 'nav', x: 1299, y: 77, w: 92, h: 21, tag: '323C005 -> 328-2', goto: 'screen-328-2' },
      { k: 'nav3281328c0023', t: 'nav', x: 800, y: 85, w: 92, h: 21, tag: '328C002 -> 328-1', goto: 'screen-328-1' },
      { k: 'nav3231323f0042', t: 'nav', x: 1299, y: 108, w: 92, h: 21, tag: '323F004 -> 323-1', goto: 'screen-323-1' },
      { k: 'nav3281328p003ab', t: 'nav', x: 1311, y: 394, w: 101, h: 21, tag: '328P003A/B -> 328-1', goto: 'screen-328-1' },
      { k: 'nav3281328c002', t: 'nav', x: 1309, y: 421, w: 92, h: 21, tag: '328C002 -> 328-1', goto: 'screen-328-1' },
      { k: 'nav3222322e004', t: 'nav', x: 63, y: 632, w: 92, h: 21, tag: '322E004 -> 322-2', goto: 'screen-322-2' },
      { k: 'nav3281328c0022', t: 'nav', x: 1289, y: 661, w: 92, h: 21, tag: '328C002 -> 328-1', goto: 'screen-328-1' },
    ],
    // ============================ 328-1  DESORPTION  (328C002 / 328C003 hydrolyser / 328C004 / 328D001) ============================
    // Seed geometry = the shape centres of UI Pages/328-1.pptx, 12192000x6858000 EMU -> 1366x720
    // stage.  The background PNG is that slide with exactly these shapes deleted, so every
    // overlay lands in the hole its own symbol left.  root DESORB_328, with ABSORB_328.D003 and LPCC_3232.E003 cross-refs.
    'screen-328-1': [
      // ---- indicators, controllers and modulating-valve openings ----
      { k: 'tic328008', t: 'ind', x: 704, y: 111, tag: 'TIC-328008', bind: 'DESORB_328.D001.TIC_328008.pv', u: '%', dec: 1, mode: 'DESORB_328.D001.TIC_328008.mode', note: 'MASTER of FIC-328404: water content in the 328C002 -> 328E004 gas line (mol%, PFD 737 = 46.2). With FIC-328404 on CAS, FV-328404 strokes the 775 reflux to hold this' },
      { k: 'tt328008', t: 'ind', x: 916, y: 112, tag: 'TT-328008', bind: 'DESORB_328.C002.TT_328008', u: 'C', dec: 1 },
      { k: 'tt3280102', t: 'ind', x: 782, y: 127, tag: 'TT-328010', bind: 'DESORB_328.C002.TT_328010', u: 'C', dec: 1 },
      { k: 'fic328404', t: 'ind', x: 581, y: 130, tag: 'FIC-328404', bind: 'DESORB_328.D001.FIC_328404.pv', u: 'M3/H', dec: 2, mode: 'DESORB_328.D001.FIC_328404.mode', cas: true, note: 'CAS slave of TIC-328008 (offgas H2O): FV-328404 strokes the 775 reflux to hold it; PFD stream 775' },
      { k: 'pic328202', t: 'ind', x: 856, y: 168, tag: 'PIC-328202', bind: 'DESORB_328.D001.PIC_328202.pv', u: 'BAR A', dec: 2, mode: 'DESORB_328.D001.PIC_328202.mode', note: '323F004/328D001 reflux drum pressure via PV-328202' },
      { k: 'tt328010', t: 'ind', x: 768, y: 196, tag: 'TT-328010', bind: 'DESORB_328.C002.TT_328010', u: 'C', dec: 1 },
      { k: 'pic328203', t: 'ind', x: 196, y: 235, tag: 'PIC-328203', bind: 'DESORB_328.C003.PIC_328203.pv', u: 'BAR A', dec: 2, mode: 'DESORB_328.C003.PIC_328203.mode', note: '328C003 overhead pressure via PV-328203' },
      { k: 'ffic329401sp', t: 'ind', x: 1017, y: 252, tag: 'FFIC-329401 SP', bind: 'DESORB_328.C004.FFIC_329401.sp', u: 'T/M3', dec: 3, ctl: 'FFIC-329401', ctlBind: 'DESORB_328.C004.FFIC_329401.pv' },
      { k: 'lic328503', t: 'ind', x: 591, y: 264, tag: 'LIC-328503', bind: 'DESORB_328.C002.LIC_328503.pv', u: '%', dec: 1, mode: 'DESORB_328.C002.LIC_328503.mode', note: 'holds 328C002 level via LV-328503' },
      { k: 'tt328012', t: 'ind', x: 280, y: 281, tag: 'TT-328012', bind: 'DESORB_328.C003.TT_328012', u: 'C', dec: 1 },
      { k: 'ffic329401mv', t: 'ind', x: 1018, y: 284, tag: 'FFIC-329401 MV', bind: 'DESORB_328.C004.FFIC_329401.op', u: 'KG/H', dec: 1, ctl: 'FFIC-329401', ctlBind: 'DESORB_328.C004.FFIC_329401.pv', ctlU: 'T/M3', note: 'controller output of FFIC-329401 (the 931 steam demand to FIC-329401, kg/h)' },
      { k: 'lic328504', t: 'ind', x: 447, y: 293, tag: 'LIC-328504', bind: 'DESORB_328.C003.LIC_328504.pv', u: '%', dec: 1, mode: 'DESORB_328.C003.LIC_328504.mode', note: 'the slide prints LIC-328503 at this position; it labels the leg whose bargraph is commented LIC-328504 (slide typo)' },
      { k: 'tic328012', t: 'ind', x: 278, y: 334, tag: 'TIC-328012', bind: 'DESORB_328.C003.TIC_328012.pv', u: 'C', dec: 1, mode: 'DESORB_328.C003.TIC_328012.mode', note: '328C003 bottom temp cascades FIC-329402 MP steam' },
      { k: 'tt328004', t: 'ind', x: 782, y: 363, tag: 'TT-328004', bind: 'DESORB_328.C004.TT_328004', u: 'C', dec: 1 },
      { k: 'fic329401', t: 'ind', x: 1188, y: 397, tag: 'FIC-329401', bind: 'DESORB_328.C004.FIC_329401.pv', u: 'KG/H', dec: 1, mode: 'DESORB_328.C004.FIC_329401.mode', cas: true, note: 'slave: CAS follows FFIC-329401 ratio on the FIC-328402 feed; LP steam via FV-329401' },
      { k: 'fic329402', t: 'ind', x: 112, y: 424, tag: 'FIC-329402', bind: 'DESORB_328.C003.FIC_329402.pv', u: 'KG/H', dec: 0, mode: 'DESORB_328.C003.FIC_329402.mode', cas: true, note: 'slave: MP steam (911) injected direct into 328C003 via FV-329402' },
      { k: 'fic328406', t: 'ind', x: 1220, y: 470, tag: 'FIC-328406', bind: 'ABSORB_328.D003.FIC_328406.pv', u: 'M3/H', dec: 2, mode: 'ABSORB_328.D003.FIC_328406.mode', note: '328E007 -> 328E001 -> 328D003 Comp-II process-condensate recycle, PFD stream 741 (0 at normal operation), via FV-328406' },
      { k: 'lic328505', t: 'ind', x: 766, y: 484, tag: 'LIC-328505', bind: 'DESORB_328.C004.LIC_328505.pv', u: '%', dec: 1, mode: 'DESORB_328.C004.LIC_328505.mode', note: 'holds 328C004 bottom level via LV-328505' },
      { k: 'tt328009', t: 'ind', x: 200, y: 487, tag: 'TT-328009', bind: 'DESORB_328.C003.TT_328009', u: 'C', dec: 1 },
      { k: 'tt328013', t: 'ind', x: 279, y: 496, tag: 'TT-328013', bind: 'DESORB_328.C003.TT_328C003', u: 'C', dec: 1 },
      { k: 'tt328005', t: 'ind', x: 606, y: 507, tag: 'TT-328005', bind: 'DESORB_328.C004.TT_328005', u: 'C', dec: 1 },
      { k: 'tt328007', t: 'ind', x: 549, y: 639, tag: 'TT-328007', bind: 'DESORB_328.C002.TT_328007', u: 'C', dec: 1 },
      { k: 'tt328006', t: 'ind', x: 902, y: 648, tag: 'TT-328006', bind: 'DESORB_328.C004.TT_328006', u: 'C', dec: 1 },
      { k: 'fic328402', t: 'ind', x: 727, y: 649, tag: 'FIC-328402', bind: 'LPCC_3232.E003.FIC_328402.pv', u: 'M3/H', dec: 2, mode: 'LPCC_3232.E003.FIC_328402.mode', note: 'Comp-II wash draw off 323E003 to 328D003 compartment II, PFD stream 744 (31478 kg/h = 31.4 m3/h des), via FV-328402' },
      { k: 'ai328701', t: 'ind', x: 826, y: 649, tag: 'AI-328701', bind: 'DESORB_328.C004.AI_328701', u: 'uS/cm', dec: 2 },
      { k: 'fv328404', t: 'avalve', x: 485, y: 161, tag: 'FV-328404', bind: 'DESORB_328.D001.FIC_328404.op', u: '%', dec: 1 },
      { k: 'pv328203', t: 'avalve', x: 419, y: 204, tag: 'PV-328203', bind: 'DESORB_328.C003.PIC_328203.op', u: '%', dec: 1 },
      { k: 'lv328503', t: 'avalve', x: 266, y: 386, tag: 'LV-328503', bind: 'DESORB_328.C002.LIC_328503.op', u: '%', dec: 1 },
      { k: 'lv328504', t: 'avalve', x: 594, y: 424, tag: 'LV-328504', bind: 'DESORB_328.C003.LIC_328504.op', u: '%', dec: 1 },
      { k: 'fv329401', t: 'avalve', x: 1042, y: 427, tag: 'FV-329401', bind: 'DESORB_328.C004.FIC_329401.op', u: '%', dec: 1 },
      { k: 'fv329402', t: 'avalve', x: 144, y: 464, tag: 'FV-329402', bind: 'DESORB_328.C003.FIC_329402.op', u: '%', dec: 1 },
      { k: 'fv328406', t: 'avalve', x: 1168, y: 509, tag: 'FV-328406', bind: 'ABSORB_328.D003.FIC_328406.op', u: '%', dec: 1 },
      { k: 'lv328505', t: 'avalve', x: 1116, y: 652, tag: 'LV-328505', bind: 'DESORB_328.C004.LIC_328505.op', u: '%', dec: 1 },
      { k: 'fv328402', t: 'avalve', x: 686, y: 689, tag: 'FV-328402', bind: 'LPCC_3232.E003.FIC_328402.op', u: '%', dec: 1 },
      // ---- level bargraphs (fill height = bound level, 0-100 %) ----
      { k: 'barlic328503', t: 'bar', x: 684, y: 252, w: 20, h: 82, tag: 'LIC-328503', bind: 'DESORB_328.C002.LIC_328503.pv' },
      { k: 'barlic328504', t: 'bar', x: 353, y: 283, w: 20, h: 93, tag: 'LIC-328504', bind: 'DESORB_328.C003.LIC_328504.pv' },
      { k: 'barlic328505', t: 'bar', x: 684, y: 446, w: 20, h: 82, tag: 'LIC-328505', bind: 'DESORB_328.C004.LIC_328505.pv' },
      // ---- pumps: A duty (drawn running), B installed standby (drawn stopped) ----
      { k: 'p328p007a', t: 'pump', x: 957, y: 576, w: 27.8, h: 24, tag: '328P007A' },
      { k: 'p328p007b', t: 'pump', x: 957, y: 623.8, w: 27.8, h: 24, tag: '328P007B', def: false },
      { k: 'p328p006a', t: 'pump', x: 381.2, y: 627, w: 27.8, h: 24, fx: true, tag: '328P006A' },
      { k: 'p328p006b', t: 'pump', x: 381.2, y: 674.7, w: 27.8, h: 24, fx: true, tag: '328P006B', def: false },
      // ---- screen-nav hotspots (slide comment "LINK TO PAGE ...") ----
      { k: 'nav3232328p002ab', t: 'nav', x: 54, y: 104, w: 105, h: 21, tag: '328P002 A/B -> 323-2', goto: 'screen-323-2' },
      { k: 'nav3232328e004', t: 'nav', x: 1299, y: 140, w: 105, h: 21, tag: '328E004 -> 323-2', goto: 'screen-323-2' },
      { k: 'nav3232pv328202', t: 'nav', x: 1300, y: 169, w: 105, h: 21, tag: 'PV-328202 -> 323-2', goto: 'screen-323-2' },
      { k: 'nav3291322d001ab', t: 'nav', x: 1307, y: 371, w: 105, h: 21, tag: '322D001 A/B -> 329-1', goto: 'screen-329-1' },
      { k: 'nav3291stmh', t: 'nav', x: 52, y: 450, w: 92, h: 21, tag: 'STMH -> 329-1', goto: 'screen-329-1' },
      { k: 'nav3282328d003', t: 'nav', x: 1311, y: 494, w: 105, h: 21, tag: '328D003 -> 328-2', goto: 'screen-328-2' },
      { k: 'nav3282328p003ab', t: 'nav', x: 1311, y: 675, w: 105, h: 21, tag: '328P003 A/B -> 328-2', goto: 'screen-328-2' },
    ],
    // ============================ 328-2  ABSORPTION  (322C001 GCB absorber / 328D003 collection tank) ============================
    // Seed geometry = the shape centres of UI Pages/328-2.pptx, 12192000x6858000 EMU -> 1366x720
    // stage.  The background PNG is that slide with exactly these shapes deleted, so every
    // overlay lands in the hole its own symbol left.  root ABSORB_328 (C001 absorber / D003 collection tank).
    'screen-328-2': [
      // ---- indicators, controllers and modulating-valve openings ----
      { k: 'tt322015', t: 'ind', x: 427, y: 81, tag: 'TT-322015', bind: 'ABSORB_328.C001.TT_322015', u: 'C', dec: 1 },
      { k: 'ft322404', t: 'ind', x: 164, y: 142, tag: 'FT-322404', bind: 'ABSORB_328.C001.cpl_kgh', u: 'KG/H', dec: 0, face: 'hic', note: 'FT-322404 condensate 954 -> 322C001; operator-set inlet flow (kg/h), des 1750' },
      { k: 'pic322201', t: 'ind', x: 471, y: 168, tag: 'PIC-322201', bind: 'ABSORB_328.C001.PIC_322201.pv', u: 'BAR A', dec: 2, mode: 'ABSORB_328.C001.PIC_322201.mode', note: 'holds 322C001 top pressure via PV-322201 to 328V001' },
      { k: 'ft322402', t: 'ind', x: 166, y: 323, tag: 'FT-322402', bind: 'ABSORB_328.D003.flow755_m3h', u: 'M3/H', dec: 1, note: '322P002 collector draw (stream 755, Amm. Water) -> 322C001, des 31.3 m3/h' },
      { k: 'tt323009', t: 'ind', x: 801, y: 336, tag: 'TT-323009', bind: 'LPCC_3232.C005.TT_323C005', u: 'C', dec: 1 },
      { k: 'lic322502', t: 'ind', x: 471, y: 358, tag: 'LIC-322502', bind: 'ABSORB_328.C001.LIC_322502.pv', u: '%', dec: 1, mode: 'ABSORB_328.C001.LIC_322502.mode', note: 'holds 322C001 sump level via LV-322502' },
      { k: 'tt323010', t: 'ind', x: 583, y: 364, tag: 'TT-323010', bind: 'RECIRC_323.F010.TT_323010', u: 'C', dec: 1 },
      { k: 'tt328015', t: 'ind', x: 846, y: 471, tag: 'TT-328015', bind: 'ABSORB_328.D003.TT_328II', u: 'C', dec: 1 },
      { k: 'lt328507', t: 'ind', x: 1167, y: 509, tag: 'LT-328507', bind: 'ABSORB_328.D003.LT_328507_open_loop', u: '%', dec: 1 },
      { k: 'lt328508', t: 'ind', x: 843, y: 515, tag: 'LT-328508', bind: 'ABSORB_328.D003.LT_328508_open_loop', u: '%', dec: 1 },
      { k: 'pv322201', t: 'avalve', x: 341, y: 116, tag: 'PV-322201', bind: 'ABSORB_328.C001.PIC_322201.op', u: '%', dec: 1 },
      { k: 'lv322502', t: 'avalve', x: 341, y: 437, tag: 'LV-322502', bind: 'ABSORB_328.C001.LIC_322502.op', u: '%', dec: 1 },
      // ---- level bargraphs (fill height = bound level, 0-100 %) ----
      { k: 'barlic322502', t: 'bar', x: 379, y: 328, w: 20, h: 98, tag: 'LIC-322502', bind: 'ABSORB_328.C001.LIC_322502.pv' },
      { k: 'barlt328508', t: 'bar', x: 1002, y: 515, w: 24, h: 91, tag: 'LT-328508', bind: 'ABSORB_328.D003.LT_328508_open_loop' },
      { k: 'barlt328507', t: 'bar', x: 1079, y: 517, w: 24, h: 91, tag: 'LT-328507', bind: 'ABSORB_328.D003.LT_328507_open_loop' },
      // ---- pumps: A duty (drawn running), B installed standby (drawn stopped) ----
      { k: 'p328p003a', t: 'pump', x: 1153.4, y: 575.8, w: 27.8, h: 24, tag: '328P003A' },
      { k: 'p322p002a', t: 'pump', x: 622.8, y: 604.6, w: 27.8, h: 24, fx: true, tag: '322P002A' },
      { k: 'p328p003b', t: 'pump', x: 1153.4, y: 623.5, w: 27.8, h: 24, tag: '328P003B', def: false },
      { k: 'p322p002b', t: 'pump', x: 622.8, y: 652.3, w: 27.8, h: 24, fx: true, tag: '322P002B', def: false },
      // ---- block valves and external-override pushbuttons ----
      { k: 'xv322915', t: 'xv', x: 272.7, y: 91, w: 44.1, h: 20.5, tag: 'XV-322915', bind: 'ABSORB_328.C001.XV_322915', cmd: '322915' },
      { k: 'ovrxv322915', t: 'ovrd', x: 250, y: 42, tag: 'EXT-OVR XV-322915', cmd: '322915', xv: 'ABSORB_328.C001.XV_322915', latch: '22_1', note: 'external override on XV-322915; lamp lit while the 22.1 steam-flood interlock is latched' },
      // ---- screen-nav hotspots (slide comment "LINK TO PAGE ...") ----
      { k: 'nav3291stls', t: 'nav', x: 52, y: 91, w: 92, h: 21, tag: 'STLS -> 329-1', goto: 'screen-329-1' },
      { k: 'nav3241b324e007', t: 'nav', x: 1311, y: 164, w: 92, h: 21, tag: '324E007 -> 324-1b', goto: 'screen-324-1b' },
      { k: 'nav3232323d011', t: 'nav', x: 1309, y: 222, w: 92, h: 21, tag: '323D011 -> 323-2', goto: 'screen-323-2' },
      { k: 'nav3241324f002', t: 'nav', x: 1309, y: 250, w: 92, h: 21, tag: '324F002 -> 324-1', goto: 'screen-324-1' },
      { k: 'nav3281328e001', t: 'nav', x: 1309, y: 294, w: 92, h: 21, tag: '328E001 -> 328-1', goto: 'screen-328-1' },
      { k: 'nav3241324e002', t: 'nav', x: 1309, y: 320, w: 92, h: 21, tag: '324E002 -> 324-1', goto: 'screen-324-1' },
      { k: 'nav3241b324e005', t: 'nav', x: 1309, y: 348, w: 92, h: 21, tag: '324E005 -> 324-1b', goto: 'screen-324-1b' },
      { k: 'nav3222322e003', t: 'nav', x: 52, y: 350, w: 92, h: 21, tag: '322E003 -> 322-2', goto: 'screen-322-2' },
      { k: 'nav3241b324e006', t: 'nav', x: 1309, y: 371, w: 92, h: 21, tag: '324E006 -> 324-1b', goto: 'screen-324-1b' },
      { k: 'nav3241b324e0072', t: 'nav', x: 1309, y: 395, w: 92, h: 21, tag: '324E007 -> 324-1b', goto: 'screen-324-1b' },
    ],
    // ============================ 324-1  EVAPORATION STAGE 1  (324E001 vacuum evaporator / 324F001 separator) ============================
    // Seed geometry = the shape centres of UI Pages/324-1.pptx, 12192000x6858000 EMU -> 1366x720
    // stage.  The background PNG is that slide with exactly these shapes deleted, so every
    // overlay lands in the hole its own symbol left.  root EVAP_324.E001; cross-refs RECIRC_323.D002 (feed) and .F010 (pre-evap).
    'screen-324-1': [
      // ---- indicators, controllers and modulating-valve openings ----
      { k: 'pic324202', t: 'ind', x: 582, y: 111, tag: 'PIC-324202', bind: 'EVAP_324.E001.PIC_324202.pv', u: 'BAR A', dec: 3, mode: 'EVAP_324.E001.PIC_324202.mode', note: 'holds 324F001 vacuum 0.33 bar a via false-air PV-324202' },
      { k: 'hic329605', t: 'ind', x: 855, y: 222, tag: 'HIC-329605', bind: 'EVAP_324.E001.HIC_329605', u: '%', dec: 1, face: 'hic', note: '324F002 vacuum-ejector motive LP steam; operator hand valve (HV-329605 tracks 1:1)' },
      { k: 'pt324201', t: 'ind', x: 475, y: 226, tag: 'PT-324201', bind: 'EVAP_324.E001.PT_324202', u: 'BAR A', dec: 3, note: '324F001 separator pressure' },
      { k: 'hic323605', t: 'ind', x: 520, y: 255, tag: 'HIC-323605', bind: 'RECIRC_323.F010.HV_323605', u: '%', dec: 1, face: 'hic' },
      { k: 'hv323605', t: 'ind', x: 615, y: 255, tag: 'HV-323605', bind: 'RECIRC_323.F010.HV_323605', u: '%', dec: 1, face: 'hic' },
      { k: 'hv329605', t: 'ind', x: 854, y: 272, tag: 'HV-329605', bind: 'EVAP_324.E001.HV_329605', u: '%', dec: 1, face: 'hic' },
      { k: 'py324201', t: 'ind', x: 475, y: 280, tag: 'PY-324201', bind: 'EVAP_324.E001.PY_324201', u: 'wt%', dec: 1, note: '324F001 melt concentration soft-sensor (VLE inversion of PT-324201 / TIC-324001)' },
      { k: 'pic329203', t: 'ind', x: 251, y: 335, tag: 'PIC-329203', bind: 'EVAP_324.E001.PIC_329203.pv', u: 'BAR A', dec: 2, mode: 'EVAP_324.E001.PIC_329203.mode', cas: true, note: 'slave: CAS follows TIC-324001; steam to 324E001 chest via PV-329203' },
      { k: 'pt323204', t: 'ind', x: 736, y: 347, tag: 'PT-323204', bind: 'RECIRC_323.F010.P_bara', u: 'BAR A', dec: 2 },
      { k: 'tic324001', t: 'ind', x: 475, y: 375, tag: 'TIC-324001', bind: 'EVAP_324.E001.TIC_324001.pv', u: 'C', dec: 1, mode: 'EVAP_324.E001.TIC_324001.mode', note: 'master: holds melt 130 C; cascades PIC-329203 chest steam-P' },
      { k: 'lic329505', t: 'ind', x: 283, y: 408, tag: 'LIC-329505', bind: 'EVAP_324.E001.LIC_329505.pv', u: '%', dec: 1, mode: 'EVAP_324.E001.LIC_329505.mode', note: '324E001 steam-condensate level; LV-329505 drains shell (active steam trap)' },
      { k: 'fic324401', t: 'ind', x: 311, y: 545, tag: 'FIC-324401', bind: 'RECIRC_323.D002.FIC_324401.pv', u: 'T/H', dec: 2, mode: 'RECIRC_323.D002.FIC_324401.mode', cas: true, note: 'slave: CAS follows LIC-323507; product to 324 evap via 323P003 A/B' },
      { k: 'pv324202', t: 'avalve', x: 205, y: 202, tag: 'PV-324202', bind: 'EVAP_324.E001.PIC_324202.op', u: '%', dec: 1 },
      { k: 'pv329203', t: 'avalve', x: 166, y: 396, tag: 'PV-329203', bind: 'EVAP_324.E001.PIC_329203.op', u: '%', dec: 1 },
      { k: 'lv329505', t: 'avalve', x: 217, y: 453, tag: 'LV-329505', bind: 'EVAP_324.E001.LIC_329505.op', u: '%', dec: 1 },
      { k: 'fv324401', t: 'avalve', x: 397, y: 518, tag: 'FV-324401', bind: 'RECIRC_323.D002.FIC_324401.op', u: '%', dec: 1 },
      // ---- level bargraphs (fill height = bound level, 0-100 %) ----
      { k: 'barlic329505', t: 'bar', x: 364, y: 412, w: 20, h: 72, tag: 'LIC-329505', bind: 'EVAP_324.E001.LIC_329505.pv' },
      // ---- pumps: A duty (drawn running), B installed standby (drawn stopped) ----
      { k: 'p323p003a', t: 'pump', x: 250.2, y: 571.2, w: 27.8, h: 24, tag: '323P003A' },
      { k: 'p323p003b', t: 'pump', x: 250.2, y: 619, w: 27.8, h: 24, tag: '323P003B', def: false },
      // ---- screen-nav hotspots (slide comment "LINK TO PAGE ...") ----
      { k: 'nav3282323c005', t: 'nav', x: 1304, y: 260, w: 105, h: 21, tag: '323C005 -> 328-2', goto: 'screen-328-2' },
      { k: 'nav3282328d003', t: 'nav', x: 1303, y: 314, w: 105, h: 21, tag: '328D003 -> 328-2', goto: 'screen-328-2' },
      { k: 'nav3231323f010', t: 'nav', x: 1303, y: 374, w: 105, h: 21, tag: '323F010 -> 323-1', goto: 'screen-323-1' },
      { k: 'nav3291322d001ab', t: 'nav', x: 62, y: 380, w: 105, h: 21, tag: '322D001 A/B -> 329-1', goto: 'screen-329-1' },
      { k: 'nav3241b324e003', t: 'nav', x: 1303, y: 422, w: 105, h: 21, tag: '324E003 -> 324-1b', goto: 'screen-324-1b' },
      { k: 'nav3231323d002', t: 'nav', x: 60, y: 594, w: 105, h: 21, tag: '323D002 -> 323-1', goto: 'screen-323-1' },
    ],
    // ============================ 324-1b  EVAPORATION STAGE 2  (324E003 deep-vacuum evaporator / 324F003) + 335 tie-in ============================
    // Seed geometry = the shape centres of UI Pages/324-1b.pptx, 12192000x6858000 EMU -> 1366x720
    // stage.  The background PNG is that slide with exactly these shapes deleted, so every
    // overlay lands in the hole its own symbol left.  root EVAP_324.E003; the Unit-335 finishing side is unmodelled -> white frames.
    'screen-324-1b': [
      // ---- indicators, controllers and modulating-valve openings ----
      { k: 'pic324203', t: 'ind', x: 474, y: 71, tag: 'PIC-324203', bind: 'EVAP_324.E003.PIC_324203.pv', u: 'BAR A', dec: 3, mode: 'EVAP_324.E003.PIC_324203.mode', note: 'holds 324F003 deep vacuum 0.131 bar a via false-air PV-324203' },
      { k: 'hic329606', t: 'ind', x: 794, y: 151, tag: 'HIC-329606', bind: 'EVAP_324.E003.HIC_329606', u: '%', dec: 1, face: 'hic' },
      { k: 'pt324204', t: 'ind', x: 434, y: 179, tag: 'PT-324204', bind: 'EVAP_324.E003.PT_324203', u: 'BAR A', dec: 3, note: '324F003 separator pressure' },
      { k: 'hv329606', t: 'ind', x: 793, y: 201, tag: 'HV-329606', bind: 'EVAP_324.E003.HV_329606', u: '%', dec: 1, face: 'hic' },
      { k: 'py324701', t: 'ind', x: 434, y: 232, tag: 'PY-324701', bind: 'EVAP_324.E003.AY_324701', u: 'wt%', dec: 1, note: '324F003 product concentration soft-sensor (VLE inversion of PT-324204 / TIC-324002); backend key AY_324701' },
      { k: 'pic329212', t: 'ind', x: 250, y: 293, tag: 'PIC-329212', bind: 'EVAP_324.E003.PIC_329212.pv', u: 'BAR A', dec: 2, mode: 'EVAP_324.E003.PIC_329212.mode', cas: true, note: 'slave: CAS follows TIC-324002; steam to 324E003 chest via PV-329212' },
      { k: 'tic324002', t: 'ind', x: 435, y: 294, tag: 'TIC-324002', bind: 'EVAP_324.E003.TIC_324002.pv', u: 'C', dec: 1, mode: 'EVAP_324.E003.TIC_324002.mode', note: 'master: holds melt 140 C; cascades PIC-329212 chest steam-P' },
      { k: 'lt324501', t: 'ind', x: 484, y: 364, tag: 'LT-324501', bind: 'EVAP_324.E003.LIC_324501.pv', u: '%', dec: 1, mode: 'EVAP_324.E003.LIC_324501.mode', note: '324F003 product level; LIC-324501 A/B is the exclusive discharge-route selector' },
      { k: 'pic335201', t: 'ind', x: 658, y: 394, tag: 'PIC-335201', bind: 'EVAP_324.E003.PIC_335201', u: 'BAR G', dec: 2, note: '335 melt-header pressure (battery-limit boundary); above the LV-324501B relief setting the B route is forced' },
      { k: 'ft335401', t: 'ind', x: 751, y: 396, tag: 'FT-335401' },
      { k: 'fy335401', t: 'ind', x: 831, y: 397, tag: 'FY-335401' },
      { k: 'fq335401', t: 'ind', x: 912, y: 398, tag: 'FQ-335401' },
      { k: 'hic335602', t: 'ind', x: 1159, y: 459, tag: 'HIC-335602' },
      { k: 'hv335602', t: 'ind', x: 1157, y: 504, tag: 'HV-335602' },
      { k: 'ffy335406', t: 'ind', x: 896, y: 515, tag: 'FFY-335406' },
      { k: 'ffic335406', t: 'ind', x: 826, y: 555, tag: 'FFIC-335406', bind: 'EVAP_324.E003.FFIC_335406.pv', u: 'RATIO', dec: 4, mode: 'EVAP_324.E003.FFIC_335406.mode', note: 'UF85-to-product ratio; MV sets FIC-335405 SP' },
      { k: 'hic335609', t: 'ind', x: 700, y: 599, tag: 'HIC-335609' },
      { k: 'fic335405a', t: 'ind', x: 781, y: 599, tag: 'FIC-335405A', bind: 'EVAP_324.E003.FIC_335405.pv', u: 'T/H', dec: 3, mode: 'EVAP_324.E003.FIC_335405.mode', cas: true, note: 'slave: CAS follows FFIC-335406; UF85 inject to product' },
      { k: 'ft335405', t: 'ind', x: 354, y: 625, tag: 'FT-335405' },
      { k: 'fy335405', t: 'ind', x: 355, y: 648, tag: 'FY-335405' },
      { k: 'fq335405', t: 'ind', x: 356, y: 672, tag: 'FQ-335405' },
      { k: 'lt335507', t: 'ind', x: 1151, y: 675, tag: 'LT-335507' },
      { k: 'hic335610', t: 'ind', x: 694, y: 699, tag: 'HIC-335610' },
      { k: 'fic335405b', t: 'ind', x: 774, y: 699, tag: 'FIC-335405B' },
      { k: 'pv324203', t: 'avalve', x: 204, y: 160, tag: 'PV-324203', bind: 'EVAP_324.E003.PIC_324203.op', u: '%', dec: 1 },
      { k: 'pv329212', t: 'avalve', x: 165, y: 354, tag: 'PV-329212', bind: 'EVAP_324.E003.PIC_329212.op', u: '%', dec: 1 },
      { k: 'lv324501a', t: 'avalve', x: 564, y: 444, tag: 'LV-324501A', bind: 'EVAP_324.E003.LV_324501A', u: '%', dec: 1, route: 'A', note: 'click A — mixed Stream 609 (402G + UF85) forward to Unit 335' },
      { k: 'lv324501b', t: 'avalve', x: 474, y: 541, tag: 'LV-324501B', bind: 'EVAP_324.E003.LV_324501B', u: '%', dec: 1, route: 'B', note: 'click B — raw Stream 402G recycle to 323D002; UF85 interlocked OFF' },
      // ---- level bargraphs (fill height = bound level, 0-100 %) ----
      { k: 'barlic324501', t: 'bar', x: 437, y: 375, w: 20, h: 79, tag: 'LIC-324501', bind: 'EVAP_324.E003.LIC_324501.pv' },
      { k: 'barlt335507', t: 'bar', x: 1046, y: 624, w: 22, h: 105, tag: 'LT-335507' },
      // ---- pumps: A duty (drawn running), B installed standby (drawn stopped) ----
      { k: 'p335p001a', t: 'pump', x: 474.4, y: 430.1, w: 27.8, h: 24, tag: '335P001A' },
      { k: 'p335p001b', t: 'pump', x: 474.4, y: 477.9, w: 27.8, h: 24, tag: '335P001B', def: false },
      { k: 'p335p002a', t: 'pump', x: 700.7, y: 626, w: 27.8, h: 24, fx: true, tag: '335P002A' },
      { k: 'p335p002b', t: 'pump', x: 700.7, y: 673.7, w: 27.8, h: 24, fx: true, tag: '335P002B', def: false },
      // ---- screen-nav hotspots (slide comment "LINK TO PAGE ...") ----
      { k: 'nav3291322d001ab', t: 'nav', x: 678, y: 187, w: 105, h: 21, tag: '322D001 A/B -> 329-1', goto: 'screen-329-1' },
      { k: 'nav3282323c005', t: 'nav', x: 1304, y: 264, w: 105, h: 21, tag: '323C005 -> 328-2', goto: 'screen-328-2' },
      { k: 'nav3282328d003', t: 'nav', x: 1304, y: 316, w: 105, h: 21, tag: '328D003 -> 328-2', goto: 'screen-328-2' },
      { k: 'nav3291329d009', t: 'nav', x: 61, y: 338, w: 105, h: 21, tag: '329D009 -> 329-1', goto: 'screen-329-1' },
      { k: 'nav3241324f001', t: 'nav', x: 61, y: 523, w: 105, h: 21, tag: '324F001 -> 324-1', goto: 'screen-324-1' },
      { k: 'nav3231323d002', t: 'nav', x: 61, y: 588, w: 105, h: 21, tag: '323D002 -> 323-1', goto: 'screen-323-1' },
    ],
  };

  let pos = {};
  try { pos = carryOver(LSK, 'ots_ov_pos_v5') || {}; } catch (e) { pos = {}; }

  // ---- user tag overrides (add/edit/delete) persisted separately from positions ----
  const MK = 'ots_ov_tags_v5';        // per screen: { add:[ {k,t,x,y,tag,bind,u,dec,cmd,id} ], edit:{ k:{...} }, del:[k] }
  let ovr = {};                       // v5: same carry-over rule as LSK -- the seven re-seeded screens
  try { ovr = carryOver(MK, 'ots_ov_tags_v4') || {}; } catch (e) { ovr = {}; }   // start clean, the rest keep their edits
  const smap = sid => (ovr[sid] || (ovr[sid] = { add: [], edit: {}, del: [] }));
  const saveTags = () => localStorage.setItem(MK, JSON.stringify(ovr));
  // effective config = seed (minus deletes, with field edits) ++ user-added tags
  function cfg(sid) {
    const o = ovr[sid] || {}, del = new Set(o.del || []), ed = o.edit || {};
    const base = (OV[sid] || []).filter(e => !del.has(e.k))
                                .map(e => ed[e.k] ? Object.assign({}, e, ed[e.k]) : e);
    return base.concat((o.add || []).filter(e => !del.has(e.k)));
  }

  const local = {};   // sid|k -> bool, local state for unbound pumps/xvs
  const elMap = {};   // sid|k -> element
  let lastS = {};
  let editing = false;
  let simBtn = null;   // fixed SLOW/FAST pacing toggle button

  const stage = () => document.getElementById('stage');
  const gp = (o, path) => path ? path.split('.').reduce((a, k) => (a == null ? undefined : a[k]), o) : undefined;
  const fmt = (v, d) => (v == null || isNaN(v)) ? '--' : Number(v).toFixed(d == null ? 1 : d);
  // controller mode badge (Item: show mode beside value -> A=Auto, M=Man, E=CAS, O=OOS).
  // Backend controller dicts emit FULL words (MAN/AUTO/CAS/OOS); pump dicts already emit letters.
  const MODE_LETTER = { MAN: 'M', AUTO: 'A', CAS: 'E', OOS: 'O', M: 'M', A: 'A', E: 'E', O: 'O' };
  function modeLetter(o) {                       // o.mode = dot-path to mode field; HIC* = operator hand station (always M)
    if (o.mode) { const m = gp(lastS, o.mode); return m ? (MODE_LETTER[m] || '') : ''; }
    return /^HIC-/.test(o.tag || '') ? 'M' : '';
  }

  // Stage aspect ratio: the 16:9 slide canvas is stretched, not letterboxed, onto 1366x720
  // (background-size:100% 100%), so x and y carry different scale factors.
  //     SLIDE_RX = (1366/12192000) / (720/6858000) = 1.06719
  const SLIDE_RX = (1366 / 12192000) / (720 / 6858000);

  // Place a pump/XV icon so it lands exactly on the symbol the slide drew there.
  //   o.w / o.h are the icon's on-stage box AFTER that anisotropic stretch.  The slide render
  //   is rotate-THEN-stretch, so the same order is reproduced here: draw the image at its
  //   un-stretched size (o.w/SLIDE_RX by o.h), rotate it, then scale X back up.  This is exact
  //   for any angle -- at rot 0 it collapses to the plain o.w x o.h box.
  //   The .ov box is sized to that same un-stretched rectangle.  It used to keep the fixed
  //   54x54 / 34x34 CSS default while the <img> inside carried the real size; because .ov is
  //   centred with translate(-50%,-50%) but the image is laid out from its top-left, every icon
  //   sat half the size difference off its symbol (the 321-1 pumps by 11 x 6 px, the XVs by 17).
  function sizeIcon(el, o) {
    const img = el.querySelector('img');
    if (!img || !o.w || !o.h) return;
    const iw = o.w / SLIDE_RX, ih = o.h;
    el.style.width = iw + 'px';
    el.style.height = ih + 'px';
    // Right-most transform applies first, which is the order PowerPoint uses: mirror the
    // symbol inside its own box (fx/fy), rotate the box, then undo the stage's anisotropic
    // squash.  Getting that order wrong puts a flipped-and-rotated pump on the wrong side.
    const flip = (o.fx || o.fy) ? ' scale(' + (o.fx ? -1 : 1) + ',' + (o.fy ? -1 : 1) + ')' : '';
    img.style.cssText = 'width:' + iw + 'px;height:' + ih + 'px;display:block;transform-origin:50% 50%;'
      + 'transform:scaleX(' + SLIDE_RX + ')' + (o.rot ? ' rotate(' + o.rot + 'deg)' : '') + flip + ';';
  }

  function svgPump() {
    return '<img src="img/pump-off.png" style="display:block;">';
  }
  function svgXV() {
    return '<img src="img/xv-close.png" style="display:block;">';
  }

  function boolState(sid, o) {
    const key = sid + '|' + o.k;
    if (o.bind) return o.t === 'pump' ? !!gp(lastS, o.bind + '.on') || !!(gp(lastS, o.bind) && gp(lastS, o.bind).on)
                                      : !!gp(lastS, o.bind);
    return key in local ? local[key] : (o.def !== false);
  }
  // pumps bind to the object (pumpA), so read .on explicitly:
  function pumpOn(sid, o) {
    const key = sid + '|' + o.k;
    if (o.bind) { const p = gp(lastS, o.bind); return !!(p && p.on); }
    return key in local ? local[key] : (o.def !== false);
  }
  function xvOpen(sid, o) {
    const key = sid + '|' + o.k;
    if (o.bind) return !!gp(lastS, o.bind);
    return key in local ? local[key] : (o.def !== false);
  }

  // Element types that can carry a trend pen: analogue value, valve opening, valve/pump state.
  const TRENDABLE = { ind: 1, avalve: 1, xv: 1, pump: 1, bar: 1, btn: 1 };
  const CTRL_RE = /[A-Z]IC-3\d{2}/i;   // any *IC-3xxxx loop controller (PIC/HIC/LIC/TIC/FIC/SIC) -> faceplate
  let BIND_MAP = {};                   // tag -> {bind,u,dec,face,fp}: first bound occurrence across ALL screens
  function buildBindMap() {            // shared tags read the SAME value on every screen they appear
    const m = {}, tm = {};
    for (const sid in OV) cfg(sid).forEach(o => {
      if (o.t === 'ind' && o.bind && !m[o.tag]) m[o.tag] = { bind: o.bind, u: o.u, dec: o.dec, face: o.face, fp: o.fp, mode: o.mode };
      // Trend map also carries 'avalve' (modulating valve OPENING %). BIND_MAP itself must
      // not: eff() uses it to let an unbound 'ind' inherit a bind, and folding valve entries
      // into that would change which value a shared tag renders.
      if ((o.t === 'ind' || o.t === 'avalve' || o.t === 'btn') && o.bind && !tm[o.tag])
        tm[o.tag] = { bind: o.bind, u: o.u, dec: o.dec, rng: o.rng };
      // Block valves and pumps trend as 0/1 digital pens. A pump binds to its object, so
      // the trendable quantity is the .on flag. Unbound ones (UI-local toggles with no
      // backend state) are skipped by the o.bind guard — there is nothing to record.
      if ((o.t === 'xv' || o.t === 'pump') && o.bind && !tm[o.tag])
        tm[o.tag] = { bind: o.t === 'pump' ? o.bind + '.on' : o.bind, u: '', dec: 0, rng: [0, 1] };
    });
    BIND_MAP = m;
    window.OV_BINDS = tm;              // trend.js resolves tag -> packet path through this
    // Mirror to localStorage so the trend POPUP window (a separate document that never runs
    // overlays.js) can resolve tags on its own.
    try { localStorage.setItem('ots_ov_binds', JSON.stringify(tm)); } catch (e) { /* quota */ }
  }
  const eff = o => (o.t === 'ind' && !o.bind && BIND_MAP[o.tag]) ? Object.assign({}, o, BIND_MAP[o.tag]) : o;
  function renderOne(sid, o) {
    const el = elMap[sid + '|' + o.k]; if (!el) return;
    o = eff(o);                        // inherit bind/unit/dec from any screen sharing this tag
    if (o.t === 'nav') return;                          // transparent screen-nav hotspot, no value
    if (o.t === 'btn') { el.dataset.tip = o.tag + ' - click for faceplate'; return; }
    if (o.t === 'hs') {                                 // hand-switch pushbutton, no value
      const open = o.xv ? !!gp(lastS, o.xv) : false;
      el.dataset.tip = o.tag + ' - ' + (o.xv ? o.xv.split('.').pop().replace('_', '-') : '')
        + ' ' + (open ? 'OPEN' : 'CLOSED') + ' (click for faceplate)';
      return;
    }
    if (o.t === 'ae') {                                 // composition indicator (AE-* tag)
      el.classList.add('ae-indicator');
      el.dataset.tip = o.tag + ' — ' + (o.note || 'Click to view composition');
      return;
    }
    if (o.t === 'pump') {
      const on = pumpOn(sid, o);
      el.classList.toggle('on', on);
      const imgSrc = on ? 'img/pump-on.png' : 'img/pump-off.png';
      const img = el.querySelector('img');
      if (img && img.src.indexOf(imgSrc) < 0) img.src = imgSrc;
      el.dataset.tip = o.tag + ' — ' + (on ? 'ON' : 'OFF') + ' (click for START/STOP faceplate)';
    } else if (o.t === 'xv') {
      const open = xvOpen(sid, o);
      el.classList.toggle('closed', !open);
      const imgSrc = open ? 'img/xv-open.png' : 'img/xv-close.png';
      const img = el.querySelector('img');
      if (img && img.src.indexOf(imgSrc) < 0) img.src = imgSrc;
      el.dataset.tip = o.tag + ' — ' + (open ? 'OPEN' : 'CLOSED');
    } else if (o.t === 'bar') {                          // level bargraph: fill height = bound value, 0-100 %
      const f = el.querySelector('.bf');
      const v = o.bind ? gp(lastS, o.bind) : null;
      const pc = (v == null || isNaN(v)) ? null : Math.max(0, Math.min(100, Number(v)));
      el.classList.toggle('empty', pc == null);
      if (f) f.style.height = (pc == null ? 0 : pc) + '%';
      el.dataset.tip = o.tag + ' - ' + (pc == null ? 'no data' : pc.toFixed(1) + ' %');
    } else if (o.t === 'ovrd') {                         // 21.x interlock override pushbutton
      const armed = !!gp(lastS, 'trip_latched.' + (o.latch || '21_4'));
      const open = !!gp(lastS, o.xv || 'XV_322901');
      el.classList.toggle('armed', armed);               // lamp lit while interlock latched
      el.classList.toggle('on', open);
      el.dataset.tip = o.tag + ' — interlock ' + (armed ? 'LATCHED (override available)' : 'clear')
        + '; XV ' + (open ? 'OPEN' : 'CLOSED') + ' (click to toggle)';
    } else { // ind
      const b = el.querySelector('b'), sp = el.querySelector('.ou'), mt = el.querySelector('.mt');   // stable nodes (built once); update text only so a click isn't swallowed by per-tick innerHTML churn
      if (!o.bind) { if (b) b.textContent = o.tag; if (sp) sp.textContent = ''; if (mt) { mt.textContent = ''; mt.className = 'mt'; } return; }   // empty slot keeps tag text
      let v = gp(lastS, o.bind);
      let u = o.u;
      if (u === 'BAR A' && typeof v === 'number') { v = v - 1.01325; u = 'BARG'; }   // Domain 1a: all PT/PIC show gauge pressure (barg = bara - 1 atm)
      if (window.IndicatorFaceplate) window.IndicatorFaceplate.publish(o.tag, v, u || '');   // shared post-dynamics registry (3-dp faceplate reads this)
      if (b) b.textContent = fmt(v, o.dec);
      if (sp) sp.textContent = u || '';
      if (mt) { const ml = modeLetter(o); mt.textContent = ml; mt.className = 'mt' + (ml ? ' m-' + ml : ''); }   // controller mode badge (A/M/E/O); '' for non-controllers
      el.dataset.tip = o.tag + (u ? ' [' + u + ']' : '') + (modeLetter(o) ? ' — ' + { A: 'AUTO', M: 'MAN', E: 'CAS', O: 'OOS' }[modeLetter(o)] : '');
    }
  }
  function renderAll() { buildBindMap(); for (const sid in OV) cfg(sid).forEach(o => renderOne(sid, o)); }

  function activate(sid, o) {                   // run-mode left-click action
    o = eff(o);                                 // shared tag opens same faceplate / inherits bind
    if (o.t === 'pump') {
      // A pump click opens its faceplate; START/STOP are issued from there, never from the symbol.
      if (o.bind && o.id && window.OTS_FACE && window.OTS_FACE.pump) { window.OTS_FACE.pump(o); return; }
      return;
    } else if (o.t === 'xv') {
      if (o.cmd) { if (window.otsSend) otsSend({ type: 'xv_toggle', id: o.cmd }); return; }
    } else if (o.t === 'hs') {                    // hand switch: opens faceplate to control XV
      if (window.OTS_FACE && window.OTS_FACE.hs) { window.OTS_FACE.hs(o); return; }
    } else if (o.t === 'ovrd') {                  // manual override: toggle the XV (open while interlock latched)
      if (o.cmd && window.otsSend) otsSend({ type: 'xv_toggle', id: o.cmd });
      return;
    } else if (o.t === 'nav') {
      if (o.goto && window.otsSwitchScreen) window.otsSwitchScreen(o.goto);
      return;
    } else if (o.t === 'ae') {                    // composition indicator: opens composition faceplate (composition only, no properties)
      if (o.stream && window.openStreamPopup) window.openStreamPopup(o.stream, true);
      return;
    } else if (o.t === 'strm') {
      if (o.stream && window.openStreamPopup) window.openStreamPopup(o.stream);
      return;
    } else if (o.t === 'btn') {                   // hand-switch button drawn on the slide (HS-322203)
      if (o.face && window.OTS_FACE && window.OTS_FACE[o.face]) { window.OTS_FACE[o.face](o); return; }
      if (CTRL_RE.test(o.tag) && window.OTS_FACE && window.OTS_FACE.ctl) { window.OTS_FACE.ctl(o); return; }
      if (window.OTS_FACE && window.OTS_FACE.indicator) { window.OTS_FACE.indicator(o); }
      return;
    } else if (o.t === 'bar') {                   // level bargraph: same faceplate route as its tag
      if (o.face && window.OTS_FACE && window.OTS_FACE[o.face]) { window.OTS_FACE[o.face](o); return; }
      if (CTRL_RE.test(o.tag) && window.OTS_FACE && window.OTS_FACE.ctl) { window.OTS_FACE.ctl(o); return; }
      if (window.OTS_FACE && window.OTS_FACE.indicator) { window.OTS_FACE.indicator(o); }
      return;
    } else if (o.t === 'avalve' && o.route) {
      const api = window.OTS_LV324501_ROUTE;
      if (api && window.otsSend) api.activate(o.route, window.otsSend);
      return;
    } else if (o.t === 'avalve') {                // an auto-valve may carry a faceplate too (PV-322203 -> HIC-322203)
      if (o.face && window.OTS_FACE && window.OTS_FACE[o.face]) { window.OTS_FACE[o.face](o); return; }
      if (CTRL_RE.test(o.tag) && window.OTS_FACE && window.OTS_FACE.ctl) { window.OTS_FACE.ctl(o); return; }
      if (window.OTS_FACE && window.OTS_FACE.indicator) { window.OTS_FACE.indicator(o); }   // opening value -> read-only faceplate
      return;
    } else if (o.t === 'ind') {
      if (o.face && window.OTS_FACE && window.OTS_FACE[o.face]) { window.OTS_FACE[o.face](o); return; }
      if (o.fp === 'SIC_321950' && window.openF50) { window.openF50(); return; }   // SIC_321950 REST faceplate
      if (o.fp === 'SIC_321951' && window.openF51) { window.openF51(); return; }   // SIC_321951 REST faceplate
      if (o.fp === 'MASTER_SP_329207' && window.OTS_FACE && window.OTS_FACE.msp) { window.OTS_FACE.msp(o); return; }   // 4-bar header MASTER SP cascade
      // A readout of ONE field of a loop (the 2026-09 `FFIC-329401 SP` / `MV` pair) opens THAT loop's
      // faceplate under its real tag and PV, so the write reaches the backend controller instead of
      // an unknown id `handle_cmd` discards.
      if (o.ctl && window.OTS_FACE && window.OTS_FACE.ctl) {
        window.OTS_FACE.ctl(Object.assign({}, o, { tag: o.ctl, bind: o.ctlBind, u: o.ctlU || o.u, dec: o.dec }));
        return;
      }
      if (CTRL_RE.test(o.tag) && window.OTS_FACE && window.OTS_FACE.ctl) { window.OTS_FACE.ctl(o); return; }   // any *IC-3* -> generic faceplate
      if (window.OTS_FACE && window.OTS_FACE.indicator) { window.OTS_FACE.indicator(o); }   // every other indicator -> read-only faceplate
      return;
    }
    const key = sid + '|' + o.k;                // unbound pump/xv -> local toggle
    local[key] = !boolState(sid, o);
    renderOne(sid, o);
  }

  function place(el, x, y) { el.style.left = x + 'px'; el.style.top = y + 'px'; }

  function attach(el, sid, o) {
    let sx, sy, ox, oy, down = false, moved = false;
    el.addEventListener('mousedown', ev => {
      if (!editing || ev.button !== 0) return;
      ev.preventDefault(); down = true; moved = false;
      sx = ev.clientX; sy = ev.clientY;
      ox = parseFloat(el.style.left); oy = parseFloat(el.style.top);
      const mm = e => {
        if (!down) return; moved = true;
        const nx = Math.max(0, Math.min(STAGE_W, ox + (e.clientX - sx)));
        const ny = Math.max(0, Math.min(STAGE_H, oy + (e.clientY - sy)));
        place(el, nx, ny);
        pos[sid + '|' + o.k] = { x: Math.round(nx), y: Math.round(ny) };
      };
      const mu = () => {
        down = false;
        document.removeEventListener('mousemove', mm);
        document.removeEventListener('mouseup', mu);
        if (moved) localStorage.setItem(LSK, JSON.stringify(pos));
      };
      document.addEventListener('mousemove', mm);
      document.addEventListener('mouseup', mu);
    });
    el.addEventListener('click', ev => {
      if (editing) return;
      if (el.dataset.dragged === '1') { el.dataset.dragged = ''; return; }  // a drag must not open a faceplate
      activate(sid, o);
    });
    el.addEventListener('contextmenu', e => {
      e.preventDefault(); e.stopPropagation();
      if (editing) { openMenu(e, sid, o); return; }                        // edit mode -> Edit/Delete menu
      // run mode -> trend context menu (Trend / Add to slot), tag resolved via OV_BINDS
      if (TRENDABLE[o.t] && window.TrendWindow) window.TrendWindow.openMenu(e, o.tag);
    });
    // drag an indicator, valve opening or valve/pump state straight onto a trend slot
    if (TRENDABLE[o.t]) {
      el.addEventListener('dragstart', ev => {
        if (editing) { ev.preventDefault(); return; }                      // edit mode keeps the reposition drag
        el.dataset.dragged = '1';
        ev.dataTransfer.setData('text/ots-tag', o.tag);
        ev.dataTransfer.setData('text/plain', o.tag);
        ev.dataTransfer.effectAllowed = 'copy';
        // Published for trend.js's dragend handoff: the payload cannot cross into the popup
        // window, so the launcher reads the tag here and tests the drop point against the
        // popup's screen rect.
        window.__ots_drag_tag = o.tag;
        if (window.TrendWindow) window.TrendWindow.open();                  // open/focus the popup so a drop lands somewhere
      });
    }
  }

  function build(sid) {
    const screen = document.getElementById(sid); if (!screen) return;
    buildBindMap();
    let layer = screen.querySelector('.ov-layer');
    if (!layer) { layer = document.createElement('div'); layer.className = 'ov-layer'; screen.appendChild(layer); }
    layer.innerHTML = '';                                                  // rebuildable after edits
    for (const key in elMap) if (key.indexOf(sid + '|') === 0) delete elMap[key];
    cfg(sid).forEach(o => {
      const el = document.createElement('div');
      el.className = 'ov ' + (o.t === 'pump' ? 'pump' : o.t === 'xv' ? 'avalve' : o.t === 'vessel' ? 'vessel' : o.t === 'nav' ? 'nav' : o.t === 'strm' ? 'strm' : o.t === 'ae' ? 'ae' : o.t === 'ovrd' ? 'ovrd' : o.t === 'hs' ? 'hs' : o.t === 'bar' ? 'bar' : o.t === 'btn' ? 'nav' : 'ind');
      if (o.t === 'ind' || o.t === 'avalve') {                                 // avalve = modulating PV opening %, rendered as a numeric indicator (bug 3: opening was never shown)
        const eo = eff(o);
        if (!eo.bind) el.classList.add('empty');
        if (eo.fp || eo.face || CTRL_RE.test(o.tag)) el.classList.add('fp');
        el.innerHTML = '<b></b> <span class="ou"></span><i class="mt"></i>';   // stable value/unit/mode nodes; renderOne sets textContent only (no innerHTML churn that swallows clicks)
      } else if (o.t === 'nav') {
        el.style.width = (o.w || 60) + 'px';
        el.style.height = (o.h || 24) + 'px';
      } else if (o.t === 'strm') {
        el.style.width = (o.w || 120) + 'px';
        el.style.height = (o.h || 16) + 'px';
        el.dataset.stream = o.stream;
      } else if (o.t === 'ae') {                                   // composition indicator (AE-* tag)
        el.innerHTML = '<b>' + o.tag + '</b>';
        el.style.padding = '4px 8px';
        el.style.background = '#0c1a28';
        el.style.border = '1px solid #2f5a78';
        el.style.borderRadius = '3px';
        el.style.color = '#8fd0ff';
        el.style.font = 'bold 10px Consolas,monospace';
        el.style.cursor = 'pointer';
        el.style.whiteSpace = 'nowrap';
        el.style.userSelect = 'none';
        el.dataset.stream = o.stream;
      } else if (o.t === 'hs') {                                   // the green pushbutton square inside
        el.innerHTML = '';                                         // the slide's "Open XV-..." panel --
        if (o.w) el.style.width = o.w + 'px';                      // the panel already prints the legend,
        if (o.h) el.style.height = o.h + 'px';                     // so the button itself carries no text
      } else if (o.t === 'btn') {                                  // transparent hotspot over a button
        el.style.width  = (o.w || 60) + 'px';                      // the slide already draws and labels
        el.style.height = (o.h || 20) + 'px';
      } else if (o.t === 'bar') {                                  // vertical level bargraph over the
        el.style.width  = (o.w || 12) + 'px';                      // slot drawn on the vessel
        el.style.height = (o.h || 80) + 'px';
        el.innerHTML = '<i class="bf"></i>';
      }
      if (o.fs) el.style.fontSize = o.fs + 'px';                   // slide-specified type size (PT-329201, LOAD)
      el.dataset.tip = o.tag;
      el.title = o.tag;
      // Only bound indicators/valve openings are draggable: an unbound white frame has no
      // packet path, so there is nothing to trend.
      if (TRENDABLE[o.t] && (eff(o).bind || o.bind)) el.draggable = true;
      if (o.t === 'pump') {
        el.innerHTML = svgPump();
        sizeIcon(el, o);
      } else if (o.t === 'xv') {
        el.innerHTML = svgXV();
        sizeIcon(el, o);
      } else if (o.t === 'vessel') {
        if (o.img) {
          el.innerHTML = `<img src="img/${o.img}" style="width:${o.w}px;height:${o.h}px;display:block;">`;
        } else if (o.w && o.h) {
          el.style.width = o.w + 'px';
          el.style.height = o.h + 'px';
          el.style.border = '2px solid #4a6b2f';
          el.style.background = 'rgba(26, 40, 8, 0.3)';
          el.style.borderRadius = '4px';
        }
      } else if (o.t === 'ovrd') el.innerHTML = '<span class="ovl"></span><b>OVRD</b>';
      const p = pos[sid + '|' + o.k] || { x: o.x, y: o.y };
      place(el, p.x, p.y);
      attach(el, sid, o);
      layer.appendChild(el);
      elMap[sid + '|' + o.k] = el;
    });
  }

  // ================= TAG EDITOR (add / edit / delete / reposition) =================
  function injectCSS() {
    if (document.getElementById('ov-css')) return;
    const s = document.createElement('style'); s.id = 'ov-css';
    s.textContent =
      '#ov-toolbar{position:fixed;right:12px;bottom:12px;display:flex;gap:6px;z-index:9000;}' +
      '#ov-toolbar button{font:600 12px "Segoe UI",system-ui;padding:6px 10px;background:#13202c;color:#cfe;border:1px solid #2f4858;border-radius:6px;cursor:pointer;}' +
      '#ov-toolbar button:hover{background:#1d3242;border-color:#4aa587;}' +
      '#ov-edit{background:#1a2e22;border-color:#3a6b4e;}' +
      'body.ov-editing #ov-edit{background:#3aa56e;color:#04140c;}' +
      '.ov-eo{display:none!important;}' +
      'body.ov-editing .ov-eo{display:inline-block!important;}' +
      'body.ov-editing .ov{outline:1px dashed rgba(120,200,255,.5);cursor:move;}' +
      '.ov.nav{background:transparent;border:1px solid transparent;border-radius:4px;}' +
      '.ov.nav:hover{border-color:rgba(127,208,216,.85);background:rgba(80,160,220,.16);box-shadow:0 0 8px rgba(127,208,216,.35) inset;}' +
      'body.ov-editing .ov.nav{border-color:rgba(255,208,0,.6);background:rgba(255,208,0,.08);}' +
      '.ov.strm{background:transparent;border:1px solid transparent;border-radius:3px;}' +
      '.ov.strm:hover{border-color:rgba(127,208,216,.85);background:rgba(80,160,220,.14);}' +
      'body.ov-editing .ov.strm{border-color:rgba(255,160,60,.7);background:rgba(255,160,60,.10);}' +
      '.ov.ae{background:#0c1a28;border:1px solid #2f5a78;border-radius:3px;color:#8fd0ff;font:bold 10px Consolas,monospace;padding:4px 8px;cursor:pointer;white-space:nowrap;user-select:none;}' +
      '.ov.ae:hover{background:#1a2e42;border-color:#4aa587;color:#aff0ff;}' +
      'body.ov-editing .ov.ae{border-color:rgba(143,208,255,.8);background:rgba(143,208,255,.12);}' +
      '.ov.ovrd{display:flex;align-items:center;gap:5px;padding:3px 7px;background:#1a1208;border:1px solid #6b5a2f;border-radius:3px;color:#cdbb78;font:bold 10px Consolas,monospace;letter-spacing:.6px;cursor:pointer;white-space:nowrap;user-select:none;}' +
      '.ov.ovrd .ovl{width:13px;height:9px;border:1px solid #6b5a2f;background:#3a3320;flex:none;}' +
      '.ov.ovrd:hover{border-color:#ffd000;color:#ffe9a0;}' +
      '.ov.ovrd:active{background:#3aa56e;color:#04140c;border-color:#3aa56e;}' +
      '.ov.ovrd.armed{border-color:#ffd000;color:#ffd000;background:#241a06;box-shadow:0 0 7px rgba(255,208,0,.55);}' +
      '.ov.ovrd.armed .ovl{background:#ffd000;border-color:#ffd000;box-shadow:0 0 5px #ffd000;animation:ovrdblink 1s steps(1) infinite;}' +
      '.ov.ovrd.on .ovl{background:#22ff22;border-color:#22ff22;}' +
      '@keyframes ovrdblink{50%{opacity:.35;}}' +
      '.ov.bar{padding:0;background:#04110d;border:1px solid #e8f4f0;border-radius:1px;overflow:hidden;display:flex;flex-direction:column-reverse;cursor:pointer;}' +
      '.ov.bar .bf{display:block;width:100%;background:var(--btn-green,#22ff22);transition:height .15s linear;}' +
      '.ov.bar.empty{border-color:#fff;background:transparent;}' +
      'body.ov-editing .ov.bar{outline:1px dashed rgba(120,200,255,.8);}' +
      '.ov.hs{padding:0;box-sizing:border-box;background:#1a2808;border:1px solid #4a6b2f;border-radius:4px;color:#a0e060;font:bold 11px Arial;cursor:pointer;white-space:nowrap;user-select:none;}' +
      '.ov.hs:hover{background:#2a3818;border-color:#6a8b4f;color:#c0ff80;}' +
      '.ov.hs:active{background:#0aa64d;color:#fff;border-color:#22ff22;}' +
      '#sim-toggle{position:fixed;left:12px;bottom:12px;z-index:9000;display:flex;align-items:center;gap:8px;font:600 12px "Segoe UI",system-ui;padding:7px 13px;background:#13202c;color:#cfe;border:1px solid #2f4858;border-radius:6px;cursor:pointer;user-select:none;}' +
      '#sim-toggle:hover{background:#1d3242;border-color:#4aa587;}' +
      '#sim-toggle .dot{width:9px;height:9px;border-radius:50%;background:#3a6b4e;box-shadow:0 0 5px #3a6b4e;flex:none;}' +
      '#sim-toggle.fast{background:#3a2a08;border-color:#b3892f;color:#ffd98a;}' +
      '#sim-toggle.fast .dot{background:#ffb000;box-shadow:0 0 8px #ffb000;}' +
      '.ov-menu{position:fixed;z-index:9100;background:#10202a;border:1px solid #2f4858;border-radius:6px;box-shadow:0 6px 20px rgba(0,0,0,.5);display:flex;flex-direction:column;min-width:128px;overflow:hidden;font:13px "Segoe UI",system-ui;}' +
      '.ov-menu button{text-align:left;padding:8px 12px;background:none;border:none;color:#cfe;cursor:pointer;}' +
      '.ov-menu button:hover{background:#1d3242;}' +
      '.ov-menu button.danger:hover{background:#5a1f1f;color:#fdd;}' +
      '#ov-modal{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:9200;display:none;align-items:center;justify-content:center;}' +
      '.ov-card{background:#0f1b24;border:1px solid #2f4858;border-radius:10px;padding:18px 20px;width:344px;box-shadow:0 12px 40px rgba(0,0,0,.6);font:13px "Segoe UI",system-ui;color:#dceaf2;}' +
      '.ov-card h3{margin:0 0 12px;font-size:15px;color:#9fead0;}' +
      '.ov-card label{display:block;margin:8px 0;font-size:12px;color:#9bb;}' +
      '.ov-card input,.ov-card select{width:100%;margin-top:3px;padding:6px 8px;background:#0a141b;border:1px solid #2f4858;border-radius:5px;color:#eaf6ff;font:13px Consolas,monospace;box-sizing:border-box;}' +
      '.ov-card .ov-row{display:flex;gap:10px;}.ov-card .ov-row label{flex:1;}' +
      '.ov-act{display:flex;align-items:center;gap:8px;margin-top:16px;}' +
      '.ov-act button{padding:7px 14px;border-radius:6px;border:1px solid #2f4858;background:#13202c;color:#cfe;cursor:pointer;font:600 12px "Segoe UI";}' +
      '.ov-act .prim{background:#2f8f5f;border-color:#3a6b4e;color:#04140c;}' +
      '.ov-act .danger{background:#3a1717;border-color:#88322f;color:#fbb;}' +
      '.ov-act button:hover{filter:brightness(1.18);}';
    document.head.appendChild(s);
  }

  // every dot-path (objects + leaves) of the live packet, for the Bind dropdown
  function flattenKeys(obj, pre, out) {
    out = out || []; pre = pre || '';
    if (obj == null || typeof obj !== 'object') return out;
    for (const k in obj) {
      const p = pre ? pre + '.' + k : k, v = obj[k];
      out.push(p);
      if (v && typeof v === 'object' && !Array.isArray(v)) flattenKeys(v, p, out);
    }
    return out;
  }

  let modalCtx = null;

  function ensureModal() {
    if (document.getElementById('ov-modal')) return;
    const m = document.createElement('div'); m.id = 'ov-modal';
    m.innerHTML =
      '<div class="ov-card">' +
        '<h3 id="ovm-title">Add Tag</h3>' +
        '<label>Tag label<input id="ovm-tag" placeholder="e.g. TI-322009" autocomplete="off"></label>' +
        '<label>Type<select id="ovm-type"><option value="ind">indicator</option><option value="pump">pump</option><option value="xv">valve (XV)</option></select></label>' +
        '<label>Bind to live value<select id="ovm-bind"></select></label>' +
        '<div class="ov-row"><label>Unit<input id="ovm-unit" placeholder="BAR G" autocomplete="off"></label><label>Decimals<input id="ovm-dec" type="number" min="0" max="4" value="1"></label></div>' +
        '<label>Command / Pump id<input id="ovm-cmd" placeholder="xv cmd (e.g. 321901) or pump id (A/B)" autocomplete="off"></label>' +
        '<div class="ov-act"><button id="ovm-del" class="danger">Delete</button><span style="flex:1"></span><button id="ovm-cancel">Cancel</button><button id="ovm-save" class="prim">Save</button></div>' +
      '</div>';
    document.body.appendChild(m);
    m.addEventListener('mousedown', e => { if (e.target === m) closeModal(); });
    m.addEventListener('keydown', e => {
      if (e.key === 'Escape') closeModal();
      else if (e.key === 'Enter' && e.target.tagName !== 'SELECT') { e.preventDefault(); saveModal(); }
    });
  }

  function fillBindOptions(sel, cur) {
    const keys = flattenKeys(lastS).sort();
    sel.innerHTML = '<option value="">(none — white frame)</option>' +
      keys.map(k => '<option value="' + k + '"' + (k === cur ? ' selected' : '') + '>' + k + '</option>').join('');
    if (cur && keys.indexOf(cur) < 0)
      sel.insertAdjacentHTML('beforeend', '<option value="' + cur + '" selected>' + cur + ' (offline)</option>');
  }

  function openModal(sid, o) {
    ensureModal();
    const add = !o; modalCtx = { sid: sid, o: o };
    document.getElementById('ovm-title').textContent = add ? 'Add Tag — ' + sid : 'Edit ' + (o.tag || 'tag');
    document.getElementById('ovm-tag').value  = add ? '' : (o.tag || '');
    document.getElementById('ovm-type').value = add ? 'ind' : o.t;
    fillBindOptions(document.getElementById('ovm-bind'), add ? '' : (o.bind || ''));
    document.getElementById('ovm-unit').value = add ? '' : (o.u || '');
    document.getElementById('ovm-dec').value  = (o && o.dec != null) ? o.dec : 1;
    document.getElementById('ovm-cmd').value  = add ? '' : (o.cmd || o.id || '');
    document.getElementById('ovm-del').style.display = add ? 'none' : '';
    document.getElementById('ov-modal').style.display = 'flex';
    setTimeout(() => document.getElementById('ovm-tag').focus(), 0);
  }
  function closeModal() { const m = document.getElementById('ov-modal'); if (m) m.style.display = 'none'; modalCtx = null; }

  function saveModal() {
    if (!modalCtx) return;
    const sid = modalCtx.sid, o = modalCtx.o;
    const tag = document.getElementById('ovm-tag').value.trim();
    if (!tag) { document.getElementById('ovm-tag').focus(); return; }
    const t = document.getElementById('ovm-type').value;
    const bind = document.getElementById('ovm-bind').value.trim();
    const u = document.getElementById('ovm-unit').value.trim();
    const dec = parseInt(document.getElementById('ovm-dec').value, 10);
    const cmd = document.getElementById('ovm-cmd').value.trim();
    const fields = { tag: tag, t: t, bind: bind };
    if (t === 'ind') { fields.u = u; fields.dec = isNaN(dec) ? 1 : dec; }
    if (t === 'xv') fields.cmd = cmd;
    if (t === 'pump') fields.id = cmd;
    if (o) {                                                   // EDIT existing
      const added = smap(sid).add.filter(e => e.k === o.k)[0];
      if (added) { ['bind', 'u', 'dec', 'cmd', 'id'].forEach(kk => delete added[kk]); Object.assign(added, fields); }
      else smap(sid).edit[o.k] = fields;                       // override seed tag
    } else {                                                   // ADD new (drops at stage center)
      const k = 'u' + Date.now().toString(36);
      const e = Object.assign({ k: k, x: STAGE_W / 2 - 20, y: STAGE_H / 2 - 9 }, fields);
      smap(sid).add.push(e);
      pos[sid + '|' + k] = { x: Math.round(e.x), y: Math.round(e.y) };
      localStorage.setItem(LSK, JSON.stringify(pos));
    }
    saveTags(); closeModal(); rebuild(sid);
  }

  function deleteTag(sid, o) {
    const added = smap(sid).add.some(e => e.k === o.k);
    if (added) smap(sid).add = smap(sid).add.filter(e => e.k !== o.k);
    else if (smap(sid).del.indexOf(o.k) < 0) smap(sid).del.push(o.k);       // tombstone seed tag
    delete pos[sid + '|' + o.k]; localStorage.setItem(LSK, JSON.stringify(pos));
    saveTags(); closeModal(); rebuild(sid);
  }

  function closeMenu() { const m = document.querySelector('.ov-menu'); if (m) m.remove(); }
  function closeMenuOnce(e) { if (!e.target.closest('.ov-menu')) { closeMenu(); document.removeEventListener('mousedown', closeMenuOnce); } }
  function openMenu(ev, sid, o) {
    closeMenu();
    const m = document.createElement('div'); m.className = 'ov-menu';
    m.innerHTML = '<button data-a="edit">✎ Edit / Bind</button><button data-a="del" class="danger">🗑 Delete</button>';
    document.body.appendChild(m);
    m.style.left = Math.min(ev.clientX, window.innerWidth - 144) + 'px';
    m.style.top  = Math.min(ev.clientY, window.innerHeight - 90) + 'px';
    m.addEventListener('click', e => {
      const a = e.target.dataset.a; if (!a) return;
      closeMenu();
      if (a === 'del') deleteTag(sid, o); else openModal(sid, o);
    });
    setTimeout(() => document.addEventListener('mousedown', closeMenuOnce), 0);
  }

  function activeSid() { const a = document.querySelector('.screen.active'); return (a && OV[a.id]) ? a.id : Object.keys(OV)[0]; }

  function resetScreen(sid) {
    if (!window.confirm('Reset all tag edits, additions & positions on ' + sid + ' back to defaults?')) return;
    delete ovr[sid]; saveTags();
    for (const key in pos) if (key.indexOf(sid + '|') === 0) delete pos[key];
    localStorage.setItem(LSK, JSON.stringify(pos));
    rebuild(sid);
  }

  function exportLayout() {
    const data = JSON.stringify({ v: 3, tags: ovr, pos: pos }, null, 2);
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([data], { type: 'application/json' }));
    a.download = 'ots-ui-layout.json'; a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  }
  function importLayout(ev) {
    const f = ev.target.files && ev.target.files[0]; if (!f) return;
    const r = new FileReader();
    r.onload = () => {
      try {
        const d = JSON.parse(r.result);
        if (d.tags) { ovr = d.tags; saveTags(); }
        if (d.pos)  { pos = d.pos; localStorage.setItem(LSK, JSON.stringify(pos)); }
        for (const sid in OV) rebuild(sid);
        window.alert('Layout imported.');
      } catch (err) { window.alert('Import failed: ' + err.message); }
    };
    r.readAsText(f); ev.target.value = '';
  }

  function rebuild(sid) { build(sid); cfg(sid).forEach(o => renderOne(sid, o)); }

  function editButton() {
    injectCSS();
    const bar = document.createElement('div'); bar.id = 'ov-toolbar';
    bar.innerHTML =
      '<button id="ov-edit">✎ Edit Layout</button>' +
      '<button class="ov-eo" data-act="add">➕ Add Tag</button>' +
      '<button class="ov-eo" data-act="reset">⟲ Reset</button>' +
      '<button class="ov-eo" data-act="export">⬇ Export</button>' +
      '<button class="ov-eo" data-act="import">⬆ Import</button>' +
      '<input id="ov-import-file" type="file" accept="application/json" hidden>';
    document.body.appendChild(bar);
    const editBtn = bar.querySelector('#ov-edit');
    editBtn.onclick = () => {
      editing = !editing;
      document.body.classList.toggle('ov-editing', editing);
      // Edit mode owns mousedown-drag for repositioning; HTML5 drag would fight it.
      document.querySelectorAll('.ov.ind, .ov.avalve, .ov.xv, .ov.pump').forEach(el => {
        if (el.dataset.trendable === '1' || el.draggable) el.dataset.trendable = '1';
        el.draggable = !editing && el.dataset.trendable === '1';
      });
      editBtn.textContent = editing ? '✓ Done' : '✎ Edit Layout';
      if (!editing) { closeMenu(); closeModal(); }
    };
    bar.querySelector('[data-act="add"]').onclick    = () => openModal(activeSid(), null);
    bar.querySelector('[data-act="reset"]').onclick  = () => resetScreen(activeSid());
    bar.querySelector('[data-act="export"]').onclick = exportLayout;
    bar.querySelector('[data-act="import"]').onclick = () => bar.querySelector('#ov-import-file').click();
    bar.querySelector('#ov-import-file').onchange    = importLayout;
    document.addEventListener('click', e => {                  // modal action buttons (delegated)
      if (e.target.id === 'ovm-save') saveModal();
      else if (e.target.id === 'ovm-cancel') closeModal();
      else if (e.target.id === 'ovm-del' && modalCtx) deleteTag(modalCtx.sid, modalCtx.o);
    });
  }

  function simToggle() {                          // global SLOW/FAST simulation-pacing toggle
    const b = document.createElement('div'); b.id = 'sim-toggle';
    b.title = 'Simulation pacing — SLOW (real-time) <-> FAST (accelerated). Click to toggle.';
    b.innerHTML = '<span class="dot"></span><span class="lbl">SLOW</span>';
    b.onclick = () => {
      const next = (gp(lastS, 'sim_mode') === 'FAST') ? 'SLOW' : 'FAST';
      if (window.otsSend) otsSend({ type: 'set_sim_mode', mode: next });
    };
    document.body.appendChild(b);
    simBtn = b;
  }
  function simRender(s) {                          // reflect backend sim_mode/sim_speed on the button
    if (!simBtn) return;
    const fast = gp(s, 'sim_mode') === 'FAST', sp = gp(s, 'sim_speed');
    simBtn.classList.toggle('fast', fast);
    simBtn.querySelector('.lbl').textContent = (fast ? 'FAST' : 'SLOW') + (sp != null ? ' ×' + sp : '');
  }

  window.OV_apply = function (s) { lastS = s; window.OTS_LAST = s; renderAll(); simRender(s); };  // app.js calls each ws packet (OTS_LAST -> faceplate prefill)

  for (const sid in OV) build(sid);
  editButton();
  simToggle();
  renderAll();
})();
