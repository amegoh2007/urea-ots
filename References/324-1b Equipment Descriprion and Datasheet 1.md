# **Comprehensive Engineering Analysis of Stamicarbon Urea Evaporation and Fluid Handling Systems**

## **1\. Introduction to the Stamicarbon Total-Recycle Urea Production Process**

The commercial synthesis and refinement of urea constitute one of the most critical pillars of the global agricultural and chemical manufacturing sectors. The modern production of urea is predicated on a two-stage chemical reaction pathway involving the highly exothermic formation of intermediate ammonium carbamate from ammonia and carbon dioxide, followed by the slower, endothermic dehydration of the ammonium carbamate to form urea and water. The Stamicarbon total-recycle $CO\_2$ stripping process is an industry-standard, state-of-the-art methodology engineered to maximize the conversion efficiency of these reactions while simultaneously minimizing utility energy consumption, limiting equipment corrosion, and maintaining exceptional product quality. In this advanced process, unconverted reactants are continuously stripped from the reactor effluent using high-pressure gaseous carbon dioxide and recycled back to the synthesis loop, ensuring near-complete utilization of the raw feedstock.  
Following the high-pressure synthesis and intermediate medium-pressure and low-pressure recirculation stages, the urea solution contains a significant mass fraction of water that must be removed to produce a final urea melt suitable for the downstream finishing processes, such as fluidized-bed granulation. In the standard 1750 Metric Tons Per Day (MTPD) capacity configuration (which can operate up to 2000 MTPD for the granulation unit), this critical moisture removal is accomplished via a highly optimized, two-stage vacuum evaporation sequence. The aqueous urea solution initially enters the evaporation section at approximately 80% concentration by weight. The first stage evaporator concentrates the solution to approximately 95% by weight, after which it flows gravitationally and under differential pressure to the second stage evaporator (Evaporator II).  
The second stage evaporation system is designed to achieve a final urea melt concentration of 98.6 wt%, a stringent and non-negotiable requirement for the downstream fluidized-bed granulation process to function correctly. This deep concentration is achieved under extreme vacuum conditions to artificially suppress the boiling point of the urea solution. Maintaining a low boiling temperature is a critical process engineering constraint in urea manufacturing, as elevated temperatures exponentially accelerate the dimerization of urea into biuret ($2 NH\_2CONH\_2 \\rightleftharpoons NH\_2CONHCONH\_2 \+ NH\_3$), an undesirable byproduct that exhibits severe phytotoxic properties in agricultural applications and degrades the structural integrity of the final granulated product.  
This report provides an exhaustive, multi-disciplinary technical analysis of three critical interconnected components within this final concentration phase: Evaporator II (324E003), Separator Evaporator II (324F003), and the Urea Feed Pump (335P001 A/B). Through the integration of original equipment manufacturer (OEM) datasheets, process flow diagrams (PFDs), piping and instrumentation diagrams (P\&IDs), distributed control system (DCS) logic, and operational narratives, this analysis rigorously maps the thermodynamic boundaries, fluid dynamic profiles, mass and heat transfer phenomena, and advanced control architectures governing the system.

## **2\. Process Flow Streams, Compositions, and Utility Tracking**

A fundamental requirement for the thermodynamic modeling and operational oversight of the Stamicarbon evaporation section is the precise mapping of all process flow streams, including their detailed chemical compositions, mass flow rates, and operating properties. The 1750 MTPD baseline process generates highly specific stream characteristics that must be tightly controlled to prevent premature crystallization, biuret formation, or excessive vapor entrainment.

### **2.1 Urea Solution and Process Intermediates**

The progression of the urea solution through the synthesis, recirculation, and evaporation stages results in distinct compositional shifts. The data extracted from the process flow diagrams (PFD No. 20 and related tables) outlines the exact molar and weight compositions of the key process streams leading up to and transitioning through the evaporation section.  
**Table 1: Process Stream Compositions and Fluid Properties**

| Stream Number | Stream Description | Biuret (wt%) | CO₂ (wt%) | H₂O (wt%) | NH₃ (wt%) | O₂ (wt%) | Urea (wt%) |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| **311** | Urea Solution | 0.28 | 3.31 | 27.16 | 4.94 | Not Spec. | 64.31 |
| **313** | Urea Solution | 0.28 | 2.88 | 28.11 | 4.48 | Not Spec. | 64.26 |
| **314** | Urea Solution | 0.36 | 1.05 | 27.72 | 2.13 | 0.40 | 68.74 |
| **954** | Condensate | Not Spec. | Not Spec. | 100.00 | Not Spec. | Not Spec. | Not Spec. |

