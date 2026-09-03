'use strict';

// Shared transmitter/HMI first-order-plus-dead-time layer.
// Uses plant simulation time, so SLOW and FAST pacing produce identical dynamics.
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.IndicatorDynamics = api;
})(typeof window !== 'undefined' ? window : globalThis, function () {
  const PROFILES = Object.freeze({
    antiSurge: Object.freeze({ service: 'anti-surge pressure/flow', tauS: 0.05, deadTimeS: 0.002 }),
    pressure: Object.freeze({ service: 'pressure', tauS: 0.75, deadTimeS: 0.10 }),
    flow: Object.freeze({ service: 'flow', tauS: 2.0, deadTimeS: 0.10 }),
    turbulentLevel: Object.freeze({ service: 'turbulent level', tauS: 7.5, deadTimeS: 0.50 }),
    calmLevel: Object.freeze({ service: 'calm level', tauS: 3.5, deadTimeS: 0.50 }),
    temperature: Object.freeze({ service: 'temperature', tauS: 30.0, deadTimeS: 1.0 }),
    analyzer: Object.freeze({ service: 'composition analyzer', tauS: 60.0, deadTimeS: 600.0 }),
    speedCurrent: Object.freeze({ service: 'speed/current', tauS: 1.0, deadTimeS: 0.10 }),
    valvePosition: Object.freeze({ service: 'valve/hand station', tauS: 3.5, deadTimeS: 0.25 }),
    totalizer: Object.freeze({ service: 'totalizer', tauS: 0.5, deadTimeS: 0.10 }),
    generic: Object.freeze({ service: 'generic', tauS: 1.0, deadTimeS: 0.10 }),
  });

  // Boiling/reacting HP inventories named in the supplied procedure and present in the HMI.
  const TURBULENT_LEVEL_TAGS = new Set(['LT-322504', 'LIC-322501', 'LT-329501']);
  const states = new Map();
  let newestClock = null;

  function finiteNonnegative(value) {
    return typeof value === 'number' && Number.isFinite(value) && value >= 0;
  }

  function baseProfile(tag) {
    const normalized = String(tag || '').trim().toUpperCase();
    const prefix = normalized.split('-')[0];
    if (TURBULENT_LEVEL_TAGS.has(normalized)) return PROFILES.turbulentLevel;
    if (/^(AT|AI|AY)$/.test(prefix)) return PROFILES.analyzer;
    if (/^(TT|TI|TIC|TDY)$/.test(prefix)) return PROFILES.temperature;
    if (/^(FQI)$/.test(prefix)) return PROFILES.totalizer;
    if (/^(FT|FI|FIC|FFIC|FY|FFY)$/.test(prefix)) return PROFILES.flow;
    if (/^(PT|PI|PIC|PY|IPY|PDY)$/.test(prefix)) return PROFILES.pressure;
    if (/^(LT|LI|LIC|LSL|LDY)$/.test(prefix)) return PROFILES.calmLevel;
    if (/^(SIC|IT)$/.test(prefix)) return PROFILES.speedCurrent;
    if (/^(HIC|HV|TV|LV|PV|FV|HS)$/.test(prefix)) return PROFILES.valvePosition;
    return PROFILES.generic;
  }

  function profile(tag, override) {
    const base = baseProfile(tag);
    const custom = override || {};
    return {
      service: typeof custom.service === 'string' && custom.service ? custom.service : base.service,
      tauS: finiteNonnegative(custom.tauS) ? custom.tauS : base.tauS,
      deadTimeS: finiteNonnegative(custom.deadTimeS) ? custom.deadTimeS : base.deadTimeS,
    };
  }

  function seed(key, raw, simTime) {
    const state = {
      lastTime: simTime,
      output: raw,
      delayedInput: raw,
      queue: [{ time: simTime, value: raw }],
    };
    states.set(key, state);
    return raw;
  }

  function reset() {
    states.clear();
    newestClock = null;
  }

  function sample(key, tag, rawValue, simTime, override) {
    const raw = Number(rawValue);
    const now = Number(simTime);
    if (!Number.isFinite(raw) || !Number.isFinite(now)) return rawValue;

    // Simulator RESET replaces State and rewinds sim_t. No pre-reset transmitter history survives.
    if (newestClock !== null && now < newestClock) reset();
    if (newestClock === null || now > newestClock) newestClock = now;

    const stateKey = String(key || tag || 'indicator');
    let state = states.get(stateKey);
    if (!state || now < state.lastTime) return seed(stateKey, raw, now);
    if (now === state.lastTime) return state.output;

    const cfg = profile(tag, override);
    state.queue.push({ time: now, value: raw });
    const cutoff = now - cfg.deadTimeS;

    // Keep the newest sample at or before the cutoff as the zero-order-held delayed input.
    while (state.queue.length >= 2 && state.queue[1].time <= cutoff) state.queue.shift();
    if (state.queue[0].time <= cutoff) state.delayedInput = state.queue[0].value;

    const dt = now - state.lastTime;
    if (cfg.tauS <= 0) {
      state.output = state.delayedInput;
    } else {
      const alpha = 1 - Math.exp(-dt / cfg.tauS);
      state.output += alpha * (state.delayedInput - state.output);
    }
    state.lastTime = now;
    return state.output;
  }

  function seconds(value) {
    if (value < 0.01) return `${Math.round(value * 1000)} ms`;
    return `${Number(value.toFixed(3))} s`;
  }

  function describe(tag, override) {
    const cfg = profile(tag, override);
    return `${cfg.service}; tau=${seconds(cfg.tauS)}, theta=${seconds(cfg.deadTimeS)}`;
  }

  return Object.freeze({ profile, sample, describe, reset, profiles: PROFILES });
});
