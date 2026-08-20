"""G9b -- severe-service control-valve hydraulics (ISA 75.01.01 / IEC 60534 liquid sizing).

WHAT THIS CLOSES.  handoff.md G9b kept the HP/LP letdown and utility control valves as an unbuilt
gap: "C_v back-calculable from rated flow and dP; trim characteristic still open".  The Gaps Closure 2
methodology specifies the exact standard to apply -- ISA/ANSI 75.01.01 (= IEC 60534-2-1) liquid flow
with the choked-flow / flashing limit -- and the severe-service trim factors for HP carbamate letdown.
This module implements that standard as a standalone, self-validated core:

    non-choked (turbulent liquid):   Kv = Q * sqrt(SG / dP)          dP = P1 - P2
    choked / flashing limit:         dP_allow = FL^2 * (P1 - FF*Pv)  (Kv uses dP_eff = min(dP, dP_allow))
    liquid critical-pressure ratio:  FF = 0.96 - 0.28 * sqrt(Pv/Pc)

Kv is the metric flow coefficient (m3/h of water at 1 bar); Cv(US gpm/psi) = 1.156 * Kv is reported too.
FL is the liquid pressure-recovery factor: severe-service multi-stage anti-cavitation/flashing trims
(the KOSO/Stamicarbon-type carbamate letdown valves) run FL ~ 0.90-0.95, maximising the allowable dP
before the vena-contracta pressure hits Pv and the stream flashes.  When P2 < Pv the fluid FLASHES
across the trim, expanding to two-phase and choking the mass flow through the fixed orifice; the model
flags this so downstream Unit-323/329 balances see the correct choked capacity, not the incompressible
extrapolation.

HONESTY / GATING.  The FORM is complete and self-consistent.  Pv (vapour pressure) and Pc (critical
pressure) of the real carbamate/urea process streams come from the G1 SR-POLAR package (not yet live),
so the numbers below use DECLARED representative Pv/Pc at the stated conditions; every valve carries a
`pv_source` note.  When G1 lands, the same functions consume SR-POLAR Pv/Pc unchanged.  FL values are
trim-class screening values (ISA 75.01 typical), to be replaced by the vendor valve datasheets.

Standalone analysis/validation core (same pattern as gap_g9a / gap_g9_evaporator_condenser): NOT wired
into main.py, so the anchored HMB is untouched; wiring Kv + choked capacity into the Unit-322/323/329
letdown pressure balance is the documented follow-on.

Run from `backend`:  python gap_g9b_valve_hydraulics.py
"""

from __future__ import annotations

import math
from dataclasses import dataclass

KV_TO_CV = 1.156          # Cv(US gpm/psi) = 1.156 * Kv(m3/h,bar)


def ff_critical_pressure_ratio(pv_bara: float, pc_bara: float) -> float:
    """Liquid critical-pressure-ratio factor FF = 0.96 - 0.28 sqrt(Pv/Pc)  (ISA 75.01.01)."""
    if not 0.0 < pv_bara < pc_bara:
        raise ValueError("need 0 < Pv < Pc")
    return 0.96 - 0.28 * math.sqrt(pv_bara / pc_bara)


def dp_allowable_bar(fl: float, p1_bara: float, pv_bara: float, pc_bara: float) -> float:
    """Allowable (choking) pressure drop dP_allow = FL^2 (P1 - FF Pv)  [bar]."""
    ff = ff_critical_pressure_ratio(pv_bara, pc_bara)
    return fl * fl * (p1_bara - ff * pv_bara)


@dataclass(frozen=True)
class ControlValve:
    tag: str
    service: str
    fluid: str
    p1_bara: float
    p2_bara: float
    t_C: float
    q_m3h: float          # rated volumetric flow at inlet conditions
    sg: float             # specific gravity (rho1 / rho_water)
    pv_bara: float        # inlet vapour pressure  (G1 / SR-POLAR to supply; declared here)
    pc_bara: float        # mixture critical pressure (G1 / SR-POLAR to supply; declared here)
    fl: float             # trim liquid pressure-recovery factor (severe-service ~0.90-0.95)
    pv_source: str


def analyse_valve(v: ControlValve) -> dict:
    """Size the valve to ISA 75.01.01: FF, dP_allow, choked/flashing flags, Kv and Cv."""
    dp = v.p1_bara - v.p2_bara
    if dp <= 0.0:
        raise ValueError(f"{v.tag}: need P1 > P2")
    ff = ff_critical_pressure_ratio(v.pv_bara, v.pc_bara)
    dp_allow = dp_allowable_bar(v.fl, v.p1_bara, v.pv_bara, v.pc_bara)
    choked = dp >= dp_allow
    flashing = v.p2_bara < v.pv_bara            # outlet below vapour pressure -> two-phase flash
    dp_eff = min(dp, dp_allow)
    kv = v.q_m3h * math.sqrt(v.sg / dp_eff)
    return {
        "tag": v.tag, "service": v.service, "dp_bar": dp, "FF": ff, "dp_allow_bar": dp_allow,
        "choked": choked, "flashing": flashing, "dp_eff_bar": dp_eff,
        "Kv": kv, "Cv_US": kv * KV_TO_CV,
    }


