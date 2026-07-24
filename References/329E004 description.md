# Scientific Technical Explanation: HP Scrubber Tempered Water Cooler (329-E-004)

## 1. Functional Role and Process Integration

In the Stamicarbon $CO_2$ stripping urea process, the High-Pressure (HP) Scrubber (322-E-003) requires a highly regulated cooling medium to absorb the intense heat of ammonium carbamate formation. However, using raw cooling water directly from the main cooling tower poses a severe operational risk: raw cooling water is too cold. If the tube wall temperature in the HP Scrubber drops below the crystallization temperature of the local carbamate solution (typically between $40^\circ\text{C}$ and $45^\circ\text{C}$ depending on the $NH_3/CO_2$ ratio and water content), solid carbamate will instantly precipitate, plugging the high-pressure tubes and forcing a plant shutdown.

To solve this, the process utilizes a **Closed Tempered Cooling Water Loop**. 
The **HP Scrubber Tempered Water Cooler (329-E-004)** is the heat exchanger responsible for maintaining the thermal balance of this closed loop. Its functional roles are:
1.  **Heat Rejection:** It removes the total enthalpy of condensation and reaction absorbed by the tempered water in 322-E-003, transferring it to the plant's main open cooling water system.
2.  **Temperature Control:** By modulating the flow of the cold main cooling water through 329-E-004, the supply temperature of the tempered water loop is tightly controlled (usually maintained around $45^\circ\text{C}$ to $55^\circ\text{C}$).

![Figure 1: P&ID configuration of the closed tempered water loop, showing 329-E-004 cooling the circulating water returning from the HP Scrubber shell before it is pumped back.](placeholder_329E004_loop.png)

---

## 2. Equipment Design and Hydrodynamics

Unlike the high-pressure, multi-phase synthesis equipment, 329-E-004 operates at low pressures (typically $< 10 \text{ bar}$) and handles single-phase liquid water on both sides.

In modern Stamicarbon facilities, 329-E-004 is almost universally a **Plate and Frame Heat Exchanger (PHE)** (e.g., Alfa Laval or Kelvion titanium/stainless steel plates). PHEs are preferred over shell-and-tube exchangers for this duty because they offer exceptionally high overall heat transfer coefficients and can operate with extremely tight temperature approaches.

* **Hot Side (Process):** Closed-loop tempered water returning from 322-E-003. Treated with specific closed-loop corrosion inhibitors.
* **Cold Side (Utility):** Main plant cooling water from the cooling tower. 

**Hydrodynamics:** The flow inside a PHE is characterized by high turbulence, even at low Reynolds numbers, due to the corrugated chevron patterns on the plates. This intense macroscopic mixing breaks up the thermal boundary layer, ensuring high convective heat transfer but at the cost of higher frictional pressure drop ($\Delta P$).

---

## 3. Heat Transfer Processes

The fundamental process inside 329-E-004 is strictly **sensible heat transfer**. There is no phase change, no boiling, and no latent heat involvement.

Heat is transferred from the bulk hot tempered water, through the convective boundary layer to the metal plate wall, conducted through the thin metal plate, and convected into the bulk cold cooling water. 

During peak summer conditions—when the main cooling tower supply temperature may reach $32^\circ\text{C}$ to $35^\circ\text{C}$—the Log Mean Temperature Difference (LMTD) shrinks considerably. Under these conditions, the efficiency of 329-E-004 becomes a critical bottleneck for the entire synthesis loop; if 329-E-004 cannot reject the heat, the HP Scrubber loses its driving force, causing unabsorbed $NH_3$ and $CO_2$ to slip into the Low-Pressure section.

---

## 4. Clarification on Mass and Material Transfer

It is crucial to highlight that under normal, healthy operating conditions, **there are absolutely zero mass transfer or material transfer processes occurring inside 329-E-004.** * **No Chemical Reactions:** The fluids on both sides are chemically stable liquid water.
* **No Phase Transfer:** Temperatures remain well below the boiling point of water at the operating pressure, meaning no vaporization or condensation occurs.
* **Hermetic Separation:** The plates provide a physical barrier. Mass transfer between the two streams would only occur in the event of a mechanical failure (e.g., a ruptured plate or failed gasket), leading to cross-contamination.