Data sourced from Process Flow Diagram No. 20, 1750 MTPD Configuration. Note: Molecular weights utilized for compositional analysis are Biuret: 103.081, CO₂: 44.0098, H₂O: 18.0152, NH₃: 17.0304, O₂: 31.9988, Urea: 60.056. While certain streams such as 315, 317, 319, 901, 902, 903, 904, 905, 906, 907, 914, and 916 are integral to the broader piping network, their specific thermodynamic parameters are omitted from the primary baseline dataset, requiring them to be inferred via mass balance continuity across the upstream unit operations.  
Stream 314 represents a critical node in the system, reflecting the urea solution as it progresses toward the evaporation phase. At 68.74 wt% urea and 27.72 wt% water, the solution is still highly aqueous. The presence of 2.13 wt% ammonia and 1.05 wt% carbon dioxide indicates residual unconverted reactants that have not been fully stripped in the upstream rectifying columns. These volatile components will flash off during the subsequent vacuum evaporation stages, requiring robust condensation and scrubbing systems to recover the ammonia and prevent environmental emissions. The biuret concentration at this stage is maintained at a very low 0.36 wt% , leaving a small operational margin to reach the maximum allowable limit of 1.0 wt% in the final granulated product. Stream 954 is tracked as pure process condensate (100% water), which is utilized extensively throughout the plant for flushing, desuperheating, and sealing applications.

### **2.2 Cooling and Circulating Water Balances**

The operation of the vacuum condensation systems, which are inextricably linked to the evaporators, requires immense volumes of cooling water. The efficiency of the vacuum ejectors and surface condensers dictates the absolute pressure that can be maintained over the boiling urea solution. Therefore, tracking the cooling water balance is paramount for plant stability.  
**Table 2: Comprehensive Cooling Water (CW) and Circulating Water Balance**

| Stream No. | Description | Mass Flow (to/h) | Operating Temp (°C) | Operating Pressure (bar a) |
| :---- | :---- | :---- | :---- | :---- |
| **1001** | Main CW Supply | 4,847 | 30.0 | 4.7 |
| **1002** | CW Branch Supply | 15 | 30.0 | 3.6 |
| **1003** | CW Branch Return | 15 | 34.0 | 2.2 |
| **1004** | CW Branch Supply | 10 | 30.0 | 3.6 |
| **1005** | CW Branch Return | 10 | 30.0 | 2.2 |
| **1006** | CW to Major Exch. | 462 | 30.0 | 3.6 |
| **1007** | CW from Major Exch. | 462 | 40.0 | 2.2 |
| **1008** | CW to Major Condenser | 1,095 | 30.0 | 3.6 |
| **1009** | CW from Major Condenser | 1,095 | 40.0 | 2.2 |
| **1010** | CW Branch Supply | 14 | 30.0 | 3.6 |
| **1011** | CW Branch Return | 14 | 40.0 | 2.2 |
| **1012** | CW Branch Supply | 302 | 30.0 | 3.6 |
| **1013** | CW Branch Return | 302 | 40.0 | 2.2 |
| **1014** | CW to Primary Condenser | 1,591 | 30.0 | 3.6 |
| **1015** | CW from Primary Condenser | 1,591 | 40.0 | 2.2 |
| **1016** | CW Branch Supply | 415 | 30.0 | 3.6 |
| **1017** | CW Branch Return | 415 | 34.0 | 2.2 |
| **1018** | CW Branch Supply | 208 | 30.0 | 3.6 |
| **1019** | CW Branch Return | 208 | 35.0 | 2.2 |
| **1020** | CW Branch Supply | 23 | 30.0 | 3.6 |
| **1021** | CW Branch Return | 23 | 35.0 | 2.2 |
| **1028** | CW Branch Supply | 408 | 30.0 | 3.6 |
| **1029** | CW Branch Return | 408 | 38.0 | 2.2 |
| **1030** | CW Branch Supply | 230 | 30.0 | 3.6 |
| **1031** | CW Branch Return | 230 | 40.0 | 2.2 |
| **1032** | CW Branch Supply | 15 | 30.0 | 3.6 |
| **1033** | CW Branch Return | 15 | 40.0 | 2.2 |
| **1036** | CW Branch Supply | 50 | 30.0 | 2.2 |
| **1037** | CW Branch Return | 50 | 40.0 | 2.2 |
| **1050** | Main CW Return | 4,847 | 39.0 | 2.2 |
| **1051** | CW System Booster | 4,865 | 39.0 | 2.5 |
| **1102** | Circ. Water High Flow | 1,094 | 55.0 | 2.5 |
| **1103** | Circ. Water High Flow Ret. | 1,094 | 65.0 | 1.5 |
| **1111** | Circ. Water High Temp | 306 | 80.0 | 9.0 |
| **1112** | Circ. Water High Temp Ret. | 306 | 95.0 | 8.0 |
| **1351** | CW Branch Supply | 10 | 30.0 | 4.7 |
| **1352** | CW Branch Return | 10 | 40.0 | 2.2 |
| **742A** | Purge Process Condensate | 18 | 89.0 | 3.9 |

