"""Audit C10, second pass — cp is per-stream everywhere it is used, not one constant per section.

Two lumped constants used to cover most of the plant:

  * `cp323 = R323_CP_SOLN` (2.5 kJ/kg.K) for the WHOLE 323 recirculation train — the 44.4 %
    granulation return at 40 C, the 55.9 % stripper bottoms at 119 C and the 80 % product at 99 C
    all shared it.  cp falls as a urea solution concentrates (molten urea ~2.07 against water's
    4.2), so a single value is wrong in both directions at once, and it is most wrong exactly where
    the model does its work, because concentrating the solution IS the job.
  * `R328_CP = A328_CP = 4.0` for every aqueous vessel from 40 C to 200 C.  Those streams are >= 98 %
    water, and water's cp is not flat: 4.18 / 4.29 / 4.49 at 40 / 140 / 200 C.

Both are now applied as a DEPARTURE from the licensor's own constant, so the design point survives
to the bit and only the off-design response changes.  These tests exist to keep that true: the
bit-exactness assertions are the ones that would let a design-point regression through if they were
ever relaxed.

Run from backend/:  python -m pytest test_equation_audit_c10_live_cp.py -q
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main  # noqa: E402


# ------------------------------------------------------------------- the 323 train, per stream
def test_the_five_323_streams_no_longer_share_one_cp():
    """If these ever collapse toward each other the lumped constant is back."""
    cps = [main.R323_CP_S208_DES, main.R323_CP_C003_DES, main.R323_CP_F004_DES,
           main.R323_CP_F010_DES, main.R323_CP_S331_DES]
    assert max(cps) - min(cps) > 0.5, cps          # measured spread is 0.75 kJ/kg.K
    # and they order the way concentration says they must: weaker solution -> higher cp
    assert main.R323_CP_S331_DES > main.R323_CP_S208_DES > main.R323_CP_C003_DES
    assert main.R323_CP_C003_DES > main.R323_CP_F004_DES > main.R323_CP_F010_DES


def test_the_product_stream_is_still_the_anchor_bit_exactly():
    """80 % urea at 99 C IS the design anchor R323_CP_SOLN was derived at, so the departure at that
    stage must be a literal 0.0 -- this is what keeps every back-solved lambda and UA valid."""
    assert main.R323_CP_F010_DES == main.urea_soln_cp(main.W_S317["Urea"], main.R323_F010_T_SP_C)
    assert abs(main.R323_CP_F010_DES - main.R323_CP_SOLN) < 1e-4


def test_the_cold_granulation_return_is_not_treated_as_product():
    """PFD stream 331 is 44.37 % urea at 40 C and it feeds 323F010 alongside the 71.7 % stream 319.
    Giving both the product's 2.5 understated the cold feed's heat load by nearly 30 %."""
    assert main.R323_CP_S331_DES > main.R323_CP_SOLN * 1.25


# ----------------------------------------------------------------- the aqueous trains, per vessel
def test_aqueous_cp_returns_each_vessel_anchor_bit_exactly_at_its_own_design_temperature():
    """Every 328 / 322C001 call site is anchored on ITS OWN design temperature.  That is what makes
    the change safe: at the seed each one returns the frozen constant to the bit, so the design
    back-solves and the boot-pinned A328_LAMBDA_ABS cannot move."""
    for anchor, T_des in ((main.R328_CP, main.R328_C002_T_BOT), (main.R328_CP, main.R328_C003_T),
                          (main.R328_CP, main.R328_C004_T),     (main.R328_CP, main.R328_D001_T),
                          (main.A328_CP, main.A328_D003_TI),    (main.A328_CP, main.A328_D003_TII),
                          (main.A328_CP, main.A328_C001_T)):
        assert main.aqueous_cp(anchor, T_des, T_des) == anchor


def test_aqueous_cp_moves_the_right_way_and_by_the_right_amount():
    """The hydrolyser runs at 200 C where water's cp is 4.49, so the frozen 4.0 was 11 % low.  The
    departure must recover that slope even though the absolute value stays on the anchor."""
    hot = main.aqueous_cp(main.R328_CP, main.R328_C003_T, main.R328_C003_T + 40.0)
    cold = main.aqueous_cp(main.R328_CP, main.R328_C003_T, main.R328_C003_T - 60.0)
    assert hot > main.R328_CP > cold
    # water gains ~0.20 kJ/kg.K between 140 and 200 C -- the departure must carry that, not invent it
    assert abs((main.aqueous_cp(main.R328_CP, 140.0, 200.0) - main.R328_CP) - 0.208) < 0.03


def test_the_carbamate_train_is_deliberately_left_alone():
    """R3232_CP covers 323E003/323E011, a strong ammonium-carbamate liquor rather than water.
    Reconciled 2026-07-24 against References/Ammonium Carbamate Heat Capacity Data.md: there is no
    single valid equation to source it to.  The rigorous e-NRTL/UNIQUAC route is a full electrolyte
    package (ion cp only at 298 K), not a lumped cp; the one closed-form Chauhan cubic is the pure
    molten salt; and the real governing property is the reaction-shifted APPARENT cp, which no
    constant can carry.  The reference's frozen band for the SOLUTION is 3.2-3.8 kJ/kg.K, Stamicarbon
    lean-NH3 at the ~3.2 low end, so 3.0 sits above pure-salt ~2.1 and ~6% below that floor -- a
    defensible lean-liquor value, not an arbitrary one.  aqueous_cp stays the WRONG correlation
    (carbamate ion cp is negative from electrostriction).  Asserted so the omission reads as a
    decision, and so the value stays pinned to the back-solved lambdas that were computed with it."""
    assert main.R3232_CP == 3.0
    assert main.R3232_CP < main.R328_CP        # carbamate solution is below the aqueous-vessel cp


# --------------------------------------------------------------------------- the seed still holds
def test_the_design_seed_is_undisturbed_by_any_of_it():
    main.state = main.State()
    for _ in range(1200):
        main.step_sim(1.0)
    s = main.state
    assert abs(s.r323_c003_T - main.R323_C003_T_SP_C) < 0.01
    assert abs(s.r323_f004_T - main.R323_F004_T_SP_C) < 0.01
    assert abs(s.r323_f010_T - main.R323_F010_T_SP_C) < 0.01
    assert abs(s.a328_c003_T - main.R328_C003_T) < 1.0
    assert abs(s.a328_c001_T - main.A328_C001_T) < 0.5
    assert abs(s.a328_d003_TII - main.A328_D003_TII) < 0.5
