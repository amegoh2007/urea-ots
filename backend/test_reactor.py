"""322R001 reactor self-test (spec docs/superpowers/specs/2026-06-03-322r001-reactor-design.md).
Plain asserts (repo has no pytest). Run:  python backend/test_reactor.py"""
import os, sys, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main
from main import MW_COMP


def test_constants_present():
    for name in ("REACT_OVERFLOW_DES", "REACT_OFFGAS_DES", "REACT_XI_UREA_DES",
                 "REACT_XI_BIU_DES", "REACT_HIC605_DES_PCT", "REACT_OVERFLOW_T_C",
                 "REACT_OFFGAS_T_C", "REACT_P_BARA", "REACT_OFFGAS_P_BARA",
                 "REACT_OFFGAS_RHO", "REACT_OVERFLOW_RHO", "REACT_TEMP_HEIGHTS_C",
                 "REACT_LEVEL_NLL_PCT"):
        assert hasattr(main, name), "missing constant %s" % name
    # overflow design vector IS stream 207 (reactor overflow = stripper feed)
    for k in MW_COMP:
        assert abs(main.REACT_OVERFLOW_DES.get(k, 0.0)
                   - main.STRIP_FEED207_KMOLH.get(k, 0.0)) < 1e-6, k
    assert abs(main.REACT_HIC605_DES_PCT - 60.0) < 1e-9
    # State defaults
    assert abs(main.state.HIC_322605 - 60.0) < 1e-9
    assert isinstance(main.state.react_overflow_kmolh, dict)
    assert abs(sum(main.state.react_overflow_kmolh.values())
               - sum(main.STRIP_FEED207_KMOLH.values())) < 1e-6
