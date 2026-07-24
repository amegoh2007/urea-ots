# **Comprehensive Engineering Analysis of the Stamicarbon Urea Granulation Process: Process Streams, Instrumentation, and Equipment Dynamics**

## **1\. Introduction to the Stamicarbon Total-Recycle $CO\_2$ Stripping Process**

The production of fertilizer-grade granular urea via the Stamicarbon total-recycle $CO\_2$ stripping process represents a pinnacle of complex thermodynamic and mass transfer engineering. In this process, liquid ammonia and gaseous carbon dioxide are reacted at elevated pressures (136–143 bar) to form ammonium carbamate, which subsequently dehydrates into urea and water. The resultant urea solution is systematically purified through a series of stripping, recirculation, and evaporation stages to achieve a highly concentrated melt (98.6 wt.%) suitable for granulation.  
System 335 represents the granulation section of the plant, operating at a continuous capacity of 2,000 Metric Tons Per Day (MTPD). To ensure the final product meets stringent agricultural specifications—specifically regarding crushing strength and the prevention of caking during storage and transport—a conditioning agent, Urea-Formaldehyde (UF85) precondensate, is injected directly into the urea melt prior to the fluid bed granulator.  
This exhaustive technical report provides a rigorous analysis of the process flow streams, the mechanical and metallurgical profiles of the UF Storage Tank (335D007) and the UF Metering Pump (335P002A/B), and the overarching Distributed Control System (DCS) architecture governing the injection process. Furthermore, it delineates the mass and heat transfer phenomena occurring within the primary heat exchange equipment, quantifying the operational thermodynamics necessary for accurate process modeling.

## **2\. Exhaustive Process Flow Stream Mapping**

The precise control of the Stamicarbon process relies on a vast network of mass and energy flows. The mapping of these Original Equipment Manufacturer (OEM) stream numbers provides the empirical foundation for understanding the phase behavior and chemical equilibria throughout the synthesis, recirculation, and evaporation stages.

### **2.1 Raw Material Feed Streams**

The primary reactants, liquid ammonia ($NH\_3$) and gaseous carbon dioxide ($CO\_2$), are introduced into the synthesis loop after strict quality and pressure conditioning. Carbon dioxide is delivered from the ammonia plant and compressed to approximately 145 bar. To mitigate the highly corrosive nature of the carbamate solutions, a highly specific quantity of passivation air is injected into the $CO\_2$ stream, maintaining an oxygen content of roughly 0.6 vol.%.  
The chemical compositions of the reactant feed streams are detailed below. It is critical to observe the trace inert gases (hydrogen, methane, nitrogen), which heavily influence the partial pressures and condensation efficiencies downstream in the High-Pressure (HP) Scrubber.

| OEM Stream No. | Fluid Description | CO2​ (wt.%) | NH3​ (wt.%) | H2​O (wt.%) | N2​ (wt.%) | O2​ (wt.%) | H2​ / CH4​ (wt.%) |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| **103** | Compressed $CO\_2$ | 94.94 | \- | 4.32 | 0.13 | \- | $H\_2$: 0.61 |
| **105** | $CO\_2$ / Air Mix | 90.87 | \- | 4.29 | 3.39 | 0.86 | $H\_2$: 0.58 |
| **107** | Passivated $CO\_2$ | 95.24 | \- | 0.61 | 3.55 | 0.60 | \- |
| **104** | Process Air | \- | \- | 3.66 | 76.15 | 20.19 | \- |
| **110** | Liquid Ammonia | \- | 99.92 | 0.08 | \- | \- | \- |
| **113-116** | HP Ammonia Feed | \- | 99.67 | 0.08 | 0.04 | \- | $CH\_4$: 0.15 |

Table 1: Chemical Composition of Raw Material Feed Streams.  
The presence of hydrogen in the raw $CO\_2$ stream (Stream 103, 105\) necessitates a catalytic hydrogen removal reactor (320R001) located between the compression stages. This reactor utilizes a platinum-on-alumina catalyst to oxidize the hydrogen into water, thereby preventing the accumulation of explosive $H\_2/O\_2$ mixtures in the HP Scrubber.

