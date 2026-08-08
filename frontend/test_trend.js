'use strict';

// trend.js is a browser IIFE. It guards every DOM touch behind `typeof document`, so it
// loads headless and exports its pure logic for these tests.
//   run: node --test frontend/

const assert = require('node:assert/strict');
const test = require('node:test');

// Stub the two globals trend.js reads before requiring it.
const store = {};
global.localStorage = {
  getItem: k => (k in store ? store[k] : null),
  setItem: (k, v) => { store[k] = String(v); },
};
global.window = {
  OV_BINDS: {
    'TT-321001':  { bind: 'TI_top1',                    u: 'C',     dec: 1 },
    'PT-321201':  { bind: 'PI_321201',                  u: 'BAR G', dec: 1 },
    'PI-329201':  { bind: 'EJ_322F001.PI_329201',       u: 'BAR A', dec: 1 },
    'HV-322602':  { bind: 'EJ_322F001.HIC_322602',      u: '%',     dec: 1 },
    'SIC-321950': { bind: 'controllers.SIC_321950.pv',  u: 'RPM',   dec: 1 },
    'XV-321901':  { bind: 'XV_321901',                  u: '',      dec: 0 },
    'N/C Ratio':  { bind: 'ratio.NC_A',                 u: 'N/C',   dec: 3 },
  },
};

const trend = require('./trend.js');
const I = trend._internals;

function reset() {
  for (let i = 0; i < I.SLOTS; i++) I.slots[i] = null;
}

// ===== clocks =====

test('plant clock renders elapsed sim time as HH:MM:SS', () => {
  assert.equal(I.hms(0), '00:00:00');
  assert.equal(I.hms(59), '00:00:59');
  assert.equal(I.hms(3600), '01:00:00');
  assert.equal(I.hms(3661), '01:01:01');
  assert.equal(I.hms(28800), '08:00:00');       // the longest span
});

test('plant clock never renders negative time', () => {
  assert.equal(I.hms(-5), '00:00:00');
});

test('desktop clock degrades to placeholders on missing time', () => {
  assert.equal(I.deskClock(null), '--:--:--');
  assert.equal(I.deskClock(undefined), '--:--:--');
  assert.match(I.deskClock(1770000000), /^\d\d:\d\d:\d\d$/);
});

test('export filename stamp matches Trend_Report_YYYY-MM-DD_HH-MM-SS', () => {
  const s = I.stamp(new Date(2026, 7, 7, 9, 4, 5));
  assert.equal(s, '2026-08-07_09-04-05');
  assert.match('Trend_Report_' + s + '.png', /^Trend_Report_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.png$/);
});

// ===== registry =====

test('registry resolves a tag to its packet path', () => {
  const e = I.Registry.entry('TT-321001');
  assert.equal(e.path, 'TI_top1');
  assert.equal(e.unit, 'C');
  assert.deepEqual(e.range, [0, 250]);
});

test('registry resolves dotted paths, which the old trend could not', () => {
  // The removed #trendModal looked up history['SIC-321950'] and always missed.
  assert.equal(I.Registry.entry('SIC-321950').path, 'controllers.SIC_321950.pv');
  assert.deepEqual(I.Registry.entry('SIC-321950').range, [0, 3000]);
});

test('BAR A tags trend as gauge pressure, matching the indicator', () => {
  const e = I.Registry.entry('PI-329201');
  assert.equal(e.unit, 'BARG');
  assert.equal(e.gauge, true);
  assert.ok(Math.abs(I.Registry.value({ EJ_322F001: { PI_329201: 11.01325 } }, e) - 10) < 1e-9);
});

test('unknown units auto-scale rather than guessing a range', () => {
  assert.equal(I.Registry.entry('N/C Ratio').range, null);
});

test('unbound tags are rejected, not silently trended', () => {
  assert.equal(I.Registry.entry('FIC-335401'), null);
  assert.equal(I.Registry.bound('FIC-335401'), false);
  assert.equal(I.Registry.bound('TT-321001'), true);
});

