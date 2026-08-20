"""Audit C10, aqueous half -- water properties from IAPWS, and the §0 justification for using them.

Departing from the PFD's tabulated density needs a stronger reason than "it looks wrong", because
CLAUDE.md §0 makes that table the strict source. The reason is specific rather than general, and
these tests encode it so it cannot be quietly forgotten:

  * the PFD's density row is RIGHT almost everywhere -- utility condensates 142-212 C to a mean
    0.04 %, and the desorption sheet's own pure-water streams to 0.02 %;
  * exactly two streams are wrong, 746 (190 C) and 747 (200 C), both from the "Amm. Water"
    mixture-model family, at +3.70 % and +3.82 %;
  * those two are IMPOSSIBLE, not merely improbable -- they exceed the density of the same water
    carrying solutes as dense as solid urea;
  * the cause is a constant thermal-expansion coefficient (beta ~ 5.5e-4 /K) frozen near the
    section's 56-60 C reference, against water's true 1.27e-3 /K at 190 C.

Reference data: IAPWS-IF97 (R7-97) Region 1 + Region 4 saturated liquid.
Correlation: Wagner & Pruss, J. Phys. Chem. Ref. Data 22 (1993) 783, Eq. 2.6 -- six PUBLISHED
coefficients, so §1 is satisfied with no regression performed at all.
"""
import random

import main as m

# IAPWS-IF97 saturated-liquid density, kg/m3.  Independent reference, not produced by the
# correlation under test.
IF97_RHO = {
    0: 999.793, 20: 998.161, 40: 992.183, 44: 990.598, 56: 985.183, 60: 983.175,
    80: 971.779, 95: 961.887, 100: 958.354, 114: 947.864, 139: 927.021, 140: 926.132,
    143: 923.439, 148: 918.866, 150: 917.007, 160: 907.450, 175: 892.288, 190: 876.084,
    200: 864.666, 212: 850.267, 220: 840.213,
}
IF97_CP = {
    0: 4.2199, 20: 4.1851, 40: 4.1788, 56: 4.1814, 60: 4.1829, 80: 4.1956, 95: 4.2106,
    100: 4.2166, 114: 4.2365, 139: 4.2838, 140: 4.2860, 143: 4.2930, 148: 4.3052,
    150: 4.3103, 160: 4.3379, 175: 4.3869, 190: 4.4468, 200: 4.4941, 212: 4.5603,
}


def test_wagner_pruss_reproduces_if97_across_the_whole_operating_range():
    """The correlation is quoted, not fitted, so this is a check that it was TRANSCRIBED right."""
    worst = 0.0
    for T, ref in IF97_RHO.items():
        dev = abs(m.water_rho_sat(T) - ref) / ref
        worst = max(worst, dev)
        assert dev < 5e-4, f"water_rho_sat({T}) = {m.water_rho_sat(T):.3f} vs IF97 {ref:.3f}"
    assert worst < 1e-4, f"worst deviation {worst:.2%} -- coefficients may be mistyped"


def test_water_cp_tracks_if97():
    for T, ref in IF97_CP.items():
        assert abs(m.cp_water_kjkgk(T) - ref) < 0.02, (
            f"cp_water_kjkgk({T}) = {m.cp_water_kjkgk(T):.4f} vs IF97 {ref:.4f}")


def test_density_falls_monotonically_with_temperature():
    ts = sorted(IF97_RHO)
    for a, b in zip(ts, ts[1:]):
        assert m.water_rho_sat(b) < m.water_rho_sat(a)


# ----------------------------------------------------------------- the bit-exactness contract
def test_anchor_identity_holds_for_every_real_anchor_in_the_model():
    """Each aqueous call site keeps its own PFD design density; the correlation supplies only the
    slope. At the design temperature the result must be the anchor to the BIT."""
    for anchor, T_des in ((933.0, 139.0), (923.28, 143.0), (1002.48, 44.0), (992.42, 40.0),
                          (1095.0, 61.0), (1005.0, 40.0), (992.4, 56.0)):
        assert m.aqueous_rho(anchor, T_des, T_des) == anchor
    for anchor, T_des in ((4.0, 139.0), (4.0, 40.0), (3.0, 56.0), (4.18, 80.0)):
        assert m.aqueous_cp(anchor, T_des, T_des) == anchor


