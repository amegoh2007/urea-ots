# Ejector-Scrubber Coupling Design

## 1. Context and Goals
Ensure that the interaction between the HP Ejector (322F001) and HP Scrubber (322E003) is accurately modeled, capturing the cascading thermodynamic and hydraulic effects when the ejector spindle (motive valve) is restricted.

## 2. Physics to Model

### 2.1 Ejector Motive Pressure (Upstream NH3 Pressure)
**Behavior:** Throttling the ejector spindle restricts the nozzle area. With a constant mass flow from the positive-displacement pumps (321P002), this area reduction forces an upstream pressure rise due to increased kinetic energy at the throat.
**Implementation:** Calculate `_phi_sp = EJ_SPINDLE_R ** ((EJ_OPEN_DES - s.HIC_322602) / 100.0)`. As the opening decreases, `_phi_sp > 1.0`. Add a backpressure term to `P_SYN_DOWN_BAR`: `15.0 * (_phi_sp**2 - 1.0)`. Use this live discharge pressure for pump `dP` calculations and the `P_disch_header_barG` reading.

### 2.2 Scrubber Overflow Line Level Drop
**Behavior:** With stronger vacuum, the ejector draws enriched carbamate from the scrubber sump faster than it condenses. The main liquid level falls below the overflow tap.
**Implementation:** Restore the gravity head multiplier on actual entrainment: `frac_eff = min(max(scrub_level_frac, 0.0), EJ_HYD_FRAC_MAX)` and `m_suc = capacity * frac_eff`. This allows the ejector to actively draw down the sump level.

### 2.3 Scrubber Overflow Line Temperature Drop
**Behavior:** As the scrubber level drops and overflow ceases, the line cools rapidly due to ambient heat losses.
**Implementation:** Apply an ambient heat loss term to `t_overflow` (TT-322002) in `scrub_322e003` when `choke_level_pct < SCRUB_LEVEL_NLL_PCT`, driving it toward 30 °C.

### 2.4 Ejector Suction Capacity and Mixed Temperature
**Behavior:** The stronger vacuum pulls more hot carbamate (~165 °C) into the cooler motive NH3 (~30 °C), raising the mixed temperature to the HPCC.
**Implementation:** This is natively solved by the existing `m_suc` mass-energy balance. The larger `m_suc` fraction naturally raises `T_d`.

### 2.5 Scrubber Exposed Tube Condensation
**Behavior:** As liquid level drops, exposed tubes facilitate direct gas-to-wall condensation (higher heat transfer coefficient) on a reduced thermal mass, raising the CW outlet temperature.
**Implementation:** In `scrub_322e003`, when `choke_level_pct < SCRUB_LEVEL_NLL_PCT`, apply an exposed-tube heat duty multiplier `chi_exposed` (up to +15% at empty) to `q_ccw_kw`.