The only "mass transfer" that occurs over a long timescale is an undesirable one: **Fouling**. Deposition of biological matter, suspended solids, or scaling minerals (like $CaCO_3$) from the open cooling water system onto the heat exchanger plates constitutes a slow, solid-phase mass transfer that degrades thermal performance.

---

## 5. Mathematical Modelling Equations

To mathematically model 329-E-004 (e.g., for performance monitoring or an Operator Training Simulator), the system is modeled as a counter-current liquid-liquid heat exchanger.

### A. Global Energy Balances
The steady-state heat duty ($Q$, in Watts) transferred between the two loops must balance (assuming negligible heat loss to the environment):

$$Q = \dot{m}_{tw} \cdot C_{p,tw} \cdot (T_{tw,in} - T_{tw,out})$$
$$Q = \dot{m}_{cw} \cdot C_{p,cw} \cdot (T_{cw,out} - T_{cw,in})$$

*Where:*
* $\dot{m}_{tw}, \dot{m}_{cw}$ = Mass flow rates of the tempered water and main cooling water (kg/s).
* $C_{p,tw}, C_{p,cw}$ = Specific heat capacities of the respective water streams (J/kg·K).
* $T_{in}, T_{out}$ = Inlet and outlet temperatures (K or $^\circ\text{C}$).

### B. Heat Transfer Rate Equation
The total heat transferred is governed by the standard design equation:

$$Q = U \cdot A \cdot \Delta T_{LMTD}$$

*Where:*
* $A$ = Total effective heat transfer area of the plates (m²).
* $U$ = Overall heat transfer coefficient (W/m²·K).
* $\Delta T_{LMTD}$ = Log Mean Temperature Difference for strictly counter-current flow:

$$\Delta T_{LMTD} = \frac{(T_{tw,in} - T_{cw,out}) - (T_{tw,out} - T_{cw,in})}{\ln \left( \frac{T_{tw,in} - T_{cw,out}}{T_{tw,out} - T_{cw,in}} \right)}$$

### C. Overall Heat Transfer Coefficient ($U$)
For a plate heat exchanger, the $U$-value is calculated by summing the thermal resistances:

$$\frac{1}{U} = \frac{1}{h_{tw}} + R_{f,tw} + \frac{t_p}{k_p} + R_{f,cw} + \frac{1}{h_{cw}}$$

*Where:*
* $h_{tw}, h_{cw}$ = Convective heat transfer coefficients of the fluid boundary layers (W/m²·K).
* $R_{f,tw}, R_{f,cw}$ = Fouling factors for the tempered water and open cooling water sides (m²·K/W).
* $t_p$ = Plate thickness (m).
* $k_p$ = Thermal conductivity of the plate material (W/m·K).

### D. Convective Heat Transfer Correlations
To dynamically model $h_{tw}$ and $h_{cw}$, empirical Nusselt number ($Nu$) correlations specific to the chevron angle of the corrugated plates must be used. A generalized form for PHEs is:

$$Nu = C \cdot Re^m \cdot Pr^n \cdot \left( \frac{\mu_{bulk}}{\mu_{wall}} \right)^{0.14}$$

By defining the Nusselt number, the convective coefficient is extracted:
$$h = \frac{Nu \cdot k_{fluid}}{D_h}$$

*Where:*
* $Re$ = Reynolds number (characterizing fluid turbulence based on channel velocity).
* $Pr$ = Prandtl number (ratio of momentum diffusivity to thermal diffusivity).
* $C, m, n$ = Empirical constants based on the plate geometry (chevron angle $\beta$).
* $\mu$ = Dynamic viscosity of water at bulk and wall temperatures.
* $k_{fluid}$ = Thermal conductivity of the water.
* $D_h$ = Hydraulic diameter of the flow channel between plates ($D_h \approx 2 \times \text{channel gap}$).

By continuously solving these equations using live DCS data, operations can track the degradation of the $U$-value over time, indicating exactly when 329-E-004 must be taken offline for mechanical cleaning (plate brushing) to restore the HP Scrubber's condensing capacity.

---
*End of Technical Reference*