Data sourced from PFD No. 28 \- Cooling Water Balance.  
The cooling water network is anchored by Stream 1001, which supplies a massive 4,847 tonnes per hour of cooling water at 30°C and 4.7 bar a. This water is distributed across numerous parallel heat exchangers. Streams 1014 and 1015 represent the largest individual consumer in this loop, utilizing 1,591 to/h to condense process vapors, resulting in a temperature rise from 30°C to 40°C. Streams 1008 and 1009 also carry a highly significant 1,095 to/h load. The strict control of these cooling water temperatures is vital; if the supply temperature exceeds 30°C due to ambient conditions or cooling tower limitations, the vacuum condensers (e.g., 324E002, 324E005) will lose efficiency, the absolute pressure in the evaporators will rise, and the urea boiling temperature will subsequently increase, drastically accelerating biuret formation.  
The circulating water streams (1102/1103 and 1111/1112) represent closed-loop tempered water systems utilized to cool specific process nodes where direct contact with cold (30°C) water would induce thermal shock or trigger instantaneous crystallization of ammonium carbamate on the tube walls. Stream 1111, for example, operates at 80°C and 9.0 bar a, returning at 95°C and 8.0 bar a.

## **3\. Equipment Analysis: Evaporator II (324E003)**

### **3.1 Role and Functional Description**

Evaporator II (Item 324E003) is a vertical shell-and-tube heat exchanger operating as the terminal concentration unit in the urea synthesis loop. Its primary operational role is to transfer thermal energy from low-pressure (LP) steam to the approximately 95% urea solution, driving the vaporization of residual water to achieve the final 98.6 wt% urea melt. The exchanger operates in a single-pass configuration on both the shell and tube sides, utilizing a natural circulation or climbing-film mechanism. As the urea solution enters the bottom of the tubes and begins to boil, the rapid expansion of flashing water vapor accelerates the two-phase mixture upward against gravity.  
The unit is vertically oriented to facilitate this upward flow, discharging the resulting high-velocity two-phase mixture directly into the overlying Separator Evaporator II (324F003). The heating medium, LP steam, is introduced into the shell side, condensing on the outer surface of the tubes and releasing its latent heat of vaporization to the process fluid.

### **3.2 Process Flow Streams and Fluid Properties**

The mass and energy balance across Evaporator II establishes the strict thermodynamic boundaries required to concentrate the urea without inducing thermal degradation.  
**Table 3: Evaporator II (324E003) Process Stream Data**

| Parameter | Shell Side (Heating Medium) | Tube Side (Process Fluid) |
| :---- | :---- | :---- |
| **Process Fluid** | Low-Pressure (LP) Steam | Urea Solution |
| **Phase State (Inlet / Outlet)** | Vapour / Liquid | Liquid / Two-Phase (Liquid \+ Vapour) |
| **Total Mass Flow** | 4,574 kg/h | 85,847 kg/h (Inlet) |
| **Vapour Mass Flow (Outlet)** | 0 kg/h | 3,653 kg/h |
| **Liquid Mass Flow (Outlet)** | 4,574 kg/h (Condensate) | 82,194 kg/h (Urea Melt) |
| **Operating Temperature (Inlet)** | 165.5 °C | 130.0 °C |
| **Operating Temperature (Outlet)** | 158.0 °C | 140.0 °C |
| **Operating Pressure** | 5.9 bar a | 0.13 bar a |
| **Density (Liquid)** | 909 kg/m³ | 1,200 kg/m³ |
| **Density (Vapour)** | 3.05 kg/m³ | Not Specified |

Data sourced from OEM Datasheet UD-AU-324-EC-0003.  
The mass flow parameters reveal that 85,847 kg/h of aqueous urea enters the tube side at 130°C. Through the addition of heat, 3,653 kg/h of water vapor is generated and flashes out of the liquid phase, leaving 82,194 kg/h of 98.6 wt% urea melt exiting at 140°C. The corresponding phase change relies on the condensation of 4,574 kg/h of LP steam on the shell side, dropping from 165.5°C to 158.0°C.

### **3.3 Mechanical Design and Material Specification**

The mechanical design of Evaporator II complies with AD-Merkblätter codes, a strict European standard for pressure vessel design, ensuring structural integrity under both internal pressure and full vacuum conditions.  
**Table 4: Evaporator II (324E003) Mechanical Specifications**

| Component | Specification | Material | Remarks |
| :---- | :---- | :---- | :---- |
| **Tubes** | 333 tubes, 38.1 mm OD x 1.65 mm wall | BC.09 (Stainless) | Full penetration welds required |
| **Tube Length** | 1,400 mm effective | BC.09 | \- |
| **Shell** | 1,000 mm OD | AA.01 / BB.01 | Carbon steel lined with BB.01 |
| **Tube Pitch** | 48 mm | \- | \- |
| **Baffles / Supports** | 0 Baffles / 1 Tube Support | BB.01 | Prevents flow-induced vibration |
| **Design Pressure** | 11 bar g / \-1 bar g (Shell) | 6 bar g / \-1 bar g (Tube) | Full vacuum rated |
| **Design Temperature** | 190 °C | 190 °C | Exceeds max operating temp |
| **Leakage Class** | DK3 | \- | High integrity boundary |
| **Weight** | 4,350 kg (Operating) / 4,170 kg (Test) | \- | \- |

