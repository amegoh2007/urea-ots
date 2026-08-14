'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const dynamics = require('./indicator_dynamics.js');

let passed = 0;
function test(name, body) {
  dynamics.reset();
  body();
  passed += 1;
  process.stdout.write(`ok ${passed} - ${name}\n`);
}

test('classifies every documented instrument service', () => {
  assert.deepStrictEqual(dynamics.profile('TT-322010'), {
    service: 'temperature', tauS: 30, deadTimeS: 1,
  });
  assert.strictEqual(dynamics.profile('PT-329201').tauS, 0.75);
  assert.strictEqual(dynamics.profile('FT-329407').tauS, 2);
  assert.strictEqual(dynamics.profile('LT-322504').service, 'turbulent level');
  assert.strictEqual(dynamics.profile('LIC-323507').service, 'calm level');
  assert.strictEqual(dynamics.profile('AT-322701').deadTimeS, 600);
  assert.strictEqual(dynamics.profile('SIC-321950').service, 'speed/current');
  assert.strictEqual(dynamics.profile('HIC-322605').service, 'valve/hand station');
  assert.strictEqual(dynamics.profile('FQI-321401').service, 'totalizer');
  assert.strictEqual(dynamics.profile('LOAD').service, 'generic');
});

test('holds a step for dead time then reaches 63.2 percent after one time constant', () => {
  const profile = { tauS: 10, deadTimeS: 2 };
  assert.strictEqual(dynamics.sample('test:tt', 'TT-TEST', 0, 0, profile), 0);
  assert.strictEqual(dynamics.sample('test:tt', 'TT-TEST', 100, 1, profile), 0);
  assert.strictEqual(dynamics.sample('test:tt', 'TT-TEST', 100, 2, profile), 0);
  const afterArrival = dynamics.sample('test:tt', 'TT-TEST', 100, 3, profile);
  assert.ok(afterArrival > 0 && afterArrival < 100);
  const oneTau = dynamics.sample('test:tt', 'TT-TEST', 100, 12, profile);
  assert.ok(Math.abs(oneTau - 63.2120559) < 1e-6, `oneTau=${oneTau}`);
});

test('returns one shared value for repeated tag reads at the same simulation time', () => {
  const profile = { tauS: 2, deadTimeS: 0.1 };
  dynamics.sample('shared:tag', 'FT-1', 0, 0, profile);
  const first = dynamics.sample('shared:tag', 'FT-1', 10, 1, profile);
  const duplicate = dynamics.sample('shared:tag', 'FT-1', 99, 1, profile);
  assert.strictEqual(duplicate, first);
});

test('clears stale history when the simulation clock rewinds', () => {
  const profile = { tauS: 10, deadTimeS: 2 };
  dynamics.sample('reset:tag', 'TT-1', 0, 10, profile);
  dynamics.sample('reset:tag', 'TT-1', 100, 20, profile);
  assert.strictEqual(dynamics.sample('reset:tag', 'TT-1', 42, 0, profile), 42);
});

test('assigns positive dynamics to every overlay indicator tag', () => {
  const source = fs.readFileSync(path.join(__dirname, 'overlays.js'), 'utf8');
  const records = [...source.matchAll(/\{[^{}]*\bt:\s*'ind'[^{}]*\}/g)];
  assert.ok(records.length >= 227, `found only ${records.length} indicator records`);
  for (const record of records) {
    const tag = record[0].match(/\btag:\s*'([^']+)'/);
    assert.ok(tag, `indicator record lacks tag: ${record[0]}`);
    const profile = dynamics.profile(tag[1]);
    assert.ok(profile.tauS > 0, `${tag[1]} has no process time constant`);
    assert.ok(profile.deadTimeS > 0, `${tag[1]} has no dead time`);
  }
});

test('loads and calls the shared service from both indicator render paths', () => {
  const html = fs.readFileSync(path.join(__dirname, 'index.html'), 'utf8');
  const app = fs.readFileSync(path.join(__dirname, 'app.js'), 'utf8');
  const overlays = fs.readFileSync(path.join(__dirname, 'overlays.js'), 'utf8');
  assert.ok(html.indexOf('indicator_dynamics.js') >= 0, 'service script is not loaded');
  assert.ok(html.indexOf('indicator_dynamics.js') < html.indexOf('app.js'), 'service must load before app.js');
  assert.match(app, /IndicatorDynamics\.sample/);
  assert.match(overlays, /IndicatorDynamics\.sample/);
  assert.match(overlays, /IndicatorDynamics\.describe/);
});

test('publishes post-dynamics values from both indicator render paths', () => {
  const html = fs.readFileSync(path.join(__dirname, 'index.html'), 'utf8');
  const app = fs.readFileSync(path.join(__dirname, 'app.js'), 'utf8');
  const overlays = fs.readFileSync(path.join(__dirname, 'overlays.js'), 'utf8');
  assert.ok(html.indexOf('indicator_dynamics.js') < html.indexOf('indicator_faceplate.js'), 'dynamics must load before the faceplate registry');
  assert.ok(html.indexOf('indicator_faceplate.js') < html.indexOf('app.js'), 'faceplate registry must load before renderers');
  assert.match(app, /IndicatorFaceplate\.publish\(instrumentTag, shown, u\)/);
  assert.match(overlays, /IndicatorFaceplate\.publish\(o\.tag, v, u\)/);
});

process.stdout.write(`# ${passed} indicator-dynamics tests passed\n`);