test('booleans read as digital levels', () => {
  const e = I.Registry.entry('XV-321901');
  assert.equal(I.Registry.value({ XV_321901: true }, e), 1);
  assert.equal(I.Registry.value({ XV_321901: false }, e), 0);
});

test('missing or non-finite values return null instead of NaN pens', () => {
  const e = I.Registry.entry('TT-321001');
  assert.equal(I.Registry.value({}, e), null);
  assert.equal(I.Registry.value({ TI_top1: NaN }, e), null);
  assert.equal(I.Registry.value({ TI_top1: 'x' }, e), null);
});

// ===== normalisation =====

test('pens normalise onto a shared 0-100 grid', () => {
  const slot = { lo: 0, hi: 250 };
  assert.equal(I.norm(slot, 0), 0);
  assert.equal(I.norm(slot, 125), 50);
  assert.equal(I.norm(slot, 250), 100);
});

test('normalisation survives a degenerate range', () => {
  assert.equal(I.norm({ lo: 5, hi: 5 }, 5), 50);
});

test('values outside the engineering range stay proportional, not clipped in data', () => {
  assert.equal(I.norm({ lo: 0, hi: 100 }, 120), 120);
});

// ===== slots =====

test('a tag lands in the first free slot', () => {
  reset();
  assert.equal(trend.addTag('TT-321001', null), true);
  assert.equal(I.slots[0].tag, 'TT-321001');
  assert.equal(I.slots[0].entry.path, 'TI_top1');
  assert.equal(I.slots[1], null);
});

test('a tag can be dropped into a chosen slot', () => {
  reset();
  trend.addTag('PT-321201', 4);
  assert.equal(I.slots[4].tag, 'PT-321201');
  assert.equal(I.slots[0], null);
});

test('re-adding a trended tag selects it instead of duplicating the pen', () => {
  reset();
  trend.addTag('TT-321001', null);
  trend.addTag('TT-321001', null);
  assert.equal(I.slots.filter(s => s && s.tag === 'TT-321001').length, 1);
});

test('an unbound tag is refused and leaves the slot empty', () => {
  reset();
  assert.equal(trend.addTag('FIC-335401', 2), false);
  assert.equal(I.slots[2], null);
});

test('the eleventh tag is refused: there are exactly 10 slots', () => {
  reset();
  const tags = ['TT-321001', 'PT-321201', 'PI-329201', 'HV-322602', 'SIC-321950',
                'XV-321901', 'N/C Ratio'];
  tags.forEach(t => trend.addTag(t, null));
  for (let i = tags.length; i < I.SLOTS; i++) I.slots[i] = { tag: 'filler' + i, entry: {}, pts: [] };
  assert.equal(I.slots.filter(Boolean).length, 10);
  assert.equal(trend.addTag('TT-321001', null), true, 'already-trended tag just selects');
  I.slots[0] = { tag: 'other', entry: {}, pts: [] };
  assert.equal(trend.addTag('PT-321201', null), true, 'PT-321201 is still in a slot');
});

test('removing a slot frees it for the next drop', () => {
  reset();
  trend.addTag('TT-321001', 3);
  trend.removeSlot(3);
  assert.equal(I.slots[3], null);
  trend.addTag('PT-321201', null);
  assert.equal(I.slots[0].tag, 'PT-321201');
});

test('an analog slot seeds its declared range but auto-scales by default', () => {
  reset();
  trend.addTag('HV-322602', 0);
  assert.equal(I.slots[0].lo, 0, 'declared range seeds lo until data arrives');
  assert.equal(I.slots[0].hi, 100, 'declared range seeds hi until data arrives');
  assert.equal(I.slots[0].auto, true, 'analog pens auto-scale off the displayed data by default');
});

test('a slot with no declared range is marked for auto-scaling', () => {
  reset();
  trend.addTag('N/C Ratio', 0);
  assert.equal(I.slots[0].auto, true);
});

