# Handoff: Open Gaps

## THERMODYNAMIC & MESH AUDIT — COMPLETED 2026-08-27

**Status:** ✓ COMPLIANT (corrective actions documented)

**Report:** `THERMODYNAMIC_MESH_AUDIT_REPORT.md`

Plant-wide thermodynamic model assignment, MESH equation closure, and ripple-effect propagation audited against the live running engine. All findings verified by executing `backend/main.py` and reading source — nothing inferred from module docstrings.

**Core Physics: COMPLIANT**
- Component balances close to machine precision (<1e-16)
- Energy balances close within 1 kW tolerance
- Recycle tears converge to 1e-15 without iterative solve
- Composition constraints (Σxᵢ = 1) hold at floating-point epsilon under extreme off-design
- Reaction kinetics respond correctly to T/N/C/H/C gradients, ceiling guard enforces X ≤ X_inf exactly
- +5% CO₂ feed step propagates through all 6 sections with correct sign and magnitude

**Corrective Actions Required:**

1. **Documentation reconciliation (highest priority, no code risk)**
   - `project.md` §5.1 claims Extended UNIQUAC electrolyte model (`props_nh3co2h2o.py`, `vle_nh3co2h2o.py`) supplies 323C003, 323F004, 328D003 bubble points
   - **Reality:** Neither module is imported at runtime; all ionic-section VLE uses IAPWS-IF97 pure-water tsat + frozen design offset
   - Action: Reclassify Extended UNIQUAC as validated-but-unintegrated research module; document as-built method

2. **Stream enthalpy population**
   - All 55 streams carry `enthalpy_kJkg` and `enthalpy_flow_kW` keys, all are `None`
   - Blocks per-stream enthalpy balance (explicitly requested in audit Phase 2)
   - Section-level energy closure unaffected and does close

3. **Steam-coupled liquid temperature lag**
   - 324E001 liquid temperature (TT-324001) begins moving in 1 s after CO₂ step
   - Arrives via shared steam header (pressure transient), not via material path (28 s dead time)
   - 180 s-residence liquid inventory should not respond in 1 s
   - Fix: route through existing `_delay(...)` mechanism

4. **Minor cleanups**
   - Remove dead `EmpiricalThermo.bubble_p` placeholder (no caller, cannot be mistaken for live fluid package)
   - Fix CO₂ pressure assertion in `audit_model_compliance.py` (feed line legitimately behind PIC-322203)

**Enhancement Opportunities (optional):**
- Integrate Extended UNIQUAC electrolyte model for rigorous HP synthesis VLE
- Integrate choked flow model (`consequence.py` ISA 75.01.01 — built but not wired to main.py)
- Experimental validation of Unit 324 vacuum VLE (0.02–1.0 bar, 35–1750× below published 35 bar floor)
- Extend stream coverage beyond 55/163 PFD streams as scenarios require

---

**Prior Closed Issues (Retained for Context):**
- FIC-328402 valve hunting resolved (commit f6c9df9, gain 0.75→0.06)
- FFIC-329401 ratio implementation verified correct
- HV-329605/329606 propagation verified
- Scenario coverage 85–90% (Scenarios.md/2/3)
- UI page 321-1 migration complete (17 indicators, 2 hand switches, 5 nav links)
  - Backend verification: PDY-321204 ✓, TI-321020 ✓, FQI-321401 ✗, FFIC-321404A/B ✗


---

**Last Updated:** 2026-08-27 (thermodynamic & MESH audit)
**Next Session:** Address corrective actions in priority order:
1. Documentation reconciliation (project.md §5.1, clarify Extended UNIQUAC status)
2. Stream enthalpy population (serialize computed values or drop schema fields)
3. Apply transport lag on steam-coupled liquid temperature path



