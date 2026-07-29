'use strict';

(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.OTS_LV324501_ROUTE = api;
})(typeof window !== 'undefined' ? window : globalThis, function () {
  const ROUTES = Object.freeze({
    A: Object.freeze({
      label: 'A - FORWARD: mixed Stream 609 (402G + UF85) to Unit 335',
    }),
    B: Object.freeze({
      label: 'B - RECYCLE: raw Stream 402G to 323D002; UF85 OFF',
    }),
  });

  function command(route) {
    const id = String(route || '').trim().toUpperCase();
    if (!ROUTES[id]) throw new Error('Unknown LV-324501 route: ' + route);
    return {type: 'lv324501_route_set', route: id};
  }

  function activate(route, send) {
    if (typeof send !== 'function') throw new TypeError('LV-324501 sender is unavailable');
    const message = command(route);
    send(message);
    return message;
  }

  return Object.freeze({ROUTES, command, activate});
});