Data sourced from OEM Datasheet UD-AU-324-EC-0003.  
The materials designated as BB.01 and BC.09 must strictly conform to Stamicarbon material specification 18005\. This specification dictates the use of highly specialized austenitic stainless steels (such as 316L Urea Grade or 25-22-2 Cr-Ni-Mo alloys) engineered with precise elemental tolerances to withstand the severely corrosive nature of ammonium carbamate and high-temperature urea solutions. On the tube side, the specifications mandate that all welds in direct contact with the process medium must be full penetration welds to eliminate crevices where stagnant corrosive liquids could accumulate and initiate localized pitting or stress corrosion cracking.

### **3.4 Overall Heat Transfer Coefficient ($U$) and Duty**

The overall heat transfer coefficient ($U$) is a critical thermodynamic metric for evaluating the performance, sizing, and lifecycle fouling degradation of the evaporator. The total thermal duty ($Q$) required by the process and provided by the equipment is 2,676 kW.  
The effective heat transfer area ($A$) can be derived from the fundamental tube geometry provided in the datasheet:  
$A \= \\pi \\cdot D\_o \\cdot L \\cdot N$  
$A \= \\pi \\cdot 0.0381 \\, \\text{m} \\cdot 1.4 \\, \\text{m} \\cdot 333 \= 55.8 \\, \\text{m}^2$  
To calculate the design overall heat transfer coefficient, the logarithmic mean temperature difference ($\\Delta T\_{LM}$) must be established based on the shell and tube terminal temperatures:

* $T\_{h,in} \= 165.5^\\circ\\text{C}$ (Steam in)  
* $T\_{h,out} \= 158.0^\\circ\\text{C}$ (Condensate out)  
* $T\_{c,in} \= 130.0^\\circ\\text{C}$ (Urea in)  
* $T\_{c,out} \= 140.0^\\circ\\text{C}$ (Urea out)

$\\Delta T\_1 \= 165.5 \- 140.0 \= 25.5^\\circ\\text{C}$  
$\\Delta T\_2 \= 158.0 \- 130.0 \= 28.0^\\circ\\text{C}$  
$\\Delta T\_{LM} \= \\frac{28.0 \- 25.5}{\\ln(28.0 / 25.5)} \= \\frac{2.5}{0.0935} \\approx 26.73^\\circ\\text{C}$  
With the duty, area, and temperature gradient established, the operational design overall heat transfer coefficient ($U\_{design}$) is calculated as:  
$U\_{design} \= \\frac{Q}{A \\cdot \\Delta T\_{LM}} \= \\frac{2,676,000 \\, \\text{W}}{55.8 \\, \\text{m}^2 \\cdot 26.73 \\, \\text{K}} \\approx 1,795.3 \\, \\text{W/m}^2\\text{K}$  
In Stamicarbon urea evaporator designs, the theoretical clean overall heat transfer coefficient ($U\_{clean}$) is typically on the order of 2,500 W/m²K. The shell-side steam condensation provides a highly efficient convective boundary layer with a localized film coefficient of $h\_{steam} \\approx 15,000$ W/m²K, while the tube-side boiling urea solution offers a primary thermal resistance with a convective coefficient of approximately $h\_{urea} \\approx 6,000$ W/m²K.  
The discrepancy between the theoretical 2,500 W/m²K clean value and the calculated design operating value of \~1,795 W/m²K indicates the engineering inclusion of a substantial fouling factor and thermal design margin. This conservative margin ensures that the evaporator can continue to meet the 2,676 kW duty requirement even after prolonged operational campaigns inevitably initiate scaling and organic fouling on the inner tube surfaces, guaranteeing sustained production capacity between scheduled maintenance turnarounds.

### **3.5 Instrumentation and Cascade Control Architecture**

The thermal control of Evaporator II is governed by an advanced cascade control architecture designed to maintain strict temperature limits with minimal overshoot. The primary process variable is the outlet temperature of the urea melt, which must not exceed 140°C to inhibit the exponential kinetics of biuret formation.

* **Primary Temperature Control (TIC324002):** A temperature indicating controller constantly monitors the urea melt exiting the evaporator.  
* **Secondary Pressure Control Cascade (PIC324212):** Rather than allowing TIC324002 to directly modulate a steam valve—which would render the system highly susceptible to upstream fluctuations in the plant's steam grid—TIC324002 outputs a dynamic setpoint to a slave pressure controller, PIC324212. PIC324212 directly measures and regulates the pressure in the MP steam supply header feeding the shell side of 324E003. If the steam header pressure transiently drops, PIC324212 immediately opens the steam supply valve to compensate, neutralizing the disturbance long before the thermal deficit can propagate through the tube walls and register as a temperature drop on TIC324002. This nested cascade arrangement provides ultra-tight thermal adherence, preventing the temperature spikes that would irreversibly degrade product quality.

