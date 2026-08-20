'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const routeApi = require('./lv324501_route.js');


test('LV-324501 A click sends forward command with truthful Stream 609 label', () => {
  const sent = [];

  const message = routeApi.activate('A', command => sent.push(command));

  assert.deepEqual(message, {type: 'lv324501_route_set', route: 'A'});
  assert.deepEqual(sent, [message]);
  assert.match(routeApi.ROUTES.A.label, /Stream 609/);
  assert.match(routeApi.ROUTES.A.label, /402G \+ UF85/);
  assert.match(routeApi.ROUTES.A.label, /Unit 335/);
});


test('LV-324501 B click sends recycle command with truthful raw-stream label', () => {
  const sent = [];

  const message = routeApi.activate('B', command => sent.push(command));

  assert.deepEqual(message, {type: 'lv324501_route_set', route: 'B'});
  assert.deepEqual(sent, [message]);
  assert.match(routeApi.ROUTES.B.label, /raw Stream 402G/);
  assert.match(routeApi.ROUTES.B.label, /323D002/);
  assert.match(routeApi.ROUTES.B.label, /UF85 OFF/);
});


test('LV-324501 UI rejects an undeclared route', () => {
  assert.throws(() => routeApi.activate('C', () => {}), /Unknown LV-324501 route/);
});


test('stage-2 overlay loads and activates both declared route commands', () => {
  const overlaySource = fs.readFileSync(path.join(__dirname, 'overlays.js'), 'utf8');
  const indexSource = fs.readFileSync(path.join(__dirname, 'index.html'), 'utf8');

  assert.match(overlaySource, /tag: 'LV-324501A'[\s\S]*route: 'A'/);
  assert.match(overlaySource, /tag: 'LV-324501B'[\s\S]*route: 'B'/);
  assert.match(overlaySource, /OTS_LV324501_ROUTE[\s\S]*api\.activate/);
  assert.ok(indexSource.indexOf('lv324501_route.js') < indexSource.indexOf('overlays.js'));
});
