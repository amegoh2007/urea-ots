# Design Specification: Recirculation Stage Pressure & Heat Coupling Model

**Date:** 2026-08-08  
**Status:** Approved  
**Target Subsystems:** `323C003`, `323E002`, `323E003`, `323D001`, `PV-323202`, `323F004`, `323E011`

---

## 1. Executive Summary & Problem Definition

In the Urea OTS simulation, opening `LV-322501` (HP Stripper `322E001` bottom letdown valve) was observed in trend reports to cause `PV-323202` (off-gas vent valve on `323D001`) to **close** (decreasing from 24.6% to 23.0%), while `PT-323201` stayed flat or slightly dropped.

### 1.1 Root Cause
In `backend/main.py` (and `backend/core/mp.py`), available vaporization kW in `323C003` was calculated as:
$$q_{305,\text{avail\_kw}} = \frac{m_{\text{feed\_323}}}{3600} \cdot c_{p,\text{feed}} \cdot (T_{\text{feed\_323}} - T_{\text{c003}}) + Q_{\text{E002}}$$
Where $T_{\text{feed\_323}} = 123.7\ ^\circ\text{C}$ (`TT-323001` post-flash liquid temperature) and $T_{\text{c003}} = 135.0\ ^\circ\text{C}$ (column bottom temperature).

Because $(123.7 - 135.0) = -11.3\ ^\circ\text{C}$ is negative, increasing feed flow $m_{\text{feed\_323}}$ made this sensible cooling term **more negative** (e.g., dropping from $-958\text{ kW}$ down to $-1143\text{ kW}$ when `LV-322501` went from 46.1% to 55.0%). This caused top vapor flow $m_{305}$ (`v305_th`) to **decrease** (from 24.58 t/h to 23.05 t/h), reducing gas generation `gen321` into `323D001`, dropping `323D001` pressure, and forcing `PIC-323202` to close `PV-323202`.

### 1.2 Physical Reality
The feed solution leaving HP Stripper `322E001` bottom is at $177.5\ ^\circ\text{C}$ (`TT-322004`) under $140\text{ bar}$. When expanded across `LV-322501` down to $4.1\text{ bar}$, its sensible enthalpy surplus above flash saturation ($119.0\ ^\circ\text{C}$) drives adiabatic flash gas generation. Opening `LV-322501` increases feed flow, which **increases** flash gas generation $m_{\text{flash}}$ AND increases reboiled vapor from `323E002`, raising $m_{305}$. Higher $m_{305}$ increases `323C003` pressure, increases gas load to `323E003` / `323D001`, increases `323D001` pressure, and forces `PIC-323202` to **open `PV-323202` wider** ($>25\%$).

---

## 2. Detailed Technical Design

### 2.1 Reformulated 323C003 Energy & Flash Vapor Balance
We reformulate the available vaporization heat $q_{305,\text{avail\_kw}}$ using the positive letdown enthalpy driving force:
$$q_{\text{flash,avail\_kw}} = \frac{m_{\text{feed\_323}}}{3600} \cdot c_{p,\text{feed}} \cdot (T_{\text{strip\_bot}} - T_{\text{flash,sat}})$$
$$q_{305,\text{avail\_kw}} = q_{\text{flash,avail\_kw}} + Q_{\text{E002,kw}}$$
Where:
- $T_{\text{strip\_bot}} = 177.5\ ^\circ\text{C}$ (`TT-322004`, live stripper bottom temperature)
- $T_{\text{flash,sat}} = 119.0\ ^\circ\text{C}$ (`TT-323001`, post-flash saturation temperature)
- $(T_{\text{strip\_bot}} - T_{\text{flash,sat}}) = +58.5\ ^\circ\text{C}$ is **strictly positive**.

Top vapor mass flow $m_{305}$ is calculated as:
$$m_{305} = \min\left(R323\_\text{PHI\_V305} \cdot m_{\text{feed\_323}}, \max\left(R323\_M305\_DES \cdot \frac{q_{305,\text{avail\_kw}} - q_{305,\text{relax\_kw}}}{R323\_Q305\_DES\_KW}, 0.0\right)\right)$$

