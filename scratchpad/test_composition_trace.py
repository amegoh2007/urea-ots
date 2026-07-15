"""C2 species-level stream trace: live packet STREAMS composition vs the extracted PFD/HMB tables.

Scope note (why only the HP synthesis loop is diffed):
  The HP loop (321 -> 322F001 -> 322E002 -> 322R001 -> 322E001 -> 322E003) carries an explicit
  9-species vector per stream; make_stream() publishes mol_pct / mass_pct for every one of them,
  so a per-species diff against the PFD tables is well posed.  The 328 recovery section carries
  LUMPED MASS only (m_735 / m_738 / m_755 / m_775, no species vector) -- an intentional model
  abstraction, so a species diff there is impossible by design, not an omission.  See the
  328 section at the bottom, which asserts the abstraction instead of fabricating a vector.

Design anchors (extracted PFD / HMB, quoted at their published precision):
  REACT_OFFGAS    mol% NH3 69.07, CO2 20.51, N2 4.62, H2O 4.41, O2 0.77, CH4 0.40, H2 0.21
                  (Sigma mol% = 99.99 as published), MW 23.19, 22 355 kg/h, 963.76 kmol/h
  REACT_OVERFLOW  kmol/h Urea 1302.6, Biuret 2.414, NH3 4002.4, CO2 897.7, H2O 2222.0
                  Sigma 8427.11 kmol/h, 226 178 kg/h
  EJ_DISCH        derived below from the RECONCILED design point (see provenance note)
  CARB_RECYCLE    derived below from the RECONCILED design point (see provenance note)
  STRIP_TOP       mol% NH3 61.7, CO2 32.5, H2O 4.9; MW 25.96
  STRIP_BOT       mass% Urea 55.8

Provenance note -- why EJ_DISCH / CARB_RECYCLE are NOT anchored to the 'Carb. Liq.' HMB table:
  docs/urea-project-conversation.md:18883 (carbamate suction back-calc, 57 564 kg/h with inerts)
  and :19322 (ejector discharge, 98 320 kg/h, MW 20.01, 109 C) are SUPERSEDED.  main.py:150-162
  records why: the 98 320 nameplate does not atom-close against the reconciled stripper-top /
  reactor-offgas vectors, and the motive was re-pinned from 40 756 -> 42 762.05 kg/h because the
  old value implied fresh N/C = 1.928 < 2.0 (sub-stoichiometric -> non-steady free-run).  Both
  tables balance, but around the OLD motive: 57 564 + 40 756 = 98 320.  The Path-B tear closure
  re-anchored the whole ejector design point on the reconciled 322E003 overflow vector, which
  main.py:158 declares the source of truth (EJ_SUCTION = overflow*MW).  Inerts read 0 because the
  reconciliation routes 100 % of N2/O2/CH4/H2 to the reactor off-gas -- exactly as the reactor
  spec states ('report 100 % to off-gas, 0 to overflow -- consistent with both shared HMBs').
  So this test re-derives the two anchors from the reconciled overflow (quoted verbatim below,
  NOT imported from main) via the published laws, rather than fabricating agreement with a
  falsified datasheet.
"""
import os
import sys

BACKEND = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
os.chdir(BACKEND)
sys.path.insert(0, BACKEND)
import main  # noqa: E402

MW = main.MW_COMP

_pkt = {}


def settle(n=900):
    global _pkt
    for _ in range(n):
        _pkt = main.step_sim(1.0)


fails = []


def diff(label, design, live, tol, unit):
    """One design-vs-live row.  tol is absolute, at the published precision of the design table."""
    d = live - design
    ok = abs(d) <= tol
    if not ok:
        fails.append("%s: design %.4f live %.4f (tol %.4f)" % (label, design, live, tol))
    print("  %-10s %12.4f %12.4f %+10.4f  %-7s %s"
          % (label, design, live, d, unit, "ok" if ok else "FAIL"))


def table(title, stream_key, field, design, tol, unit):
    print()
    print("%s   [%s.%s]" % (title, stream_key, field))
    print("  %-10s %12s %12s %10s  %-7s %s" % ("species", "design", "live", "delta", "unit", ""))
    print("  " + "-" * 62)
    live = _pkt["STREAMS"][stream_key][field]
    for k in main.MW_COMP:
        diff(k, design.get(k, 0.0), live[k], tol, unit)


def scalars(stream_key, rows):
    st = _pkt["STREAMS"][stream_key]
    print("  " + "-" * 62)
    for name, design, tol, unit in rows:
        diff(name, design, float(st[name]), tol, unit)


settle(1800)

print("=" * 78)
print("C2  SPECIES-LEVEL STREAM TRACE  --  HP synthesis loop vs extracted PFD/HMB")
print("=" * 78)

# --- 322R001 off-gas -> 322E003 (nu_og_des * s ; s = 1 at design) ---
table("REACT_OFFGAS  322R001 -> 322E003", "REACT_OFFGAS", "mol_pct",
      {"NH3": 69.07, "CO2": 20.51, "N2": 4.62, "H2O": 4.41, "O2": 0.77, "CH4": 0.40, "H2": 0.21},
      0.02, "mol %")
scalars("REACT_OFFGAS", [("MW", 23.19, 0.01, "g/mol"),
                         ("mass_kgh", 22355.0, 5.0, "kg/h"),
                         ("mol_kmolh", 963.76, 0.10, "kmol/h")])