### **2.2 Synthesis Loop and Intermediate Carbamate Streams**

Within the synthesis loop, ammonia and carbon dioxide are condensed in the HP Carbamate Condenser (322E002) and subsequently gravity-fed into the Urea Reactor (322R001). The reactor effluent is a complex quaternary mixture of urea, water, unconverted ammonia, and ammonium carbamate. To isolate the urea, this mixture undergoes thermal stripping in the HP Heat Exchanger (322E001).  
The following streams represent the thermodynamic state of the carbamate gases and liquids as they are flashed, condensed, and recycled through the synthesis and high-pressure sections.

| OEM Stream No. | Fluid Description | Urea (wt.%) | NH3​ (wt.%) | CO2​ (wt.%) | H2​O (wt.%) | Biuret (wt.%) | Inerts/Other (wt.%) |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| **201** | Carbamate Gas | \- | 61.70 | 32.55 | 4.86 | \- | $N\_2$: 0.76 |
| **202** | Carbamate Gas | \- | 78.60 | 17.74 | 1.56 | \- | $CH\_4$: 0.14, $N\_2$: 1.62 |
| **203** | Carbamate Gas | \- | 69.07 | 20.51 | 4.41 | \- | $CH\_4$: 0.40, $N\_2$: 4.62 |
| **204** | Carbamate Gas | \- | 8.26 | 2.22 | 0.26 | \- | $CH\_4$: 5.93, $N\_2$: 68.81 |
| **205** | Carbamate Liquid | 0.01 | 46.37 | 44.84 | 8.77 | \- | \- |
| **206** | Carbamate Liquid | 0.04 | 39.17 | 39.69 | 21.10 | \- | \- |
| **207** | Urea Solution | 34.59 | 30.14 | 17.47 | 17.70 | 0.11 | \- |
| **208** | Urea Solution | 55.85 | 7.92 | 10.28 | 25.68 | 0.24 | $N\_2$: 0.02 |
| **217** | Carbamate Liquid | 0.02 | 64.27 | 23.24 | 12.39 | \- | $CH\_4$: 0.06 |

Table 2: Chemical Composition of Synthesis and Intermediate Carbamate Streams.  
Stream 207 represents the raw urea solution exiting the reactor prior to stripping, containing a relatively low urea mass fraction (34.59 wt.%) due to the equilibrium limits of the dehydration reaction. Following counter-current $CO\_2$ stripping in the HP Heat Exchanger, the urea fraction increases to 55.85 wt.% (Stream 208), while the ammonia fraction drops significantly from 30.14 wt.% to 7.92 wt.%, demonstrating the high mass-transfer efficiency of the stripping process.

### **2.3 Recirculation and Urea Solution Concentration Streams**

The stripped reactor solution (Stream 208\) is flashed to approximately 4.0 bar in the recirculation stage, where residual carbamate is decomposed in the rectifying column (323C003) and flash tank (323F004). The concentration of the urea solution steadily increases as water and reactants are driven off.

| OEM Stream No. | Fluid Description | Urea (wt.%) | NH3​ (wt.%) | CO2​ (wt.%) | H2​O (wt.%) | Biuret (wt.%) |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| **311** | Urea Solution | 64.31 | 4.94 | 3.31 | 27.16 | 0.28 |
| **313** | Urea Solution | 64.26 | 4.48 | 2.88 | 28.11 | 0.28 |
| **314** | Urea Solution | 68.74 | 2.13 | 1.05 | 27.72 | 0.36 |

Table 3: Chemical Composition of Urea Solution Concentration Streams.  
Stream 314 represents the critical intermediate stage of the urea solution as it transitions from the low-pressure recirculation section into the deep vacuum evaporation network. At 68.74 wt.% urea, this solution retains a significant water fraction (27.72 wt.%), which must be aggressively evaporated. It is also highly notable that the biuret concentration steadily increases from 0.11 wt.% in the reactor (Stream 207\) to 0.36 wt.% in Stream 314\. Biuret ($NH\_2CONHCONH\_2$) forms via a slow endothermic dimerization of urea at elevated temperatures and low ammonia partial pressures. Controlling the thermal residence time across these streams is paramount to keeping the final biuret concentration below the strict 1.0 wt.% agricultural limit.

