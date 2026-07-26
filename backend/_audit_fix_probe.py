"""Design-point + off-design probe for the 328 / 323-324 audit fixes.

Run before and after each edit and diff the two JSON files:

    python _audit_fix_probe.py before.json
    python _audit_fix_probe.py after.json

`design` must stay bit-exact (CLAUDE.md: off-design states resolve bit-exact with the 100 %
steady-state HMB).  The `probe_*` blocks are the behaviours the audit found frozen; they are
EXPECTED to change once a defect is fixed.
"""
import json
import sys

import main as M


def _seed():
    M.state = M.State()
    M.last_packet = {}
    return M.state


def _settle(n, dt=0.1):
    for _ in range(n):
        M.step_sim(dt)
    return M.step_sim(dt)


_BLOCKS = ("RECIRC_323", "LPCC_3232", "DESORB_328", "ABSORB_328", "EVAP_324", "SPECIES_323_324")


def _flat(prefix, node, out):
    if isinstance(node, dict):
        for k, v in node.items():
            _flat(prefix + "." + str(k), v, out)
    elif isinstance(node, (int, float)) and not isinstance(node, bool):
        out[prefix] = node


def _pick(p):
    """Every scalar the audited units publish, flattened to dotted keys."""
    out = {}
    for blk in _BLOCKS:
        if blk in p:
            _flat(blk, p[blk], out)
    return out


def design():
    _seed()
    return _pick(_settle(100))


def probe_c004_steam_cut():
    """C1: cut LP steam to 328C004 by 30 %.  A real column must cool."""
    s = _seed()
    _settle(50)
    T0 = s.a328_c004_T
    s.FIC_329401["mode"] = "MAN"
    s.FIC_329401["op"] = 35.0
    _settle(6000)
    return {"T_before": T0, "T_after": s.a328_c004_T, "dT": s.a328_c004_T - T0}


def probe_c002_recycle_cut():
    """C1: cut the 328C003 overhead relief.  328C002 must cool."""
    s = _seed()
    _settle(50)
    T0 = s.a328_c002_T
    s.PIC_328203["mode"] = "MAN"
    s.PIC_328203["op"] = 20.0
    _settle(6000)
    return {"T_before": T0, "T_after": s.a328_c002_T, "dT": s.a328_c002_T - T0}


def probe_f001_level():
    """C3: 324F001 holdup must respond to a feed step."""
    s = _seed()
    _settle(50)
    M0 = s.r324_f001_M
    s.FIC_324401["mode"] = "MAN"
    s.FIC_324401["op"] = min(100.0, s.FIC_324401["op"] * 1.25)
    _settle(3000)
    return {"M_before": M0, "M_after": s.r324_f001_M, "dM": s.r324_f001_M - M0}


def probe_vacuum_selfreg():
    """C5: shut the 324F002 motive steam.  Pressure must rise but SETTLE, not ramp to the clamp."""
    s = _seed()
    _settle(50)
    P0 = s.r324_f001_P
    s.PIC_324202["mode"] = "MAN"          # remove the false-air trim: test the NODE, not the loop
    s.HIC_329605 = 25.0                   # partial motive cut (not a full shutdown)
    _settle(3000)
    P1 = s.r324_f001_P
    _settle(9000)
    return {"P_before": P0, "P_at_300s": P1, "P_at_1200s": s.r324_f001_P,
            "settled": abs(s.r324_f001_P - P1) < 1e-4,
            "clamped": abs(s.r324_f001_P - 1.0) < 1e-9}


def probe_d003_from_324():
    """C2: a 324 evaporation change must reach the 328D003 Comp-I inflow."""
    s = _seed()
    _settle(50)
    MI0, TI0 = s.a328_d003_MI, s.a328_d003_TI
    s.TIC_324001["mode"] = "MAN"
    s.TIC_324001["op"] = s.TIC_324001["op"] * 0.70
    _settle(6000)
    return {"MI_before": MI0, "MI_after": s.a328_d003_MI, "dMI": s.a328_d003_MI - MI0,
            "TI_before": TI0, "TI_after": s.a328_d003_TI, "dTI": s.a328_d003_TI - TI0}


def probe_e007_live():
    """C10: a 328C004 cooldown must drop the 328C002 feed temperature (stream 738)."""
    s = _seed()
    _settle(50)
    s.FIC_329401["mode"] = "MAN"
    s.FIC_329401["op"] = 20.0
    p = _settle(6000)
    d = p["DESORB_328"]
    return {"T_c004": round(s.a328_c004_T, 4),
            "TT_328010": d["C002"].get("TT_328010"),
            "TT_328008": d["C002"].get("TT_328008"),
            "TT_328006": d["C004"].get("TT_328006")}


def main():
    out = {
        "design": design(),
        "probe_c004_steam_cut": probe_c004_steam_cut(),
        "probe_c002_recycle_cut": probe_c002_recycle_cut(),
        "probe_f001_level": probe_f001_level(),
        "probe_vacuum_selfreg": probe_vacuum_selfreg(),
        "probe_d003_from_324": probe_d003_from_324(),
        "probe_e007_live": probe_e007_live(),
    }
    path = sys.argv[1] if len(sys.argv) > 1 else "probe_out.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, sort_keys=True)
    for k, v in out.items():
        if k != "design":
            print(k, json.dumps(v, sort_keys=True))


if __name__ == "__main__":
    main()