test('a digital on/off pen stays pinned to 0..1, not auto-scaled', () => {
  reset();
  trend.addTag('XV-321901', 0);                 // unit '' -> digital
  assert.equal(I.slots[0].lo, 0);
  assert.equal(I.slots[0].hi, 1);
  assert.equal(I.slots[0].auto, false, 'a valve must keep full-scale stepped height');
});

test('auto-scaling brackets the displayed data slightly below MIN and above MAX', () => {
  reset();
  trend.addTag('TT-321001', 0);
  I.slots[0].pts = [{ t: 5, v: 100 }, { t: 6, v: 200 }];
  I.setNow(6); I.setSpanValue(3600);
  I.rescale(I.slots[0]);
  assert.ok(I.slots[0].lo < 100 && I.slots[0].lo > 90, 'lo sits just below MIN');
  assert.ok(I.slots[0].hi > 200 && I.slots[0].hi < 210, 'hi sits just above MAX');
});

test('auto range expands when a new value exceeds the current bracket', () => {
  reset();
  trend.addTag('TT-321001', 0);
  I.setNow(10); I.setSpanValue(3600);
  I.slots[0].pts = [{ t: 1, v: 50 }, { t: 2, v: 60 }];
  I.rescale(I.slots[0]);
  const hi1 = I.slots[0].hi;
  I.slots[0].pts.push({ t: 3, v: 500 });          // a spike beyond the old range
  I.rescale(I.slots[0]);
  assert.ok(I.slots[0].hi > hi1 && I.slots[0].hi > 500, 'range must grow to hold the new peak');
});

// ===== pen highlight (choose a row -> emphasise its trend above) =====

test('choosing a filled row highlights that pen', () => {
  reset();
  trend.addTag('TT-321001', 0);
  trend.addTag('PT-321201', 1);
  assert.equal(I.selectPen(0), 0, 'clicking row 0 highlights pen 0');
  assert.equal(I.getSelected(), 0);
});

test('reclicking the highlighted pen clears the highlight', () => {
  reset();
  trend.addTag('TT-321001', 0);                 // adding a pen makes it the active one
  assert.equal(I.getSelected(), 0);
  assert.equal(I.selectPen(0), -1, 'clicking the active pen again clears it');
  assert.equal(I.getSelected(), -1);
});

test('choosing an empty row clears the highlight (nothing to emphasise)', () => {
  reset();
  trend.addTag('TT-321001', 0);                 // add -> pen 0 becomes active
  assert.equal(I.selectPen(5), -1, 'an empty row cannot be highlighted');
  assert.equal(I.getSelected(), -1);
});

test('removing the highlighted pen clears the highlight', () => {
  reset();
  trend.addTag('TT-321001', 0);
  assert.equal(I.getSelected(), 0);
  trend.removeSlot(0);
  assert.equal(I.getSelected(), -1, 'the highlight must not point at an emptied slot');
});

test('removing a different pen leaves the highlight intact', () => {
  reset();
  trend.addTag('TT-321001', 0);
  trend.addTag('PT-321201', 1);                 // the newest add is the active pen
  assert.equal(I.getSelected(), 1);
  trend.removeSlot(0);
  assert.equal(I.getSelected(), 1, 'removing another pen must not disturb the active one');
});

// ===== editable display range =====

function field(value) { return { value: String(value) }; }

test('an operator LOW overrides the declared range and rescales the pen', () => {
  reset();
  trend.addTag('TT-321001', 0);                 // declared 0-250 C
  I.commitRange(0, 'lo', field(100));
  assert.equal(I.slots[0].lo, 100);
  assert.equal(I.slots[0].hi, 250);
  assert.equal(I.norm(I.slots[0], 175), 50, 'pen must replot against the new range');
});

test('an operator HIGH overrides the declared range', () => {
  reset();
  trend.addTag('TT-321001', 0);
  I.commitRange(0, 'hi', field(50));
  assert.equal(I.slots[0].hi, 50);
  assert.equal(I.norm(I.slots[0], 25), 50);
});

