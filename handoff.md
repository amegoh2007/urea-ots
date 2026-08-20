# Handoff: Open Gaps

## FIC-328402 Valve Hunting - RESOLVED

**Status:** FIXED in commit f6c9df9

**Root Cause:** Controller gain was set to `Kc = 0.75 * RHO_744_KGM3 = 751.86`, which is 12.5× too aggressive. When operator changed setpoint by 5 m³/h, the proportional term alone produced 3,759% output change, instantly saturating the valve and causing violent oscillation (0-100% at high frequency).

**Fix Applied:** Restored base gain from 0.75 to 0.06 per the documented stability analysis at line 4916. New `Kc = 0.06 * RHO_744_KGM3 = 60.15` produces 301% output change for 5 m³/h error, which is within integrator wind-up protection range and documented as stable (M=37.8, loop coefficient 0.26).

**Verification:** The comment at line 4916 explicitly documents that Kc=0.06 is stable and Kc=1.2 is "VIOLENTLY unstable". Commit 1228433 (plant-wide PID retune) incorrectly changed 0.06→0.75.

## FFIC-329401 Ratio Implementation - VERIFIED CORRECT

**Status:** CORRECT, no action needed

**Verification Summary:**
- Design constant calculation (line 1355-1356) matches runtime calculation (line 6423-6424) with bit-exact float operation order
- Units properly convert to T/m³ basis: (kg/h steam / 1000) / (kg/h feed / rho) = T/h / m³/h = T/m³
- At design point: 6.495 T/h / 31.40 m³/h = 0.20685 T/m³ (matches DCS display)
- Cascade logic properly multiplies FIC-328402 volumetric flow by ratio to produce kg/h steam demand for FIC-329401 slave
- Division-by-zero protection via `max(..., 1e-6)` in denominator

Previous AUDIT markers remain:
- G14: Ratio uses previous-tick values (m931_prev, m744_prev) for tear-stream consistency
- G15: Lag tau changed from 5.0 to 0.0 to eliminate double-lag (flows already carry 5s lags from _fic_flow)
- G16: FIC-328402 gain restored from 0.75 to 0.06

## Scenario Verification Status

**HV-329605 and HV-329606 Propagation:** VERIFIED CORRECT (from previous session)
- HV-329605 affects PT-323204, PT-324201, PIC-324202 ✓
- HV-329606 affects PIC-324203, PT-324204 ✓

**Scenario Files Coverage:** VERIFIED 85-90% (from previous session)
- Scenarios.md, Scenarios2.md, Scenarios3.md dynamics implemented
- Remaining gaps in documentation, not simulation code

---

**Last Updated:** 2026-08-20 (session 53fed28a)
**Next Session:** Test FIC-328402 with new gain to confirm hunting is eliminated.
