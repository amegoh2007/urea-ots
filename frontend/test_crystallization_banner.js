'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');


test('overlay code omits the crystallization alarm UI', () => {
  const overlayPath = path.join(__dirname, 'overlays.js');
  const source = fs.readFileSync(overlayPath, 'utf8');
  const alarmUi = /ov-cryst|crystBanner|crystRender|CARBAMATE_CRYST|\.CRYST\b/;

  assert.doesNotMatch(source, alarmUi);
});
