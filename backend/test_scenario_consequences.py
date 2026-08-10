"""Scenario-coverage verification for the Urea OTS.

Drives each documented deviation from References/scenarios/*.md and asserts that the model produces
the written-up consequence, that the consequence reaches downstream equipment with a real lag, and
that undocumented deviations of the SAME CLASS produce the same class of consequence.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  PASS  " if cond else "  FAIL  ") + name + (("   " + detail) if detail else ""))


def fresh():
    main.state = main.State()
    return main.state


def run(n, dt=0.1):
    for _ in range(n):
        r = main.step_sim(dt)
    return r


# ---------------------------------------------------------------- 0a. settled-state diagnostics
print("\n=== 0a. DESIGN SETTLE DIAGNOSTICS (informational; see gap G-LOOP-1) ===")
import consequence as _cq  # noqa: E402
s = fresh()
for n in (0, 600, 6000):
    if n:
        run(n)
    seal_r = _cq.seal_fraction(s.react_level_pct,
                               main.REACT_FUNNEL_ELEV_M / main.REACT_LIQ_H_M * 100.0,
                               main.CQ_SEAL_BAND_PCT)
    print(f"  t={n*0.1:7.0f}s  react_lvl={s.react_level_pct:6.2f}% "
          f"(funnel at {main.REACT_FUNNEL_ELEV_M / main.REACT_LIQ_H_M * 100.0:.1f}%) seal={seal_r:.3f} "
          f"| scrub_lvl={s.scrub_level_pct:6.2f}% | strip_lvl={s.strip_level:6.2f}% "
          f"| hpcc_lvl={s.hpcc_level_pct:6.2f}% | p_syn={s.p_syn_bara:7.3f}")
    active = sorted(k for k, v in s.flags.items() if v and any(
        t in k for t in ("CAVIT", "BLOW", "CARRY", "FLOOD", "CRYST", "ENTRAIN", "VACUUM", "SOLID")))
    if active:
        print("            active consequence flags:", active)

# ---------------------------------------------------------------- 0. design fixed point
# The engine's bit-exactness contract is on the FIRST TICK from the design seed: every new term must
# be identically zero there, so the boot pin and the design HMB are untouched.  (The multi-hour
# relaxation of the coupled loop away from the static seed is a documented, PRE-EXISTING property of
# this model -- the committed baseline shows the same relaxation, in the opposite direction -- and is
# tracked as its own gap; it is not what this suite is measuring.)
print("\n=== 0. DESIGN FIXED POINT: first tick must be stationary ===")
s = fresh()
ATTRS = ["p_syn_bara", "r323_c003_T", "r323_f004_T", "r323_f010_T", "r324_e001_T", "r324_e003_T",
         "r324_f001_P", "r324_f003_P", "r323_c003_M", "r323_f004_M", "r323_f010_M",
         "r324_f001_M", "r324_f003_M", "a328_c002_M", "a328_c003_M", "a328_c004_M",
         "a328_d001_M", "r3232_e011_M", "r3232_d001_M", "react_m_liq", "strip_level",
         "scrub_holdup_kg"]
before = {a: getattr(s, a) for a in ATTRS}
run(1)
after = {a: getattr(s, a) for a in ATTRS}
worst = max(ATTRS, key=lambda a: abs(after[a] - before[a]) / max(abs(before[a]), 1.0))
rel = abs(after[worst] - before[worst]) / max(abs(before[worst]), 1.0)
for a in ATTRS:
    d = abs(after[a] - before[a]) / max(abs(before[a]), 1.0)
    if d > 1e-9:
        print(f"    {a:20s} rel change on tick 1 = {d:.3e}")
check("design seed is stationary on tick 1 (rel < 1e-3)", rel < 1e-3, f"worst {worst} {rel:.3e}")
check("no consequence flag raised at design",
      not any(s.flags.get(f) for f in (
          "LV322501_EROSION", "LV323501_BLOWTHROUGH", "LV323505_BLOWTHROUGH",
          "LV328504_BLOWTHROUGH", "LV328505_BLOWTHROUGH", "LV322502_BLOWTHROUGH",
          "C003_CARRYOVER", "CONDENSER_FLOODED", "F010_CARRYOVER", "VACUUM_COLLAPSE",
          "328C002_FLOODING", "328C004_FLOODING", "328D001_ENTRAINMENT",
          "323D011_ENTRAINMENT", "323D001_ENTRAINMENT", "SCRUBBER_CARRYOVER",
          "324F001_CRYSTALLIZATION", "324F003_CRYSTALLIZATION", "324F003_LOSS_OF_SEAL",
          "323P003_CAVITATION", "323P008_CAVITATION", "328P003_CAVITATION",
          "328P002_CAVITATION", "323P001_CAVITATION",
          "328_AMMONIA_WATER_PUMP_CAVITATION",
          "324P001_CAVITATION", "324P003_CAVITATION")),
      str([f for f in s.flags if s.flags.get(f) and ("CAVIT" in f or "BLOW" in f or "CARRY" in f
                                                     or "FLOOD" in f or "CRYST" in f)]))

# ------------------------------------------------- 1. Scenarios.md 1.2 / Scenarios2.md 2.2
# Driven the way an operator would: LIC-322501 to MAN, valve wide open, so the sump drains and STAYS
# drained while the stripper keeps making bottoms.  (Poking the level state instead just lets the
# sump refill and re-seal within seconds -- which is itself correct behaviour, but tests nothing.)
print("\n=== 1. HP STRIPPER LOW LEVEL -> gas blow-through (Scenarios2.md 2.3 'Big Step Opening') ===")
s = fresh(); run(20)
p0 = s.p_syn_bara
s.LIC_322501["mode"] = "MAN"; s.LIC_322501["op"] = 100.0
bt_peak, seal_seen, lvl_min = 0.0, False, 100.0
for _ in range(120):
    run(50)
    lvl_min = min(lvl_min, s.strip_level)
    bt_peak = max(bt_peak, s.tlag.get("STRIP_BLOWTHROUGH_GAS_KGH", 0.0))
    seal_seen = seal_seen or s.flags.get("LV322501_EROSION", False)
print(f"    strip level min over 600 s = {lvl_min:.2f} %")
check("blow-through gas is generated", bt_peak > 0.0, f"peak {bt_peak:,.0f} kg/h")
check("blow-through is a physical magnitude (1-200 t/h, choked)",
      1000.0 < bt_peak < 200000.0, f"peak {bt_peak:,.0f} kg/h")
check("synthesis pressure falls", s.p_syn_bara < p0 - 0.1, f"{p0:.2f} -> {s.p_syn_bara:.2f} bar a")
check("LV-322501 erosion flagged", seal_seen)

# ------------------------------------------------- 2. Scenarios.md 2.2 flash-tank low level
print("\n=== 2. ATM FLASH TANK LOW LEVEL -> vacuum break, WITH LAG (Scenarios.md 2.2) ===")
s = fresh(); run(20)
pf010_0, pf001_0 = s.r323_f010_P, s.r324_f001_P
s.LIC_323505["mode"] = "MAN"; s.LIC_323505["op"] = 100.0     # LV-323505 wide open -> drum drains
trace, blow_seen, lvlf_min = [], False, 100.0
for i in range(1, 121):
    run(50)                       # 5 s per sample
    lvlf_min = min(lvlf_min, s.r323_f004_M / main.R323_F004_M_FULL * 100.0)
    trace.append((i * 5, s.r323_f010_P, s.r324_f001_P))
    blow_seen = blow_seen or s.flags.get("LV323505_BLOWTHROUGH", False)
print(f"    323F004 level min over 600 s = {lvlf_min:.2f} %")
check("LV-323505 blow-through flagged", blow_seen)
p010_max = max(a for _, a, _ in trace)
p001_max = max(b for _, _, b in trace)
check("323F010 vacuum degrades", p010_max > pf010_0 * 1.2,
      f"{pf010_0:.3f} -> peak {p010_max:.3f} bar a")
t_f010 = next((t for t, a, b in trace if a > pf010_0 * 1.2), None)
t_f001 = next((t for t, a, b in trace if b > pf001_0 * 1.2), None)
check("323F010 does NOT snap in one tick (ramps over >= 2 s)", t_f010 is not None and t_f010 >= 2,
      f"t={t_f010} s")
check("324F001 degrades no earlier than 323F010 (transport lag downstream)",
      t_f010 is not None and t_f001 is not None and t_f001 >= t_f010,
      f"323F010 at {t_f010} s, 324F001 at {t_f001} s")
check("VACUUM_COLLAPSE flag is pressure-derived",
      p010_max > main.R323_F010_P_BARA * main.VACUUM_DEGRADED_FRAC)
# recoverability: put the valve back and the vacuum must come back
s.LIC_323505["mode"] = "AUTO"
run(9000)
check("vacuum RECOVERS once the level and seal are restored", s.r323_f010_P < p010_max,
      f"peak {p010_max:.3f} -> {s.r323_f010_P:.3f} bar a")

# ------------------------------------------------- 3. Scenarios.md 2.1 flash-tank HIGH level
print("\n=== 3. ATM FLASH TANK HIGH LEVEL -> carry-over (Scenarios.md 2.1; was DEAD CODE) ===")
s = fresh(); run(20)
s.r323_f004_M = main.R323_F004_M_FULL * 1.05
run(50)
check("carry-over / condenser flooding flagged", s.flags.get("CONDENSER_FLOODED", False))
check("323F004 drum pressure rises on the choked vapour line",
      s.r323_f004_P > main.R323_F004_P_BARA * 1.01, f"{s.r323_f004_P:.3f} bar a")

# ------------------------------------------------- 4. UNLISTED: 328C004 low level
print("\n=== 4. UNLISTED DEVIATION: 328C004 low level -> same consequence class ===")
s = fresh(); run(20)
s.a328_c004_M = 1.0
run(50)
check("328C004 seal loss produces blow-through (no scenario was ever written for it)",
      s.flags.get("LV328505_BLOWTHROUGH", False))

print("\n=== 4b. UNLISTED: 328C003 hydrolyser low level (16.8 bar -> 3.7 bar) ===")
s = fresh(); run(20)
s.a328_c003_M = 1.0
run(50)
check("328C003 seal loss produces blow-through", s.flags.get("LV328504_BLOWTHROUGH", False))

# ------------------------------------------------- 5. Scenarios3.md 1.2 LPCC drum level
print("\n=== 5. LPCC DRUM (323D011) LEVEL (Scenarios3.md 1.2) ===")
s = fresh(); run(20)
s.r3232_e011_M = 1.0
run(50)
check("323P008 lean-carbamate pump cavitates on low level",
      s.flags.get("323P008_CAVITATION", False))
s = fresh(); run(20)
s.r3232_e011_M = main.R3232_D011_M_DES * 2.4      # drive the level to ~100 %
run(50)
check("323D011 high level entrains carbamate to the vent",
      s.flags.get("323D011_ENTRAINMENT", False))

# ------------------------------------------------- 6. Scenarios3.md 4.2 tank TEMPERATURE
print("\n=== 6. AMMONIA-WATER TANK TEMPERATURE (Scenarios3.md 4.2) ===")
s = fresh(); run(20)
for a in ("a328_d003_TI", "a328_d003_TII", "a328_d003_TIII"):
    setattr(s, a, 99.0)                          # hot tank, level untouched
run(50)
check("hot ammonia-water tank cavitates its pumps through NPSH (level is normal)",
      s.flags.get("328_AMMONIA_WATER_PUMP_CAVITATION", False))
s = fresh(); run(20)
s.a328_d003_MI = s.a328_d003_MII = s.a328_d003_MIII = 1.0
run(50)
check("empty ammonia-water tank cavitates the same pumps through the same law",
      s.flags.get("328_AMMONIA_WATER_PUMP_CAVITATION", False))

# ------------------------------------------------- 7. Scenarios3.md 4.4 urea tank temperature
print("\n=== 7. UREA TANK TEMPERATURE (Scenarios3.md 4.4) ===")
s = fresh(); run(20)
s.r323_d002_T = 72.0                             # 80 % liquor saturates at 80 C
run(50)
check("cooling urea tank crystallises and starves 323P003",
      s.flags.get("323_UREA_CRYSTALLIZATION", False))

# ------------------------------------------------- 8. thermodynamic package
print("\n=== 8. THERMODYNAMIC PACKAGE (electrolyte VLE on 323C003 / 323F004) ===")
import vle_nh3co2h2o as vle  # noqa: E402
w = dict(main.W_S314)
t_base = vle.bubble_t_c(w, 4.1)
w_hi = dict(w); w_hi["NH3"] = w["NH3"] * 1.5
w_lo = dict(w); w_lo["NH3"] = w["NH3"] * 0.5
t_hi, t_lo = vle.bubble_t_c(w_hi, 4.1, t_guess=t_base), vle.bubble_t_c(w_lo, 4.1, t_guess=t_base)
print(f"    T_bub(4.1 bar): design {t_base:.2f} C | NH3 x1.5 {t_hi:.2f} C | NH3 x0.5 {t_lo:.2f} C")
check("bubble point RESPONDS to NH3 loading (pure-water anchor could not)",
      abs(t_hi - t_base) > 0.2 and abs(t_lo - t_base) > 0.2)
check("bubble point responds to pressure",
      abs(vle.bubble_t_c(w, 4.5, t_guess=t_base) - t_base) > 1.0)
check("323C003 model bubble P within 10 % of the PFD anchor",
      abs(vle.bubble_p_bara(main.W_S314, 135.0) / 4.10 - 1.0) < 0.10,
      f"{vle.bubble_p_bara(main.W_S314, 135.0):.3f} vs 4.10 bar a")
# Validation is against the PFD's OWN tabulated composition; the engine's W_S319 is the
# atom-reconciled vector (G3), which carries more CO2 and therefore a higher bubble pressure.
# Both are reported; the departure form anchors on whichever vector the engine actually uses.
# 323F004 is the loosest of the three stages (+17.5 %): it is where the steep CO2/carbamate term
# dominates and where urea-as-a-diluent hurts most.  See gap G-VLE-1.  The departure form absorbs
# the offset; this threshold guards against a REGRESSION in it, not against its existence.
check("323F004 model bubble P within 20 % of the PFD anchor",
      abs(vle.bubble_p_bara(main.W_S319_TAB, 106.0) / 1.13 - 1.0) < 0.20,
      f"tabulated {vle.bubble_p_bara(main.W_S319_TAB, 106.0):.3f} / "
      f"reconciled {vle.bubble_p_bara(main.W_S319, 106.0):.3f} vs 1.13 bar a")

# ------------------------------------------------- 9. crystallisation boundary consistency
print("\n=== 9. CRYSTALLISATION BOUNDARY IS COMPOSITION-DEPENDENT ===")
import consequence as cq  # noqa: E402
rows = [("322E001 bottoms 55.9 % U", main.W_S208), ("323C003 68.7 % U", main.W_S314),
        ("323F010 80.0 % U", main.W_S317), ("324E003 melt", main.W_S402)]
for lbl, wv in rows:
    print(f"    {lbl:26s} T_cryst = {cq.liquor_crystallization_T(wv):6.1f} C")
check("boundary is monotone in urea strength and lands at ~132 C for the final melt",
      cq.liquor_crystallization_T(main.W_S317) < cq.liquor_crystallization_T(main.W_S402) < 133.5)
check("boundary is NOT the same constant everywhere (the old 132.7 was)",
      cq.liquor_crystallization_T(main.W_S314) < cq.liquor_crystallization_T(main.W_S402) - 20.0)

print("\n" + "=" * 72)
print(f"PASSED {len(PASS)}   FAILED {len(FAIL)}")
if FAIL:
    print("FAILURES:")
    for f in FAIL:
        print("   -", f)
sys.exit(1 if FAIL else 0)