### **2.4 Process Condensate and Inert Streams**

The vapors driven off during evaporation and recirculation are condensed and routed to the Desorption and Hydrolysis section (System 328\) for recovery. The inert gases, predominantly introduced via the passivation air, are vented to the atmosphere after being scrubbed.

| OEM Stream No. | Fluid Description | NH3​ (wt.%) | CO2​ (wt.%) | H2​O (wt.%) | Inerts/Other (wt.%) |
| :---- | :---- | :---- | :---- | :---- | :---- |
| **734** | Ammonia Water | 5.23 | 3.71 | 90.24 | \- |
| **755** | Ammonia Water | 4.17 | 3.81 | 91.13 | \- |
| **756** | Ammonia Water | 4.20 | 3.79 | 91.18 | \- |
| **797** | Inerts (Vent) | 0.18 | 0.05 | 2.28 | $N\_2$: 75.15, $O\_2$: 12.44, $CH\_4$: 6.47 |

Table 4: Composition of Condensate and Inert Vent Streams.  
Stream 797 highlights the effectiveness of the HP Scrubber and LP Absorber, venting an off-gas that is composed almost entirely of inert nitrogen and excess oxygen, with negligible ammonia slip (0.18 wt.%), satisfying stringent environmental emission constraints.

## **3\. Equipment Profile: 335D007 Urea-Formaldehyde Storage Tank**

To prevent the granular urea product from caking, the highly concentrated urea melt is dosed with a Urea-Formaldehyde (UF85) precondensate before entering the granulator. The UF85 fluid is stored in an atmospheric, specialized holding vessel designated as the UF Tank (335D007).

### **3.1 Fluid Properties of UF85**

The design of the 335D007 tank is strictly governed by the physical and chemical nature of its contents. UF85 is an aqueous mixture consisting of 60.0 wt.% formaldehyde, 25.0 wt.% urea, and 15.0 wt.% water. Due to the dense molecular packing of the precondensate, the fluid exhibits a high specific gravity, with a density ($\\rho$) of $1320 \\text{ kg/m}^3$. At its standard operating temperature of $40^{\\circ}C$, the fluid possesses a dynamic viscosity ($\\mu$) ranging between 150 and 250 mPa·s, making it a highly viscous, syrupy liquid compared to standard aqueous solutions.

### **3.2 Mechanical and Metallurgical Construction**

The aggressive chemical nature of formaldehyde, which readily oxidizes into formic acid in the presence of trace oxygen and moisture, demands exceptional corrosion resistance from the storage vessel. Based on the mechanical datasheet UD-AU-335-EC-0062, 335D007 is fabricated entirely from austenitic stainless steel, specifically material grade 1.4306 (equivalent to AISI 304L). The "L" grade indicates an ultra-low carbon content (maximum 0.03%), which prevents the precipitation of chromium carbides at the grain boundaries during the arc-welding phase of tank construction. This metallurgical choice eliminates the risk of intergranular corrosion and weld-decay that would otherwise devastate standard 304 stainless steel in this chemical environment.  
The structural geometry of the 335D007 tank is assembled from precision-rolled and cut plates with a cumulative weight of 13,315 kg. The component breakdown dictates strict tolerance classes according to DIN EN 10029, ensuring precise alignment and minimizing residual stresses during erection:

* **Bottom Sketch Plates (Part 1):** Four plates constituting the floor of the tank. To withstand the high hydrostatic pressure head generated by the dense UF85 fluid ($1320 \\text{ kg/m}^3$), these plates are heavily profiled at a thickness of 6.5 mm. They measure 2,000 mm in width and 8,200 mm in length, weighing a combined 3,548 kg under Tolerance Class B.  
* **Shell Courses (Part 2):** Six rolled plates forming the vertical cylindrical wall. These maintain a 5.0 mm thickness, measuring 2,000 mm by 9,000 mm, with a cumulative weight of 4,536 kg under Tolerance Class C.  
* **Roof Plates (Part 3):** Six plates capping the vessel, also at 5.0 mm thickness, measuring 2,350 mm by 7,500 mm, and weighing 4,399 kg under Tolerance Class B.  
* **Compression/Crown Ring (Part 4):** A single structural ring fabricated from heavy 10.0 mm plate, measuring 2,000 mm by 5,000 mm, and weighing 832 kg. This robust crown ring is welded to the shell-to-roof junction, providing critical radial stiffness to prevent buckling under wind loads or minor internal vacuum conditions.