## **4\. Equipment Analysis: Separator Evaporator II (324F003)**

### **4.1 Role and Functional Description**

Immediately following the sensible and latent heat addition in 324E003, the highly turbulent, two-phase mixture of concentrated urea melt and flashed water vapor enters the Separator Evaporator II (324F003). This unit functions as an advanced flash vessel, physically disengaging the vapor phase from the heavy urea melt under deep vacuum. Operating at 0.131 bar a (absolute), the internal low pressure allows the residual water to vaporize aggressively at 140°C, well below the atmospheric boiling point of the solution.  
The internal geometry of the separator is critical to its mass transfer operation. It contains a strategically positioned vortex breaker and a funnel, colloquially referred to in the process industry as an inverted "Chinese hat". The high-velocity two-phase fluid emerging from the evaporator tubes impacts these internals, promoting the agglomeration of liquid droplets through impingement coalescence. The vapor decelerates due to the expanded cross-sectional area of the 2,500 mm diameter vessel and rises to the top outlet. The inverted hat specifically impedes the turbulent surging of the boiling liquid pool at the bottom of the vessel, preventing microscopic urea droplets from being entrained into the vapor stream flowing to Condenser II (324E005). Minimizing entrainment is vital, as urea carryover would severely foul the downstream condenser tubes and result in unacceptable product loss to the process condensate system.

### **4.2 Process Flow Streams and Fluid Properties**

The feed to the separator is the direct upward discharge from Evaporator II. Inside the vessel, phase separation yields two distinct discharge streams: the overhead vapor and the bottom liquid melt.  
**Table 5: Separator Evaporator II (324F003) Design Parameters**

| Parameter | Specification |
| :---- | :---- |
| **Operating Pressure** | 0.131 bar a |
| **Operating Temperature** | 140 °C |
| **Liquid Density (Urea Melt)** | 1,220 kg/m³ |
| **Vapour Density (Water/NH3/CO2)** | 0.075 kg/m³ |
| **Volume/Dimensions** | 2,500 mm OD, 1,550 mm cylindrical height |
| **Insulation** | 100 mm "Hot" Type |

Data sourced from OEM Datasheet UD-AU-324-EC-0008.  
The separated vapor leaves the top of the vessel and is condensed, forming a process condensate that is subsequently routed to the ammonia water tank for desorption and hydrolysis recovery. The deep vacuum (0.131 bar a) is generated and maintained by a sequence of high-velocity steam ejectors (324F004 and 324F005) located downstream of the condensers.

### **4.3 Nozzle Mapping and Mechanical Design**

The structural design of the separator must accommodate immense external atmospheric pressure forces due to the internal vacuum, necessitating high-integrity materials and generous wall thicknesses, despite the sub-atmospheric internal operating pressure. The vessel is fabricated from Stamicarbon-specified BB.01 stainless steel.  
**Table 6: Nozzle Schedule for Separator Evaporator II (324F003)**

| Nozzle | Designation | Size (DN) | Flange Type/Facing | Remarks |
| :---- | :---- | :---- | :---- | :---- |
| **N1** | Connection Preevaporator | \- | \- | Facing per template (direct integration from 324E003) |
| **N2** | Liquid Outlet | 350 mm | WN, D | Discharges to Urea Feed Pump 335P001 |
| **N3** | Vapour Outlet | 600 mm | STUB | Discharges to Condenser II 324E005 |
| **N6** | Heating Steam Inlet | 50 mm | WN, D | Feeds internal steam tracing coil |
| **N7** | Steam Condensate Out | 50 mm | WN, D | Internal coil condensate return |
| **N8** | Manhole | 600 mm | WN, D | Equipped with davit and blind flange; BB.01 lining |
| **N9** | Pressure Transmitter | 80 mm | WN, D | Connects to PT 324204 |
| **N12** | Steam Inlet | 15 mm | WN, D | Purge/utility connection |
| **N13** | Instrument Air Inlet | 15 mm | WN, D | Purge/utility connection |
| **N14** | Condensate Outlet | 15 mm | WN, D | Purge/utility connection |
| **N15** | Vent (Steam Condensate) | 25 mm | WN, D | Blind flanged |
| **N16** | Vent (Heating Steam) | 25 mm | WN, D | Blind flanged |
| **N17 A-D** | Vent (Skirt) | 100 mm | \- | 114.3 x 8 mm pipe extensions |

Data sourced from OEM Datasheet.  
A critical feature of the mechanical design is the internal steam heating coil (tracing coil fabricated from 1.4306 stainless steel) fed via nozzles N6 and N7. This coil prevents the highly concentrated (98.6 wt%) urea melt from crystallizing on the vessel walls during steady-state or transient operations. The solidification point of pure urea is approximately 132.6°C; therefore, maintaining localized surface temperatures above this threshold is an absolute necessity. The design specification dictates that this tracing coil is rated for 165°C steam at 6 / \-1 bar g, providing ample thermal margin to prevent cold spots within the separator body.

