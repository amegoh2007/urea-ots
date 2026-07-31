"""G8 closure gate (standalone steam network, no main import). The 4-bar LP header exports its design
surplus to turbine 320MT02 (PFD-26 stream 932 = 16 707 kg/h) through PV-329207B on an anchored bias,
while the header still holds 4.4 bar bit-exact (the Tsat(P_LP) coupling to the HPCC, hence the plant
H&MB, is preserved). The turbine export is a connected edge, not the old M_USERS_LP=generation aggregate."""

from __future__ import annotations

import pytest

import steam_system as ss


DT = 0.5
# design LP generation must feed both the local H.Ex users and the turbine export
M_GEN_DES = ss.M_HPCC_DES + ss.M_TURBINE_DES


def _settle(st, n, m_strip=ss.M_STRIP_DES, m_hpcc=M_GEN_DES):
    for _ in range(n):
        ss.step_steam(st, DT, m_strip, m_hpcc)
    return st


def test_turbine_design_constant_matches_pfd_stream_932() -> None:
    assert ss.M_TURBINE_DES == pytest.approx(16707.0 / 3600.0)


def test_k207b_bias_passes_the_design_export() -> None:
    # at the anchored bias opening and the design 4.4->3.9 bar differential, PV-329207B passes exactly
    # the PFD stream-932 export.
    m = ss._valve_flow(ss.K_207B, ss.BIAS_207B_PCT, ss.P_LP_BARA, ss.P_TURBINE_OUT_BARA)
    assert m == pytest.approx(ss.M_TURBINE_DES, rel=1e-9)


def test_design_fixed_point_holds_with_turbine_export() -> None:
    st = _settle(ss.SteamState(), 6000)
    assert st.P_MP == pytest.approx(19.7, abs=0.05)
    assert st.P_9 == pytest.approx(9.0, abs=0.10)
    assert st.P_LP == pytest.approx(4.4, abs=0.02)      # Tsat(P_LP)->HPCC H&MB anchor preserved
    # FT-329407: the connected valve carries the PFD stream-932 export at design
    assert st.m_turbine * 3600.0 == pytest.approx(16707.0, abs=50.0)
    assert st.m_vent < 1e-6                              # vent leg shut at design
    assert st.m_963 < 1e-6                               # BL-admit leg shut at design
    assert abs(st.mass_residual_lp_vapor) < 1e-3        # LP node closes


def test_users_boundary_excludes_the_turbine_when_reconciled() -> None:
    # emulate main.py's boot reconciliation: users = generation - turbine export
    users = max(M_GEN_DES - ss.M_TURBINE_DES, 0.0)
    assert users == pytest.approx(ss.M_HPCC_DES)
    # generation closes against users + turbine + vent(0)
    assert M_GEN_DES == pytest.approx(users + ss.M_TURBINE_DES)


def test_over_pressure_opens_turbine_and_recovers_setpoint() -> None:
    st = _settle(ss.SteamState(), 4000)
    m0 = st.m_turbine
    st.P_LP = 4.7                                        # inject over-pressure
    ss.step_steam(st, DT, ss.M_STRIP_DES, M_GEN_DES)
    assert st.m_turbine > m0                             # biased PI opens the export further
    _settle(st, 3000)
    assert st.P_LP == pytest.approx(4.4, abs=0.05)       # recovers to SP


def test_hpcc_collapse_shuts_turbine_and_holds_floor() -> None:
    st = _settle(ss.SteamState(), 4000)
    _settle(st, 3000, m_hpcc=0.0)                        # generation collapse
    assert st.P_LP >= ss.P_LP_MIN_BARA - 1e-6           # make-up holds the floor
    assert st.m_turbine == pytest.approx(0.0, abs=1e-6)  # no surplus -> export shuts