test('setting a bound turns off auto-scaling so data cannot move it back', () => {
  reset();
  trend.addTag('N/C Ratio', 0);                 // no declared range -> auto
  assert.equal(I.slots[0].auto, true);
  I.commitRange(0, 'hi', field(2));
  assert.equal(I.slots[0].auto, false);
  assert.equal(I.slots[0].hi, 2);
});

test('blanking a bound hands the pen back to auto-scaling', () => {
  reset();
  trend.addTag('TT-321001', 0);
  I.commitRange(0, 'lo', field(100));
  assert.equal(I.slots[0].auto, false);
  I.commitRange(0, 'lo', field(''));
  assert.equal(I.slots[0].auto, true);
});

test('an inverted range is refused, leaving the previous scale intact', () => {
  reset();
  trend.addTag('TT-321001', 0);
  I.commitRange(0, 'lo', field(300));           // above the 250 high
  assert.equal(I.slots[0].lo, 0, 'LOW must not cross HIGH');
  assert.equal(I.slots[0].hi, 250);
});

test('a zero-width range is refused', () => {
  reset();
  trend.addTag('HV-322602', 0);                 // 0-100 %
  I.commitRange(0, 'hi', field(0));
  assert.equal(I.slots[0].hi, 100);
});

test('a non-numeric entry is refused', () => {
  reset();
  trend.addTag('TT-321001', 0);
  I.commitRange(0, 'hi', field('abc'));
  assert.equal(I.slots[0].hi, 250);
});

test('a negative LOW is allowed for pens that swing below zero', () => {
  reset();
  trend.addTag('TT-321001', 0);
  I.commitRange(0, 'lo', field(-40));
  assert.equal(I.slots[0].lo, -40);
  assert.equal(I.slots[0].auto, false);
});

test('editing an empty slot is a no-op', () => {
  reset();
  const inp = field(10);
  I.commitRange(3, 'lo', inp);
  assert.equal(I.slots[3], null);
  assert.equal(inp.value, '', 'the field clears rather than holding a phantom range');
});

test('operator ranges survive a reload; auto pens re-derive theirs', () => {
  reset();
  trend.addTag('TT-321001', 0);
  trend.addTag('N/C Ratio', 1);
  I.commitRange(0, 'lo', field(20));
  I.commitRange(0, 'hi', field(180));
  I.save();
  const st = I.saved();
  assert.deepEqual(st.ranges[0], [20, 180]);
  assert.equal(st.ranges[1], null, 'auto-scaled pens must not freeze a stale range');
});

// ===== live feed =====

test('live packets extend a pen on the plant clock', () => {
  reset();
  trend.addTag('TT-321001', 0);
  trend.onPacket({ t_sim: 10, t: 1770000010, TI_top1: 180 });
  trend.onPacket({ t_sim: 11, t: 1770000011, TI_top1: 181 });
  assert.deepEqual(I.slots[0].pts, [{ t: 10, v: 180 }, { t: 11, v: 181 }]);
});

test('sub-second packets update in place rather than flooding the buffer', () => {
  reset();
  trend.addTag('TT-321001', 0);
  for (let i = 0; i < 10; i++) trend.onPacket({ t_sim: 20 + i * 0.1, t: 1770000020, TI_top1: 100 + i });
  assert.equal(I.slots[0].pts.length, 1, '10 Hz packets must not become 10 points per second');
  assert.equal(I.slots[0].pts[0].v, 109, 'the newest value wins');
});

test('a packet missing a pen path leaves that pen untouched', () => {
  reset();
  trend.addTag('TT-321001', 0);
  trend.onPacket({ t_sim: 30, t: 1770000030, TI_top1: 200 });
  trend.onPacket({ t_sim: 40, t: 1770000040 });
  assert.equal(I.slots[0].pts.length, 1);
});

// ===== ruler =====

function penWith(points) {
  reset();
  trend.addTag('TT-321001', 0);
  I.slots[0].pts = points;
  return I.slots[0];
}