### **4.4 Instrumentation, Level Measurement, and Vacuum Control Loops**

The instrumentation logic architected around 324F003 is fundamentally linked to the thermodynamic requirements of urea concentration and the chemical degradation kinetics of the product.

* **Vacuum Control (PIC324203):** The internal pressure of the separator is monitored by PT 324204, mounted on nozzle N9. This transmitter feeds a pressure indicating controller (PIC324203). Rather than attempting to mechanically throttle the massive 600 mm vapor line (N3) directly—which would require an expensive, high-maintenance, and sluggish control valve—PIC324203 controls a small bleed valve (PV324203) that introduces a precisely controlled amount of atmospheric air into the vapor line upstream of Condenser II (324E005). This "false air" acts as a non-condensable gas, reducing the partial pressure of the condensable vapors and purposely degrading the condenser's overall heat transfer coefficient. By manipulating the condenser's efficiency, the controller precisely modulates the upstream vacuum in 324F003 to exactly 0.13 bar a.  
* **Level Control and Residence Time Constraint:** A standard chemical flash separator might maintain a static liquid level within the main vessel body to provide buffer capacity. However, in urea synthesis, the residence time of the melt at 140°C must be absolutely minimized to arrest the temperature-dependent biuret formation reaction. Therefore, the 350 mm liquid outlet (N2) discharges directly into a vertical drop pipe known as a barometric leg, which feeds the Urea Feed Pump (335P001).  
* Crucially, **the liquid level is not measured in the main volume of 324F003**. Instead, it is measured *inside the suction line* (the barometric leg) by a level indicating controller (LIC324501). This advanced engineering design ensures the vessel drains completely and continuously, leaving no stagnant pools of product, limiting the residence time strictly to the transit velocity through the piping network.

## **5\. Equipment Analysis: Urea Feed Pump (335P001 A/B)**

### **5.1 Role and Functional Description**

The Urea Feed Pump (335P001 A/B) serves as the primary motive force responsible for transferring the fully concentrated 98.6 wt% urea melt from the evaporation section to the fluidized-bed granulation unit (335R001). Because the granulation process relies on the precise atomization of the melt through hundreds of microscopic spray headers, the pump must deliver a highly stable, non-pulsating, high-pressure flow.  
An essential auxiliary chemical engineering function occurs directly at the suction side of this pump. Urea Formaldehyde (UF), consisting of 60.0 wt% Formaldehyde, 25.0 wt% Urea, and 15.0 wt% Water, is injected directly into the melt at the pump suction via UF dosing pumps (335P002 A/B). The formaldehyde acts as a crucial granulation aid, preventing caking of the final product and increasing the mechanical crushing strength of the solid granules. Introducing the UF at the pump suction capitalizes on the extreme turbulent shear forces generated by the pump's spinning impeller, ensuring a perfectly homogenous mixture of the additive into the highly viscous urea melt before it reaches the granulator.

### **5.2 Process Flow Streams and Fluid Properties**

The pump handles a non-Newtonian, high-temperature fluid operating precariously close to its solidification point, requiring specialized hydraulic design.  
**Table 7: Urea Feed Pump (335P001 A/B) Operating Data**

| Parameter | Value |
| :---- | :---- |
| **Fluid Pumped** | Urea Melt (98.5 \- 98.6 wt%) |
| **Operating Temperature** | 140 °C |
| **Fluid Density** | 1,221 kg/m³ |
| **Dynamic Viscosity** | 2.22 cP |
| **Rated Capacity** | 82.0 m³/h |
| **Normal Capacity** | 70.5 m³/h |
| **Suction Pressure (Rated / Normal)** | 0.95 bar a / 0.60 bar a |
| **Discharge Pressure (Rated / Normal)** | 8.75 bar a / 6.65 bar a |
| **Differential Head (Rated / Normal)** | 65.2 m / 50.5 m |
| **Fluid Vapour Pressure** | 0.13 bar a |

Data sourced from OEM Datasheet UD-AU-335-EC-0039.

### **5.3 Pump Hydraulics, Mechanical Design, and NPSH Analysis**

