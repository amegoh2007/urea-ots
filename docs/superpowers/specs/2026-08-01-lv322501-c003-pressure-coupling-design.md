# LV-322501 to 323C003 Pressure Coupling Design

Date: 2026-08-01

## Objective

Replace the empirical 323C003 pressure target with a source-calibrated relation that makes a change in LV-322501 opening produce the correct gas-load and pressure response in 323C003. Preserve the field-calibrated 46.1% normal valve opening and the existing external simulation state and telemetry.

## Evidence and constraints

- The original LV-322501 datasheet identifies a linear installed valve characteristic, 114.58 m3/h normal liquid flow, and 126.10 m3/h maximum liquid flow. Its general note that maximum flow is at about 90% travel is not used to replace the field-calibrated normal opening.
- The active simulator's normal LV-322501 opening remains 46.1%. At unchanged upstream hydraulic conditions, the valve-caused liquid-flow ratio is therefore `u / 46.1`, where `u` is valve opening in percent.
- The Unit 323 PFD table reports 5,064.7 m3/h for stream 301, the prompt flash gas generated after LV-322501; 2,875.7 m3/h for stream 302, the heater gas entering 323C003; and 7,677.1 m3/h for stream 305, the gas leaving 323C003 for 323E003.
- Streams 301 and 305 are both reported at 119 C and 4.1 bara. Stream 302 is reported at 135 C and has a different composition, so its actual-volume rate must not be added directly to the 119 C rates. The LV-dependent increment can instead be transported consistently from stream 301 to stream 305 because those two reported volume rates share pressure and temperature.
- The effective non-LV design gas load expressed at stream-305 conditions is `7,677.1 - 5,064.7 = 2,612.4 m3/h`. It groups the stream-302 contribution and the column's design equilibrium effects without assigning the raw volume difference to an unsupported condensation mechanism.
- The PFD stream-301 mass entry is inconsistent by a factor of approximately ten with both its molar flow times molecular weight and its volume flow times density. The pressure relation therefore uses the internally consistent reported volume, pressure, and temperature anchors rather than the corrupted mass entry.
- The PFD design pressures are 4.1 bara in 323C003 and 3.2 bara at the 323E003/323D001 downstream boundary.
- The 323C003 datasheet provides vessel dimensions but not the operating liquid level or working free-vapor volume. The available 323E003 source provides exchanger geometry but not transient shell-side vapor holdup. A first-principles gas-inventory time constant therefore cannot be derived without inventing operating data.
- The current simulator already carries a 90 s first-order 323C003 pressure response. This value is retained as a simulator dynamic calibration, not represented as a datasheet-derived constant.
- No original 323E003 PDF is present in the supplied references. The available transcribed 323E003 datasheet is used and this limitation remains explicit.

## Considered approaches

### Full gas-inventory balance

A gas-mole inventory with pressure-dependent outflow would be the most physical dynamic model. It requires the working vapor volume, operating liquid level, flash composition, and condenser response. Those inputs are absent, so this approach would introduce unsupported assumptions and is rejected for this change.

### Linear pressure gain

A local law of the form `P = 4.1 + k (u - 46.1)` is easy to implement. It cannot correctly incorporate live downstream pressure and becomes inaccurate away from the design point. It is retained only as a local analytical check.

### Calibrated near-design gas-load surrogate

The selected approach decomposes the gas-load index into an LV-dependent prompt-flash term and a remaining live-overhead term, then calibrates a near-design `P^2` surrogate to the reported upstream and downstream pressures. It is nonlinear, preserves non-valve pressure drivers, uses live downstream pressure, and closes the design point exactly without inventing vessel holdup. It is not represented as a dry-pipe conductance or a rigorous condenser model.

## Selected relation

Let:

- `r_lv` be the live LV-322501 liquid-flow ratio relative to its design flow;
- `r_305` be the live modeled stream-305 mass-flow ratio relative to its design flow, used as a proxy for the remaining gas load;
- `Q301,0 = 5,064.7 m3/h`;
- `Q305,0 = 7,677.1 m3/h`;
- `Qother,0 = Q305,0 - Q301,0 = 2,612.4 m3/h`;
- `PC,0 = 4.1 bara`;
- `PE,0 = 3.2 bara`.

The existing valve hydraulics calculate the live liquid flow. The pressure relation consumes its normalized result directly:

```
r_lv = drain_kgh / STRIP_BOT_DES_KGH
```

The denominator is the existing runtime design anchor, `STRIP_BOT_DES_KGH = 130,482 kg/h`. The PFD's 130,582 kg/h and the valve-datasheet mass flow remain source cross-checks, not alternate runtime denominators. Only at design synthesis pressure and with `f_drain = 1` does the normalization reduce to:

```
r_lv = u / 46.1
```

The remaining live gas-load proxy is normalized from the already-calculated top-vapor flow:

```
r_305 = m_305 / R323_M305_DES
```

To isolate the LV prompt-gas effect without removing the existing reboiler/overhead driver, decompose the equivalent gas-load index at stream-305 design conditions:

```
Q_eq = Q301,0 * r_lv + Qother,0 * r_305
     = Q305,0 * r_305 + Q301,0 * (r_lv - r_305)
```