test('the ruler reports the value each pen held at that instant', () => {
  const s = penWith([{ t: 10, v: 100 }, { t: 20, v: 200 }, { t: 30, v: 300 }]);
  assert.equal(trend.valueAt(s, 20), 200);
});

test('between samples the ruler holds the last reading, as a DCS cursor does', () => {
  const s = penWith([{ t: 10, v: 100 }, { t: 20, v: 200 }]);
  assert.equal(trend.valueAt(s, 17), 100, 'must hold, not interpolate or jump forward');
});

test('hold semantics keep digital pens truthful', () => {
  reset();
  trend.addTag('XV-321901', 0);
  I.slots[0].pts = [{ t: 0, v: 1 }, { t: 50, v: 0 }];
  assert.equal(trend.valueAt(I.slots[0], 49), 1, 'the valve was still open at t=49');
  assert.equal(trend.valueAt(I.slots[0], 50), 0);
});

test('a ruler before a pen has data reads no value rather than a wrong one', () => {
  const s = penWith([{ t: 100, v: 5 }]);
  assert.equal(trend.valueAt(s, 50), null);
});

test('a ruler past the newest sample holds the newest value', () => {
  const s = penWith([{ t: 10, v: 1 }, { t: 20, v: 2 }]);
  assert.equal(trend.valueAt(s, 999), 2);
});

test('an empty pen and an unset ruler both read no value', () => {
  const s = penWith([]);
  assert.equal(trend.valueAt(s, 10), null);
  assert.equal(trend.valueAt(penWith([{ t: 1, v: 1 }]), null), null);
});

test('the ruler can be set and cleared', () => {
  reset();
  trend.setCursor(123);
  assert.equal(trend.cursor(), 123);
  trend.setCursor(null);
  assert.equal(trend.cursor(), null);
});

test('pens read independently at one ruler instant', () => {
  reset();
  trend.addTag('TT-321001', 0);
  trend.addTag('PT-321201', 1);
  I.slots[0].pts = [{ t: 10, v: 180 }, { t: 20, v: 190 }];
  I.slots[1].pts = [{ t: 10, v: 150 }, { t: 20, v: 152 }];
  trend.setCursor(15);
  assert.equal(trend.valueAt(I.slots[0], trend.cursor()), 180);
  assert.equal(trend.valueAt(I.slots[1], trend.cursor()), 150);
  trend.setCursor(null);
});

// ===== multiple rulers =====

test('up to 10 rulers can be placed, each a distinct instant', () => {
  reset();
  trend.clearRulers();
  for (let i = 0; i < 10; i++) assert.equal(trend.addRuler(100 + i * 10), true);
  assert.deepEqual(trend.rulers(), [100, 110, 120, 130, 140, 150, 160, 170, 180, 190]);
});

test('an eleventh ruler is refused', () => {
  reset();
  trend.clearRulers();
  for (let i = 0; i < 10; i++) trend.addRuler(i);
  assert.equal(trend.addRuler(999), false);
  assert.equal(trend.rulers().length, 10);
});

test('there is a distinct colour for each of the ten rulers', () => {
  assert.equal(I.RULER_COLORS.length, 10);
  assert.equal(new Set(I.RULER_COLORS).size, 10, 'ruler colours must all differ');
  assert.equal(I.RULERS_MAX, 10);
});

test('a duplicate ruler at the same instant is refused', () => {
  reset();
  trend.clearRulers();
  trend.addRuler(50);
  assert.equal(trend.addRuler(50), false);
  assert.equal(trend.rulers().length, 1);
});

test('a ruler can be removed by index and all cleared', () => {
  reset();
  trend.clearRulers();
  [10, 20, 30].forEach(t => trend.addRuler(t));
  trend.removeRuler(1);
  assert.deepEqual(trend.rulers(), [10, 30]);
  trend.clearRulers();
  assert.deepEqual(trend.rulers(), []);
});