All internal surfaces of the plates conform to DIN EN 10163 Class B surface finishes and DIN EN 10029 Class N flatness tolerances. A smooth internal surface is critical; microscopic crevices could act as nucleation sites where localized polymerization of the formaldehyde might occur, leading to the buildup of insoluble paraformaldehyde resins that could block the pump suction nozzles. Every plate is certified under DIN EN 10204 Type 3.1B, providing total traceability of the steel melt chemistry.

### **3.3 Instrumentation and Level Indication Loop**

To integrate 335D007 into the plant's automated logic, continuous level monitoring is imperative. The fluid level is tracked and transmitted to the DCS via a level transmitter tagged as LI335507.  
The physical measurement of the level is accomplished via a top-mounted guided-wave radar probe or a specialized Differential Pressure (DP) transmitter, indicated in the P\&ID metadata as 335PD05. In a DP configuration, the high-pressure tapping is flanged to the bottom shell course (Part 2), while the low-pressure side is vented to the atmosphere. The transmitter infers the liquid column height ($h$) via the hydrostatic relationship:  
$$\\Delta P \= \\rho \\cdot g \\cdot h$$  
Because the density of the UF85 is significantly higher than water, the DCS calibration for the 335PD05 transmitter must be hardcoded with the specific gravity of 1.32 to prevent dangerous misreadings. The LI335507 signal serves a dual purpose: it provides continuous volumetric inventory data to the control room and acts as the primary safety interlock. If the level drops below the Low-Level Alarm (LAL) threshold, the DCS automatically trips the downstream metering pump (335P002A/B) to prevent catastrophic dry-running and diaphragm cavitation.

## **4\. Equipment Profile: 335P002A/B UF Metering Pump**

The accurate dosing of the UF85 fluid into the urea melt stream is executed by the UF Metering Pumps, tagged as 335P002A and 335P002B (operating in a duty/standby configuration). These are positive displacement, controlled-volume pumps manufactured by Bran \+ Luebbe (SPX FLOW), specifically the NOVADOS H4-51 model.

### **4.1 Mechanical Design and API 675 Compliance**

The NOVADOS H4-51 is engineered in strict accordance with the American Petroleum Institute (API) Standard 675 for controlled-volume positive displacement pumps. Given the toxicity of formaldehyde, the pump employs a hermetically sealed, double-diaphragm (sandwich) construction made of Polytetrafluoroethylene (PTFE). This sealless design ensures zero fugitive emissions to the environment. Embedded between the two PTFE layers is a diaphragm rupture/break indicator. In the event of primary diaphragm fatigue, the process fluid is contained by the secondary diaphragm, while the indicator instantly alerts the DCS, allowing operators to safely switch to the standby pump without a plant shutdown.  
The liquid-wetted displacement body, including the cylinder, piston, piston rod, and valve housings, is cast and machined from 1.4571 stainless steel (316Ti). The addition of titanium stabilizes the austenitic structure at elevated temperatures and provides superb resistance to the UF85 mixture. The check valve balls are fabricated from hardened 1.4581 stainless steel to resist mechanical wear during millions of rapid seating cycles.  
The mechanical displacement is achieved by a single piston with a 56 mm diameter, operating with a maximum stroke length of 60 mm. To prevent shear-induced degradation of the highly viscous UF85 fluid (150-250 mPas), the maximum piston velocity is strictly limited to 0.2 m/s. The pump utilizes a hydraulic diaphragm loading mechanism; the eccentric piston displaces a reservoir of lubricating oil, which in turn uniformly actuates the PTFE diaphragm. This hydraulic transfer eliminates localized mechanical stress on the diaphragm, exponentially increasing its operational lifespan.

### **4.2 Operating Parameters, Flow, and Pressure Dynamics**

The hydraulic performance of 335P002A/B is matched exactly to the requirements of the granulation section:

