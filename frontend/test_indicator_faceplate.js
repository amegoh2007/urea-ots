'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const faceplate = require('./indicator_faceplate.js');

let passed = 0;
function test(name, body) {
  faceplate.reset();
  body();
  passed += 1;
  process.stdout.write(`ok ${passed} - ${name}\n`);
}

test('formats every finite numeric PV with exactly three decimals', () => {
  assert.strictEqual(faceplate.display(7), '7.000');
  assert.strictEqual(faceplate.display(12.34567), '12.346');
  assert.strictEqual(faceplate.display(-0.0049), '-0.005');
});

test('preserves discrete process text exactly', () => {
  assert.strictEqual(faceplate.display('ON'), 'ON');
  assert.strictEqual(faceplate.display('LOW'), 'LOW');
});

test('shows an em dash for an unavailable PV', () => {
  assert.strictEqual(faceplate.display(null), '—');
  assert.strictEqual(faceplate.display(undefined), '—');
  assert.strictEqual(faceplate.display(Number.NaN), '—');
});

test('returns the latest published post-dynamics value and unit by tag', () => {
  faceplate.publish('TI-321020', 28.1234, 'C');
  faceplate.publish('TI-321020', 29.9876, 'C');
  assert.deepStrictEqual(faceplate.read('TI-321020'), {
    tag: 'TI-321020', value: 29.9876, unit: 'C', display: '29.988',
  });
});

test('integrates the shared registry with every indicator route', () => {
  const html = fs.readFileSync(path.join(__dirname, 'index.html'), 'utf8');
  const app = fs.readFileSync(path.join(__dirname, 'app.js'), 'utf8');
  const overlays = fs.readFileSync(path.join(__dirname, 'overlays.js'), 'utf8');

  assert.ok(html.indexOf('indicator_faceplate.js') >= 0, 'registry script is not loaded');
  assert.ok(html.indexOf('indicator_faceplate.js') < html.indexOf('app.js'), 'registry must load before app.js');
  assert.match(html, /id="indicatorModal"/);
  assert.match(app, /IndicatorFaceplate\.publish/);
  assert.match(overlays, /IndicatorFaceplate\.publish/);
  assert.match(overlays, /OTS_FACE\.indicator/);
  assert.match(app, /IndicatorFaceplate\.display/);
});

process.stdout.write(`# ${passed} indicator-faceplate tests passed\n`);