The pump supplied by KSB (Model CPK-CHXYD 80-250, manufactured in Pegnitz, Germany) is a horizontal, radially split, single-stage, single-entry centrifugal process pump featuring a heavy-duty back-pull-out design. This structural design, compliant with API 610 and EN ISO 5199 (Class II) standards, permits maintenance personnel to extract the entire rotating assembly (impeller, shaft, seals, and bearing housing) from the rear without disturbing the suction or discharge casing piping. This capability is highly advantageous given the extensive, rigid steam tracing and jacketing wrapped around the urea piping to prevent crystallization; dismantling piping for pump maintenance would be economically prohibitive and technically hazardous. The unit utilizes a single mechanical seal designed to API 682, 4th edition, Category 1 specifications, providing a dynamic barrier against the 140°C melt.  
The hydraulic performance curve of the CPK 80-250 can be conceptually reconstructed based on the datasheet parameters. The pump is driven by a 37 kW electric motor operating at a synchronous speed of 2,955 rpm, utilizing a radial impeller trimmed to an operational diameter of 212 mm (with a maximum allowable trim of 260 mm and a minimum of 200 mm).

* **System vs. Pump Curve Dynamics:** The datasheet lists a rated flow of 82 m³/h producing a differential head of 65.2 m, requiring 29.5 kW of shaft power at a hydraulic efficiency of 60%. At the "normal" continuous flow of 70.5 m³/h, the required differential head is listed as 50.5 m. On a standard centrifugal pump performance curve, moving to the left (lower flow) typically results in a *higher* produced head. The apparent contradiction in the data (lower head at lower flow) reflects the *system resistance curve* rather than the pump's hydraulic performance curve. At the normal flow of 70.5 m³/h, the piping system and downstream spray nozzles only require 50.5 m of head; however, the pump will inherently produce approximately 68-70 m of head at this flow rate on its efficiency curve. The excess hydraulic energy (approx. 18-20 m of head) is actively dissipated across the discharge level control valve (LV324501A).  
* **NPSH Margin and Cavitation Risk:** The Net Positive Suction Head Required (NPSHr) by the pump impeller is 3.4 meters. The Net Positive Suction Head Available (NPSHa) at the normal operating point is given as 3.9 meters. The physical equation governing this is: $NPSHa \= \\frac{P\_{suction} \- P\_{vapor}}{\\rho g} \+ H\_{static} \- H\_{friction}$ Because the urea melt inside the Separator Evaporator II (324F003) is actively boiling, the fluid is precisely at its vapor pressure ($P\_{suction} \\approx P\_{vapor}$). Consequently, the thermodynamic pressure terms cancel out entirely, leaving the NPSHa almost exclusively dependent on the physical static elevation of the fluid above the pump centerline ($H\_{static}$). The extremely tight NPSH margin (0.5 m) reinforces why the level must be measured and strictly maintained in the vertical barometric suction leg. If the liquid level in the leg drops by merely half a meter, $NPSHa$ will fall below $NPSHr$, inducing spontaneous phase-change cavitation. Cavitation in a high-temperature urea melt would lead to catastrophic localized shockwave pressures, mechanical pitting of the 212 mm impeller, and immediate, catastrophic failure of the API 682 mechanical seal.

### **5.4 Instrumentation and Split-Range Control Loops**

The pump's output is governed by a highly responsive split-range level control loop intended to protect the pump from dry-running or dead-heading, while dynamically managing process disruptions in the downstream granulation unit.

* **Split-Range Control (LIC324501):** The level transmitter on the pump suction line feeds a level indicating controller (LIC324501). This single controller commands two distinct flow valves:  
  1. **LV324501A:** The forward-flow valve routing the 98.6% melt directly to the granulator distribution header.  
  2. **LV324501B:** A recycle valve that routes the melt back upstream to the Urea Solution Tank (323D002).  
* Under stable, steady-state operation, LV324501A modulates to match the pump's discharge to the exact evaporation rate of 324E003, maintaining a steady hydrostatic head in the barometric leg. If the granulation unit trips, blocks, or halts production, LIC324501 automatically forces LV324501A to close and proportionally opens LV324501B. This establishes a continuous recycle loop, keeping the pump running and the melt flowing at velocity. Stagnant urea melt would rapidly crystallize within minutes, requiring extensive and hazardous steam-lancing to clear the blocked pipes.  
* **Recycle Chemistry Constraint:** When the system operates in bypass (routing 98.6% melt back to the 80% tank), pure steam condensate must be actively injected into the recycle line. Failing to dilute the returning melt would rapidly drive the bulk concentration of the Urea Solution Tank to levels where the ambient temperature could trigger sudden, massive crystallization of the entire tank inventory, potentially causing a total plant shutdown lasting several days.

## **6\. Mathematical Modeling Considerations for Digital Twins**

For process engineers and control systems analysts seeking to develop high-fidelity digital twins or dynamic simulations of this subsection of the Stamicarbon plant (e.g., in Aspen HYSYS, Aspen Plus, or gPROMS), several phenomenological models must be integrated.

### **6.1 Thermodynamic and Phase Equilibria Modeling**

The Separator Evaporator II requires a rigorous Vapor-Liquid Equilibrium (VLE) model. The fluid is a quaternary system ($NH\_3$-$CO\_2$-$H\_2O$-Urea). Standard equations of state (EOS) like Peng-Robinson or Soave-Redlich-Kwong are wholly insufficient due to the highly non-ideal, electrolytic nature of the ammonium carbamate species in solution. An extended UNIQUAC model or an activity coefficient model like Electrolyte-NRTL (Non-Random Two-Liquid) must be parameterized specifically for the Stamicarbon phase equilibria to accurately predict the flashing of water and ammonia at 0.131 bar a and 140°C.

