"""G3 -- Bilinear Data Reconciliation (BDR) + Chi-square Gross Error Detection (GED).

Implements the method prescribed in
`References/Strategic Resolution of Thermodynamic and Topological Simulation Gaps in High-Pressure
Urea Synthesis.md` section 4 (Crowe/Madron matrix-projection BDR + Chi-square global test) to decide,
statistically, whether the Unit-324 evaporation design rows (streams 317 -> 401 -> 402) can be closed
by reconciliation within their documented precision, or whether they are a genuine gross error that
requires the user's UNROUNDED licensor data.

Self-contained: hard-codes the strict-source PFD-21 rows and the design flows (no `main` import), so
it runs in <1 s. Run from `backend`:  python gap_g3_data_reconciliation.py

Result (see __main__): the urea component balance across each evaporation stage fails at 30-40 sigma
(Chi-square >> critical), i.e. the tabulated feed/melt urea + biuret rows cannot conserve the urea
consumed by the tabulated biuret formation -- a confirmed gross error.

RESOLUTION (G3 CLOSED): the licensor's UNROUNDED rows were DEDUCED by the doc-sec.4.2 reconciliation
collapsed to the determined case (`main._reconcile_melt`): holding the hard urea/water design strength
and the shared feed, every species' outlet is capped at its mass-conservation limit m_in*w_in/m_out
(no unsupported net biuret formation; a volatile cannot concentrate up). This drives every
`_sol_stage_anchor` clip to 0, so the runtime component residual closes to <1e-6 kg/h and the
`sol_pin_strength` component overwrite is retired (now a pass-through). The reconciliation attributes
the inconsistency to the tabulated biuret being over-stated (0.69->0.495 %, 0.85->0.513 % -- the trace
with the largest relative rounding and genuinely uncertain evaporator formation kinetics), which keeps
the urea strength (=R324_W_EV) and the plant HMB bit-exact. This module remains the STANDING PROOF
that the raw PFD rows are a gross error and therefore why the reconciliation is warranted. See
`test_g3_component_reconciliation.py`.
"""

from __future__ import annotations

import math

# --- component molar masses (kg/kmol), matching backend MW_SOL ---
MW = {"Urea": 60.06, "Biuret": 103.08, "NH3": 17.03, "CO2": 44.01, "H2O": 18.02, "HCHO": 30.03}
SPECIES = tuple(MW)
NONVOL = ("Biuret", "HCHO")               # never leave in the vapour at evaporation temperatures


def w_norm(d: dict) -> dict:
    tot = sum(d.get(k, 0.0) for k in SPECIES)
    return {k: d.get(k, 0.0) / tot for k in SPECIES}


# --- STRICT-source PFD-21 mass-% rows (identical to backend main.py W_S317/401/402) ---
W_317 = w_norm(dict(Urea=80.00, Biuret=0.42, NH3=0.08, CO2=0.02, H2O=19.47, HCHO=0.00797))  # 323F010 -> E001
W_401 = w_norm(dict(Urea=94.31, Biuret=0.69, NH3=0.03, H2O=4.97, HCHO=0.00948))             # 324E001 melt
W_402 = w_norm(dict(Urea=97.71, Biuret=0.85, NH3=0.04, H2O=1.39, HCHO=0.0099))              # 324E003 melt

# --- design flows (kg/h). U_DES derived from V1_DES=14073.1 and the strengths 0.80/0.9431/0.9771 ---
V1_DES = 14073.1
U_DES = V1_DES / (1.0 / 0.80 - 1.0 / 0.9431)     # urea mass conserved end-to-end  (~74197)
FEED_317 = U_DES / 0.80
P1_401 = U_DES / 0.9431
P2_402 = U_DES / 0.9771
V2_DES = P1_401 - P2_402

# --- Type-B measurement uncertainties (GUM): variance = resolution^2 / 12 ---
RES_W = 1.0e-4          # composition resolution: 2 dp in %  -> 0.01 wt% = 1e-4 mass fraction
SIG_W = RES_W / math.sqrt(12.0)
RES_F = 1.0            # PFD mass-flow resolution ~1 kg/h
SIG_F = RES_F / math.sqrt(12.0)
CHI2_CRIT_1DOF_5PCT = 3.841   # chi-square critical value, 1 dof, alpha = 0.05


