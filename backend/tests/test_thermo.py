from backend.core.thermo import EmpiricalThermo

def test_thermo_bubble_p():
    thermo = EmpiricalThermo()
    # Stubbed values for N/C, H/C
    p = thermo.bubble_p(170.0, 3.1, 0.5)
    assert p > 0.0