def test_ratio_must_be_parenthesised():
    """This guards a real trap, measured rather than assumed.

    `anchor * (r / r)` returns anchor bit-exactly for every operand pair, because r/r is exactly
    1.0 and multiplying by 1.0 is exact. `anchor * r / r` evaluates left to right, rounds the
    intermediate product, and does NOT round-trip -- for roughly 10 % of operand pairs. If anyone
    ever "simplifies" the parentheses out of aqueous_rho, the design anchor stops being bit-exact
    and the pin moves. This test exists to fail loudly at that moment.
    """
    random.seed(7)
    bad_paren = bad_flat = 0
    for _ in range(20000):
        a = random.uniform(800.0, 1400.0)
        r = random.uniform(700.0, 1100.0)
        if a * (r / r) != a:
            bad_paren += 1
        if a * r / r != a:
            bad_flat += 1
    assert bad_paren == 0, "parenthesised form is not exact -- the whole pattern is unsound"
    assert bad_flat > 0, (
        "the unparenthesised form round-tripped every time; this test can no longer detect the "
        "trap it exists to guard")


# --------------------------------------------------- why departing from the PFD is justified
def test_the_two_bad_pfd_densities_are_physically_impossible():
    """746 and 747 exceed what the same water could weigh even if every solute were solid urea.

    That is the load-bearing argument for §0: the model follows the PFD where the PFD is sound and
    departs from it only at two entries that cannot be true. If a future property change ever made
    these reachable, the justification would be void -- hence the assertion.
    """
    RHO_SOLID_UREA = 1335.0
    for T, ws, pfd in ((190.0, 0.03335, 908.5), (200.0, 0.00966, 897.7)):
        rho_w = m.water_rho_sat(T)
        rho_max = 1.0 / ((1.0 - ws) / rho_w + ws / RHO_SOLID_UREA)
        assert pfd > rho_max, (
            f"PFD {pfd} at {T} C is no longer above the physical maximum {rho_max:.1f} -- "
            "the justification for departing from the table has changed")


def test_the_pfd_is_trusted_where_it_is_sound():
    """The other side of the same argument. The desorption sheet's own pure-water streams and the
    utility condensates agree with IAPWS to a few hundredths of a percent, so the departure is
    confined to the mixture-model family and is not a blanket rejection of the source."""
    for T, pfd in ((88.0, 966.40), (89.0, 965.74), (143.0, 923.28),   # desorption pure water
                   (142.0, 924.28), (151.0, 915.76), (175.0, 891.84), (212.0, 850.84)):  # utility
        dev = abs(m.water_rho_sat(T) - pfd) / pfd
        assert dev < 1e-3, f"PFD {pfd} at {T} C now deviates {dev:.2%} from IAPWS"


def test_model_anchors_are_the_sound_pfd_values_not_the_impossible_ones():
    """The engine's aqueous density anchors must never be 908.5 or 897.7."""
    for anchor in (m.R328_C002_RHO, m.R328_C004_RHO, m.RHO_744_KGM3, m.RHO_741_KGM3):
        assert abs(anchor - 908.5) > 1.0 and abs(anchor - 897.7) > 1.0


def test_frozen_beta_signature_of_the_licensor_model():
    """The diagnosis itself: the tabulated pair implies an expansivity near 5.5e-4 /K, which is
    water at ~60 C -- the desorption section's own reference -- not water at 190-200 C."""
    import math
    beta = -math.log(908.5 / 933.0) / (190.0 - 139.0)      # from PFD 743 -> 746
    assert 4.5e-4 < beta < 6.5e-4, f"implied beta {beta:.3e}"
    # water's real expansivity at 190 C, from the correlation itself
    real = -(m.water_rho_sat(191.0) - m.water_rho_sat(189.0)) / (2.0 * m.water_rho_sat(190.0))
    assert real > 2.0 * beta, (
        f"real beta {real:.3e} is no longer far above the implied {beta:.3e}")