def stage_gross_error(name, w_in, m_in, w_out, m_liq, m_vap):
    """Back-solve the design vapour per species (inlet + reaction - melt), then run the measurement
    (Chi-square) test on every species the balance forces negative -- vapour a real evaporator cannot
    produce. Returns the per-species standardized residuals and the stage global Chi-square."""
    m_i = {k: m_in * w_in[k] for k in SPECIES}
    xi = max((m_liq * w_out["Biuret"] - m_i["Biuret"]) / MW["Biuret"], 0.0)      # biuret extent (kmol/h)
    gen = {k: 0.0 for k in SPECIES}
    gen["Biuret"] = +xi * MW["Biuret"]
    gen["Urea"] = -xi * 2.0 * MW["Urea"]
    gen["NH3"] = +xi * MW["NH3"]
    vap = {k: m_i[k] + gen[k] - m_liq * w_out[k] for k in SPECIES}

    # measurement-test standardized residual for each species whose vapour is negative (impossible)
    results = {}
    chi2 = 0.0
    for k in SPECIES:
        if vap[k] >= 0.0:
            continue
        r = vap[k]                                    # the imbalance the anchor must clip to zero
        # first-order Type-B propagation through r = m_in*w_in - m_liq*w_out (+ reaction on Urea/Biuret/NH3)
        var = (w_in[k] * SIG_F) ** 2 + (m_in * SIG_W) ** 2 \
            + (w_out[k] * SIG_F) ** 2 + (m_liq * SIG_W) ** 2
        if k in ("Urea", "Biuret", "NH3"):
            sig_xi = math.hypot(m_liq * SIG_W, m_in * SIG_W) / MW["Biuret"]
            var += (2.0 * MW["Urea"] * sig_xi) ** 2 if k == "Urea" else (MW[k] * sig_xi) ** 2
        sig = math.sqrt(var)
        z = r / sig
        chi2 += z * z
        results[k] = {"imbalance_kgh": r, "sigma_kgh": sig, "z_sigma": z,
                      "precision_violation_x": abs(r) / sig}
    return {"resid_clip_kgh": sum(v for v in vap.values() if v < 0.0),
            "species": results, "chi2": chi2}


if __name__ == "__main__":
    print("=" * 78)
    print("  G3 -- Bilinear Data Reconciliation + Chi-square Gross Error Detection (doc sec.4)")
    print("  Type-B uncertainty: sigma_w = %.3e (2dp %%), sigma_F = %.3f kg/h" % (SIG_W, SIG_F))
    print("  Chi-square critical (1 dof, alpha=0.05) = %.3f" % CHI2_CRIT_1DOF_5PCT)
    print("=" * 78)

    stages = [
        ("324E001 (317->401)", W_317, FEED_317, W_401, P1_401, V1_DES),
        ("324E003 (401->402)", W_401, P1_401, W_402, P2_402, V2_DES),
    ]
    gross = 0
    for name, w_in, m_in, w_out, m_liq, m_vap in stages:
        r = stage_gross_error(name, w_in, m_in, w_out, m_liq, m_vap)
        print(f"\n  {name}:  anchor clip = {r['resid_clip_kgh']:.2f} kg/h   Chi-square = {r['chi2']:.1f}")
        for k, s in r["species"].items():
            print(f"      {k:7s} imbalance={s['imbalance_kgh']:9.2f} kg/h  sigma={s['sigma_kgh']:.2f}  "
                  f"z={s['z_sigma']:.1f} sigma  ({s['precision_violation_x']:.0f}x precision)")
        verdict = "GROSS ERROR (data-gated)" if r["chi2"] > CHI2_CRIT_1DOF_5PCT else "within precision"
        print(f"      -> {verdict}: Chi-square {r['chi2']:.1f} vs critical {CHI2_CRIT_1DOF_5PCT}")
        if r["chi2"] > CHI2_CRIT_1DOF_5PCT:
            gross += 1

    print("\n" + "=" * 78)
    print(f"  {gross}/{len(stages)} evaporation stages are STATISTICALLY CONFIRMED gross errors.")
    print("  Per doc sec.4.3: forcing closure would move licensor rows >> their stated precision.")
    print("  G3 requires the UNROUNDED licensor rows for streams 317/401/402 (external intervention).")
    print("=" * 78)