Near the design and vendor-maximum range, assume locally fixed temperature, composition, and compressibility and calibrate a reduced-order `P^2` pressure-drop surrogate. `K_eq` is an empirical gas-load coefficient for the combined gas path and condensing boundary, not a sourced dry-pipe conductance:

```
K_eq = Q305,0 / sqrt(PC,0^2 - PE,0^2)
     = 2,995.1 m3/(h bar)
```

Using the beginning-of-substep 323E003/323D001 absolute pressure `P_E003,begin`, the 323C003 target is:

```
P_C003,target = sqrt(P_E003,begin^2 + (Q_eq / K_eq)^2)
```

The existing first-order dynamics remain:

```
dP_C003/dt = (P_C003,target - P_C003) / 90 s
```

The simulator's existing pressure safety bounds remain the final numerical guard. No rounding is applied to the internal state.

The pure helper raises `ValueError` for a non-finite input, a negative flow ratio, or a nonpositive downstream absolute pressure. Runtime callers pass the already bounded nonnegative flows and positive pressure state.

## Design checks

- At `r_lv = r_305 = 1` and `P_E003,begin = 3.2 bara`, the relation returns exactly `P_C003,target = 4.1 bara`.
- Holding `r_305 = 1`, its local LV sensitivity is approximately `+0.0229 bara` per opening percentage point at unchanged upstream hydraulics and downstream pressure.
- The vendor liquid-flow ratio is `126.10 / 114.58 = 1.10054`. Applied to the preserved field calibration, its equivalent opening is `46.1 * 1.10054 = 50.74%`. For the immediate LV-only response with `r_305 = 1`, the target is approximately `4.21 bara` at 3.2 bara downstream pressure.
- The partial pressure response to `r_lv` is strictly positive. This gives the prompt opening signal that the lagging stream-305 calculation currently misses.
- Reboiler and other live overhead changes remain pressure drivers through the `Qother,0 * r_305` term instead of being discarded by the replacement.
- At `r_lv = r_305 = 0`, `Q_eq = 0` and the target equals the downstream pressure; the model does not retain an artificial gas load after total shutdown.
- Increasing the 323E003/323D001 pressure increases the next C003 target without adding a duplicate downstream pressure state.

## Software integration

Add a small pure pressure-coupling helper under `backend` containing the source constants and target calculation. The helper accepts the live valve liquid-flow ratio, remaining overhead-load ratio, and downstream absolute pressure. It enforces the stated input contract and returns an unrounded absolute-pressure target.

In the Unit 323 section of `step_sim`:

1. retain the existing LV-322501 liquid-flow calculation and the 46.1% calibration;
2. calculate `r_lv = drain_kgh / STRIP_BOT_DES_KGH`;
3. calculate `r_305 = m_305 / R323_M305_DES` after the existing energy-limited overhead calculation;
4. pass both ratios and the existing beginning-of-substep `s.r3232_d001_P` state to the helper;
5. replace the current empirical stream-305 pressure target with the derived target;
6. retain the existing 90 s state update and pressure bounds.

The 323E003/323D001 pressure is advanced later in the same explicit substep. Consuming its beginning value here preserves the existing one-substep tear and avoids an algebraic loop; integration tests account for that update order.

The public API, saved state shape, controller tags, and existing pressure telemetry remain unchanged.

## Verification strategy

Development follows a red-green-refactor sequence.

Pure equation tests cover:

1. exact reproduction of 4.1 bara at `r_lv = r_305 = 1`;
2. monotonic response to each nonnegative gas-load ratio;
3. the 50.74% vendor maximum-flow equivalent and approximately 4.21 bara immediate result at `r_305 = 1`;
4. the local analytical LV sensitivity;
5. monotonic coupling to positive downstream absolute pressure;
6. equality with downstream pressure when both gas-load ratios are zero;
7. `ValueError` for every specified invalid input class.

Integrated simulation tests cover:

1. preserved fresh-state design pressure and exact `r_lv = 1` at design synthesis pressure with `f_drain = 1`;
2. a positive initial 323C003 pressure derivative after an LV-322501 opening increase;
3. a negative derivative after a closing change;
4. retained pressure response to a reboiler/live-`m_305` perturbation at fixed LV flow;
5. propagation of an altered beginning-of-substep 323E003/323D001 backpressure on the next C003 update;
6. comparable results across supported integration step sizes.

Final verification runs the focused Unit 323 equation-audit tests, session regression tests relevant to fresh design and time-step behavior, and repository diff checks. Only the specification and implementation files for this change are staged; unrelated working-tree files remain untouched.

## Source files

- `References/Datasheets/LV-322501 Datasheet.pdf`
- `References/Datasheets/323C003 Datasheet.pdf`
- `References/323E003 323D001 323P001 Datasheets.md`
- `References/Combined_1750_MTPD_100% load_PFD TablesProcess_Data.md`
- `backend/main.py` for the existing runtime calibration and update order

## Completion boundary

This change establishes an evidence-backed, near-design reduced-order pressure target and a directionally correct dynamic response between LV-322501 and 323C003 pressure while retaining the live overhead driver. It does not claim a first-principles vapor-inventory transient, a rigorous condensing-exchanger pressure-drop model, re-identify the existing 90 s time constant, or predict far-off-design changes in flash fraction, gas composition, compressibility, heater-gas flow, or condenser holdup. Those require additional operating data or a validated thermodynamic and equipment-inventory model.
