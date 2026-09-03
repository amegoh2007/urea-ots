# LV-322501 Pressure-Impact Retuning Design

Date: 2026-08-09

## Objective

Strengthen the simulated effect of opening or closing `LV-322501` on `PT-323201` and `PIC-323203` without changing the field-calibrated valve opening, controller tuning, public state, or design heat-and-mass balance.

## Evidence

### PT-323201 field response

`References/Urea_Startup_28-06-2025_Trends.md` contains 721 samples at 30-second intervals. During the clean 20-40% `LV-322501` ramp, ordinary least squares gives:

- `d(PT-323201) / d(LV-322501) = 0.124139 bar per opening point`;
- `R2 = 0.999260` over 167 samples;
- the median five-minute secant slope is `0.102564 bar per opening point` over 239 moving windows.

The existing gas-load equation produces only `0.022932 bar per opening point` at the design state. It therefore captures about one fifth of the field sensitivity.

The retuning adds a conservative `0.100 bar per opening point` residual to the existing source-derived gas-load response. The combined local design sensitivity becomes about `0.122932 bar per opening point`, matching the clean field ramp without discarding the existing overhead and downstream-pressure drivers.

### PIC-323203 process balance

The 1,750 MTPD PFD reports the following `323E011` design streams:

| Quantity | Flow (kg/h) |
| --- | ---: |
| Gas feeds `701 + 786 + 321` | 6,029 |
| Liquid ammonia-water feed `791` | 1,534 |
| Condensed gas retained in liquid `718` | 5,589 |
| Uncondensed gas vent `702` | 440 |

The current model multiplies every E011 inlet disturbance by the design vent fraction, `440 / 7,563 = 0.05818`. This suppresses 94.2% of every incremental gas disturbance before the `PIC-323203` pressure balance sees it. It also treats liquid stream 791 as vapor-generation load.

The PFD supports a capacity closure instead: the condenser removes its design gas capacity of 5,589 kg/h, and gas above that capacity enters the vent-space pressure balance. Liquid stream 791 does not generate vent gas.

## Considered approaches

### Retune only the C003 pressure gain

This approach can match `PT-323201`, but it leaves `PIC-323203` behind the fixed 5.8% E011 split. It does not meet the full objective.

### Retune PIC-323203

The supplied tuning sheet specifies `Kc = 0.60` and `Ti = 100 s`. Increasing controller gain would hide the weak process disturbance and conflict with the source. This approach is rejected.

### Retune both process closures

The selected approach adds the observed residual sensitivity to the C003 pressure target and replaces the E011 proportional vent generation with the PFD condensation-capacity balance. It preserves the sourced controller tuning and strengthens both requested paths.

## Detailed design

### PT-323201 target

Retain the existing equivalent gas load:

```text
Qeq = Q301,des * r_lv + (Q305,des - Q301,des) * r_305
Phyd = sqrt(Pdown^2 + (Qeq / Keq)^2)
```

Add the field residual through the live LV flow ratio:

```text
Kfield = 0.100 bar per opening point * 46.1 opening points
       = 4.61 bar per unit LV flow ratio

Ptarget = max(Pdown, Phyd + Kfield * (r_lv - 1))
```

The downstream-pressure floor prevents the upstream target from falling below its discharge pressure on a large closure. At `r_lv = r_305 = 1` and `Pdown = 3.2 bara`, the target remains exactly `4.1 bara`.

Keep the current `R323_C003_P_TAU_S = 1.0 s`. The reference data identifies steady sensitivity, not a replacement time constant.

### PIC-323203 gas generation

Define the gas feed independently of liquid stream 791:

```text
gas_in_e011 = in_e011 - m_402
gen_v011 = max(gas_in_e011 - 5,589, 0)
```

At design, `gas_in_e011 = 6,029 kg/h`, so `gen_v011 = 440 kg/h`. The pressure inventory, valve equation, and `PIC-323203` tuning remain unchanged. An additional 1,000 kg/h gas load now adds 1,000 kg/h to vent-space generation instead of 58.2 kg/h.

## Software boundaries

- Extend `backend/c003_pressure_coupling.py` with the field residual and a pure E011 vent-generation helper.
- Update `backend/main.py` to consume the E011 helper.
- Add a new focused test file. Do not restore or stage the user's deleted test files.
- Keep `LV322501_OPEN_DES = 46.1`, `PIC-323203` tuning, controller modes, telemetry keys, API routes, and saved-state shape unchanged.
- Apply the same E011 closure to `backend/core/lp.py` only if that port contains the active duplicate equation and can consume the helper without broad refactoring.

## Verification

Tests will prove:

1. the C003 design point remains exactly 4.1 bara;
2. the local combined LV sensitivity lies within the measured 0.10-0.13 bar per opening point band;
3. opening and closing produce signed `PT-323201` responses;
4. E011 generates exactly 440 kg/h vent gas at design;
5. incremental gas above the 5,589 kg/h condenser capacity reaches the pressure balance one-for-one;
6. stream 791 does not generate vent gas;
7. an integrated LV opening produces materially larger `PT-323201` and `PIC-323203` responses than a closing case;
8. fresh-state design values and focused Section 323 regressions remain valid.

## Sources

- `project.md`
- `References/Urea_Startup_28-06-2025_Trends.md`
- `References/Combined_1750_MTPD_100% load_PFD TablesProcess_Data.md`
- `References/323E011 323D011 323P008 Datasheets.md`
- `References/Master_PID_Tuning_Constants.md`
- `References/Urea_Operating_Manual_Helwan.md`