### 2.2 323E002 Steam Flow & Duty Coupling to 323C003 Pressure
The steam heat duty $Q_{\text{E002,kw}}$ is calculated from live steam chest pressure $p_{\text{chest,e002}}$ (driven by `TIC-323007` / `PIC-329202` / `PV-329202`):
$$Q_{\text{E002,kw}} = \max\left(R323\_\text{E002\_UA\_KW} \cdot (T_{\text{sat,steam}}(p_{\text{chest,e002}}) - T_{\text{c003}}), 0.0\right)$$
- **Steam Flow Increase**: Opening steam valve `PV-329202` raises $p_{\text{chest,e002}}$, increasing $Q_{\text{E002,kw}}$, increasing $q_{305,\text{avail\_kw}}$, and increasing $m_{305}$.
- **Target Pressure Coupling**:
  $$r_{\text{LV,c003}} = \frac{m_{\text{feed\_323}}}{\text{STRIP\_BOT\_DES\_KGH}}$$
  $$r_{305,\text{c003}} = \frac{m_{305}}{R323\_M305\_DES}$$
  $$p_{\text{c003,tgt}} = \text{c003\_pressure\_target\_bara}(r_{\text{LV,c003}}, r_{305,\text{c003}}, P_{\text{d001}})$$
  $$P_{\text{c003}} = \text{clamp}\left(P_{\text{c003}} + \frac{p_{\text{c003,tgt}} - P_{\text{c003}}}{\tau_{\text{P}}} \cdot dt, 1.0, 12.0\right)$$
  Increasing `LV-322501` liquid feed OR `323E002` steam flow increases $p_{\text{c003,tgt}}$ and $P_{\text{c003}}$ (`PT-323201`).

### 2.3 Gas-Load Propagation to 323E003, 323D001, and PV-323202
1. Top vapor $m_{305}$ enters `323E003` (LP Carbamate Condenser). Un-condensed equilibrium off-gas generation `gen321` into `323D001` is:
   $$\text{gen321} = R3232\_\text{E003\_PHI321} \cdot (m_{305} + R3232\_M797\_DES)$$
   Since $m_{305}$ increases with `LV-322501` opening or steam flow, `gen321` increases monotonically.
2. In `323D001`, pressure $P_{\text{d001}}$ (`s.r3232_d001_P`) updates via mass accumulation:
   $$P_{\text{d001}} = \max\left(P_{\text{d001}} + R3232\_\text{D001\_P\_KP} \cdot \frac{\text{gen321} - m_{321}}{3600} \cdot dt, 0.1\right)$$
3. Direct-acting controller `PIC-323202` evaluates $P_{\text{d001}} > \text{SP}$ ($3.2\text{ bar a}$), increasing valve stroke `pic202_op` (`PV-323202`).
4. Vent flow $m_{321}$ increases ($m_{321} = R3232\_\text{E003\_M321\_DES} \cdot \frac{\text{pic202\_op}}{R3232\_\text{E003\_PV\_OP\_DES}}$), venting excess off-gas to `323E011` / GCB until $P_{\text{d001}}$ stabilizes back at $3.2\text{ bar a}$.

### 2.4 Downstream Flowsheet Propagation Audit
- **`323F004` (Flash Tank 2nd Stage)**: Feed $m_{314}$ from `323C003` bottom letdown (`LV-323501`) flashes using sensible heat $(T_{\text{c003}} - T_{\text{f004,sat}})$, generating flash gas $m_{701}$ proportional to $m_{314}$.
- **`323E011` / `323D011` (LP Carbamate Condenser 2nd Stage)**: Total gas load $in_{\text{e011}}$ receives $m_{321} + m_{701} + m_{402} + m_{701,\text{abs}}$. Increasing $m_{321}$ raises $P_{\text{e011}}$ and forces `PIC-323203` to open `PV-323203` to `323C005`.
- **Core Modules Alignment**: Updates apply to `backend/main.py` as well as `backend/core/lp.py` and `backend/core/mp.py` to maintain single-source physical consistency.

---

## 3. Verification Plan

### 3.1 Automated Tests
1. **`test_lv322501_opening_increases_pv323202_stroke`**:
   - Set `LIC-322501` to manual, step `op` from 46.1% to 55.0%.
   - Assert $m_{305} > 24,582\text{ kg/h}$.
   - Assert $P_{\text{c003}} > 4.10\text{ bar a}$.
   - Assert $P_{\text{d001}} > 3.20\text{ bar a}$.
   - Assert `PV-323202` stroke $> 25.0\%$.
2. **`test_323e002_steam_chest_pressure_affects_c003_and_pv323202`**:
   - Increase `TIC-323007` setpoint / `PV-329202` steam valve opening.
   - Assert $Q_{\text{E002,kw}}$, $m_{305}$, $P_{\text{c003}}$, $P_{\text{d001}}$, and `PV-323202` stroke increase.
3. **`test_lv322501_closing_decreases_pv323202_stroke`**:
   - Step `LV-322501` from 46.1% down to 35.0%.
   - Assert monotonic decrease in $m_{305}$, $P_{\text{c003}}$, $P_{\text{d001}}$, and `PV-323202`.
4. **Regression Suite**:
   - Run `PYTHONPATH=backend python -m pytest backend/test_c003_pressure_coupling.py`.

---

## 4. Spec Self-Review Checklist
- [x] **Placeholder scan**: No TBD/TODOs. All equations, parameters, and tags explicitly defined.
- [x] **Internal consistency**: Energy balances, mass balances, and pressure targets align across all 4 stages.
- [x] **Scope check**: Focused specifically on Recirculation Stage pressure/heat coupling defect & downstream propagation.
- [x] **Ambiguity check**: Exact sign conventions and variable definitions specified.