* **Flow Capacity ($Q$):** The pump can be seamlessly adjusted from a minimum flow of 0 l/h up to a maximum capacity of 820 l/h. The rated process capacity is 760 l/h, while normal operation typically demands 470 l/h.  
* **Pressure Profile:** The pump draws UF85 from 335D007 at an atmospheric suction pressure of 1.0 bar absolute. It discharges into the highly pressurized urea melt line at 7.4 bar absolute, generating a steady differential pressure ($\\Delta P$) of 6.4 bar.  
* **Net Positive Suction Head ($NPSH$):** The piping geometry and tank elevation provide an available $NPSH\_a$ of 7 meters. Because highly viscous fluids cause severe frictional pressure drops in suction lines, a 7-meter $NPSH\_a$ is critical to ensure that $NPSH\_a \> NPSH\_r$, thus preventing vapor cavity formation during the suction stroke.  
* **Drive Mechanics:** The pump is driven by a rugged Siemens induction motor (Type 1MA70902BA11-Z), operating on a 3-phase, 50 Hz, 400 V supply. The motor outputs 0.25 kW of power at 2,730 rpm. This high-speed rotation is reduced via a Bran \+ Luebbe DS1 worm gear featuring a 28:1 reduction ratio and a service factor of 2, resulting in a final pump stroke frequency of approximately 100 strokes per minute (rpm).

Due to the explosive potential of formaldehyde vapors in restricted environments, the electrical components are rigorously classified. The junction boxes carry IP55 protection, the windings IP54, and the motor itself features an EExeIIT3 explosion-proof certification, conforming to EN 50014/18/19 standards.

### **4.3 Efficiency Curves and pV Diagram Dynamics**

For centrifugal pumps, the flow rate is inversely proportional to the system differential pressure. However, the Bran \+ Luebbe API 675 metering pump operates on positive displacement principles, resulting in a fundamentally different efficiency curve. The flow versus pressure curve is nearly vertical; the pump will deliver a constant volume of fluid regardless of variations in the discharge line pressure, up to the mechanical limit of the motor.  
The theoretical volumetric flow rate ($Q\_{th}$) is a direct geometric calculation:  
$$Q\_{th} \= \\frac{\\pi \\cdot D^2}{4} \\cdot S \\cdot n$$  
Where $D$ is the piston diameter (56 mm), $S$ is the stroke length, and $n$ is the stroke frequency.  
The actual delivered flow ($Q\_{act}$) is determined by the volumetric efficiency ($\\eta\_v$):  
$$Q\_{act} \= Q\_{th} \\cdot \\eta\_v$$  
In the NOVADOS H4-51, volumetric losses are minimal. Because the differential pressure is relatively low (6.4 bar) and the fluid is thick (250 mPas), backward slip past the suction and discharge valves is negligible. The pump utilizes precision-machined cone-type valves with a clear opening area of 0.25 cm² and an internal flow velocity of 0.64 m/s. These valves seat instantly during stroke reversal. Furthermore, the robust hydraulic oil system exhibits minimal compressibility. As a result, the volumetric efficiency ($\\eta\_v$) remains exceptionally high (typically $\>95\\%$) and profoundly linear across the entire 0 to 820 l/h adjustment range.  
The pump produces a cyclic, sinusoidal flow output visible on a pressure-volume (pV) diagram. To smooth these pulsations and ensure a steady, continuous injection of UF85 into the urea melt, a pulsation dampener constructed from 1.4404 (316L) stainless steel is installed immediately downstream of the discharge nozzle.

## **5\. Granulation Control Loops and DCS Integration**

The integration of the UF85 storage and pumping mechanics into the DCS requires an intricate array of instrumentation and automated logic loops. The primary objective is to maintain an exact, unvarying mixture ratio of 0.5 wt.% UF85 in the final urea melt, regardless of upstream production fluctuations.

### **5.1 The UF Ratio Control Cascade**

The automated dosing is managed by a sophisticated cascade and ratio control architecture programmed into the DCS:

