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
      { k: 'ft3',  t: 'ind', x: 93,   y: 452, tag: 'FT-322403' },                       // unbound -> empty slot
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
      { k: 'pt9206', t: 'ind', x: 1242, y: 145, tag: 'PT-329206' },
      { k: 'tt9001', t: 'ind', x: 1048, y: 259, tag: 'TT-329001', bind: 'HPCC_322E002.TT_329001', u: 'C', dec: 1 },   // 322D001 A/B condensate -> 322E002 shell (BFW feed)
      { k: 'py9207', t: 'ind', x: 1094, y: 208, tag: 'PY-329207B' },
      { k: 'tt014',  t: 'ind', x: 638,  y: 398, tag: 'TT-322014', bind: 'STRIP_322E001.TT_322014', u: 'C', dec: 1 },
      { k: 'hv605',  t: 'ind', x: 823,  y: 392, tag: 'HV-322605', bind: 'REACT_322R001.HV_322605', u: '%', dec: 1, face: 'hic' },
      { k: 'lic501', t: 'ind', x: 861,  y: 471, tag: 'LIC-322501', bind: 'STRIP_322E001.LIC_322501.pv', u: '%', dec: 1, mode: 'STRIP_322E001.LIC_322501.mode' },
      { k: 'pic9204',t: 'ind', x: 1113, y: 380, tag: 'PIC-329204' },
      { k: 'hic9601',t: 'ind', x: 1127, y: 489, tag: 'HIC-329601' },
      { k: 'ft9403', t: 'ind', x: 1127, y: 520, tag: 'FT-329403' },
      { k: 'lv501',  t: 'ind', x: 1110, y: 612, tag: 'LV-322501', bind: 'STRIP_322E001.LV_322501', u: '%', dec: 1 },
      { k: 'tt004',  t: 'ind', x: 1037, y: 619, tag: 'TT-322004', bind: 'STRIP_322E001.TT_322004', u: 'C', dec: 1 },
      { k: 'pt3201', t: 'ind', x: 1187, y: 617, tag: 'PT-323201' },
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
      { k: 'hic601', t: 'ind',    x: 211, y: 370, tag: 'HIC-329601', bind: 'STEAM_SYSTEM.HP_VENT.pct',   u: '%',     dec: 1 },   // hand ctrl of 329D005 atm vent
      { k: 'hv601',  t: 'avalve', x: 140, y: 438, tag: 'HV-329601',  bind: 'STEAM_SYSTEM.HP_VENT.pct',   u: '%',     dec: 1 },   // 329D005 atm vent valve
      // ===== 329D009 MP 9-bar drum (split-range PIC-329205 : PV-329205A admit / PV-329205B let-down) =====
      { k: 'pic205', t: 'ind',    x: 653, y: 430, tag: 'PIC-329205', bind: 'STEAM_SYSTEM.PIC_329205.pv', u: 'BAR A', dec: 2,
        mode: 'STEAM_SYSTEM.PIC_329205.mode', note: 'up P9 => PV-329205B let-down (9->4 bar) opens; down P9 => PV-329205A admits 25-bar BL steam' },
      { k: 'pv205a', t: 'avalve', x: 589, y: 548, tag: 'PV-329205A', bind: 'STEAM_SYSTEM.DRUM_9BAR.admit_pct',   u: '%', dec: 1 },
      { k: 'pv205b', t: 'avalve', x: 847, y: 361, tag: 'PV-329205B', bind: 'STEAM_SYSTEM.DRUM_9BAR.letdown_pct', u: '%', dec: 1 },
      { k: 'lic503', t: 'ind', x: 1002, y: 505, tag: 'LIC-329503' },   // 329D009 level (unmodelled)
      { k: 'lv503',  t: 'ind', x: 1002, y: 581, tag: 'LV-329503'  },
      // ===== 322D001A/B LP drums + 4-bar header pressure indicators (PI-329206 / PI-329207) =====
      { k: 'tt001',  t: 'ind',    x: 614, y: 271, tag: 'TT-329001',  bind: 'STEAM_SYSTEM.LP.TI_sat',  u: 'C',     dec: 1 },   // temp inside 322D001A/B
      { k: 'pi206',  t: 'ind',    x: 625, y: 179, tag: 'PI-329206',  bind: 'STEAM_SYSTEM.LP.P_bara',  u: 'BAR A', dec: 2 },
      { k: 'pi207',  t: 'ind',    x: 753, y: 179, tag: 'PI-329207',  bind: 'STEAM_SYSTEM.LP.P_bara',  u: 'BAR A', dec: 2 },   // 2nd header P indicator
      { k: 'lic504', t: 'ind', x: 394,  y: 222, tag: 'LIC-329504' },
      { k: 'lv504',  t: 'ind', x: 194,  y: 294, tag: 'LV-329504'  },
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
      { k: 'hic602',  t: 'ind',    x: 301,  y: 420, tag: 'HIC-329602' },   // 963 make-up hand ctrl (unmodelled)
      { k: 'hv602',   t: 'ind',    x: 291,  y: 475, tag: 'HV-329602'  },   // 963 make-up isolation (unmodelled)
      { k: 'ft407',   t: 'ind',    x: 1081, y: 141, tag: 'FT-329407'  },   // 320MT02 turbine steam flow
      // ===== 329D005 level (LIC/LV-329502, unmodelled) + O2-scavenger dosing pumps =====
      { k: 'lic502',  t: 'ind', x: 744, y: 625, tag: 'LIC-329502' },
      { k: 'lv502',   t: 'ind', x: 731, y: 697, tag: 'LV-329502'  },
      { k: 'u001m01', t: 'pump', x: 1262, y: 570, tag: '329U001-M01' },   // O2 scavenger dosing (unmodelled -> local toggle)
      { k: 'u001m02', t: 'pump', x: 1262, y: 651, tag: '329U001-M02' },
      // ===== screen-nav hotspots: boundary exchangers with live 322-1 home screen =====
      { k: 'nav-e002a', t: 'nav', x: 48, y: 158, w: 80, h: 24, tag: '322E002 -> 322-1', goto: 'screen-322-1' },
      { k: 'nav-e002b', t: 'nav', x: 68, y: 317, w: 80, h: 24, tag: '322E002 -> 322-1', goto: 'screen-322-1' },
      { k: 'nav-e001a', t: 'nav', x: 68, y: 446, w: 80, h: 24, tag: '322E001 -> 322-1', goto: 'screen-322-1' },
      { k: 'nav-e001b', t: 'nav', x: 68, y: 490, w: 80, h: 24, tag: '322E001 -> 322-1', goto: 'screen-322-1' },
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
      const v = gp(lastS, o.bind);
      if (b) b.textContent = fmt(v, o.dec);
      if (sp) sp.textContent = o.u || '';
      if (mt) { const ml = modeLetter(o); mt.textContent = ml; mt.className = 'mt' + (ml ? ' m-' + ml : ''); }   // controller mode badge (A/M/E/O); '' for non-controllers
      el.dataset.tip = o.tag + (o.u ? ' [' + o.u + ']' : '') + (modeLetter(o) ? ' — ' + { A: 'AUTO', M: 'MAN', E: 'CAS', O: 'OOS' }[modeLetter(o)] : '');
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
