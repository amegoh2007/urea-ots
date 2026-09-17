'use strict';

(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.IndicatorFaceplate = api;
})(typeof window !== 'undefined' ? window : globalThis, function () {
  const values = new Map();

  function display(value) {
    if (value == null || (typeof value === 'number' && !Number.isFinite(value))) return '—';
    return typeof value === 'number' ? value.toFixed(3) : String(value);
  }

  function publish(tag, value, unit) {
    const key = String(tag || '');
    if (!key) return null;
    const sample = { tag: key, value, unit: unit || '', display: display(value) };
    values.set(key, sample);
    return sample;
  }

  function read(tag) {
    return values.get(String(tag || '')) || null;
  }

  function reset() {
    values.clear();
  }

  return { publish, read, display, reset };
});
