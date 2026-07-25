"""Regression gate for the three Mapping vacuum sign-rules (References/Mapping of Evaporation Section.md).

    A) HV-323605 opening up  -> 323F010 pressure down  (and vice versa).
    B) HV-329605 opening up  -> 323F010, 324F001, 324E002-shell pressure down.
    C) HV-329606 opening up  -> 324F003, 324E005-shell pressure down.

324E002 shell is the 324F001 manifold node (r324_f001_P) and 324E005 shell is the 324F003 node
(r324_f003_P), so those are covered by the F001/F003 pressures.  323F010 has no controller, so its
response is sustained directly; the 324 separators are held to SP by PIC-324202/324203, so their loops
are put in MAN to expose the direct ejector effect (in AUTO the rule shows as a transient the PIC trims).

Run from backend/:  python -m pytest test_vacuum_valve_rules.py -q -p no:cacheprovider
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main  # noqa: E402

DT = 0.25


def _fresh(seconds=300.0):
    main.state = main.State()
    _run(seconds)
    return main.state


def _run(seconds):
    for _ in range(int(seconds / DT)):
        main.step_sim(DT)


def test_design_vacuum_pressures_are_bit_exact_at_the_seed():
    """The new live 323F010 pressure and the re-tied 324F003 ejector pull must be literal identities
    at the design seed, or the anchor has moved.  m_evap == pull == R323_MEVAP_DES -> dP/dt == 0."""
    s = main.State()
    assert s.r323_f010_P == main.R323_F010_P_BARA
    assert s.HIC_323605 == main.R323_HIC605_DES_PCT
    assert s.HIC_329606 == main.R324_HIC9606_DES_PCT
    # ejpull ratio is exactly 1.0 at the design opening
    assert s.HIC_329606 / main.R324_HIC9606_DES_PCT == 1.0


def test_rule_A_hv323605_moves_323f010_pressure():
    s = _fresh(300.0)
    base = s.r323_f010_P
    s.HIC_323605 = 80.0                       # open the gas outlet wider
    _run(300.0)
    opened = s.r323_f010_P
    s.HIC_323605 = 25.0                       # throttle it
    _run(300.0)
    closed = s.r323_f010_P
    assert opened < base - 1e-3, (base, opened)      # A: open -> pressure falls
    assert closed > opened + 1e-3, (opened, closed)  # and vice versa


def test_rule_B_hv329605_drops_324f001_and_323f010():
    s = _fresh(300.0)
    s.PIC_324202["mode"] = "MAN"              # expose the direct ejector effect
    p001, p010 = s.r324_f001_P, s.r323_f010_P
    s.HIC_329605 = 85.0
    _run(400.0)
    assert s.r324_f001_P < p001 - 1e-3, (p001, s.r324_f001_P)   # 324F001 (== 324E002 shell)
    assert s.r323_f010_P < p010 - 1e-3, (p010, s.r323_f010_P)   # 323F010 on the same 324F002 manifold


def test_rule_C_hv329606_drops_324f003():
    s = _fresh(300.0)
    s.PIC_324203["mode"] = "MAN"
    p003 = s.r324_f003_P
    s.HIC_329606 = 85.0
    _run(400.0)
    assert s.r324_f003_P < p003 - 1e-3, (p003, s.r324_f003_P)   # 324F003 (== 324E005 shell)
