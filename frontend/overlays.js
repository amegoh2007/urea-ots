'use strict';
// Rev2 image-backed UI — live overlay layer driven by the tagged DCS screenshots.
// Opaque divs sit on top of the cleaned screenshot and cover ("crop") the static
// symbols/values baked into the image, replacing them with LIVE sim data:
//   type 'ind'  -> black indicator box, live value + unit (or empty slot if unbound)
//   type 'pump' -> dynamic ON/OFF icon  (green = ON, grey = OFF)
//   type 'xv'   -> dynamic OPEN/CLOSED bowtie (green = OPEN, red = CLOSED)
// Coordinates were read from the tagged screenshots; click "Edit Layout" to drag any
// element exactly onto its symbol — positions persist to localStorage (alignment
// solved permanently, no code edits).
//
// EVERY tagged transmitter on both screens is POSITIONED (mapped from the tagged shots).
// Binding still respects "one unit at a time": 321-1 is the active unit -> all its
// indicators bound to packet keys. 322-2 is downstream -> only backend-modelled tags
// carry live binds: the 322F001 HP-ejector boundary (motive-A TI-321020 + XV-322901 from
// 321; suction-B TI-322002 + PI-329201 = 322E003 overflow; discharge TT-322012 -> 322E002
// HPCC) plus HIC-322602. Every other tag is a WHITE-FRAME empty slot (tag text only)
// awaiting binding when its upstream unit (322E003 scrubber, etc.) is modelled.
(function () {
  const STAGE_W = 1366, STAGE_H = 720;
  const LSK = 'ots_ov_pos_v3';   // bumped: backgrounds swapped -> discard stale drag positions

  // bind = dot-path into the ws packet ('FI_321401', 'pumpA.current', 'SIC_321950.pv').
  // dec  = decimals. fp = controller id for left-click faceplate. No bind => empty slot.
  const OV = {
    'screen-321-1': [
      // ---- indicators (all bound: active unit) ----
      { k: 'tt1',  t: 'ind', x: 396,  y: 178, tag: 'TT-321001', bind: 'TI_top1',     u: 'C',     dec: 1 },
      { k: 'tt2',  t: 'ind', x: 624,  y: 175, tag: 'TT-321002', bind: 'TI_top2',     u: 'C',     dec: 1 },
      { k: 'py2',  t: 'ind', x: 797,  y: 119, tag: 'PY-321202', bind: 'PY_321202',   u: 'BAR G', dec: 1 },
      { k: 'ipy',  t: 'ind', x: 797,  y: 175, tag: 'IPY-321201',bind: 'PY_321201',   u: 'BAR G', dec: 1 },
      { k: 'pd3',  t: 'ind', x: 878,  y: 223, tag: 'PDY-321203',bind: 'PDY_321203',  u: 'BAR G', dec: 1 },
      { k: 'pd4',  t: 'ind', x: 1054, y: 176, tag: 'PDY-321204',bind: 'PDY_321204',  u: 'BAR G', dec: 1 },
      { k: 't20',  t: 'ind', x: 1119, y: 246, tag: 'TT-321020', bind: 'TI_321020',   u: 'C',     dec: 1 },
      { k: 'ft',   t: 'ind', x: 296,  y: 235, tag: 'FT-321401', bind: 'FI_321401',   u: 'T/H',   dec: 2 },
      { k: 'fqi',  t: 'ind', x: 292,  y: 280, tag: 'FQI-321401',bind: 'totalizer',   u: 'T',     dec: 2 },
      { k: 'pt1',  t: 'ind', x: 749,  y: 317, tag: 'PT-321201', bind: 'PI_321201',   u: 'BAR G', dec: 1 },
      { k: 'pt2',  t: 'ind', x: 949,  y: 317, tag: 'PT-321202', bind: 'PI_321202',   u: 'BAR G', dec: 1 },
      { k: 'i61',  t: 'ind', x: 894,  y: 469, tag: 'IT-321961', bind: 'pumpA.current',u: 'A',    dec: 1 },
      { k: 'i62',  t: 'ind', x: 1119, y: 469, tag: 'IT-321962', bind: 'pumpB.current',u: 'A',    dec: 1 },
      { k: 's50',  t: 'ind', x: 862,  y: 528, tag: 'SIC-321950',bind: 'controllers.SIC_321950.pv',u: 'RPM',  dec: 1, fp: 'SIC_321950', mode: 'controllers.SIC_321950.mode' },
      { k: 's51',  t: 'ind', x: 1104, y: 528, tag: 'SIC-321951',bind: 'controllers.SIC_321951.pv',u: 'RPM',  dec: 1, fp: 'SIC_321951', mode: 'controllers.SIC_321951.mode' },
      { k: 'nca',  t: 'ind', x: 296,  y: 522, tag: 'N/C Ratio 321P002A', bind: 'ratio.NC_A', u: '', dec: 3 },
      { k: 'ncb',  t: 'ind', x: 300,  y: 587, tag: 'N/C Ratio 321P002B', bind: 'ratio.NC_B', u: '', dec: 3 },
      { k: 'lsl',  t: 'ind', x: 513,  y: 264, tag: 'LSL-321501', bind: 'LI_321501',  u: '%',     dec: 1 },
      { k: 'ft3',  t: 'ind', x: 93,   y: 452, tag: 'FT-322403', bind: 'CO2_FEED.FT_322403', u: 'NM3/H', dec: 0 },   // CO2 feed 320K002 -> XV-322902 -> 322E001
      // ---- pumps ----
      { k: 'pa',  t: 'pump', x: 861,  y: 445, bind: 'pumpA', id: 'A', tag: '321P002A' },
      { k: 'pb',  t: 'pump', x: 1087, y: 445, bind: 'pumpB', id: 'B', tag: '321P002B' },
      // ---- XVs ----
      { k: 'xva', t: 'xv',   x: 629,  y: 230, bind: 'XV_321901', cmd: '321901', tag: 'XV-321901' },
      { k: 'xvb', t: 'xv',   x: 1198, y: 337, bind: 'XV_322901', cmd: '322901', tag: 'XV-322901' },
      // 21.4 interlock override pushbutton (beside XV-322901): opens the NH3 shut-off XV while the
      //   loss-of-CO2 21.4 interlock is latched.  Lamp lit = interlock latched (override armed).
      { k: 'ovrd322901', t: 'ovrd', x: 1198, y: 382, cmd: '322901', latch: '21_4', xv: 'XV_322901', tag: 'XV-322901 INTERLOCK OVERRIDE' },
    ],
    'screen-322-2': [
      // ---- indicators: ALL tags positioned; only 3 bound, rest = white-frame empty slots ----
      { k: 'ti09',  t: 'ind', x: 225, y: 68,  tag: 'TI-322009',  bind: 'SCRUB_322E003.TT_322009',  u: 'C', dec: 1 },
      { k: 'tt11',  t: 'ind', x: 390, y: 65,  tag: 'TT-322011',  bind: 'SCRUB_322E003.TT_322011',  u: 'C', dec: 1 },
      { k: 'h604',  t: 'ind', x: 929, y: 63,  tag: 'HIC-322604', bind: 'SCRUB_322E003.HIC_322604', u: '%', dec: 1, face: 'hic' },
      { k: 'hv604', t: 'ind', x: 928, y: 137, tag: 'HV-322604',  bind: 'SCRUB_322E003.HV_322604',  u: '%', dec: 1, face: 'hic' },
      { k: 'ti12',  t: 'ind', x: 143, y: 152, tag: 'TT-322012', bind: 'EJ_322F001.TT_322012', u: 'C',     dec: 1 },
      { k: 'pi2',   t: 'ind', x: 239, y: 151, tag: 'PI-329201', bind: 'EJ_322F001.PI_329201', u: 'BAR A', dec: 1 },
      { k: 'i007',  t: 'ind', x: 995, y: 227, tag: 'IT-329007'  },
      { k: 'ti02',  t: 'ind', x: 255, y: 243, tag: 'TI-322002', bind: 'EJ_322F001.TI_322002', u: 'C',     dec: 1 },
      { k: 'tv05',  t: 'ind', x: 714, y: 253, tag: 'TV-329005',  bind: 'SCRUB_322E003.ccw.TIC_329005.op', u: '%',   dec: 1 },
      { k: 'tic05', t: 'ind', x: 497, y: 277, tag: 'TIC-329005', bind: 'SCRUB_322E003.ccw.TIC_329005.pv', u: 'C',   dec: 1, mode: 'SCRUB_322E003.ccw.TIC_329005.mode' },
      { k: 'lt01',  t: 'ind', x: 142, y: 306, tag: 'LT-329501',  bind: 'SCRUB_322E003.LT_329501',        u: '%',   dec: 1 },
      { k: 'fic09', t: 'ind', x: 590, y: 334, tag: 'FIC-329409', bind: 'SCRUB_322E003.ccw.FIC_329409.pv', u: 'T/H', dec: 1, mode: 'SCRUB_322E003.ccw.FIC_329409.mode' },
      { k: 'fv09',  t: 'ind', x: 714, y: 327, tag: 'FV-329409',  bind: 'SCRUB_322E003.ccw.FIC_329409.op', u: '%',   dec: 1 },
      { k: 'tdy25', t: 'ind', x: 494, y: 344, tag: 'TDY-329125', bind: 'SCRUB_322E003.ccw.TDY_329125',   u: 'C',   dec: 1 },
      { k: 'i008',  t: 'ind', x: 995, y: 351, tag: 'IT-329008'  },
      { k: 'ti25',  t: 'ind', x: 988, y: 402, tag: 'TI-329125',  bind: 'SCRUB_322E003.ccw.TT_329125',    u: 'C', dec: 1 },
      { k: 'h602',  t: 'ind', x: 103, y: 531, tag: 'HIC-322602',bind: 'EJ_322F001.HIC_322602', u: '%',     dec: 1, face: 'hic' },
      { k: 't21',   t: 'ind', x: 148, y: 652, tag: 'TI-321020', bind: 'TI_321020',  u: 'C',     dec: 1 },
      // pumps (state-only: no backend toggle handler yet -> local toggle)
      { k: 'p2a', t: 'pump', x: 558, y: 43,  tag: '329P002A' },
      { k: 'p2b', t: 'pump', x: 558, y: 84,  tag: '329P002B' },
      { k: 'p6a', t: 'pump', x: 956, y: 246, tag: '329P006A' },
      { k: 'p6b', t: 'pump', x: 956, y: 323, tag: '329P006B' },
      { k: 'p4a', t: 'pump', x: 795, y: 447, tag: '329P004A' },
      { k: 'p4b', t: 'pump', x: 795, y: 507, tag: '329P004B', def: false },
      // XVs
      { k: 'xv3', t: 'xv',   x: 226, y: 466, tag: 'XV-322903' },
      { k: 'xv1', t: 'xv',   x: 214, y: 593, bind: 'XV_322901', cmd: '322901', tag: 'XV-322901' },
      // HV-322602 opening (driven by HIC-322602) — placed below h602 per updated 322-2 tagged
      { k: 'hv602', t: 'ind', x: 128, y: 578, tag: 'HV-322602', bind: 'EJ_322F001.HIC_322602', u: '%', dec: 1, face: 'hic' },
      // ---- stream-inspector hotspots (click = composition/properties popup; drag in edit mode to align) ----
      { k: 'strm-soffg', t: 'strm', stream: 'SCRUB_OFFGAS',    tag: 'SCRUBBER OFF-GAS → HV-322604', x: 560,  y: 60,  w: 230, h: 16 },
      { k: 'strm-soglp', t: 'strm', stream: 'SCRUB_OFFGAS_LP', tag: 'OFF-GAS LP → 322C001',         x: 1005, y: 150, w: 150, h: 16 },
      { k: 'strm-ccws',  t: 'strm', stream: 'CCW_SUPPLY',      tag: 'CCW SUPPLY → 322E003',         x: 840,  y: 285, w: 90,  h: 16 },
      { k: 'strm-ccwr',  t: 'strm', stream: 'CCW_RETURN',      tag: 'CCW RETURN → 329P006 A/B',     x: 1010, y: 430, w: 80,  h: 16 },
      // ---- screen-nav hotspots (Item 3): jump to equipment's home screen ----
      { k: 'nav-r001', t: 'nav', x: 6, y: 104, w: 78, h: 24, tag: '322R001 → 322-1', goto: 'screen-322-1' },
      { k: 'nav-e002', t: 'nav', x: 6, y: 164, w: 96, h: 26, tag: '322E002 → 322-1', goto: 'screen-322-1' },
      { k: 'nav-p002', t: 'nav', x: 6, y: 622, w: 98, h: 24, tag: '321P002A/B → 321-1', goto: 'screen-321-1' },
    ],
    'screen-322-1': [
      // ===== STREAM-INSPECTOR HOTSPOTS (clickable process lines; drag in edit mode to align) =====
      { k: 'strm-co2',   t: 'strm', stream: 'CO2_FEED',     tag: 'CO2 FEED GAS',          x: 360, y: 600, w: 160, h: 20 },
      { k: 'strm-nh3',   t: 'strm', stream: 'NH3_FEED',     tag: 'NH3 EX 309E005',        x: 360, y: 418, w: 160, h: 18 },
      { k: 'strm-disch', t: 'strm', stream: 'HP_DISCH',     tag: 'NH3 HP DISCHARGE',      x: 560, y: 300, w: 160, h: 18 },
      { k: 'strm-carb',  t: 'strm', stream: 'CARB_RECYCLE', tag: 'CARBAMATE EX 322E003',  x: 560, y: 360, w: 160, h: 18 },
      { k: 'strm-ejd',   t: 'strm', stream: 'EJ_DISCH',     tag: 'CARB. LIQ. → 322E002',  x: 760, y: 340, w: 160, h: 18 },
      { k: 'strm-stop',  t: 'strm', stream: 'STRIP_TOP',    tag: 'STRIP TOP GAS',         x: 760, y: 200, w: 160, h: 18 },
      { k: 'strm-sbot',  t: 'strm', stream: 'STRIP_BOT',    tag: 'STRIP BOTTOM SOLN',     x: 1012, y: 518, w: 40, h: 110 },
      { k: 'strm-prod',  t: 'strm', stream: 'HPCC_PROD',    tag: 'HPCC PRODUCT → 322R001',x: 980, y: 300, w: 160, h: 18 },
      { k: 'strm-stm',   t: 'strm', stream: 'HPCC_STEAM',   tag: 'LP STEAM 4.4 BARA',     x: 980, y: 180, w: 160, h: 18 },
      { k: 'strm-cond',  t: 'strm', stream: 'HPCC_COND',    tag: 'BFW/COND → 322E002',    x: 980, y: 420, w: 160, h: 18 },
      { k: 'strm-rov',   t: 'strm', stream: 'REACT_OVERFLOW', tag: 'OVERFLOW → 322E001',    x: 650, y: 376, w: 220, h: 20 },
      { k: 'strm-rog',   t: 'strm', stream: 'REACT_OFFGAS',   tag: 'REACTOR GAS → 322E003', x: 840, y: 84, w: 240, h: 20 },
      // ===== CO2 FEED LINE (Item 5) — bound to backend CO2_FEED packet =====
      { k: 'hic203', t: 'ind',    x: 100,  y: 472, tag: 'HIC-322203', bind: 'CO2_FEED.HIC_322203', u: '%',     dec: 1, face: 'hic2' },
      { k: 'pv203',  t: 'avalve', x: 197,  y: 486, tag: 'PV-322203',  bind: 'CO2_FEED.PV_322203',  u: '%',     dec: 1 },
      { k: 'pic203', t: 'ind',    x: 128,  y: 525, tag: 'PIC-322203', bind: 'CO2_FEED.PIC_322203', u: 'BAR A', dec: 1, face: 'pic', mode: 'CO2_FEED.PIC_mode' },
      { k: 'fy403',  t: 'ind',    x: 289,  y: 520, tag: 'FY-322403',  bind: 'CO2_FEED.FY_322403',  u: 'T/H',   dec: 2 },
      { k: 'ft403',  t: 'ind',    x: 289,  y: 561, tag: 'FT-322403',  bind: 'CO2_FEED.FT_322403',  u: 'NM3/H', dec: 0 },
      { k: 'ti017',  t: 'ind',    x: 308,  y: 628, tag: 'TI-322017',  bind: 'CO2_FEED.TI_322017',  u: 'C',     dec: 1 },
      { k: 'xv902',  t: 'xv',     x: 830,  y: 590, tag: 'XV-322902',  bind: 'CO2_FEED.XV_322902',  cmd: '322902' },
      { k: 'load',   t: 'ind',    x: 1231, y: 698, tag: 'LOAD',       bind: 'CO2_FEED.Load',       u: '%',     dec: 1 },
      // NH3 feed (modelled in 321) — boundary tag
      { k: 'ft401',  t: 'ind',    x: 284,  y: 423, tag: 'FT-321401',  bind: 'FI_321401',           u: 'T/H',   dec: 2 },
      // ---- pumps (321P002A/B feed station — modelled in 321) ----
      { k: 'pa', t: 'pump', x: 58, y: 57,  bind: 'pumpA', id: 'A', tag: '321P002A' },
      { k: 'pb', t: 'pump', x: 58, y: 121, bind: 'pumpB', id: 'B', tag: '321P002B' },
      // ---- pump speed / ratio controllers (modelled in 321) ----
      { k: 's950b', t: 'ind', x: 491, y: 443, tag: 'SIC-321950',    bind: 'controllers.SIC_321950.pv', u: 'RPM', dec: 1, fp: 'SIC_321950', mode: 'controllers.SIC_321950.mode' },
      { k: 's951b', t: 'ind', x: 497, y: 492, tag: 'SIC-321951',    bind: 'controllers.SIC_321951.pv', u: 'RPM', dec: 1, fp: 'SIC_321951', mode: 'controllers.SIC_321951.mode' },
      { k: 'nca2',  t: 'ind', x: 419, y: 448, tag: 'N/C 321P002A',  bind: 'ratio.NC_A', u: '', dec: 3 },
      { k: 'ncb2',  t: 'ind', x: 414, y: 497, tag: 'N/C 321P002B',  bind: 'ratio.NC_B', u: '', dec: 3 },
      // ---- screen-nav hotspots (Item 3) ----
      { k: 'nav-321',  t: 'nav', x: 494,  y: 534, w: 70, h: 24, tag: '321-1',             goto: 'screen-321-1' },
      { k: 'nav-e003', t: 'nav', x: 1271, y: 78,  w: 80, h: 22, tag: '322E003 → 322-2', goto: 'screen-322-2' },
      { k: 'nav-f001', t: 'nav', x: 1283, y: 113, w: 80, h: 22, tag: '322F001 → 322-2', goto: 'screen-322-2' },
      // ---- white-frame (unbound: downstream 322 reactor/scrubber/condenser, bind when modelled) ----
      { k: 'at701',  t: 'ind', x: 209,  y: 285, tag: 'AT-322701', bind: 'REACT_322R001.AT_322701', u: 'N/C', dec: 3 },
      { k: 'lt504',  t: 'ind', x: 354,  y: 326, tag: 'LT-322504', bind: 'REACT_322R001.LT_322504', u: '%', dec: 1 },
      { k: 'pt9201', t: 'ind', x: 740,  y: 42,  tag: 'PT-329201', bind: 'EJ_322F001.PI_329201', u: 'BAR A', dec: 1 },   // same loop 329201 as 322-2 PI-329201 (322E003 overflow P); PT=field xmtr, PI=indicator, one backend key
      { k: 'tt009',  t: 'ind', x: 595,  y: 105, tag: 'TT-322009', bind: 'REACT_322R001.TT_322009', u: 'C', dec: 1 },
      { k: 'tt005',  t: 'ind', x: 543,  y: 145, tag: 'TT-322005', bind: 'REACT_322R001.TT_322005', u: 'C', dec: 1 },
      { k: 'tt012b', t: 'ind', x: 735,  y: 145, tag: 'TT-322012', bind: 'HPCC_322E002.TT_322012', u: 'C', dec: 1 },   // 322F001 ejector-disch liquid feed -> 322E002
      { k: 'tt013',  t: 'ind', x: 864,  y: 143, tag: 'TT-322013', bind: 'STRIP_322E001.TT_322013', u: 'C', dec: 1 },
      { k: 'tt006',  t: 'ind', x: 543,  y: 195, tag: 'TT-322006', bind: 'REACT_322R001.TT_322006', u: 'C', dec: 1 },
      { k: 'ft9407', t: 'ind', x: 807,  y: 212, tag: 'FT-329407' },
      { k: 'tt007',  t: 'ind', x: 543,  y: 247, tag: 'TT-322007', bind: 'REACT_322R001.TT_322007', u: 'C', dec: 1 },
      { k: 'tt008',  t: 'ind', x: 543,  y: 297, tag: 'TT-322008', bind: 'REACT_322R001.TT_322008', u: 'C', dec: 1 },
      { k: 'tt010',  t: 'ind', x: 597,  y: 335, tag: 'TT-322010', bind: 'HPCC_322E002.TT_322010', u: 'C', dec: 1 },   // 322E002 liquid product temp -> 322R001
      { k: 'h605',   t: 'ind', x: 830,  y: 325, tag: 'HIC-322605', bind: 'REACT_322R001.HIC_322605', u: '%', dec: 1, face: 'hic' },
      { k: 'pt9206', t: 'ind', x: 1242, y: 145, tag: 'PT-329206', bind: 'STEAM_SYSTEM.LP.P_bara', u: 'BAR A', dec: 2 },   // LP header P (same node as PI-329206)
      { k: 'tt9001', t: 'ind', x: 1048, y: 259, tag: 'TT-329001', bind: 'HPCC_322E002.TT_329001', u: 'C', dec: 1 },   // 322D001 A/B condensate -> 322E002 shell (BFW feed)
      { k: 'py9207', t: 'ind', x: 1094, y: 208, tag: 'PY-329207B' },
      { k: 'tt014',  t: 'ind', x: 638,  y: 398, tag: 'TT-322014', bind: 'STRIP_322E001.TT_322014', u: 'C', dec: 1 },
      { k: 'hv605',  t: 'ind', x: 823,  y: 392, tag: 'HV-322605', bind: 'REACT_322R001.HV_322605', u: '%', dec: 1, face: 'hic' },
      { k: 'lic501', t: 'ind', x: 861,  y: 471, tag: 'LIC-322501', bind: 'STRIP_322E001.LIC_322501.pv', u: '%', dec: 1, mode: 'STRIP_322E001.LIC_322501.mode' },
      { k: 'pic9204',t: 'ind', x: 1113, y: 380, tag: 'PIC-329204', bind: 'STEAM_SYSTEM.PIC_329204.pv', u: 'BAR A', dec: 2,
        mode: 'STEAM_SYSTEM.PIC_329204.mode', note: 'AUTO holds 329D005 at SP via PV-329204; MAN sets PV-329204 opening directly' },   // 329D005 = 322E001 shell P
      { k: 'hic9601',t: 'ind', x: 1127, y: 489, tag: 'HIC-329601', bind: 'STEAM_SYSTEM.HP_VENT.pct', u: '%', dec: 1, face: 'hic' },
      { k: 'ft9403', t: 'ind', x: 1127, y: 520, tag: 'FT-329403' },
      { k: 'lv501',  t: 'ind', x: 1110, y: 612, tag: 'LV-322501', bind: 'STRIP_322E001.LV_322501', u: '%', dec: 1 },
      { k: 'tt004',  t: 'ind', x: 1037, y: 619, tag: 'TT-322004', bind: 'STRIP_322E001.TT_322004', u: 'C', dec: 1 },
      { k: 'pt3201', t: 'ind', x: 1187, y: 617, tag: 'PT-323201', bind: 'RECIRC_323.C003.P_bara', u: 'BAR A', dec: 2,
        note: 'rect col 323C003 pressure; rises with top-vapour 305 as LV-322501 opens (K_P = 1.20 bar a per unit fractional gas-phase excess)' },
    ],
    'screen-329-1': [
      // Positions rescanned from tagged 329-1 shot (value-box centres, transform x*1.2936 / y*1.4343).
      // ===== 25-bar BL supply header (stream 901 ex 320E006) =====
      { k: 'pt251',  t: 'ind', x: 136, y: 627, tag: 'PT-329251',  bind: 'STEAM_SYSTEM.SUPPLY_25BAR.P_bara', u: 'BAR A', dec: 2 },
      { k: 'tt101',  t: 'ind', x: 191, y: 651, tag: 'TT-329101',  bind: 'STEAM_SYSTEM.SUPPLY_25BAR.TI_sat', u: 'C',     dec: 1 },
      { k: 'ft403',  t: 'ind', x: 52,  y: 640, tag: 'FT-329403' },                                       // supply flow — no dedicated packet stream, white frame
      // ===== 329D005 HP saturator (stream 902; PIC-329204 / PV-329204) + HP atm vent HIC/HV-329601 =====
      { k: 'pic204', t: 'ind',    x: 317, y: 634, tag: 'PIC-329204', bind: 'STEAM_SYSTEM.PIC_329204.pv', u: 'BAR A', dec: 2,
        mode: 'STEAM_SYSTEM.PIC_329204.mode', note: 'AUTO holds 329D005 at SP via PV-329204; MAN sets PV-329204 opening directly' },   // 329D005 = 322E001 shell P
      { k: 'pv204',  t: 'avalve', x: 313, y: 703, tag: 'PV-329204',  bind: 'STEAM_SYSTEM.MP.supply_pct', u: '%',     dec: 1 },
      { k: 'hic601', t: 'ind',    x: 211, y: 370, tag: 'HIC-329601', bind: 'STEAM_SYSTEM.HP_VENT.pct',   u: '%',     dec: 1, face: 'hic' },   // hand ctrl of 329D005 atm vent
      { k: 'hv601',  t: 'ind',    x: 140, y: 438, tag: 'HV-329601',  bind: 'STEAM_SYSTEM.HP_VENT.pct',   u: '%',     dec: 1, face: 'hic' },   // 329D005 atm vent valve
      // ===== 329D009 MP 9-bar drum (split-range PIC-329205 : PV-329205A admit / PV-329205B let-down) =====
      { k: 'pic205', t: 'ind',    x: 653, y: 430, tag: 'PIC-329205', bind: 'STEAM_SYSTEM.PIC_329205.pv', u: 'BAR A', dec: 2,
        mode: 'STEAM_SYSTEM.PIC_329205.mode', note: 'up P9 => PV-329205B let-down (9->4 bar) opens; down P9 => PV-329205A admits 25-bar BL steam' },
      { k: 'pv205a', t: 'avalve', x: 589, y: 548, tag: 'PV-329205A', bind: 'STEAM_SYSTEM.DRUM_9BAR.admit_pct',   u: '%', dec: 1 },
      { k: 'pv205b', t: 'avalve', x: 847, y: 361, tag: 'PV-329205B', bind: 'STEAM_SYSTEM.DRUM_9BAR.letdown_pct', u: '%', dec: 1 },
      { k: 'lic503', t: 'ind',    x: 1002, y: 505, tag: 'LIC-329503', bind: 'STEAM_SYSTEM.LIC_329503.pv', u: '%', dec: 1,
        mode: 'STEAM_SYSTEM.LIC_329503.mode', note: 'AUTO holds 329D009 level via LV-329503 drain to 322D001A/B; MAN sets LV-329503 opening directly' },
      { k: 'lv503',  t: 'avalve', x: 1002, y: 581, tag: 'LV-329503',  bind: 'STEAM_SYSTEM.LIC_329503.op', u: '%', dec: 1 },
      // ===== 322D001A/B LP drums + 4-bar header pressure indicators (PI-329206 / PI-329207) =====
      { k: 'tt001',  t: 'ind',    x: 614, y: 271, tag: 'TT-329001',  bind: 'STEAM_SYSTEM.LP.TI_sat',  u: 'C',     dec: 1 },   // temp inside 322D001A/B
      { k: 'pi206',  t: 'ind',    x: 625, y: 179, tag: 'PI-329206',  bind: 'STEAM_SYSTEM.LP.P_bara',  u: 'BAR A', dec: 2 },
      { k: 'pi207',  t: 'ind',    x: 753, y: 179, tag: 'PI-329207',  bind: 'STEAM_SYSTEM.LP.P_bara',  u: 'BAR A', dec: 2 },   // 2nd header P indicator
      { k: 'lic504', t: 'ind',    x: 394,  y: 222, tag: 'LIC-329504', bind: 'STEAM_SYSTEM.LIC_329504.pv', u: '%', dec: 1,
        mode: 'STEAM_SYSTEM.LIC_329504.mode', note: 'reverse-acting: AUTO holds 322D001A/B level via LV-329504 make-up from 329P001A/B pumps; MAN sets LV-329504 opening directly' },
      { k: 'lv504',  t: 'avalve', x: 194,  y: 294, tag: 'LV-329504',  bind: 'STEAM_SYSTEM.LIC_329504.op', u: '%', dec: 1 },
      // ===== 4-bar header MASTER SP trio (A vent SP+0.1 / B turbine make-up SP / C BL make-up SP-0.1) =====
      // all 3 controllers open the MASTER SP faceplate (managed as one when MASTER ON).
      { k: 'msp',     t: 'ind', x: 52,  y: 90,  tag: 'MASTER-SP',   fp: 'MASTER_SP_329207' },
      { k: 'startup', t: 'ind', x: 26,  y: 166, tag: 'STARTUP SW' },   // start-up mode pushbutton (unmodelled)
      { k: 'pic207a', t: 'ind', x: 983,  y: 112, tag: 'PIC-329207A', bind: 'STEAM_SYSTEM.PIC_329207A.pv', u: 'BAR A', dec: 2, fp: 'MASTER_SP_329207', mode: 'STEAM_SYSTEM.PIC_329207A.mode' },   // vent leg (SP+0.1)
      { k: 'pic207b', t: 'ind', x: 1184, y: 75,  tag: 'PIC-329207B', bind: 'STEAM_SYSTEM.PIC_329207B.pv', u: 'BAR A', dec: 2, fp: 'MASTER_SP_329207', mode: 'STEAM_SYSTEM.PIC_329207B.mode' },   // 320MT02 turbine make-up (SP)
      { k: 'pic207c', t: 'ind', x: 317,  y: 143, tag: 'PIC-329207C', bind: 'STEAM_SYSTEM.PIC_329207C.pv', u: 'BAR A', dec: 2, fp: 'MASTER_SP_329207', mode: 'STEAM_SYSTEM.PIC_329207C.mode' },   // BL make-up (SP-0.1)
      { k: 'pv207a',  t: 'avalve', x: 828,  y: 178, tag: 'PV-329207A', bind: 'STEAM_SYSTEM.PIC_329207A.op', u: '%', dec: 1 },   // 4-bar vent valve (leg A)
      { k: 'pv207b',  t: 'avalve', x: 1190, y: 215, tag: 'PV-329207B', bind: 'STEAM_SYSTEM.PIC_329207B.op', u: '%', dec: 1 },   // 320MT02 turbine make-up valve (leg B)
      { k: 'pv207c',  t: 'avalve', x: 301,  y: 383, tag: 'PV-329207C', bind: 'STEAM_SYSTEM.PIC_329207C.op', u: '%', dec: 1 },   // BL make-up valve (leg C, stream 963)
      { k: 'hic602',  t: 'ind',    x: 301,  y: 420, tag: 'HIC-329602', bind: 'STEAM_SYSTEM.PIC_329207C.op', u: '%', dec: 1, face: 'hic' },   // 963 make-up hand ctrl -> PV-329207C opening
      { k: 'hv602',   t: 'ind',    x: 291,  y: 475, tag: 'HV-329602',  bind: 'STEAM_SYSTEM.PIC_329207C.op', u: '%', dec: 1, face: 'hic' },   // 963 make-up isolation -> PV-329207C opening
      { k: 'ft407',   t: 'ind',    x: 1081, y: 141, tag: 'FT-329407'  },   // 320MT02 turbine steam flow
      // ===== 329D005 level (LIC/LV-329502) + O2-scavenger dosing pumps =====
      { k: 'lic502',  t: 'ind',    x: 744, y: 625, tag: 'LIC-329502', bind: 'STEAM_SYSTEM.LIC_329502.pv', u: '%', dec: 1,
        mode: 'STEAM_SYSTEM.LIC_329502.mode', note: 'AUTO holds 329D005 level via LV-329502 drain to 329D009; MAN sets LV-329502 opening directly' },
      { k: 'lv502',   t: 'avalve', x: 731, y: 697, tag: 'LV-329502',  bind: 'STEAM_SYSTEM.LIC_329502.op', u: '%', dec: 1 },
      { k: 'u001m01', t: 'pump', x: 1262, y: 570, tag: '329U001-M01' },   // O2 scavenger dosing (unmodelled -> local toggle)
      { k: 'u001m02', t: 'pump', x: 1262, y: 651, tag: '329U001-M02' },
      // ===== screen-nav hotspots: boundary exchangers with live 322-1 home screen =====
      { k: 'nav-e002a', t: 'nav', x: 48, y: 158, w: 80, h: 24, tag: '322E002 -> 322-1', goto: 'screen-322-1' },
      { k: 'nav-e002b', t: 'nav', x: 68, y: 317, w: 80, h: 24, tag: '322E002 -> 322-1', goto: 'screen-322-1' },
      { k: 'nav-e001a', t: 'nav', x: 68, y: 446, w: 80, h: 24, tag: '322E001 -> 322-1', goto: 'screen-322-1' },
      { k: 'nav-e001b', t: 'nav', x: 68, y: 490, w: 80, h: 24, tag: '322E001 -> 322-1', goto: 'screen-322-1' },
    ],
    // ============================ 323-1  LP RECIRCULATION & PRE-EVAPORATION ============================
    // coords = STAGE 1366x720 (tagged native 1287x612 scaled x1.06138 / y1.17647).  bind -> RECIRC_323 telemetry tree.
    // unbound `ind` = WHITE FRAME (unmodelled boundary/downstream, tag text only).  3 cascade slaves flagged cas:true.
    'screen-323-1': [
      // ---- 323C003 rectifying column / 323E002 heater : isenthalpic letdown -> 4.1 bar, hold 135 C ----
      { k: 'tt001', t: 'ind', x: 255, y: 133, tag: 'TT-323001', bind: 'RECIRC_323.C003.feed_T',   u: 'C',     dec: 1 },   // feed ex 322E001
      { k: 'tt002', t: 'ind', x: 388, y: 496, tag: 'TT-323002', bind: 'RECIRC_323.C003.TT_323002', u: 'C',     dec: 1 },   // column bottoms 135 C
      { k: 'pt201', t: 'ind', x: 482, y: 232, tag: 'PT-323201', bind: 'RECIRC_323.C003.P_bara',    u: 'BAR A', dec: 2 },
      { k: 'tic07', t: 'ind', x: 448, y: 441, tag: 'TIC-323007', bind: 'RECIRC_323.C003.TIC_323007.pv', mode: 'RECIRC_323.C003.TIC_323007.mode', u: 'C',     dec: 1, note: 'master: cascades PIC-329202 steam-P to 323E002 to hold 135 C' },
      { k: 'pic02', t: 'ind', x: 137, y: 244, tag: 'PIC-329202', bind: 'RECIRC_323.C003.PIC_329202.pv', mode: 'RECIRC_323.C003.PIC_329202.mode', u: 'BAR A', dec: 2, cas: true, note: 'slave: CAS follows TIC-323007; drives PV-329202 steam to 323E002' },
      { k: 'pv02',  t: 'avalve', x: 108, y: 333, tag: 'PV-329202', bind: 'RECIRC_323.C003.PIC_329202.op', u: '%', dec: 1 },
      { k: 'lic01', t: 'ind', x: 482, y: 289, tag: 'LIC-323501', bind: 'RECIRC_323.C003.LIC_323501.pv', mode: 'RECIRC_323.C003.LIC_323501.mode', u: '%', dec: 1, note: 'holds 323C003 level via LV-323501 bottoms drain to 323F004' },
      { k: 'lv01',  t: 'avalve', x: 469, y: 381, tag: 'LV-323501', bind: 'RECIRC_323.C003.LIC_323501.op', u: '%', dec: 1 },
      { k: 'lic01b',t: 'ind', x: 177, y: 555, tag: 'LIC-323501', bind: 'RECIRC_323.C003.LIC_323501.pv', mode: 'RECIRC_323.C003.LIC_323501.mode', u: '%', dec: 1 },   // dup readout, recycle line
      { k: 'lv01b', t: 'avalve', x: 162, y: 625, tag: 'LV-323501', bind: 'RECIRC_323.C003.LIC_323501.op', u: '%', dec: 1 },   // dup valve symbol
      // ---- 323F004 flash tank : adiabatic flash -> 1.13 bar, ~106 C ----
      { k: 'tt14',  t: 'ind', x: 695, y: 361, tag: 'TT-323014', bind: 'RECIRC_323.F004.TT_323005', u: 'C', dec: 1 },
      { k: 'lic05', t: 'ind', x: 761, y: 279, tag: 'LIC-323505', bind: 'RECIRC_323.F004.LIC_323505.pv', mode: 'RECIRC_323.F004.LIC_323505.mode', u: '%', dec: 1, note: 'holds 323F004 level via LV-323505 drain to 323F010 pre-evaporator' },
      { k: 'lv05',  t: 'avalve', x: 751, y: 527, tag: 'LV-323505', bind: 'RECIRC_323.F004.LIC_323505.op', u: '%', dec: 1 },
      // ---- 323F010 / 323E010 pre-evaporator : vacuum 0.46 bar, hold 99 C ----
      { k: 'pt204', t: 'ind', x: 996, y: 244, tag: 'PT-323204', bind: 'RECIRC_323.F010.P_bara', u: 'BAR A', dec: 2 },
      { k: 'tic12', t: 'ind', x: 1040, y: 418, tag: 'TIC-323012', bind: 'RECIRC_323.F010.TIC_323012.pv', mode: 'RECIRC_323.F010.TIC_323012.mode', u: 'C', dec: 1, note: 'master: cascades PIC-329208 steam-P to 323E010 to hold 99 C' },
      { k: 'pic08', t: 'ind', x: 1153, y: 309, tag: 'PIC-329208', bind: 'RECIRC_323.F010.PIC_329208.pv', mode: 'RECIRC_323.F010.PIC_329208.mode', u: 'BAR A', dec: 2, cas: true, note: 'slave: CAS follows TIC-323012; drives PV-329208 steam to 323E010' },
      { k: 'pv08',  t: 'avalve', x: 1140, y: 391, tag: 'PV-329208', bind: 'RECIRC_323.F010.PIC_329208.op', u: '%', dec: 1 },
      // ---- 323D002 urea solution tank : atmospheric, two-compartment (I active 80 m3 / II passive 300 m3) ----
      { k: 'tt103', t: 'ind', x: 761, y: 707, tag: 'TT-323103', bind: 'RECIRC_323.D002.T_C',      u: 'C', dec: 1 },
      { k: 'lt504', t: 'ind', x: 817, y: 665, tag: 'LT-323504', bind: 'RECIRC_323.D002.LI_comp2', u: '%', dec: 1 },   // passive compartment II
      { k: 'lic07', t: 'ind', x: 1087, y: 665, tag: 'LIC-323507', bind: 'RECIRC_323.D002.LIC_323507.pv', mode: 'RECIRC_323.D002.LIC_323507.mode', u: '%', dec: 1, note: 'master: active compartment I level cascades FIC-324401 product flow' },
      { k: 'fic01', t: 'ind', x: 1270, y: 674, tag: 'FIC-324401', bind: 'RECIRC_323.D002.FIC_324401.pv', mode: 'RECIRC_323.D002.FIC_324401.mode', u: 'T/H', dec: 2, cas: true, note: 'slave: CAS follows LIC-323507; product to 324 evap via 323P003 A/B' },
      { k: 'pic203',  t: 'ind', x: 609,  y: 122, tag: 'PIC-323203', bind: 'LPCC_3232.E011.PIC_323203.pv', u: 'BAR A', dec: 2,
        mode: 'LPCC_3232.E011.PIC_323203.mode', note: '323E011/D011 LP node P; flash vapour 701 (LV-323501 -> 323F004) accumulates it. AUTO holds SP via PV-323203; MAN lets P ramp' },
      { k: 'tt004',   t: 'ind', x: 439,  y: 124, tag: 'TT-323004', bind: 'RECIRC_323.C003.feed_T', u: 'C', dec: 1 },   // rect col top vapour 119C (flash feed T)
      { k: 'hic605',  t: 'ind', x: 992,  y: 142, tag: 'HIC-323605', bind: 'EVAP_324.VAC.vent_kgh', u: 'kg/h', dec: 1 },   // 324E002 vent hand ctrl -> non-condensable vent flow
      { k: 'pv203',   t: 'ind', x: 1220, y: 142, tag: 'PV-323203', bind: 'LPCC_3232.E011.PIC_323203.op', u: '%', dec: 1 },   // GCB off-gas valve stroke -> vapour 011 to 323C005
      { k: 'hv605',   t: 'ind', x: 1058, y: 199, tag: 'HV-323605',  bind: 'EVAP_324.VAC.vent_kgh', u: 'kg/h', dec: 1 },   // 324E002 vent valve -> non-condensable vent flow
      { k: 'pic4202', t: 'ind', x: 1277, y: 209, tag: 'PIC-324202', bind: 'EVAP_324.E001.PIC_324202.pv', u: 'BAR A', dec: 3,
        mode: 'EVAP_324.E001.PIC_324202.mode' },   // 324E002 pressure
      // ---- WHITE FRAMES : unmodelled boundary / downstream (tag only; bind when upstream modelled) ----
      { k: 'fic5407', t: 'ind', x: 1214, y: 468, tag: 'FIC-335407' },   // 335 pump flow (downstream unit)
      { k: 'fv5407',  t: 'ind', x: 1116, y: 549, tag: 'FV-335407'  },   // 335 valve (downstream unit)
    ],
    // ============================ 323-2  LP RECIRCULATION 2 (323D001 / 323E003 / 323E011 / 323C005) ============================
    // coords = STAGE 1366x720 (native 1357x644 scaled x1.006632 / y1.118012).  root LPCC_3232 (+ DESORB_328.D001 / ABSORB_328 cross-refs drawn on this screen).
    'screen-323-2': [
      // ---- 323D001 solution tank + 323E003 heater : E003 block, ~85 C, 4.0 barg, pump-speed pair ----
      { k: 'tt003',  t: 'ind', x: 292,  y: 434, tag: 'TT-323003',  bind: 'LPCC_3232.E003.TT_323003',    u: 'C',     dec: 1 },   // 85.5 C 323E003 outlet
      { k: 'pic202', t: 'ind', x: 149,  y: 302, tag: 'PIC-323202', bind: 'LPCC_3232.E003.PIC_323202.pv', mode: 'LPCC_3232.E003.PIC_323202.mode', u: 'BAR A', dec: 2, note: 'holds 323D001 off-gas pressure via PV-323202 vent to GCB' },
      { k: 'pv202',  t: 'avalve', x: 38, y: 134, tag: 'PV-323202', bind: 'LPCC_3232.E003.PIC_323202.op', u: '%', dec: 1 },
      { k: 'lt502',  t: 'ind', x: 40,   y: 440, tag: 'LT-323502',  bind: 'LPCC_3232.E003.LI_323502',    u: '%',     dec: 1 },   // 323D001 level
      { k: 'sic901', t: 'ind', x: 40,   y: 552, tag: 'SIC-323901', bind: 'LPCC_3232.E003.SIC_323901.pv', mode: 'LPCC_3232.E003.SIC_323901.mode', u: 'RPM', dec: 0, note: '323P001A pump speed; MAN/AUTO/CAS' },
      { k: 'sic902', t: 'ind', x: 211,  y: 556, tag: 'SIC-323902', bind: 'LPCC_3232.E003.SIC_323902.pv', mode: 'LPCC_3232.E003.SIC_323902.mode', u: 'RPM', dec: 0, note: '323P001B pump speed; MAN/AUTO/CAS' },
      { k: 'tic013', t: 'ind', x: 285,  y: 345, tag: 'TIC-323013', bind: 'LPCC_3232.E003.TIC_323013.pv', mode: 'LPCC_3232.E003.TIC_323013.mode', u: 'C', dec: 1, note: 'holds 323E003 tempered-water supply temp (55 C) via the TV-323013A/B split range' },
      { k: 'tv013a', t: 'avalve', x: 297, y: 197, tag: 'TV-323013A', bind: 'LPCC_3232.E003.TV_323013A', u: '%', dec: 1 },   // cold make-up
      { k: 'tv013b', t: 'avalve', x: 362, y: 268, tag: 'TV-323013B', bind: 'LPCC_3232.E003.TV_323013B', u: '%', dec: 1 },   // hot bypass (opposite)
      // ---- 323C005 rectifying column : C005 block ----
      { k: 'ttc005', t: 'ind', x: 1102, y: 108, tag: 'TT-323C005', bind: 'LPCC_3232.C005.TT_323C005',   u: 'C',   dec: 1 },   // 52.8 C overhead
      { k: 'lic503', t: 'ind', x: 1102, y: 525, tag: 'LIC-323503', bind: 'LPCC_3232.C005.LIC_323503.pv', mode: 'LPCC_3232.C005.LIC_323503.mode', u: '%', dec: 1, note: 'holds 323C005 bottoms level via LV-323503 drain' },
      { k: 'lv503',  t: 'avalve', x: 855, y: 506, tag: 'LV-323503', bind: 'LPCC_3232.C005.LIC_323503.op', u: '%', dec: 1 },
      { k: 'fic405', t: 'ind', x: 886,  y: 313, tag: 'FIC-323405', bind: 'LPCC_3232.C005.FIC_323405.pv', mode: 'LPCC_3232.C005.FIC_323405.mode', u: 'T/H', dec: 2, note: '323C005 reflux/feed flow via FV-323405' },
      { k: 'fv405',  t: 'avalve', x: 896, y: 399, tag: 'FV-323405', bind: 'LPCC_3232.C005.FIC_323405.op', u: '%', dec: 1 },
      { k: 'fic418', t: 'ind', x: 629,  y: 552, tag: 'FIC-323418', bind: 'LPCC_3232.C005.FIC_323418.pv', mode: 'LPCC_3232.C005.FIC_323418.mode', u: 'T/H', dec: 2, note: '64.2 t/h 323C005 bottoms to 323E003' },
      // ---- 323E011 / 323D011 pre-evaporator package : E011 block ----
      { k: 'tt011',  t: 'ind', x: 1027, y: 572, tag: 'TT-323011',  bind: 'LPCC_3232.E011.TT_323011',    u: 'C',   dec: 1 },
      { k: 'fic402', t: 'ind', x: 1299, y: 296, tag: 'FIC-323402', bind: 'LPCC_3232.E011.FIC_323402.pv', mode: 'LPCC_3232.E011.FIC_323402.mode', u: 'T/H', dec: 2, note: '323E011 feed/steam flow via FV-323402' },
      { k: 'fv402',  t: 'avalve', x: 1253, y: 244, tag: 'FV-323402', bind: 'LPCC_3232.E011.FIC_323402.op', u: '%', dec: 1 },
      { k: 'fic401', t: 'ind', x: 579,  y: 637, tag: 'FIC-323401', bind: 'LPCC_3232.E011.FIC_323401.pv', mode: 'LPCC_3232.E011.FIC_323401.mode', u: 'T/H', dec: 2, note: '323E011 draw flow via FV-323401' },
      { k: 'fv401',  t: 'avalve', x: 523, y: 682, tag: 'FV-323401', bind: 'LPCC_3232.E011.FIC_323401.op', u: '%', dec: 1 },
      // ---- 328D001 reflux drum (drawn on 323-2) : DESORB_328.D001 cross-ref ----
      { k: 'pic8202', t: 'ind', x: 800, y: 106, tag: 'PIC-328202', bind: 'DESORB_328.D001.PIC_328202.pv', mode: 'DESORB_328.D001.PIC_328202.mode', u: 'BAR A', dec: 2, note: '323F004/328D001 reflux drum pressure via PV-328202' },
      { k: 'pv8202', t: 'avalve', x: 549, y: 196, tag: 'PV-328202', bind: 'DESORB_328.D001.PIC_328202.op', u: '%', dec: 1 },
      { k: 'lic8501', t: 'ind', x: 493, y: 319, tag: 'LIC-328501', bind: 'DESORB_328.D001.LIC_328501.pv', mode: 'DESORB_328.D001.LIC_328501.mode', u: '%', dec: 1, note: 'holds 328D001 level via LV-328501' },
      { k: 'lv8501', t: 'avalve', x: 528, y: 500, tag: 'LV-328501', bind: 'DESORB_328.D001.LIC_328501.op', u: '%', dec: 1 },
      { k: 'tic8002', t: 'ind', x: 609, y: 366, tag: 'TIC-328002', bind: 'DESORB_328.D001.TIC_328002.pv', mode: 'DESORB_328.D001.TIC_328002.mode', u: 'C', dec: 1, note: '328D001 reflux temp via TV-328002' },
      { k: 'tv8002', t: 'avalve', x: 835, y: 215, tag: 'TV-328002', bind: 'DESORB_328.D001.TIC_328002.op', u: '%', dec: 1 },
      { k: 'fi8404', t: 'ind', x: 1163, y: 604, tag: 'FI-328404',  bind: 'DESORB_328.D001.FIC_328404.pv', u: 'M3/H', dec: 2 },
      // ---- WHITE FRAMES : unmodelled boundary / analyzer / downstream (tag text only) ----
      { k: 'tt005w', t: 'ind', x: 43,   y: 244, tag: 'TT-323005', bind: 'RECIRC_323.F004.TT_323005', u: 'C', dec: 1 },   // 323F004 flash temp (hold 106 C)
      { k: 'lt506w', t: 'ind', x: 40,   y: 369, tag: 'LT-323506'  },   // 2nd level boundary
      { k: 'p003w',  t: 'ind', x: 373,  y: 72,  tag: '329P003'    },   // 329 pumps (other unit)
      { k: 'tt015',  t: 'ind', x: 503,  y: 235, tag: 'TT-323015', bind: 'LPCC_3232.E003.TT_323015', u: 'C', dec: 1 },   // 323E003 -> 323P003 TW return (1103, 65 C)
      { k: 'pt8401w',t: 'ind', x: 614,  y: 502, tag: 'PT-328401'  },   // 328P002 discharge (unmodelled)
      { k: 'p002w',  t: 'ind', x: 624,  y: 475, tag: '328P002'    },   // reflux pumps (unmodelled toggle)
      { k: 'e003w',  t: 'ind', x: 50,   y: 680, tag: '322E003'    },   // absorber recycle boundary
      { k: 'ovr001', t: 'ovrd', x: 269, y: 635, tag: 'EXT-OVR 323P001A/B' },   // external-override arm box
    ],
    // ============================ 328-1  DESORPTION (328C002 / 328C003 / 328C004 + 328D001 reflux) ============================
    // coords = STAGE 1366x720 (native 1361x644 scaled x1.003674 / y1.118012).  root DESORB_328 (+ ABSORB_328.D003 / LPCC_3232.E003 cross-refs).
    'screen-328-1': [
      // ---- 328C002 top separator : C002 block ----
      { k: 'lic8503', t: 'ind', x: 597, y: 263, tag: 'LIC-328503', bind: 'DESORB_328.C002.LIC_328503.pv', mode: 'DESORB_328.C002.LIC_328503.mode', u: '%', dec: 1, note: 'holds 328C002 level via LV-328503' },
      { k: 'lv8503', t: 'avalve', x: 146, y: 434, tag: 'LV-328503', bind: 'DESORB_328.C002.LIC_328503.op', u: '%', dec: 1 },
      // ---- 328C003 first desorber : C003 block, PIC-328203 / TIC-328012 / FIC-326402 steam ----
      { k: 'pic8203', t: 'ind', x: 151, y: 145, tag: 'PIC-328203', bind: 'DESORB_328.C003.PIC_328203.pv', mode: 'DESORB_328.C003.PIC_328203.mode', u: 'BAR A', dec: 2, note: '328C003 overhead pressure via PV-328203' },
      { k: 'pv8203', t: 'avalve', x: 442, y: 173, tag: 'PV-328203', bind: 'DESORB_328.C003.PIC_328203.op', u: '%', dec: 1 },
      { k: 'tic8012', t: 'ind', x: 231, y: 268, tag: 'TIC-328012', bind: 'DESORB_328.C003.TIC_328012.pv', mode: 'DESORB_328.C003.TIC_328012.mode', u: 'C', dec: 1, note: '328C003 bottom temp cascades FIC-326402 LS steam' },
      { k: 'fic6402', t: 'ind', x: 35,  y: 285, tag: 'FIC-326402', bind: 'DESORB_328.C003.FIC_326402.pv', mode: 'DESORB_328.C003.FIC_326402.mode', u: 'KG/H', dec: 0, cas: true, note: 'slave: LS steam to 328E-reboiler via FV-326402' },
      { k: 'fv6402', t: 'avalve', x: 120, y: 335, tag: 'FV-326402', bind: 'DESORB_328.C003.FIC_326402.op', u: '%', dec: 1 },
      { k: 'lic8505', t: 'ind', x: 763, y: 419, tag: 'LIC-328505', bind: 'DESORB_328.C003.LIC_328505.pv', mode: 'DESORB_328.C003.LIC_328505.mode', u: '%', dec: 1, note: 'holds 328C003 bottom level via LV-328505' },
      { k: 'lv8505', t: 'avalve', x: 1144, y: 665, tag: 'LV-328505', bind: 'DESORB_328.C003.LIC_328505.op', u: '%', dec: 1 },
      // ---- 328C004 second desorber / hydrolyser : C004 block, FFIC-328401 ratio + FIC-328401 HS steam ----
      { k: 'lic8504', t: 'ind', x: 412, y: 240, tag: 'LIC-328504', bind: 'DESORB_328.C004.LIC_328504.pv', mode: 'DESORB_328.C004.LIC_328504.mode', u: '%', dec: 1, note: 'holds 328C004 level via LV-328504' },
      { k: 'lv8504', t: 'avalve', x: 542, y: 356, tag: 'LV-328504', bind: 'DESORB_328.C004.LIC_328504.op', u: '%', dec: 1 },
      { k: 'ffic401', t: 'ind', x: 964, y: 218, tag: 'FFIC-328401', bind: 'DESORB_328.C004.FFIC_328401.pv', mode: 'DESORB_328.C004.FFIC_328401.mode', u: 'T/M3', dec: 4, note: 'HS steam-to-feed ratio (E1); MV sets FIC-328401 SP' },
      { k: 'fic8401', t: 'ind', x: 1184, y: 296, tag: 'FIC-328401', bind: 'DESORB_328.C004.FIC_328401.pv', mode: 'DESORB_328.C004.FIC_328401.mode', u: 'T/H', dec: 2, cas: true, note: 'slave: CAS follows FFIC-328401 ratio; HS steam via FV-328401' },
      { k: 'fv8401', t: 'avalve', x: 1014, y: 324, tag: 'FV-328401', bind: 'DESORB_328.C004.FIC_328401.op', u: '%', dec: 1 },
      // ---- 328D001 reflux drum : D001 block, TIC-328008 / FIC-328404 / PIC-328202 ----
      { k: 'tic8008', t: 'ind', x: 693, y: 50,  tag: 'TIC-328008', bind: 'DESORB_328.D001.TIC_328008.pv', mode: 'DESORB_328.D001.TIC_328008.mode', u: 'C', dec: 1, note: '328D001 vent temp / %H2O control' },
      { k: 'fic8404', t: 'ind', x: 542, y: 76,  tag: 'FIC-328404', bind: 'DESORB_328.D001.FIC_328404.pv', mode: 'DESORB_328.D001.FIC_328404.mode', u: 'M3/H', dec: 2, note: '328D001 reflux flow via FV-328404' },
      { k: 'fv8404', t: 'avalve', x: 462, y: 112, tag: 'FV-328404', bind: 'DESORB_328.D001.FIC_328404.op', u: '%', dec: 1 },
      { k: 'pic82021',t: 'ind', x: 853, y: 136, tag: 'PIC-328202', bind: 'DESORB_328.D001.PIC_328202.pv', mode: 'DESORB_328.D001.PIC_328202.mode', u: 'BAR A', dec: 2, note: '328D001 pressure via PV-328202' },
      { k: 'pv82021', t: 'avalve', x: 1295, y: 165, tag: 'PV-328202', bind: 'DESORB_328.D001.PIC_328202.op', u: '%', dec: 1 },
      // ---- 328D003 collection tank (drawn on 328-1) : ABSORB_328.D003 cross-ref ----
      { k: 'fic8406', t: 'ind', x: 1069, y: 425, tag: 'FIC-328406', bind: 'ABSORB_328.D003.FIC_328406.pv', mode: 'ABSORB_328.D003.FIC_328406.mode', u: 'M3/H', dec: 2, note: '328D003 collect draw via FV-328406' },
      { k: 'fv8406', t: 'avalve', x: 1069, y: 458, tag: 'FV-328406', bind: 'ABSORB_328.D003.FIC_328406.op', u: '%', dec: 1 },
      // ---- 323 recycle : LPCC_3232.E003.FIC_328402 cross-ref ----
      { k: 'fic8402', t: 'ind', x: 672, y: 632, tag: 'FIC-328402', bind: 'LPCC_3232.E003.FIC_328402.pv', mode: 'LPCC_3232.E003.FIC_328402.mode', u: 'M3/H', dec: 2, note: '328 recycle to 323E003 via FV-328402' },
      { k: 'fv8402', t: 'avalve', x: 612, y: 632, tag: 'FV-328402', bind: 'LPCC_3232.E003.FIC_328402.op', u: '%', dec: 1 },
      // ---- WHITE FRAMES : unmodelled boundary / analyzer / downstream ----
      { k: 'tt8008w', t: 'ind', x: 1009, y: 61,  tag: 'TT-328008', bind: 'DESORB_328.D001.TT_328008', u: 'C', dec: 1 },   // Desorber-I top / E007 cold-out (114C, absolute; TIC-328008 PV now H2O inferential)
      { k: 'tt8011w', t: 'ind', x: 386,  y: 126, tag: 'TT-328011', bind: 'DESORB_328.C003.TT_328012', u: 'C', dec: 1 },   // hydrolyser top vapour ~190C (stream 746, absolute)
      { k: 'tt8010w', t: 'ind', x: 788,  y: 142, tag: 'TT-328010', bind: 'DESORB_328.D001.TT_328008', u: 'C', dec: 1 },   // Desorber-I feed 114C (E007 cold-out, absolute)
      { k: 'tt8012w', t: 'ind', x: 271,  y: 218, tag: 'TT-328012', bind: 'DESORB_328.C003.TT_328012', u: 'C', dec: 1 },   // hydrolyser 3rd-tray ~190C (absolute; TIC-328012 PV now differential)
      { k: 'tt8004w', t: 'ind', x: 788,  y: 293, tag: 'TT-328004' },
      { k: 'tt8013w', t: 'ind', x: 271,  y: 380, tag: 'TT-328013', bind: 'DESORB_328.C003.TT_328C003', u: 'C', dec: 1 },   // hydrolyser bottom 200C
      { k: 'tt8009w', t: 'ind', x: 186,  y: 512, tag: 'TT-328009' },
      { k: 'tt8005w', t: 'ind', x: 597,  y: 517, tag: 'TT-328005' },
      { k: 'tt8007w', t: 'ind', x: 492,  y: 587, tag: 'TT-328007', bind: 'DESORB_328.C002.TT_328007', u: 'C', dec: 1 },   // 328E007 process outlet 89C
      { k: 'lt8507w', t: 'ind', x: 1294, y: 380, tag: 'LT-328507' },
      { k: 'ai8701w', t: 'ind', x: 838,  y: 632, tag: 'AI-328701' },   // conductivity analyzer
      { k: 'p006w',   t: 'ind', x: 421,  y: 632, tag: '328P006'   },
      { k: 'p007w',   t: 'ind', x: 959,  y: 596, tag: '328P007'   },
    ],
    // ============================ 328-2  ABSORPTION (322C001 absorber + 328D003 collection) ============================
    // coords = STAGE 1366x720 (native 1357x639 scaled x1.006632 / y1.126761).  root ABSORB_328 (C001 absorber / D003 collection tank).
    'screen-328-2': [
      // ---- 322C001 GCB absorber : C001 block ----
      { k: 'tt2015', t: 'ind', x: 340, y: 71,  tag: 'TT-322015',  bind: 'ABSORB_328.C001.TT_322015',    u: 'C',   dec: 1 },   // absorber temp
      { k: 'pic2201', t: 'ind', x: 372, y: 194, tag: 'PIC-322201', bind: 'ABSORB_328.C001.PIC_322201.pv', mode: 'ABSORB_328.C001.PIC_322201.mode', u: 'BAR A', dec: 2, note: 'holds 322C001 top pressure via PV-322201 to 328V001' },
      { k: 'pv2201', t: 'avalve', x: 247, y: 133, tag: 'PV-322201', bind: 'ABSORB_328.C001.PIC_322201.op', u: '%', dec: 1 },
      { k: 'lic2502', t: 'ind', x: 372, y: 355, tag: 'LIC-322502', bind: 'ABSORB_328.C001.LIC_322502.pv', mode: 'ABSORB_328.C001.LIC_322502.mode', u: '%', dec: 1, note: 'holds 322C001 sump level via LV-322502' },
      { k: 'lv2502', t: 'avalve', x: 247, y: 423, tag: 'LV-322502', bind: 'ABSORB_328.C001.LIC_322502.op', u: '%', dec: 1 },
      { k: 'ovr915', t: 'ovrd', x: 121, y: 63, tag: 'XV-322915', bind: 'ABSORB_328.C001.XV_322915', note: 'external override forces XV-322915 CLOSED' },
      // ---- 328D003 collection tank : D003 block, twin-compartment levels ----
      { k: 'lt8508', t: 'ind', x: 644, y: 513, tag: 'LT-328508',  bind: 'ABSORB_328.D003.LI_328II',     u: '%',   dec: 1 },   // compartment II
      { k: 'lt8507', t: 'ind', x: 886, y: 513, tag: 'LT-328507',  bind: 'ABSORB_328.D003.LI_328I',      u: '%',   dec: 1 },   // compartment I
      // ---- WHITE FRAMES : unmodelled boundary / analyzer / downstream ----
      { k: 'ft2404w', t: 'ind', x: 156, y: 161, tag: 'FT-322404' },
      { k: 'ft2402w', t: 'ind', x: 106, y: 257, tag: 'FT-322402' },
      { k: 'tt3010w', t: 'ind', x: 508, y: 358, tag: 'TT-323010', bind: 'RECIRC_323.F010.TT_323010', u: 'C', dec: 1 },   // pre-evaporator 99C
      { k: 'tt3009w', t: 'ind', x: 624, y: 295, tag: 'TT-323009', bind: 'LPCC_3232.C005.TT_323C005', u: 'C', dec: 1 },   // atm absorber scrub liquid 55C
      { k: 'tt8015w', t: 'ind', x: 654, y: 420, tag: 'TT-328015', bind: 'ABSORB_328.D003.TT_328II', u: 'C', dec: 1 },   // NH3 recovery tank Comp-II 44C
      { k: 'p2002w',  t: 'ind', x: 352, y: 599, tag: '322P002'   },
      { k: 'p3003w',  t: 'ind', x: 941, y: 625, tag: '328P003'   },
      { k: 'nav-321', t: 'nav', x: 44, y: 189, w: 90, h: 22, tag: '321E001 -> 321-1', goto: 'screen-321-1' },
      { k: 'e2003w',  t: 'ind', x: 44, y: 315, tag: '322E003'    },
    ],
    // ============================ 324-1  EVAPORATION STAGE 1 (324E001 vacuum evaporator / 324F001 separator) ============================
    // coords = STAGE 1366x720 (native 1357x647 scaled x1.006632 / y1.112828).  root EVAP_324.E001; cross-refs RECIRC_323.D002 / .F010.
    'screen-324-1': [
      // ---- 324E001 / 324F001 vacuum evaporator : E001 block ----
      { k: 'pic4202', t: 'ind', x: 672, y: 67,  tag: 'PIC-324202', bind: 'EVAP_324.E001.PIC_324202.pv', mode: 'EVAP_324.E001.PIC_324202.mode', u: 'BAR A', dec: 3, note: 'holds 324F001 vacuum 0.33 bar a via false-air PV-324202' },
      { k: 'pt4201',  t: 'ind', x: 455, y: 164, tag: 'PT-324201',  bind: 'EVAP_324.E001.PT_324202', u: 'BAR A', dec: 3, note: '324F001 separator pressure' },
      { k: 'tic4001', t: 'ind', x: 458, y: 282, tag: 'TIC-324001', bind: 'EVAP_324.E001.TIC_324001.pv', mode: 'EVAP_324.E001.TIC_324001.mode', u: 'C', dec: 1, note: 'master: holds melt 130 C; cascades PIC-329203 chest steam-P' },
      { k: 'pic9203', t: 'ind', x: 206, y: 274, tag: 'PIC-329203', bind: 'EVAP_324.E001.PIC_329203.pv', mode: 'EVAP_324.E001.PIC_329203.mode', u: 'BAR A', dec: 2, cas: true, note: 'slave: CAS follows TIC-324001; steam to 324E001 chest via PV-329203' },
      { k: 'pv9203',  t: 'avalve', x: 111, y: 334, tag: 'PV-329203', bind: 'EVAP_324.E001.PIC_329203.op', u: '%', dec: 1 },
      { k: 'fic4401', t: 'ind', x: 260, y: 521, tag: 'FIC-324401', bind: 'RECIRC_323.D002.FIC_324401.pv', mode: 'RECIRC_323.D002.FIC_324401.mode', u: 'T/H', dec: 2, cas: true, note: 'slave: CAS follows 323 LIC-323507; 80% carbamate feed to 324E001 via FV-324401' },
      { k: 'fv4401',  t: 'avalve', x: 317, y: 541, tag: 'FV-324401', bind: 'RECIRC_323.D002.FIC_324401.op', u: '%', dec: 1 },
      // ---- 323 cross-refs (upstream 323D002 sump / 323F010 recirc heater drawn on 324-1) ----
      { k: 'lt3507',  t: 'ind', x: 141, y: 523, tag: 'LT-323507',  bind: 'RECIRC_323.D002.LIC_323507.pv', u: '%', dec: 1, note: '323D002 comp I level (master of FIC-324401)' },
      { k: 'pt3204',  t: 'ind', x: 760, y: 250, tag: 'PT-323204',  bind: 'RECIRC_323.F010.P_bara', u: 'BAR A', dec: 2 },
      { k: 'tic3012', t: 'ind', x: 525, y: 504, tag: 'TIC-323012', bind: 'RECIRC_323.F010.TIC_323012.pv', mode: 'RECIRC_323.F010.TIC_323012.mode', u: 'C', dec: 1 },
      { k: 'pic9208', t: 'ind', x: 835, y: 437, tag: 'PIC-329208', bind: 'RECIRC_323.F010.PIC_329208.pv', mode: 'RECIRC_323.F010.PIC_329208.mode', u: 'BAR A', dec: 2, cas: true },
      { k: 'pv9208',  t: 'avalve', x: 845, y: 524, tag: 'PV-329208', bind: 'RECIRC_323.F010.PIC_329208.op', u: '%', dec: 1 },
      // ---- WHITE FRAMES : unmodelled analyzer / steam-condensate / hand valves / downstream ----
      { k: 'py4201w',  t: 'ind', x: 455,  y: 220, tag: 'PY-324201'  },
      { k: 'lic9505w', t: 'ind', x: 211,  y: 376, tag: 'LIC-329505' },
      { k: 'lv9505w',  t: 'ind', x: 189,  y: 432, tag: 'LV-329505'  },
      { k: 'hic3605w', t: 'ind', x: 557,  y: 172, tag: 'HIC-323605', bind: 'EVAP_324.VAC.vent_kgh', u: 'kg/h', dec: 1 },   // 324E002 vent hand ctrl -> non-condensable vent flow
      { k: 'hv3605w',  t: 'ind', x: 642,  y: 201, tag: 'HV-323605',  bind: 'EVAP_324.VAC.vent_kgh', u: 'kg/h', dec: 1 },   // 324E002 vent valve -> non-condensable vent flow
      { k: 'hic9605w', t: 'ind', x: 921,  y: 134, tag: 'HIC-329605' },
      { k: 'hv9605w',  t: 'ind', x: 926,  y: 191, tag: 'HV-329605'  },
      { k: 'pic3203w', t: 'ind', x: 1208, y: 469, tag: 'PIC-323203', bind: 'LPCC_3232.E011.PIC_323203.pv', u: 'BAR A', dec: 2,
        mode: 'LPCC_3232.E011.PIC_323203.mode', note: '323E011/D011 LP node P; flash vapour 701 (LV-323501 -> 323F004) accumulates it. AUTO holds SP via PV-323203; MAN lets P ramp' },
      { k: 'p3003aw',  t: 'ind', x: 235,  y: 610, tag: '323P003A'   },
      { k: 'p3003bw',  t: 'ind', x: 234,  y: 668, tag: '323P003B'   },
      // ---- nav hotspots (right-edge stream sinks) ----
      { k: 'nav-323c005', t: 'nav', x: 1299, y: 172, w: 92, h: 24, tag: '323C005 -> 323-2',  goto: 'screen-323-2'  },
      { k: 'nav-328d003', t: 'nav', x: 1299, y: 206, w: 92, h: 24, tag: '328D003 -> 328-2',  goto: 'screen-328-2'  },
      { k: 'nav-323f010', t: 'nav', x: 1299, y: 278, w: 92, h: 24, tag: '323F010 -> 323-1',  goto: 'screen-323-1'  },
      { k: 'nav-324e003', t: 'nav', x: 1299, y: 364, w: 92, h: 24, tag: '324E003 -> 324-1b', goto: 'screen-324-1b' },
    ],
    // ============================ 324-1b  EVAPORATION STAGE 2 (324E003 deep-vacuum evaporator / 324F003 separator) + 335 finishing tie-in ============================
    // coords = STAGE 1366x720 (native 1359x648 scaled x1.005151 / y1.111111).  root EVAP_324.E003; downstream 335 unmodelled -> WHITE.
    'screen-324-1b': [
      // ---- 324E003 / 324F003 deep-vacuum evaporator : E003 block ----
      { k: 'pic4203', t: 'ind', x: 362, y: 72,  tag: 'PIC-324203', bind: 'EVAP_324.E003.PIC_324203.pv', mode: 'EVAP_324.E003.PIC_324203.mode', u: 'BAR A', dec: 3, note: 'holds 324F003 deep vacuum 0.131 bar a via false-air PV-324203' },
      { k: 'pv4203',  t: 'avalve', x: 106, y: 120, tag: 'PV-324203', bind: 'EVAP_324.E003.PIC_324203.op', u: '%', dec: 1 },
      { k: 'pt4204',  t: 'ind', x: 384, y: 193, tag: 'PT-324204', bind: 'EVAP_324.E003.PT_324203', u: 'BAR A', dec: 3, note: '324F003 separator pressure' },
      { k: 'tic4002', t: 'ind', x: 375, y: 281, tag: 'TIC-324002', bind: 'EVAP_324.E003.TIC_324002.pv', mode: 'EVAP_324.E003.TIC_324002.mode', u: 'C', dec: 1, note: 'master: holds melt 140 C; cascades PIC-329212 chest steam-P' },
      { k: 'pic9212', t: 'ind', x: 136, y: 271, tag: 'PIC-329212', bind: 'EVAP_324.E003.PIC_329212.pv', mode: 'EVAP_324.E003.PIC_329212.mode', u: 'BAR A', dec: 2, cas: true, note: 'slave: CAS follows TIC-324002; steam to 324E003 chest via PV-329212' },
      { k: 'pv9212',  t: 'avalve', x: 97,  y: 332, tag: 'PV-329212', bind: 'EVAP_324.E003.PIC_329212.op', u: '%', dec: 1 },
      // ---- 324F003 product level : split-range LIC-324501 (LV-A forward / LV-B recycle) ----
      { k: 'lic4501', t: 'ind', x: 507, y: 371, tag: 'LIC-324501', bind: 'EVAP_324.E003.LIC_324501.pv', mode: 'EVAP_324.E003.LIC_324501.mode', u: '%', dec: 1, note: 'split-range: LV-324501A forward to 335 / LV-324501B recycle to 324E001' },
      { k: 'li4f003', t: 'ind', x: 538, y: 410, tag: 'LI-324F003', bind: 'EVAP_324.E003.LI_324F003', u: '%', dec: 1 },
      { k: 'lv4501a', t: 'avalve', x: 711, y: 347, tag: 'LV-324501A', bind: 'EVAP_324.E003.LIC_324501.op', u: '%', dec: 1 },
      { k: 'lv4501b', t: 'avalve', x: 598, y: 622, tag: 'LV-324501B', bind: 'EVAP_324.E003.LIC_324501.op', u: '%', dec: 1 },
      // ---- 335 UF85 injection : FFIC-335406 ratio master -> FIC-335405 slave ----
      { k: 'ffic5406', t: 'ind', x: 1020, y: 573, tag: 'FFIC-335406', bind: 'EVAP_324.E003.FFIC_335406.pv', mode: 'EVAP_324.E003.FFIC_335406.mode', u: 'RATIO', dec: 4, note: 'UF85-to-product ratio; MV sets FIC-335405 SP' },
      { k: 'fic5405a', t: 'ind', x: 927, y: 509, tag: 'FIC-335405A', bind: 'EVAP_324.E003.FIC_335405.pv', mode: 'EVAP_324.E003.FIC_335405.mode', u: 'T/H', dec: 3, cas: true, note: 'slave: CAS follows FFIC-335406; UF85 inject to product' },
      // ---- DCS override boxes ----
      { k: 'ovr4501a', t: 'ovrd', x: 741, y: 408, tag: 'EXT-OVR LV-324501A' },
      { k: 'ovrtrip',  t: 'ovrd', x: 741, y: 547, tag: 'TRIP_35_3'         },
      { k: 'ovr4501b', t: 'ovrd', x: 698, y: 667, tag: 'EXT-OVR LV-324501B' },
      { k: 'ovr5602',  t: 'ovrd', x: 940, y: 462, tag: 'EXT-OVR HV-335602' },
      // ---- WHITE FRAMES : downstream 335 finishing / analyzer / hand valves / pumps (unmodelled) ----
      { k: 'ay4701w',  t: 'ind', x: 375,  y: 240, tag: 'AY-324701'   },
      { k: 'fic5401w', t: 'ind', x: 907,  y: 322, tag: 'FIC-335401'  },
      { k: 'hic5602w', t: 'ind', x: 980,  y: 369, tag: 'HIC-335602'  },
      { k: 'hv5602w',  t: 'ind', x: 975,  y: 436, tag: 'HV-335602'   },
      { k: 'ffy5406w', t: 'ind', x: 1076, y: 462, tag: 'FFY-335406'  },
      { k: 'fic5405bw',t: 'ind', x: 935,  y: 649, tag: 'FIC-335405B' },
      { k: 'hv5609w',  t: 'ind', x: 851,  y: 509, tag: 'HV-335609'   },
      { k: 'hv5610w',  t: 'ind', x: 851,  y: 649, tag: 'HV-335610'   },
      { k: 'lt5507w',  t: 'ind', x: 1287, y: 619, tag: 'LT-335507'   },
      { k: 'r001w',    t: 'ind', x: 1292, y: 361, tag: '335R001A/B'  },
      { k: 'd004w',    t: 'ind', x: 1303, y: 417, tag: '335D004'     },
      { k: 'p001aw',   t: 'ind', x: 513,  y: 456, tag: '335P001A'    },
      { k: 'p001bw',   t: 'ind', x: 513,  y: 500, tag: '335P001B'    },
      { k: 'p002w',    t: 'ind', x: 811,  y: 588, tag: '335P002'     },
      { k: 'p006w',    t: 'ind', x: 1223, y: 453, tag: '335P006'     },
      // ---- nav hotspots ----
      { k: 'nav-324e001', t: 'nav', x: 40,   y: 170, w: 80, h: 24, tag: '324E001 -> 324-1', goto: 'screen-324-1' },
      { k: 'nav-328v001', t: 'nav', x: 1299, y: 172, w: 92, h: 24, tag: '328V001 -> 328-2', goto: 'screen-328-2' },
      { k: 'nav-328d3b',  t: 'nav', x: 1299, y: 206, w: 92, h: 24, tag: '328D003 -> 328-2', goto: 'screen-328-2' },
    ],
  };

  let pos = {};
  try { pos = JSON.parse(localStorage.getItem(LSK) || '{}'); } catch (e) { pos = {}; }

  // ---- user tag overrides (add/edit/delete) persisted separately from positions ----
  const MK = 'ots_ov_tags_v3';        // per screen: { add:[ {k,t,x,y,tag,bind,u,dec,cmd,id} ], edit:{ k:{...} }, del:[k] }
  let ovr = {};
  try { ovr = JSON.parse(localStorage.getItem(MK) || '{}'); } catch (e) { ovr = {}; }
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
  let crystEl = null;  // fixed carbamate-crystallization alarm banner (Bug 2)

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

  function svgPump() {
    return '<svg viewBox="0 0 56 56" style="width:100%;height:100%;display:block;">' +
      '<circle cx="28" cy="32" r="22" class="body"/>' +
      '<polygon points="18,20 18,44 42,32" class="tri"/></svg>';
  }
  function svgXV() {
    return '<svg class="sym" viewBox="0 0 34 24" style="width:100%;height:100%;display:block;">' +
      '<polygon points="2,2 17,12 2,22" fill="#0c0c0c" stroke="#22ff22" stroke-width="2"/>' +
      '<polygon points="32,2 17,12 32,22" fill="#0c0c0c" stroke="#22ff22" stroke-width="2"/></svg>';
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

  const CTRL_RE = /[A-Z]IC-3\d{2}/i;   // any *IC-3xxxx loop controller (PIC/HIC/LIC/TIC/FIC/SIC) -> faceplate
  let BIND_MAP = {};                   // tag -> {bind,u,dec,face,fp}: first bound occurrence across ALL screens
  function buildBindMap() {            // shared tags read the SAME value on every screen they appear
    const m = {};
    for (const sid in OV) cfg(sid).forEach(o => {
      if (o.t === 'ind' && o.bind && !m[o.tag]) m[o.tag] = { bind: o.bind, u: o.u, dec: o.dec, face: o.face, fp: o.fp, mode: o.mode };
    });
    BIND_MAP = m;
  }
  const eff = o => (o.t === 'ind' && !o.bind && BIND_MAP[o.tag]) ? Object.assign({}, o, BIND_MAP[o.tag]) : o;
  function renderOne(sid, o) {
    const el = elMap[sid + '|' + o.k]; if (!el) return;
    o = eff(o);                        // inherit bind/unit/dec from any screen sharing this tag
    if (o.t === 'nav') return;                          // transparent screen-nav hotspot, no value
    if (o.t === 'pump') {
      const on = pumpOn(sid, o);
      el.classList.toggle('on', on);
      el.dataset.tip = o.tag + ' — ' + (on ? 'ON' : 'OFF');
    } else if (o.t === 'xv') {
      const open = xvOpen(sid, o);
      el.classList.toggle('closed', !open);
      el.dataset.tip = o.tag + ' — ' + (open ? 'OPEN' : 'CLOSED');
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
      if (o.bind && o.id) { if (window.otsSend) otsSend({ type: 'pump_toggle', id: o.id }); return; }
    } else if (o.t === 'xv') {
      if (o.cmd) { if (window.otsSend) otsSend({ type: 'xv_toggle', id: o.cmd }); return; }
    } else if (o.t === 'ovrd') {                  // manual override: toggle the XV (open while interlock latched)
      if (o.cmd && window.otsSend) otsSend({ type: 'xv_toggle', id: o.cmd });
      return;
    } else if (o.t === 'nav') {
      if (o.goto && window.otsSwitchScreen) window.otsSwitchScreen(o.goto);
      return;
    } else if (o.t === 'strm') {
      if (o.stream && window.openStreamPopup) window.openStreamPopup(o.stream);
      return;
    } else if (o.t === 'ind') {
      if (o.face && window.OTS_FACE && window.OTS_FACE[o.face]) { window.OTS_FACE[o.face](o); return; }
      if (o.fp === 'SIC_321950' && window.openF50) { window.openF50(); return; }   // SIC_321950 REST faceplate
      if (o.fp === 'SIC_321951' && window.openF51) { window.openF51(); return; }   // SIC_321951 REST faceplate
      if (o.fp === 'MASTER_SP_329207' && window.OTS_FACE && window.OTS_FACE.msp) { window.OTS_FACE.msp(o); return; }   // 4-bar header MASTER SP cascade
      if (CTRL_RE.test(o.tag) && window.OTS_FACE && window.OTS_FACE.ctl) { window.OTS_FACE.ctl(o); return; }   // any *IC-3* -> generic faceplate
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
    el.addEventListener('click', () => { if (!editing) activate(sid, o); });
    el.addEventListener('contextmenu', e => {
      e.preventDefault(); e.stopPropagation();
      if (editing) { openMenu(e, sid, o); return; }                        // edit mode -> Edit/Delete menu
      if (o.t === 'ind' && o.bind && window.openTrend) window.openTrend(o.tag);
    });
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
      el.className = 'ov ' + (o.t === 'pump' ? 'pump' : o.t === 'xv' ? 'avalve' : o.t === 'nav' ? 'nav' : o.t === 'strm' ? 'strm' : o.t === 'ovrd' ? 'ovrd' : 'ind');
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
      }
      el.dataset.tip = o.tag;
      el.title = o.tag;
      if (o.t === 'pump') el.innerHTML = svgPump();
      else if (o.t === 'xv') el.innerHTML = svgXV();
      else if (o.t === 'ovrd') el.innerHTML = '<span class="ovl"></span><b>OVRD</b>';
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
      '.ov.ovrd{display:flex;align-items:center;gap:5px;padding:3px 7px;background:#1a1208;border:1px solid #6b5a2f;border-radius:3px;color:#cdbb78;font:bold 10px Consolas,monospace;letter-spacing:.6px;cursor:pointer;white-space:nowrap;user-select:none;}' +
      '.ov.ovrd .ovl{width:13px;height:9px;border:1px solid #6b5a2f;background:#3a3320;flex:none;}' +
      '.ov.ovrd:hover{border-color:#ffd000;color:#ffe9a0;}' +
      '.ov.ovrd:active{background:#3aa56e;color:#04140c;border-color:#3aa56e;}' +
      '.ov.ovrd.armed{border-color:#ffd000;color:#ffd000;background:#241a06;box-shadow:0 0 7px rgba(255,208,0,.55);}' +
      '.ov.ovrd.armed .ovl{background:#ffd000;border-color:#ffd000;box-shadow:0 0 5px #ffd000;animation:ovrdblink 1s steps(1) infinite;}' +
      '.ov.ovrd.on .ovl{background:#22ff22;border-color:#22ff22;}' +
      '@keyframes ovrdblink{50%{opacity:.35;}}' +
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
      '.ov-act button:hover{filter:brightness(1.18);}' +
      '#ov-cryst{position:fixed;left:50%;top:10px;transform:translateX(-50%);z-index:9500;display:none;flex-direction:column;gap:3px;min-width:352px;max-width:62vw;padding:9px 15px;border-radius:7px;box-shadow:0 6px 22px rgba(0,0,0,.55);}' +
      '#ov-cryst.warn{display:flex;background:#3a2a08;border:1px solid #b3892f;color:#ffdf9a;}' +
      '#ov-cryst.alarm{display:flex;background:#3a0d0d;border:1px solid #ff3030;color:#ffc2c2;animation:crystblink 1s steps(1) infinite;}' +
      '#ov-cryst .ttl{font:800 12px "Segoe UI",system-ui;letter-spacing:.7px;display:flex;align-items:center;gap:7px;margin-bottom:1px;}' +
      '#ov-cryst .ttl .ic{font-size:15px;line-height:1;}' +
      '#ov-cryst .row{font:600 11px Consolas,monospace;opacity:.96;white-space:nowrap;}' +
      '#ov-cryst .row .eq{display:inline-block;min-width:126px;}' +
      '#ov-cryst .row .st{display:inline-block;min-width:52px;font-weight:800;}' +
      '@keyframes crystblink{50%{opacity:.42;}}';
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

  function crystBanner() {                         // Bug 2: plant-wide carbamate-crystallization banner
    if (document.getElementById('ov-cryst')) return;
    const d = document.createElement('div'); d.id = 'ov-cryst';
    document.body.appendChild(d); crystEl = d;
  }
  function crystRender(s) {                         // read CRYST + flags each packet; amber WARN / red-blink ALARM
    if (!crystEl) return;
    const C = s && s.CRYST, F = (s && s.flags) || {};
    crystEl.classList.remove('warn', 'alarm');
    if (!C) { crystEl.style.display = 'none'; return; }
    const alarms = [], warns = [], bad = [];
    for (const eq in C) {
      const r = C[eq]; if (!r) continue;
      if (r.state === 'ALARM')      alarms.push([eq, r]);
      else if (r.state === 'WARN')  warns.push([eq, r]);
      else if (r.state === 'BAD')   bad.push([eq, r]);   // bad PV surfaces too (never silently OK)
    }
    const alarm = !!F.CARBAMATE_CRYST_ALARM || alarms.length > 0;
    const warn  = !!F.CARBAMATE_CRYST_WARN  || warns.length > 0;
    if (!alarm && !warn && bad.length === 0) { crystEl.style.display = 'none'; crystEl.innerHTML = ''; return; }
    const rows = (alarm ? alarms.concat(warns) : warns).concat(bad);
    const cls  = alarm ? 'alarm' : 'warn';
    const ttl  = alarm ? 'CARBAMATE CRYSTALLIZATION — ONSET'
                       : 'CARBAMATE CRYSTALLIZATION — APPROACHING';
    let html = '<div class="ttl"><span class="ic">⚠</span>' + ttl + '</div>';
    rows.forEach(function (p) {
      const eq = p[0], r = p[1];
      let det = '';
      if (r.state === 'BAD') det = 'bad PV — unverifiable';
      else det = 'margin ' + r.margin + '°C'
               + (r.T_cryst != null ? '  (Tcryst ' + r.T_cryst + '°C, T ' + (r.T_cryst + r.margin).toFixed(1) + '°C)' : '');
      html += '<div class="row"><span class="eq">' + eq + '</span><span class="st">' + r.state + '</span>' + det + '</div>';
    });
    crystEl.innerHTML = html;
    crystEl.classList.add(cls);
    crystEl.style.display = 'flex';
  }

  window.OV_apply = function (s) { lastS = s; window.OTS_LAST = s; renderAll(); simRender(s); crystRender(s); };  // app.js calls each ws packet (OTS_LAST -> faceplate prefill)

  for (const sid in OV) build(sid);
  editButton();
  simToggle();
  crystBanner();
  renderAll();
})();