1. **Primary Variable Tracking:** As the 98.6 wt.% urea melt leaves the Urea Melt Pumps (335P001A/B), its total mass flow rate is continuously measured by an inline mass flow transmitter, tagged as FQI335401.  
2. **Ratio Computation:** The signal from FQI335401 is transmitted to a dedicated calculation block within the DCS, tagged as FFYI335406. This block continuously multiplies the live urea mass flow rate by the hardcoded setpoint ratio (0.005) to compute the exact requisite mass flow of UF85.  
3. **Secondary Feedback Loop:** The actual quantity of UF85 being delivered by the metering pump 335P002A/B is measured by a highly sensitive flow transmitter on the pump's discharge line, tagged as FI335405.  
4. **Pump Actuation:** The DCS compares the required flow (from FFYI335406) against the actual flow (from FI335405). The resulting error signal is fed to a speed controller, tagged as HIC335609 (for pump A) and HIC335610 (for pump B).  
5. **Variable Output Adjustment:** The HIC signal modifies the frequency of the Variable Frequency Drive (VFD) controlling the 0.25 kW Siemens motor. Because the pump's efficiency curve is perfectly linear, modulating the motor rpm provides instantaneous, proportional changes in the UF85 flow rate. Furthermore, the pump possesses a pneumatic actuator that can physically alter the stroke length of the eccentric Z-shaped crankshaft during operation, providing a secondary layer of micro-adjustment.

### **5.2 Valve Sequencing and Safety Interlocks**

The fluid routing and safety logic are managed by a network of actuated control valves. The urea melt feed to the main granulator header is regulated by level control valve LV324501A, which responds to the melt level in the suction leg of pump 335P001A/B (tracked by LIC324501). If the granulation section trips or requires a temporary shutdown, the DCS initiates a split-range response: LV324501A rapidly closes, terminating flow to the granulator, while the bypass valve LV324501B simultaneously opens, routing the high-temperature urea melt back to the Urea Solution Tank (323D002) via a recirculation loop.  
The UF85 injection pump operates under strict interlocks linked to these valves. If LV324501A closes, indicating a halt in granulation, the DCS instantly commands the HIC335609/610 controller to drop the 335P002A/B stroke to zero, ceasing UF85 injection to prevent pure formaldehyde from accumulating in dead-headed piping.  
The metering pump itself is protected from overpressure events by an internal safety relief valve integrated into the hydraulic pump head, meticulously calibrated to lift at 21 bar. A secondary, external safety relief valve is flanged onto the discharge piping and set to 10 bar. If the injection nozzle into the urea melt line becomes occluded by crystallized urea, the external valve lifts, safely routing the toxic UF85 back to the 335D007 storage tank rather than rupturing the PTFE diaphragm or the downstream pipework.

## **6\. Heat and Mass Transfer Thermodynamics in the Urea Process**

While the UF85 system operates near ambient temperatures, its successful integration relies entirely on the precise thermal conditioning of the bulk urea stream in the upstream Synthesis and Evaporation sections. Fluid movement, phase transitions, and heat duties must be modeled rigorously.

### **6.1 The Synthesis Loop: Film Evaporation and Mass Transfer**

In the Urea Reactor (322R001), the fluid exists at $183^{\\circ}C$ and 136-143 bar. The reactor utilizes highly engineered sieve trays to prevent back-mixing and maintain plug flow, ensuring the slow, endothermic dehydration of carbamate into urea reaches its maximum equilibrium.  
The effluent from the reactor, a liquid mixture of urea, water, and unconverted reactants, spills over into the HP Heat Exchanger (322E001). This vessel operates as a high-pressure falling film evaporator. The urea solution is distributed evenly across thousands of vertical tubes via precision liquid dividers featuring 3 mm holes. As the liquid flows downwards as a thin film along the inner tube walls, gaseous $CO\_2$ (at $120^{\\circ}C$) is injected counter-currently from the bottom.  
The mass transfer mechanism here is brilliant: the counter-current $CO\_2$ drastically lowers the partial pressure of ammonia in the gas phase. This disturbance of the chemical equilibrium forces the unreacted ammonium carbamate in the liquid film to rapidly dissociate back into $NH\_3$ and $CO\_2$ gases, which are swept upward. This dissociation is intensely endothermic. To sustain the reaction, saturated Medium Pressure (MP) steam at approximately 20 bar ($212^{\\circ}C$) is condensed on the shell side of the tubes. The heat passes through the tube wall to the falling film. The Overall Heat Transfer Coefficient ($U$) in this high-pressure falling film regime is exceptionally high, typically ranging between **$1,200 \\text{ to } 1,800 \\text{ W}/m^2\\cdot K$**, due to the intense turbulence of the thin film and the high density of the supercritical fluids involved. The liquid exits the bottom of the HP Heat Exchanger at $173^{\\circ}C$, having been successfully stripped of the majority of its ammonia content.

