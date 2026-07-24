# Stamicarbon Urea Process Equipment Report

This report provides a technical review of the role, operational principles, and mechanical data for two critical assets deployed in the Stamicarbon urea production process: the **HP Ammonia Pump ($321\text{P}002\text{ A/B}$)** and the **NH3 Intermediate Tank ($321\text{D}003$)**.

---

## 1. High-Pressure Ammonia Pump ($321\text{P}002\text{ A/B}$)

### Role and Operation in the Stamicarbon Process
In a Stamicarbon synthesis loop, ammonia ($\text{NH}_3$) and carbon dioxide ($\text{CO}_2$) are reacted at high pressures to form ammonium carbamate, which is subsequently dehydrated to yield urea. Because the reactor operates at high synthesis pressures, liquid ammonia must be elevated from storage or recovery pressures up to full synthesis pressure.

[cite_start]The $321\text{P}002\text{ A/B}$ unit is a high-pressure, reciprocating plunger pump engineered for this severe service[cite: 13, 109, 539]. [cite_start]Liquid ammonia is a volatile, liquefied gas [cite: 573, 576] [cite_start]with zero lubrication properties and a high vapor pressure ($10.135\text{ bar(a)}$ at normal operating temperatures)[cite: 581, 588]. [cite_start]To prevent flashing, cavitation, and structural dynamic failure caused by pressure pulsations typical of reciprocating positive displacement pumps, the pump is integrated with a suction stabilizer ($321\text{P}002\text{AD}01$) [cite: 517] [cite_start]and a discharge resonator ($321\text{P}002\text{AD}02$)[cite: 517]. 

[cite_start]Flow regulation is managed via a variable-speed drive system [cite: 694] [cite_start]consisting of an electric motor [cite: 563] [cite_start]coupled to a hydraulic torque converter [cite: 517] [cite_start]and a reduction gearbox[cite: 517]. Adjusting the plunger stroke speed controls the precise molar dosing of ammonia into the high-pressure synthesis section to maintain the optimal Nitrogen-to-Carbon feed ratio.

### Technical Specification & Operating Conditions

* [cite_start]**Equipment Identification:** HP Ammonia Pump ($321\text{P}002\text{ A/B}$) [cite: 13, 109]
* [cite_start]**Service Configuration:** 1 Operating / 1 Stand-by ($321\text{P}002\text{ A}$ and $321\text{P}002\text{ B}$) [cite: 546, 547]
* [cite_start]**Manufacturer & Model:** PERONI POMPE SPA — Model PTO $190140 \times 205$ [cite: 113, 149]

#### Process & Fluid Design Data
* [cite_start]**Fluid Profile:** Liquefied Ammonia Gas [cite: 573, 576] (Toxic, Corrosive to Copper/Copper Alloys) [cite_start][cite: 617, 638]
* [cite_start]**Fluid Properties:** * Normal Operating Temperature: $25^\circ\text{C}$ [cite: 581]
    * [cite_start]Liquid Density: $605\text{ kg/m}^3$ [cite: 591, 592]
    * [cite_start]Viscosity: $0.115\text{ mPa}\cdot\text{s}$ [cite: 595]
    * [cite_start]Vapor Pressure: $10.135\text{ bar(a)}$ [cite: 587, 588]
* [cite_start]**Volumetric Capacity:** * Rated: $82\text{ m}^3/\text{h}$ [cite: 1119]
    * [cite_start]Normal: $67.1\text{ m}^3/\text{h}$ [cite: 621]
    * [cite_start]Minimum: $20.13\text{ m}^3/\text{h}$ [cite: 621]
* [cite_start]**Pressure Bounds:** * Suction Pressure (Normal): $20\text{ bar(a)}$ [cite: 621]
    * [cite_start]Discharge Pressure (Normal): $165\text{ bar(a)}$ [cite: 621] [cite_start]/ Rated: $180\text{ bar(a)}$ [cite: 621]
    * [cite_start]Safety Valve Set Pressure: $199\text{ bar(g)}$ [cite: 621]
* [cite_start]**Hydraulic Performance:** * Volumetric Efficiency ($\eta_v$): $95\%$ [cite: 726]
    * [cite_start]Mechanical Efficiency ($\eta_m$): $91.5\%$ [cite: 726]
    * [cite_start]Net Positive Suction Head Available ($\text{NPSHA}$): $135\text{ m}$ to $139\text{ m}$ [cite: 621]
    * [cite_start]Net Positive Suction Head Required ($\text{NPSHR}$): $10\text{ m}$ [cite: 726, 1119]

#### Mechanical Construction Features
* [cite_start]**Pump Topology:** Horizontal 3-Plunger (Triplex) Reciprocating Pump [cite: 772]
* [cite_start]**Geometrical Parameters:** * Plunger Diameter: $140\text{ mm}$ [cite: 772]
    * [cite_start]Stroke Length: $205\text{ mm}$ [cite: 772]
    * [cite_start]Average Plunger Velocity: $1.04\text{ m/s}$ [cite: 772] (Max limit: $1.5\text{ m/s}$) [cite_start][cite: 689].
