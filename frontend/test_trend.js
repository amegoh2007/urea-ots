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

test('a slot carries its declared engineering range', () => {
  reset();
  trend.addTag('HV-322602', 0);
  assert.equal(I.slots[0].lo, 0);
  assert.equal(I.slots[0].hi, 100);
  assert.equal(I.slots[0].auto, false);
});

test('a slot with no declared range is marked for auto-scaling', () => {
  reset();
  trend.addTag('N/C Ratio', 0);
  assert.equal(I.slots[0].auto, true);
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