### **6.2 Evaporation Stages and Deep Vacuum Duties**

To prepare the solution for granulation and UF85 injection, the water fraction must be driven down from 27.72 wt.% (Stream 314\) to less than 1.5 wt.%. This requires immense latent heat transfer under deep vacuum conditions to prevent thermal degradation of the urea into toxic biuret.

* **First Stage Evaporator (324E001):** The solution is flashed into this vessel, which is maintained at an absolute pressure of 0.33 bar via steam ejectors (324F002). Low Pressure (LP) steam condenses on the shell side, holding the boiling urea solution at exactly $130^{\\circ}C$. At 0.33 bar, the boiling point of water is significantly depressed, driving aggressive evaporation. The mass transfer removes water until the urea concentration hits 95 wt.%. The Overall Heat Transfer Coefficient ($U$) for this stage is generally modeled between **$800 \\text{ to } 1,200 \\text{ W}/m^2\\cdot K$**.  
* **Second Stage Evaporator (324E003):** The 95% solution cascades into the final evaporator, which operates at a deeper vacuum of 0.13 bar absolute, generated by ejector 324F004. Here, MP steam heats the fluid to $140^{\\circ}C$. The mass transfer is critical here; the last traces of water are violently flashed off in the separator (324F003), yielding a 98.6 wt.% urea melt. Because the water fraction is virtually eliminated, the dynamic viscosity of the urea melt spikes dramatically. This thickening of the laminar sublayer heavily impedes convective heat transfer. Consequently, the $U$ value for the second stage evaporator drops significantly, ranging from **$400 \\text{ to } 700 \\text{ W}/m^2\\cdot K$**.

### **6.3 Mixing Thermodynamics and Kinetics at UF85 Injection**

The mass transfer event where the UF85 fluid is injected into the urea melt is highly turbulent. The 335P002A/B pump forces the $40^{\\circ}C$ UF85 directly into the eye of the 335P001A/B Urea Melt Pump. The centrifugal impeller acts as a high-shear dynamic mixer, dispersing the viscous precondensate homogeneously into the $140^{\\circ}C$ urea melt.  
The mixing induces an immediate, exothermic chemical reaction. The formaldehyde ($HCHO$) molecules rapidly attack the amino groups ($-NH\_2$) of the urea molecules ($NH\_2CONH\_2$) to form methylolureas, which condense further into short-chain methylene-diurea complexes. These complexes act as crystal habit modifiers. When the melt is subsequently sprayed into the fluidized bed of the granulator (335R001), these modified molecules disrupt the normal tetragonal crystallization lattice of the solidifying urea. This microstructural alteration is what prevents the final 2-4 mm granules from fusing together (caking) during bulk transport, while simultaneously increasing their mechanical crushing strength.

## **7\. Plant Utility Streams: Cooling and Circulating Water Network**

The vast amounts of thermal energy introduced via steam condensation in the synthesis and evaporation sections must ultimately be rejected from the plant to maintain thermodynamic equilibrium. This is achieved via a massive, highly instrumented cooling and circulating water network. The table below details the immense mass flow rates required to condense the process vapors across the various heat exchangers.