### **6.2 Heat Exchanger Modeling (324E003)**

The evaporator must be modeled as a distributed parameter system. The shell-side condensing steam can be modeled assuming an isothermal boundary condition, as the latent heat of vaporization dominates the energy transfer:  
$\\frac{dT\_{steam}}{dz} \\approx 0$  
On the tube side, the urea solution undergoes subcooled sensible heating followed by convective nucleate boiling. The governing energy balance along the vertical axis $z$ is:  
$\\dot{m}\_{urea} \\frac{dh}{dz} \= U(z) \\cdot \\pi \\cdot D\_o \\cdot N \\cdot (T\_{steam} \- T\_{urea}(z))$  
Where $h$ is the specific enthalpy of the two-phase mixture. The overall heat transfer coefficient $U(z)$ transitions dynamically. In the lower subcooled region, $U$ is governed by Dittus-Boelter or Sieder-Tate correlations for single-phase liquid forced convection. Once the vapor pressure of the water in the solution exceeds the local static pressure, boiling commences. In this region, Chen's correlation or the Shah correlation for flow boiling should be utilized to capture the massive enhancement in $U$ due to nucleate boiling and convective thinning of the liquid film against the tube walls.

### **6.3 Hydraulic and Mechanical Separation Modeling**

The mechanical separation efficiency in 324F003 can be modeled using the terminal settling velocity ($v\_t$) of a urea droplet in the low-density vapor field: $v\_t \= \\sqrt{\\frac{4gD\_p(\\rho\_L \- \\rho\_V)}{3 C\_d \\rho\_V}}$ Given the vapor density $\\rho\_V \= 0.075$ kg/m³ and liquid density $\\rho\_L \= 1,220$ kg/m³, the density differential is extreme. The inverted "Chinese hat" acts to artificially increase the effective droplet diameter $D\_p$ via impingement coalescence, ensuring that $v\_t$ exceeds the upward superficial vapor velocity, forcing the urea droplets to fall into the barometric leg rather than escaping through Nozzle N3.  
Dynamic modeling of the Urea Feed Pump must incorporate the pump affinity laws and the non-linear system resistance curve. The pump performance curve can be modeled as a quadratic decay:  
$H\_{pump}(Q) \= H\_{shutoff} \- K\_p Q^2$  
The dynamic system curve is:  
$H\_{sys}(Q) \= \\Delta Z \+ \\frac{\\Delta P}{\\rho g} \+ K\_v(x) Q^2$  
Here, $K\_v(x)$ represents the variable flow resistance dictated by the instantaneous stroke position $x$ of the split-range control valves LV324501A/B. In a transient simulation, integrating the rate of change of the liquid level in the barometric leg $\\frac{dL}{dt}$ with the instantaneous NPSHa will accurately predict the onset of pump cavitation if valve response times lag behind upstream flow perturbations.

## **7\. Conclusions**

The final concentration stage of the Stamicarbon total-recycle urea process represents a masterclass in highly constrained thermodynamic engineering and fluid mechanics. The exhaustive analysis of Evaporator II (324E003), Separator Evaporator II (324F003), and the Urea Feed Pump (335P001 A/B) reveals a system meticulously balanced to achieve deep water extraction while absolutely preventing thermal degradation and byproduct formation.  
By operating under a deep, artificially maintained vacuum of 0.131 bar a, the equipment successfully depresses the boiling point of the solution to 140°C, isolating the urea from the exponential reaction kinetics of biuret formation. The mechanical design reflects this intense operational environment, pairing AD-Merkblätter compliant, vacuum-rated vessels with specialized internal geometries—like the inverted vortex breaker—to maximize multiphase separation efficiency. Furthermore, the reliance on a barometric drop leg rather than a static vessel pool demonstrates a fundamental engineering prioritization of minimizing fluid residence time over traditional volumetric buffer-capacity control.  
The fluid handling architecture, centered entirely on the API 610 compliant KSB CPK 80-250 centrifugal process pump, navigates the severe hydraulic challenges of pumping a boiling, highly viscous, non-Newtonian melt with an exceptionally narrow 0.5-meter NPSH safety margin. The strategic chemical engineering decision to inject urea formaldehyde directly at the pump suction brilliantly leverages the impeller's immense kinetic shear forces to homogenize the granulation additive, thereby optimizing downstream product quality and structural strength. Ultimately, the interconnected cascade thermal controls, false-air vacuum regulation, and split-range hydraulic bypass loops form a highly resilient, fault-tolerant operational envelope, ensuring the continuous, safe, and efficient delivery of high-purity 98.6 wt% urea melt to the final granulation stage.  