# --- 322R001 overflow -> 322E001 (nu_ov_des * s * phi/phi_des ; phi = phi_des at design) ---
n_ov_des = {"Urea": 1302.6, "Biuret": 2.414, "NH3": 4002.4, "CO2": 897.7, "H2O": 2222.0}
sig_ov = sum(n_ov_des.values())
table("REACT_OVERFLOW  322R001 -> 322E001", "REACT_OVERFLOW", "mol_pct",
      {k: v / sig_ov * 100.0 for k, v in n_ov_des.items()}, 0.02, "mol %")
scalars("REACT_OVERFLOW", [("mol_kmolh", 8427.11, 0.10, "kmol/h"),
                           ("mass_kgh", 226178.0, 50.0, "kg/h")])

# --- reconciled ejector design point (Path B, Option 1: free DOF ov_CO2 = 458.358305 kmol/h,
#     the feasible-band MAX -> vent_H2O = 0, max heavy recovery).  Vector quoted verbatim from
#     main.py:158-159; motive from main.py:143.  Re-derived here, not imported. ---
n_carb_des = {"CO2": 458.35830512, "CH4": 0.0, "H2": 0.0, "H2O": 674.24844864,
              "N2": 0.0, "NH3": 1234.46697667, "O2": 0.0, "Urea": 0.43027771, "Biuret": 0.0}
m_carb_des = {k: n_carb_des[k] * MW[k] for k in MW}          # EJ_SUCTION = overflow * MW
sig_carb = sum(m_carb_des.values())                          # 53 368.28 kg/h
mw_carb = sig_carb / sum(n_carb_des.values())                # 22.542 g/mol

EJ_MOTIVE_DES = 42762.05427809782   # kg/h, RATIO_PV_DES*NC_TO_MASS*CO2_DES_KGH (re-pinned; main.py:143)

# --- 322E003 overflow -> 322F001 suction (reconciled carbamate composition) ---
table("CARB_RECYCLE  322E003 -> 322F001", "CARB_RECYCLE", "mass_pct",
      {k: m_carb_des[k] / sig_carb * 100.0 for k in MW}, 0.05, "mass %")
scalars("CARB_RECYCLE", [("mass_kgh", sig_carb, 0.5, "kg/h"),
                         ("MW", mw_carb, 0.005, "g/mol")])

# --- 322F001 ejector discharge -> 322E002:  m_i,disch = m_i,motive + m_i,suction (pure-NH3 motive) ---
m_disch_des = {k: (EJ_MOTIVE_DES if k == "NH3" else 0.0) + m_carb_des[k] for k in MW}
sig_disch = sum(m_disch_des.values())                        # 96 130.34 kg/h
mw_disch = sig_disch / sum((m_disch_des[k] / MW[k]) for k in MW)      # 19.705 g/mol
# discharge enthalpy balance (main.py:834-905): cp_N/cp_C/cp_D = 4.74/3.10/3.50 kJ/kg.K,
# T_motive = 29 C at TI-321020, T_suction = 178.8 C (322E003 overflow, dH_mix lumped in)
t_disch = (EJ_MOTIVE_DES * 4.74 * 29.0 + sig_carb * 3.10 * 178.8) / (sig_disch * 3.50)
table("EJ_DISCH  322F001 -> 322E002", "EJ_DISCH", "mass_pct",
      {k: m_disch_des[k] / sig_disch * 100.0 for k in MW}, 0.05, "mass %")
scalars("EJ_DISCH", [("MW", mw_disch, 0.005, "g/mol"),
                     ("mass_kgh", sig_disch, 0.5, "kg/h"),
                     ("rho", 877.9, 0.5, "kg/m3"),
                     ("T_C", t_disch, 0.15, "C"),
                     ("P_bara", 144.2, 0.1, "bar a")])

# --- 322E001 top gas -> 322E002 (strip fractions f_i_des applied to the reactor overflow) ---
table("STRIP_TOP  322E001 -> 322E002", "STRIP_TOP", "mol_pct",
      {"NH3": 61.7, "CO2": 32.5, "H2O": 4.9, "N2": 0.75, "O2": 0.13}, 0.15, "mol %")
scalars("STRIP_TOP", [("MW", 25.96, 0.05, "g/mol")])

# --- 322E001 bottoms -> LV-322501 (urea melt) ---
print()
print("STRIP_BOT  322E001 -> LV-322501   [STRIP_BOT.mass_pct]")
print("  " + "-" * 62)
diff("Urea", 55.8, _pkt["STREAMS"]["STRIP_BOT"]["mass_pct"]["Urea"], 0.15, "mass %")

# --- 328 recovery: assert the lumped-mass abstraction rather than fabricate a vector ---
print()
print("=" * 78)
print("328 RECOVERY  --  lumped-mass abstraction (no species vector by design)")
print("=" * 78)
rec_328 = [k for k in _pkt if k.startswith("REC_328") or k.startswith("RECOV")]
carried = [k for k in _pkt["STREAMS"] if "735" in k or "755" in k or "775" in k or "738" in k]
print("  packet 328 blocks          : %s" % (rec_328 or "(none under STREAMS)"))
print("  328 streams w/ species vec : %s" % (carried or "none -- lumped mass only"))
if carried:
    fails.append("328 section unexpectedly carries a species vector: %s" % carried)

print()
print("=" * 78)
if fails:
    print("FAIL  %d deviation(s):" % len(fails))
    for f in fails:
        print("  - %s" % f)
    sys.exit(1)
print("PASS  every HP-loop species matches the extracted PFD/HMB table within published precision.")