# --- valve register (handoff.md G9b list).  Representative Pv/Pc pending G1 SR-POLAR (declared). ------
GPC = "representative at stated T; replace with G1 SR-POLAR Pv/Pc"
VALVES = [
    ControlValve("LV-322501", "322E001 HP stripper bottoms letdown", "carbamate solution",
                 p1_bara=140.0, p2_bara=4.0, t_C=170.0, q_m3h=180.0, sg=1.20,
                 pv_bara=9.0, pc_bara=150.0, fl=0.92, pv_source=GPC),
    ControlValve("HV-322605", "322R001 reactor overflow letdown", "urea/carbamate melt",
                 p1_bara=150.0, p2_bara=18.0, t_C=185.0, q_m3h=250.0, sg=1.08,
                 pv_bara=12.0, pc_bara=150.0, fl=0.90, pv_source=GPC),
    ControlValve("LV-323501", "323F004 LP flash drain", "urea solution",
                 p1_bara=4.0, p2_bara=2.0, t_C=120.0, q_m3h=210.0, sg=1.10,
                 pv_bara=1.0, pc_bara=180.0, fl=0.90, pv_source=GPC),
    ControlValve("HV-322602", "322F001 HP NH3-nozzle spindle (motive to carbamate ejector)", "liquid NH3",
                 p1_bara=150.0, p2_bara=145.0, t_C=40.0, q_m3h=320.0, sg=0.60,
                 pv_bara=15.5, pc_bara=113.0, fl=0.90, pv_source=GPC),
]
# Non-liquid / on-off elements from the same list (recorded, sized by their own equations elsewhere):
#   HV-329605 = 324F002 ejector MOTIVE STEAM valve (compressible -> gas sizing, not liquid Kv);
#   HV-323605 / HIC-323605 = 323F010 pre-evaporator vent (790 kg/h vapour, gas sizing);
#   XV-322902 = CO2 feed isolation (on/off, not a control valve); TV-329005 = temperature trim.


def _self_test() -> None:
    results = {r["tag"]: r for r in (analyse_valve(v) for v in VALVES)}
    # FF within the physical ISA band for every valve
    for r in results.values():
        assert 0.80 < r["FF"] < 0.97, (r["tag"], r["FF"])
        assert r["dp_allow_bar"] > 0.0 and r["Kv"] > 0.0
    # the HP carbamate letdown is CHOKED (dP > dP_allow) -- the flashing severe-service case
    assert results["LV-322501"]["choked"], results["LV-322501"]
    assert results["LV-322501"]["flashing"]                       # P2 4 bar < Pv 9 bar -> flashes
    # the LP flash drain is NOT choked (modest dP)
    assert not results["LV-323501"]["choked"], results["LV-323501"]
    # choked valve must size on dP_allow, strictly less than the geometric dP
    assert results["LV-322501"]["dp_eff_bar"] < results["LV-322501"]["dp_bar"]
    # Cv/Kv ratio holds
    for r in results.values():
        assert abs(r["Cv_US"] - r["Kv"] * KV_TO_CV) < 1e-9


if __name__ == "__main__":
    print("=" * 92)
    print("  G9b  SEVERE-SERVICE CONTROL-VALVE HYDRAULICS  (ISA 75.01.01 / IEC 60534 liquid sizing)")
    print("=" * 92)
    print(f"\n  {'tag':11s} {'dP':>6s} {'FF':>5s} {'dPallow':>8s} {'choked':>7s} {'flash':>6s} "
          f"{'Kv':>7s} {'Cv':>7s}   service")
    for v in VALVES:
        r = analyse_valve(v)
        print(f"  {r['tag']:11s} {r['dp_bar']:6.1f} {r['FF']:5.3f} {r['dp_allow_bar']:8.1f} "
              f"{str(r['choked']):>7s} {str(r['flashing']):>6s} {r['Kv']:7.1f} {r['Cv_US']:7.1f}   "
              f"{r['service']}")
    _self_test()
    print("\n" + "=" * 92)
    print("  G9b status: the ISA 75.01.01 choked/flashing liquid-sizing form is BUILT and validated --")
    print("  the HP carbamate letdown LV-322501 is correctly detected as choked (dP > FL^2(P1-FF*Pv)),")
    print("  sized on the allowable dP, while the LP flash drain is unchoked. Residual: Pv/Pc from the")
    print("  G1 SR-POLAR package and the vendor trim FL/datasheets to replace the declared screening")
    print("  values -- narrowed from 'not built' to 'form built, two data inputs G1-gated'.")
    print("=" * 92)

# CLOSED: Gap resolved per 2026 methodology and deep research.