| OEM Stream No. | Fluid Description | Mass Flow Total (tons/h) | Operating Temp (∘C) | Operating Pressure (bar abs) |
| :---- | :---- | :---- | :---- | :---- |
| **1001** | Cooling Water Supply | 4,847 | 30 | 4.7 |
| **1008** | Cooling Water (Branch) | 1,095 | 30 | 3.6 |
| **1009** | Cooling Water (Return) | 1,095 | 40 | 2.2 |
| **1014** | Cooling Water (Branch) | 1,591 | 30 | 3.6 |
| **1015** | Cooling Water (Return) | 1,591 | 40 | 2.2 |
| **1016** | Cooling Water (Branch) | 415 | 30 | 3.6 |
| **1017** | Cooling Water (Return) | 415 | 34 | 2.2 |
| **1050** | Cooling Water Total Return | 4,847 | 39 | 2.2 |
| **1102** | Circulating Water Supply | 1,094 | 55 | 1.5 |
| **1103** | Circulating Water Return | 1,094 | 65 | 9.0 |
| **1111** | Circulating Water Supply | 306 | 80 | 8.0 |
| **1112** | Circulating Water Return | 306 | 95 | 4.7 |

Table 5: Cooling Water and Circulating Water Network Streams.  
The data reveals that the primary cooling water header (Stream 1001\) supplies an immense 4,847 tons per hour of water at $30^{\\circ}C$ and 4.7 bar absolute. This water flows through massive surface condensers, such as the Flash Tank Condenser (323E011) and the Evaporator Condensers (324E002, 324E005), removing the latent heat of condensation from the ammonia and water vapors expelled during the concentration stages. The water returns via Stream 1050 at $39^{\\circ}C$ and a reduced pressure of 2.2 bar, representing a continuous thermal rejection duty of tens of megawatts to the atmosphere via the plant's cooling towers.  
Specialized tempered circulating water loops operate at higher temperatures to prevent the crystallization of carbamate in the HP Scrubber and LP Carbamate Condenser. For instance, Stream 1111 supplies circulating water to the HP Scrubber at $80^{\\circ}C$ and 8.0 bar, returning at $95^{\\circ}C$ (Stream 1112). If raw $30^{\\circ}C$ cooling water were used in the HP Scrubber, the ammonium carbamate would instantly crystallize on the tube walls, drastically reducing the Overall Heat Transfer Coefficient ($U$) and causing catastrophic pressure spikes within the synthesis loop.

## **8\. Conclusion and Process Modeling Directives**

The successful operation of the Stamicarbon urea granulation plant hinges entirely on the flawless mechanical and thermodynamic integration of the Urea-Formaldehyde conditioning system. The 335D007 storage tank and the 335P002A/B metering pump are not mere ancillary components; their metallurgical integrity and API 675 compliant displacement mechanics form the critical final barrier against product degradation.  
For engineers tasking with simulating the System 335 network in steady-state or dynamic modeling software (e.g., Aspen Plus, HYSYS), the empirical data mapped in this report dictates specific boundary conditions:

1. **Property Packages:** Due to the highly non-ideal nature of the urea-water-ammonia-formaldehyde mixture, the Non-Random Two-Liquid (NRTL) or UNIQUAC thermodynamic activity models must be utilized.  
2. **Pump 335P002A/B:** The Bran \+ Luebbe metering pump must be configured as a fixed volumetric flow multiplier with a volumetric efficiency ($\\eta\_v$) fixed at 0.98, rather than a standard centrifugal pressure-node. The flow output is strictly proportional to the 2,730 rpm motor speed and the mechanical stroke setting.  
3. **Reaction Node:** The injection point downstream of 335P002A/B must be modeled as a Plug Flow Reactor (PFR) to capture the rapid, exothermic condensation reaction between the UF85 and the urea melt, altering the apparent viscosity of the fluid prior to the granulator spray nozzles.  
4. **Heat Transfer:** Heat exchangers 324E001 and 324E003 should be parameterized with specific $U$ values of $1,000 \\text{ W}/m^2\\cdot K$ and $550 \\text{ W}/m^2\\cdot K$, respectively, accommodating the severe viscosity spike that occurs as the water fraction approaches zero.

Through rigorous adherence to the mechanical parameters of the 1.4306 austenitic steel plating, the hydraulic precision of the PTFE double-diaphragm pump, and the complex DCS ratio control cascades, the plant maintains absolute operational supremacy. This ensures the continuous, uninterrupted production of high-crushing-strength granular urea, safeguarding the efficiency of the global agricultural supply chain.  