* [cite_start]**Crankshaft Speed Profile:** * Rated Speed: $152\text{ rpm}$ [cite: 726]
    * [cite_start]Normal: $124\text{ rpm}$ [cite: 726]
    * [cite_start]Minimum: $37\text{ rpm}$ [cite: 726]
* [cite_start]**Load Metrics:** Allowable Plunger Load: $355\text{ kN}$ [cite: 772][cite_start], Max Design Load: $270\text{ kN}$[cite: 772].
* [cite_start]**Shaft Power Requirements:** * Rated Pump Shaft Power: $400\text{ kW}$ [cite: 726]
    * [cite_start]Driver Power Requirement at Safety Valve Condition: $548\text{ kW}$ [cite: 726]
    * [cite_start]Recommended Motor Shaft Rating: $575\text{ kW}$ [cite: 726, 1484]
* [cite_start]**Drive Train Components:** * *Motor:* Provided by Uhde [cite: 170]
    * [cite_start]*Torque Converter:* VOITH Turbo GmbH — Model EL 10 [cite: 1466] (Speed adjustment window: $25\%$ to $100\%$) [cite_start][cite: 1470, 1471]. [cite_start]Efficiency range: $50\%$ to $80\%$[cite: 1481, 1482].
    * [cite_start]*Gear Reducer:* Flender — Model H2SH12 [cite: 1506, 1507] ($1:9.716$ gear ratio) [cite_start][cite: 1544]. [cite_start]Max continuous torque capability: $61,200\text{ Nm}$[cite: 1514].
* [cite_start]**Materials of Construction (No Copper or Copper Alloys Permitted):** [cite: 638, 726]
    * [cite_start]*Manifold:* Carbon Steel A350LF2 [cite: 727]
    * [cite_start]*Stuffing Boxes (Cylinder):* Forged Steel A711 Gr 4140 [cite: 727]
    * [cite_start]*Plungers:* Stainless Steel AISI 420 with Chromium Carbide Coating [cite: 727]
    * [cite_start]*Valves and Seats:* Stainless Steel AISI 304 with Stellite cladding [cite: 727]
    * [cite_start]*Packing Rings:* PTFE + Kevlar + Graphite matrix [cite: 727] (flushed by steam condensate) [cite_start][cite: 632].
* [cite_start]**Nozzle Connection Index:** * Suction Flange: DN 150, PN 40, Type DIN 2635 Flange Face D [cite: 735]
    * [cite_start]Discharge Flange: DN 100, PN 250, Type DIN 2628 Lens Ring Face L [cite: 735]

---

## 2. Liquid Ammonia Intermediate Tank ($321\text{D}003$)

### Role and Operation in the Stamicarbon Process
The Liquid Ammonia Intermediate Tank ($321\text{D}003$) serves as a surge, buffer, and degasification vessel situated on the low-pressure boundary of the synthesis loop infrastructure. It stabilizes incoming liquid ammonia recovered from the downstream low-pressure condensation and recycling networks, or fresh feed from battery limits, before it is pumped by the high-pressure injection pumps ($321\text{P}002\text{ A/B}$).

[cite_start]Operating at a design pressure of $30\text{ bar(g)}$ [cite: 3570] [cite_start]and insulated to handle low-temperature thermal transients down to $-33^\circ\text{C}$[cite: 3570], this vessel cushions pressure spikes and ensures a steady static suction head ($\text{NPSHA}$) to prevent vapor-lock or cavitation in the high-pressure plunger heads.

### Technical Specification & Design Data

* [cite_start]**Equipment Identification:** NH3 Intermediate Tank ($321\text{D}003$) [cite: 3516, 3518]
* [cite_start]**Design Classification:** ASME Section VIII, Division 1, Edition 2001, Addenda 2003 [cite: 3086] (Classification Group 4 Pressure Vessel) [cite_start][cite: 4067].
* [cite_start]**Vessel Construction Geometry:** Vertical Cylindrical Shell [cite: 3570] [cite_start]supported by a steel skirt structure[cite: 3179, 3580].

#### Process Design & Design Thresholds
* [cite_start]**Process Fluid:** Liquid Ammonia [cite: 3570]
* [cite_start]**Density Profile:** Fluid Matrix Liquid Phase Density: $604.82\text{ kg/m}^3$ [cite: 3570]
* [cite_start]**Operating Baselines:** Operating Pressure: $26.0\text{ bar(a)}$ [cite: 3570] ($20.58\text{ bar(g)[cite_start]}$) [cite: 3095][cite_start], Operating Temperature: $25.0^\circ\text{C}$[cite: 3570].
* [cite_start]**Design Envelopes:** Design Pressure: $30.0\text{ bar(g)}$ [cite: 3570][cite_start], Design Temperature Zone: $-33.0^\circ\text{C}$ to $+65.0^\circ\text{C}$[cite: 3570].
* [cite_start]**Joint Performance:** Joint Efficiency Factor: $0.85$ [cite: 3105, 3574][cite_start], Corrosion Allowance: $3.0\text{ mm}$ [cite: 3574][cite_start], Post-Weld Heat Treatment ($\text{PWHT}$): Required/Yes[cite: 3101, 3574].
* [cite_start]**Geometric Volume Metrics:** Shell Outer Diameter: $1000\text{ mm}$ [cite: 3570][cite_start], Shell Inside Diameter: $970\text{ mm}$ [cite: 3570][cite_start], Height of Shell (Cylindrical): $1400\text{ mm}$[cite: 3570].