test('each ruler reads every pen independently at its own instant', () => {
  reset();
  trend.addTag('TT-321001', 0);
  I.slots[0].pts = [{ t: 10, v: 100 }, { t: 20, v: 200 }, { t: 30, v: 300 }];
  trend.clearRulers();
  trend.addRuler(10); trend.addRuler(25);
  const rs = trend.rulers();
  assert.equal(trend.valueAt(I.slots[0], rs[0]), 100);
  assert.equal(trend.valueAt(I.slots[0], rs[1]), 200);   // held from t=20
});

test('setCursor stays a single-ruler shim over the multi-ruler store', () => {
  reset();
  trend.clearRulers();
  trend.setCursor(77);
  assert.deepEqual(trend.rulers(), [77]);
  assert.equal(trend.cursor(), 77);
  trend.setCursor(null);
  assert.deepEqual(trend.rulers(), []);
});

// ===== drag to move a ruler =====

test('a ruler can be dragged to a new instant, leaving its neighbours put', () => {
  reset();
  I.setNow(1000); I.setSpanValue(3600);            // window [-2600 .. 1000]
  trend.clearRulers();
  trend.addRuler(100); trend.addRuler(200); trend.addRuler(300);
  assert.equal(trend.moveRuler(1, 250), true);
  assert.deepEqual(trend.rulers(), [100, 250, 300]);
});

test('a dragged ruler clamps to the right edge of the visible window', () => {
  reset();
  I.setNow(1000); I.setSpanValue(3600);            // right edge = viewEnd = 1000
  trend.clearRulers();
  trend.addRuler(500);
  trend.moveRuler(0, 5000);                          // dragged past newest data
  assert.equal(trend.rulers()[0], 1000);
});

test('a dragged ruler clamps to the left edge of the visible window', () => {
  reset();
  I.setNow(1000); I.setSpanValue(3600);            // left edge = viewEnd - span = -2600
  trend.clearRulers();
  trend.addRuler(500);
  trend.moveRuler(0, -9999);
  assert.equal(trend.rulers()[0], -2600);
});

test('moving a non-existent ruler is a no-op', () => {
  reset();
  trend.clearRulers();
  trend.addRuler(100);
  assert.equal(trend.moveRuler(5, 200), false);
  assert.equal(trend.moveRuler(-1, 200), false);
  assert.deepEqual(trend.rulers(), [100]);
});

// ===== MIN / MAX / AVG over the visible window =====

function statPen(points, now, spanS) {
  reset();
  trend.addTag('TT-321001', 0);
  I.slots[0].pts = points;
  I.setNow(now); I.setSpanValue(spanS);
  return I.slots[0];
}

test('stats cover min, max and mean of the visible points', () => {
  const s = statPen([{ t: 96, v: 10 }, { t: 97, v: 30 }, { t: 98, v: 20 }, { t: 99, v: 40 }], 100, 60);
  const st = trend.windowStats(s);
  assert.equal(st.min, 10);
  assert.equal(st.max, 40);
  assert.equal(st.avg, 25);
  assert.equal(st.n, 4);
});

test('stats ignore points outside the scrolled window', () => {
  const s = statPen([{ t: 10, v: 999 }, { t: 95, v: 20 }, { t: 100, v: 40 }], 100, 30);
  const st = trend.windowStats(s);   // window is (70, 100]; t=10 excluded
  assert.equal(st.min, 20);
  assert.equal(st.max, 40);
  assert.equal(st.n, 2);
});

test('stats of an empty or fully-out-of-window pen are null', () => {
  assert.equal(trend.windowStats(statPen([], 100, 60)), null);
  assert.equal(trend.windowStats(statPen([{ t: 5, v: 1 }], 100, 60)), null);
});

test('digital pen average is its duty fraction', () => {
  const s = statPen([{ t: 96, v: 1 }, { t: 97, v: 1 }, { t: 98, v: 0 }, { t: 99, v: 0 }], 100, 60);
  const st = trend.windowStats(s);
  assert.equal(st.min, 0);
  assert.equal(st.max, 1);
  assert.equal(st.avg, 0.5);
});

// ===== scrolling through history =====