#### Structural Material Distribution
* **Pressure Boundary Shell & Heads:** Carbon Steel Plate SA516 Gr. [cite_start]70 [cite: 3236, 3574]
* [cite_start]**Nozzle Flanges:** Low Temperature Forged Carbon Steel SA350 LF2 [cite: 3574]
* **Nozzle Structural Pipes:** Low Temperature Seamless Carbon Steel SA333 Gr. [cite_start]6 [cite: 3189, 3574]
* **Skirt Shell Base:** Carbon Steel SA516 Gr. [cite_start]70 [cite: 3171, 3580]
* [cite_start]**Main External Fasteners:** Studs SA320 B7 paired with Heavy Hex Nuts SA194 4 [cite: 3574] (validated for impact testing down to $-33^\circ\text{C}$) [cite_start][cite: 3584].
* [cite_start]**Main Flange Seal Gaskets:** Spiral Wound Gasket (Graphite matrix with Stainless Steel inner and outer retention rings)[cite: 3583].
* [cite_start]**Vessel Weights:** Empty Shipping/Delivery Weight: $1750\text{ kg}$ [cite: 3574][cite_start], Operating Weight filled with process medium: $2570\text{ kg}$ [cite: 3574][cite_start], Full Water-Filled Hydrostatic Test Weight: $3100\text{ kg}$[cite: 3123, 3574].

#### [cite_start]Nozzle Schedule Summary [cite: 3594]

| Nozzle Symbol | Process Description | Nominal Size (DN) | Pressure Rating (PN) | Flange Facing Spec | Orientation Angle |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **N1** | NH3 Inlet | $150\text{ mm}$ | PN 40 | DIN 2635 Face D | [cite_start]$120^\circ$ [cite: 3727] |
| **N2** | NH3 Outlet | $150\text{ mm}$ | PN 40 | DIN 2635 Face D | [cite_start]$230^\circ$ [cite: 3713] |
| **N3A/B** | Skirt Vent | $65\text{ mm}$ | — | — | [cite_start]$135^\circ / 315^\circ$ [cite: 3707, 3725] |
| **N4** | Drain | $50\text{ / }25\text{ mm}$ | PN 40 | DIN 2635 Face D | [cite_start]$180^\circ$ [cite: 3730] |
| **N5** | Manhole | $600\text{ mm}$ | — | [cite_start]WN Male/Female [cite: 3603] | [cite_start]$90^\circ$ [cite: 3724] |
| **N6** | NH3 Outlet | $50\text{ / }25\text{ mm}$ | PN 40 | DIN 2635 Face D | [cite_start]Center Axis [cite: 3709] |
| **N7A/B** | LIS 321501 | $50\text{ / }25\text{ mm}$ | PN 40 | DIN 2635 Face D | [cite_start]$150^\circ$ [cite: 3731] |
| **N8** | SV (Safety Valve) | $80\text{ mm}$ | PN 40 | DIN 2635 Face D | [cite_start]Off-Center Axis [cite: 3719] |
| **N9** | NH3 Inlet | $100\text{ mm}$ | PN 40 | DIN 2635 Face D | [cite_start]$255^\circ$ [cite: 3710] |
| **N10** | Skirt Manway | $500\text{ mm}$ | — | — | [cite_start]$90^\circ$ [cite: 3724] |
| **N11** | Spare (with Blind Flange) | $80\text{ mm}$ | PN 40 | DIN 2635 Face D | [cite_start]$200^\circ$ [cite: 3734] |
| **N12** | TW 321001 (Thermowell) | $50\text{ mm}$ | PN 40 | DIN 2635 Face D | [cite_start]$185^\circ$ [cite: 3732] |
| **N13** | TW 321002 (Thermowell) | $50\text{ mm}$ | PN 40 | DIN 2635 Face D | [cite_start]$200^\circ$ [cite: 3734] |

-	“FI-321401” U/S intermediate tank “321D003” represents NH3 feed flow from BL
-	“321D003” – Intermediate Tank – (Feed: NH3 from BL). (Discharge: Feed to HP NH3 pumps 321P002 A/B), 
“TI-321001” temp. of NH3 inside “321D003”
-	XV-321901 (D/S “321D003) and (U/S HP NH3 pumps 321P002 A/B)
-	“PI-321201” 321P002A suction pressure
-	”PI-321202” 321P002B suction pressure
-	HP NH3 pump A “321P002 A” 
-	“SIC-321950 controls 321P002A speed which in turn controls the flow of NH3
-	HP NH3 pump B “321P002B”
-	“SIC-321951” controls 321P002B speed which in turn controls the flow of NH3
-	 Both “321P002A” and “321P002B” pumps: Feed: NH3 from “321D003”  Discharge: NH3 to “322F001” (HP Ejector),