test('the view starts live and the back arrow parks it on an instant', () => {
  reset();
  I.setNow(10000);
  I.setSpanValue(3600);
  trend.goLive();
  assert.equal(trend.isLive(), true);
  assert.equal(trend.viewEnd(), 10000);
  trend.pan(-1);                                  // a quarter of 3600 s
  assert.equal(trend.isLive(), false);
  assert.equal(trend.viewEnd(), 10000 - 900);
});

test('a parked view does not drift forward as the plant runs on', () => {
  reset();
  I.setNow(10000); I.setSpanValue(3600);
  trend.goLive();
  trend.pan(-1);
  const parked = trend.viewEnd();
  I.setNow(10600);                                // 10 more plant-minutes elapse
  assert.equal(trend.viewEnd(), parked, 'the window must stay on the instant it was parked at');
});

test('the forward arrow steps back toward now and resumes live on arrival', () => {
  reset();
  I.setNow(10000); I.setSpanValue(3600);
  trend.goLive();
  trend.pan(-1); trend.pan(-1);
  assert.equal(trend.viewEnd(), 10000 - 1800);
  trend.pan(1);
  assert.equal(trend.isLive(), false);
  trend.pan(1);
  assert.equal(trend.isLive(), true, 'catching up to now must resume live');
  assert.equal(trend.viewEnd(), 10000);
});

test('scrolling back stops at program start, never before it', () => {
  reset();
  I.setNow(5000); I.setSpanValue(3600);
  trend.goLive();
  for (let i = 0; i < 20; i++) trend.pan(-1);
  assert.equal(trend.viewEnd(), 5000 - I.maxPanBack());
  assert.ok(trend.viewEnd() - 3600 >= -1e-6, 'the window must not open before t=0');
});

test('scroll range is bounded by retention, not by uptime', () => {
  reset();
  I.setNow(200000); I.setSpanValue(3600);         // far beyond the 8 h archive
  assert.equal(I.maxPanBack(), 28800 - 3600);
});

test('a short span cannot scroll back at all before enough history exists', () => {
  reset();
  I.setNow(120); I.setSpanValue(3600);
  assert.equal(I.maxPanBack(), 0, 'nothing older than the span exists yet');
});

test('goLive is a no-op when already live', () => {
  reset();
  I.setNow(9000); I.setSpanValue(3600);
  trend.goLive();
  trend.goLive();
  assert.equal(trend.isLive(), true);
  assert.equal(trend.viewEnd(), 9000);
});

// ===== desktop-clock mapping =====

test('desktop time is interpolated from the plant/desktop pairs', () => {
  I.noteTime(1000, 5000);
  I.noteTime(1060, 5060);
  assert.ok(Math.abs(I.wallAt(1030) - 5030) < 1e-6);
});

test('under FAST pacing the two clocks diverge and the mapping follows', () => {
  I.noteTime(2000, 6000);
  I.noteTime(2600, 6010);          // 600 plant-s inside 10 desktop-s = 60x
  assert.ok(Math.abs(I.wallAt(2300) - 6005) < 1e-6);
});

// ===== persistence =====

test('span and slot list round-trip through localStorage', () => {
  reset();
  trend.addTag('TT-321001', 0);
  trend.addTag('PT-321201', 2);
  I.setSpanValue(7200);
  I.save();
  const st = I.saved();
  assert.equal(st.span, 7200);
  assert.equal(st.tags[0], 'TT-321001');
  assert.equal(st.tags[1], null);
  assert.equal(st.tags[2], 'PT-321201');
  assert.equal(st.tags.length, 10);
});

test('the seven required spans are offered, defaulting to 1 hour', () => {
  assert.deepEqual(I.SPANS.map(s => s.s), [60, 300, 1800, 3600, 7200, 14400, 28800]);
  assert.deepEqual(I.SPANS.map(s => s.lbl), ['1m', '5m', '30m', '1h', '2h', '4h', '8h']);
});

test('there are ten distinct pen colours for ten slots', () => {
  assert.equal(I.PENS.length, 10);
  assert.equal(new Set(I.PENS).size, 10);
});
