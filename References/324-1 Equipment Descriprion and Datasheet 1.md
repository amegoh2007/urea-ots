# **Engineering Analysis, Thermodynamic Mapping, and Control Architecture of Stamicarbon Urea Evaporation Systems: 323P003, 324E001, and 324F001**

## **1\. Fundamentals of the Stamicarbon Total-Recycle Evaporation Process**

The industrial synthesis of urea via the Stamicarbon total-recycle carbon dioxide stripping process relies on an intricate thermodynamic balance across its sequential stages: high-pressure synthesis, recirculation, and evaporation. To yield a final granulated product that meets stringent agricultural and industrial physical specifications, the process demands precise thermal, hydraulic, and mass transfer management. Following the synthesis and recirculation stages, where unconverted ammonia and carbon dioxide are stripped and recycled via the high-pressure (HP) heat exchanger and the low-pressure (LP) carbamate condenser, the residual urea solution contains a significant fraction of water. This water is an unavoidable stoichiometric byproduct of the endothermic dehydration of ammonium carbamate, and its removal is the primary functional mandate of the evaporation unit.  
Within the specific operational context of the Helwan Fertilizer Company (HFC) complex—which operates with a synthesis capacity of 1750 Metric Tons Per Day (MTPD) and a downstream granulation capacity of 2000 MTPD—the evaporation topology is designated as System 324\. The evaporation section is tasked with concentrating the aqueous urea solution from an initial concentration of approximately 69% by weight, achieved post-rectification, to an intermediate 80% by weight after the pre-evaporator, and ultimately to a final melt concentration of 98.6% by weight, which is optimal for the downstream fluid-bed granulation process.  
The transition of the urea solution from the bulk storage tank through the first critical evaporation stage forms the basis of this engineering analysis. This report exhaustively evaluates three interconnected pieces of process equipment within this unit operation: the Urea Solution Pump (323P003 A/B), the Evaporator I (324E001), and the Separator Evaporator I (324F001). By tracking the specific mass flow streams, mapping the instrumentation and distributed control system (DCS) architectures, analyzing the thermodynamic heat and mass transfer phenomena, delineating the hydraulic performance curves, and computing the overall heat transfer coefficients, this document establishes a rigorous mathematical and qualitative framework for modeling, operating, and optimizing the Stamicarbon evaporation section.

## **2\. Process Flow Stream Mapping and Thermodynamic Trajectories**

The hydraulic and thermal progression of the urea fluid is governed by strict stoichiometric equilibria and partial pressure requirements. Tracking the input and discharge streams through the equipment sequence reveals the progressive elimination of water and residual reactants (ammonia and carbon dioxide). The flow topology begins in the recirculation stage, passes through a flash tank and pre-evaporator, and enters the main evaporation block under evaluation.

### **2.1 Feed and Discharge Topology Overview**

In the Stamicarbon operational sequence, the urea solution is initially received from the rectifying column (323C003) operating at approximately 4.1 bar. The fluid is expanded across a level control valve (LV323501) into a flash tank (323F004) maintained at 1.1 bar, which adiabatically drops the fluid temperature from 135°C to 107°C, driving off a significant portion of water and ammonia. This solution is subsequently routed through the pre-evaporator (323E010), concentrating the fluid to roughly 80% urea by weight at a temperature of 99°C under a partial vacuum of 0.46 bar absolute.  
This 80% urea solution is continuously collected in the smaller compartment (Compartment I) of the Urea Solution Tank (323D002). To minimize the generation of biuret—a harmful diamide byproduct formed by the thermal decomposition and dimerization of urea at elevated temperatures and prolonged residence times—the solution is immediately drawn from Compartment I by the primary Urea Solution Pump (323P003 A/B).  
The discharge piping of pump 323P003 directs the fluid straight into the lower channel of Evaporator I (324E001) at a rated operational flow of 114,000 kg/h. The fluid enters the vertical shell-and-tube heat exchanger at 99°C. As it ascends through the tubes, it is heated to an exit temperature of 130°C under a deep operational vacuum of 0.33 bar absolute. Concurrently, the shell side of the exchanger is supplied with 23,600 kg/h of saturated low-pressure (LP) steam at 144°C and 3.7 bar absolute. This steam condenses isothermally, surrendering its latent heat of vaporization to drive the tube-side evaporation of the aqueous urea.  
The boiling, two-phase urea and water vapor mixture exits the upper tubesheet of Evaporator I and immediately enters the expansive volume of Separator Evaporator I (324F001). Inside this vessel, profound deceleration of the vapor phase allows the liquid droplets to disengage. The evaporated water, carrying trace fractions of unreacted ammonia and carbon dioxide, is drawn off from the top vapor nozzle to Condenser 324E002. The remaining liquid, now concentrated to a target of 95% urea by weight, exits the bottom liquid nozzle (N2) of the separator. It then flows via gravity through a sealed barometric leg directly into the subsequent second-stage evaporator (324E003), which operates at an even deeper vacuum of 0.13 bar absolute.

### **2.2 Complete Stream Compositions, Properties, and Molecular Matrices**

The overall compositional profile shifts drastically across the 300-series concentration network. Evaluating the compositional matrix of the upstream intermediate urea solution streams illustrates the mass transfer trajectory required to achieve the ultimate 95% concentration target. Process data from the 1750 MTPD configuration explicitly maps the 300-series process streams.  
The transition of the liquid urea solution is captured by tracking the progression through the intermediate stream markers. The molecular weights utilized for the mass fraction balances are standard constants: Urea (60.056 kg/kmol), Water (18.0152 kg/kmol), Ammonia (17.0304 kg/kmol), Carbon Dioxide (44.0098 kg/kmol), and Biuret (103.081 kg/kmol).

| Stream Number | Stream Description | Urea (wt. %) | Water (wt. %) | Ammonia (wt. %) | CO₂ (wt. %) | Biuret (wt. %) |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| **311** | Urea Sol. | 64.31 | 27.16 | 4.94 | 3.31 | 0.28 |
| **313** | Urea Sol. | 64.26 | 28.11 | 4.48 | 2.88 | 0.28 |
| **314** | Urea Sol. | 68.74 | 27.72 | 2.13 | 1.05 | 0.36 |

As the fluid transitions through the sequential flashing and pre-evaporation stages (typified by the progression toward Stream 314), the concentration of urea climbs from 64.31% to 68.74%, while the volatile reactants, ammonia and carbon dioxide, are aggressively stripped out by the decreasing total pressure. Ammonia fractions drop from 4.94% to 2.13%, and carbon dioxide is reduced from 3.31% to 1.05%. Noticeably, the thermal degradation of the product is empirically visible in the data; the biuret concentration climbs from 0.28% to 0.36% as the fluid absorbs thermal energy.  
By the time the fluid traverses the pre-evaporator and reaches the suction of the Urea Solution Pump (323P003), it achieves a nominal concentration of 80% urea. The thermodynamic and physical properties of this specific pump feed are highly sensitive to temperature. At the operating condition of 99°C, the liquid density is established at 1174 kg/m³, generating a dynamic viscosity of 1.25 cP. The fluid's vapor pressure is documented at 0.46 bar absolute.  
The gas and vapor streams evolving from the evaporation networks are equally complex. The 300-series carbamate gases (Streams 301, 302, 305, 321\) are characterized by immense concentrations of ammonia and carbon dioxide, completely devoid of urea. For instance, Stream 321 contains 55.3% ammonia, 33.18% carbon dioxide, and 9.48% water by weight, representing the flashed vapors that must be condensed and recycled to the high-pressure synthesis loop.  
Upon the 80% urea solution exiting Separator Evaporator I (324F001) under a vacuum of 0.33 bar absolute and a temperature of 130°C, the mass fraction of the liquid reaches 95% urea. At this operating juncture, the liquid density marginally increases to 1200 kg/m³. The separated vapor phase within the 324F001 vessel exhibits a density of 0.14 kg/m³ , demonstrating the massive volumetric expansion that occurs during the phase change. This expansion requires massive cross-sectional areas for efficient droplet disengagement.

## **3\. Engineering Analysis of the Urea Solution Pump (323P003 A/B)**

The 323P003 A/B is the fundamental prime mover for the evaporation block. Designed and fabricated by KSB-AG in Pegnitz, Germany, the unit is a heavy-duty centrifugal pump, model designation CPK-CX 80-200. Operating continuously in an outdoor, unheated environment characterized by a corrosive atmosphere laden with ammonium nitrate, urea dust, and silica, the pump's mechanical and metallurgical integrity is paramount.

### **3.1 Mechanical and Metallurgical Construction**

The CPK-CX 80-200 is a horizontal, single-stage centrifugal pump adhering to EN ISO 5199 (Technical Specification for Centrifugal Pumps Class II) and balanced dynamically according to DIN ISO 1940 and VDI 2060 standards. Handling an 80% urea solution at 99°C requires rigorous metallurgical discipline; the fluid is highly corrosive and prone to rapid crystallization if the temperature drops or if dead-legs exist within the casing. Consequently, the use of non-ferrous metals in wetted areas is strictly prohibited without explicit engineering approval.  
Because the fluid is exceptionally hazardous and must not be allowed to leak into the atmosphere, the shaft sealing architecture is governed by API 682 (Shaft Sealing Systems for Centrifugal and Rotary Pumps). The specific sealing arrangement includes provisions for flushing with steam condensate (at a maximum of 46°C and 15 bar) to dissolve any crystallized urea that might accumulate at the seal faces, thereby preventing catastrophic mechanical seal failure and ensuring continuous operational availability.

### **3.2 Hydraulic Performance and Efficiency Dynamics**

Analyzing the hydraulic performance of the 323P003 A/B involves mapping its empirical curve against the thermodynamic constraints of the urea fluid. The radial-flow impeller is rated with a working diameter of 174 mm, while the casing can accommodate a maximum impeller diameter of 209 mm and a minimum of 140 mm.  
The primary hydraulic operating parameters at the normal design point are defined as follows:

* **Rated Capacity ($Q$):** 97 m³/h (equivalent to 0.0269 m³/s)  
* **Minimum Continuous Flow ($Q\_{min}$):** 35 m³/h  
* **Maximum Allowable Flow ($Q\_{max}$):** 180 m³/h  
* **Differential Head ($H$):** 34 meters  
* **Operating Speed ($N$):** 2950 RPM  
* **Fluid Density ($\\rho$):** 1174 kg/m³  
* **Dynamic Viscosity ($\\mu$):** 1.25 cP

The theoretical hydraulic power ($P\_h$) transmitted directly to the fluid by the impeller is calculated by the fundamental equation:  
$$P\_h \= \\rho \\cdot g \\cdot Q \\cdot H$$  
$$P\_h \= 1174 \\, \\text{kg/m}^3 \\cdot 9.81 \\, \\text{m/s}^2 \\cdot 0.0269 \\, \\text{m}^3/\\text{s} \\cdot 34 \\, \\text{m} \\approx 10,534 \\, \\text{W} \= 10.53 \\, \\text{kW}$$  
The data sheet specifies the maximum rated efficiency ($\\eta$) of the pump at this operating point as 74.6%. Therefore, the predicted shaft power ($P\_s$) required to drive the pump is:  
$$P\_s \= \\frac{P\_h}{\\eta} \= \\frac{10.53}{0.746} \\approx 14.1 \\, \\text{kW}$$  
However, the empirical specification mandates a required power at the coupling of 19.2 kW. The delta between the theoretical 14.1 kW and the specified 19.2 kW accounts for the parasitic mechanical losses derived from the heavy-duty API 682 shaft sealing friction, bearing drag, and conservative safety margins applied for the specific dynamic viscosity (1.25 cP) of the concentrated urea solution. To provide an extensive buffer, the pump is coupled to a 30 kW electric motor (classification IEC-200L) operating on a 400V, 50 Hz, 3-phase power supply. The 30 kW motor ensures that the pump can operate at the far right of its performance curve (up to 180 m³/h) without tripping the motor's thermal overload relays.

### **3.3 Suction Thermodynamics and Cavitation Mitigation**

Because the 80% urea solution is fed to the pump at 99°C—which corresponds to a vapor pressure of 0.46 bar absolute—the fluid is dangerously close to its boiling point under the 1 bar absolute suction pressure conditions. If the localized pressure at the eye of the impeller drops below 0.46 bar, the liquid will flash into vapor. The subsequent collapse of these vapor bubbles as they move into the higher-pressure regions of the volute constitutes cavitation, leading to severe pitting of the 174 mm impeller and total loss of prime.  
To mitigate this, the Net Positive Suction Head (NPSH) available from the system must strictly exceed the NPSH required by the pump. The system design ensures an NPSH available of 5.0 meters, which provides a comfortable hydraulic margin over the pump’s NPSH required of 3.8 meters.

## **4\. Evaporator I (324E001) Thermal and Mechanical Design**

Evaporator I (324E001) acts as the primary thermal engine for water removal in the 324 system. Its function is to inject 14,100 kW of thermal energy into the 114,000 kg/h flow of urea solution, executing a phase change that drives the concentration from 80% to 95%.

### **4.1 Mechanical Construction and TEMA Compliance**

The 324E001 unit is a vertically oriented, parallel-arrangement shell-and-tube heat exchanger. The mechanical design is governed by the AD-Merkblätter pressure vessel code, with seismic engineering corresponding to UBC 1994 (Zone II b). The process side (tube side), which contacts the highly corrosive boiling urea, is constructed entirely of stainless steel matching Stamicarbon material specification 18005 (BB.01/BC.09). The shell side is fabricated from carbon steel (P265GH/BB.01), as it only handles clean utility steam and condensate.  
The tube bundle features an immense heat transfer area of 510 m², constructed from 1,108 seamless stainless-steel tubes. Each tube has an outer diameter of 25.00 mm, a robust wall thickness of 1.60 mm, and an effective length of 6,000 mm. The tubes are arranged on a 32 mm pitch. The shell encasing the bundle has an inside diameter of 1,250 mm and an outside diameter of 1,270 mm, containing 15 baffles to optimize the steam distribution and support the tubes against flow-induced vibration.  
The total delivery weight of the exchanger is 12,000 kg. During normal operation, filled with process fluid, the weight increases to 17,200 kg. A critical mechanical feature of this vertical exchanger is the integration of an expansion joint (bellows) in the shell. Because the stainless-steel tubes expand at a different thermal rate than the carbon-steel shell, the bellows absorb the longitudinal stress. This expansion joint is engineered to withstand a minimum of 1,000 operational load cycles and 10,000 bursting load cycles.

### **4.2 Heat Transfer Mechanisms and Thermal Modeling**

Fluid enters the bottom channel (Nozzle N1, DN 150\) of the vertical exchanger and travels upward through the single-pass tube bundle. As the urea solution absorbs thermal energy from the shell-side steam, the sensible heat raises the fluid temperature from 99°C to 130°C. Upon reaching the saturation temperature corresponding to the 0.33 bar absolute tube-side operating pressure, the fluid undergoes a phase change, transitioning into a two-phase boiling regime.  
The rapid volumetric expansion of the generated water vapor accelerates the fluid up the tube walls in a climbing-film (annular) flow pattern. This high-velocity upward flow dramatically enhances the convective heat transfer coefficient by shearing and thinning the viscous sublayer of the liquid film against the inner tube wall. The two-phase mixture exits the top channel and flows directly into the Separator Evaporator.  
Concurrently, the shell side is fed with 23,600 kg/h of saturated low-pressure (LP) steam through Nozzle N2 (DN 400). The steam operates at 3.7 bar absolute and 144°C. The latent heat of vaporization is transferred through the tube walls, and the steam condenses isothermally. The resulting 23,600 kg/h of condensate exits the shell through Nozzle N3 (DN 150).

### **4.3 Overall Heat Transfer Coefficient ($U$) Calculation**

Calculating the Overall Heat Transfer Coefficient ($U$) provides critical insights into the thermal efficiency and fouling status of the equipment, parameters highly relevant for computational modeling and predictive maintenance.  
The established thermal parameters are:

* **Total Heat Duty ($Q$):** 14,100 kW \= $14,100,000$ W  
* **Total Exchange Surface Area ($A$):** 510 m²  
* **Shell Side Temperature (Isothermal Steam):** $T\_{h,in} \= 144^\\circ\\text{C}$, $T\_{h,out} \= 144^\\circ\\text{C}$  
* **Tube Side Temperature (Urea Solution Heating):** $T\_{c,in} \= 99^\\circ\\text{C}$, $T\_{c,out} \= 130^\\circ\\text{C}$

Because the shell-side fluid (steam) undergoes isothermal condensation, the flow arrangement (counter-current versus co-current) does not mathematically alter the temperature profile geometry. The Logarithmic Mean Temperature Difference ($\\Delta T\_{LMTD}$) is derived from the temperature approaches at the two ends of the exchanger.  
Let $\\Delta T\_1$ be the temperature difference at the cold fluid inlet:  
$$\\Delta T\_1 \= T\_{h,out} \- T\_{c,in} \= 144^\\circ\\text{C} \- 99^\\circ\\text{C} \= 45^\\circ\\text{C}$$  
Let $\\Delta T\_2$ be the temperature difference at the cold fluid outlet:  
$$\\Delta T\_2 \= T\_{h,in} \- T\_{c,out} \= 144^\\circ\\text{C} \- 130^\\circ\\text{C} \= 14^\\circ\\text{C}$$  
The LMTD is defined as:  
$$\\Delta T\_{LMTD} \= \\frac{\\Delta T\_1 \- \\Delta T\_2}{\\ln\\left(\\frac{\\Delta T\_1}{\\Delta T\_2}\\right)}$$  
$$\\Delta T\_{LMTD} \= \\frac{45 \- 14}{\\ln\\left(\\frac{45}{14}\\right)} \= \\frac{31}{\\ln(3.214)} \= \\frac{31}{1.1675} \\approx 26.55^\\circ\\text{C}$$  
The Overall Heat Transfer Coefficient ($U$) is subsequently derived from the fundamental heat transfer equation:  
$$Q \= U \\cdot A \\cdot \\Delta T\_{LMTD}$$  
$$U \= \\frac{Q}{A \\cdot \\Delta T\_{LMTD}} \\\\ U \= \\frac{14,100,000 \\, \\text{W}}{510 \\, \\text{m}^2 \\cdot 26.55 \\, \\text{K}} \\approx 1041.3 \\, \\frac{\\text{W}}{\\text{m}^2\\cdot\\text{K}}$$  
A theoretical overall heat transfer coefficient of **1041.3 W/m²K** is an exceptionally robust value, characteristic of highly efficient two-phase boiling heat transfer occurring in clean climbing-film evaporators.  
**Impact of Fouling:** The sustained performance of the 324E001 exchanger depends heavily on mitigating thermal resistance caused by fouling. The utility specifications for the plant mandate incorporating significant fouling factors. For tube-side operations exceeding 115°C—which Evaporator I achieves as the bulk fluid reaches 130°C—the prescribed tube-side fouling factor increases from 0.00018 m²K/W to 0.00034 m²K/W. Simultaneously, the shell-side fouling factor (accounting for scale and impurities in the LP steam) is designated at 0.000086 m²K/W. Operating the equipment precisely at the specified 130°C and 0.33 bar absolute minimizes the precipitation of urea and the polymerization into biuret, keeping the true $R\_{f,tube}$ aligned with the design estimates and ensuring the 14,100 kW duty can be continuously met.

## **5\. Separator Evaporator I (324F001) Mass Transfer and Hydraulics**

The Separator Evaporator I (324F001) is a massive vertical vessel positioned immediately downstream of the evaporator outlet. Its operational mandate is to execute the physical mass transfer separation of the two-phase mixture exiting the evaporator tubes, isolating the concentrated 95% urea liquid melt from the flashed water, ammonia, and carbon dioxide vapors.

### **5.1 Vessel Dimensions and Mechanical Specifications**

The separator is an imposing structure designed under the AD-Merkblätter code. It features an outside diameter of 4,600 mm, an inside diameter of 4,570 mm, and a total delivery weight of 21,500 kg (excluding the connected evaporator). All wetted surfaces, internals, and structural clips are constructed from stainless steel (Stamicarbon 18005 spec, BB.01 grade).  
The vessel is characterized by a multitude of specialized nozzles designed to handle the complex internal flows:

* **N1:** Direct connection flange to Evaporator I.  
* **N2:** Liquid Outlet (DN 400, PN 10), discharging the 95% melt.  
* **N3:** Vapour Outlet (DN 900, 914 x 7.1 mm pipe), routing vapors to Condenser 324E002.  
* **N4 & N5:** Flush Water Inlets (DN 25, PN 40), used to supply high-pressure condensate to the internal spray rings.  
* **N6 & N7:** Heating Steam Inlet and Condensate Outlet (DN 50, PN 40), connecting to the internal steam tracing coils.  
* **N8:** Manhole (DN 600, PN 10\) equipped with a cover and davit arm for internal inspection.  
* **N9:** Pressure Transmitter Connection (DN 80, PN 40\) for PT 324201\.

To maintain the adiabatic integrity of the internal volume and prevent localized cold spots that could induce rapid urea crystallization, the exterior of the 4.6-meter diameter vessel is wrapped with 100 mm of hot insulation. Additionally, a steam tracing coil constructed of 1.4306 stainless steel is wrapped around the lower sections, tracing the bottom head and the manhole area. This coil utilizes 6 bar, 165°C steam to maintain skin temperatures.

### **5.2 Mass Transfer and Droplet Separation Mechanics**

The two-phase fluid enters the separator vessel via the connection nozzle N1. As the fluid transitions from the 1,108 narrow 25 mm tubes of the evaporator into the cavernous 4,570 mm internal diameter of the separator, the vertical velocity of the vapor phase is drastically reduced. According to Stokes' Law, this massive reduction in upward drag force allows the heavier liquid urea droplets to decouple from the vapor stream and fall into the boiling liquid pool at the bottom of the vessel.  
To refine the separation efficiency and prevent the entrainment of fine urea mist into the overhead condenser (which would cause severe fouling and product loss), the rising vapor must pass through a specialized droplet separator. This internal demister consists of impingement vanes mounted on an internal circumferential ring. As the vapor navigates the tortuous, highly turbulent path through the vanes, inertial impaction causes the microscopic urea droplets to collide with the vane surfaces, coalesce into larger drops, and drip back into the liquid pool below.  
Because highly concentrated 95% urea is exceptionally prone to crystallization, these vanes can easily become plugged. To mitigate this, the internal spray nozzles are flushed every eight hours. A full-cone sprayer and a circular spray ring header fitted with flat-jet sprayers are installed above the vanes, fed by the flush water inlets N4 and N5. These sprayers inject process condensate delivered by the LP absorber feed pumps to dissolve any crystalline buildup, ensuring the pressure drop across the vanes remains negligible.

### **5.3 Hydraulic Management and the Vortex Breaker**

At the bottom of the vessel, the boiling liquid pool requires careful hydraulic management to prevent the entrainment of vapor into the liquid discharge line. An inverted "Chinese hat" vortex breaker is installed directly over the 400 mm liquid outlet nozzle (N2). This robust baffle impedes the rotational, cyclonic movement of the boiling solution. By breaking the vortex, the baffle ensures a smooth, solid-liquid entry into the discharge piping, preventing gas blow-by that could induce cavitation in downstream pumps or disrupt the vacuum balance of the sequential evaporation stages.

## **6\. Instrumentation, Level Indication, and Control Loop Architectures**

Robust control architectures are mandatory in urea evaporation to govern the precise balance between vacuum pressure, steam input, flow rates, and fluid levels. Any deviation outside the operating envelopes can lead to catastrophic crystallization (solidification point of pure urea is 132.6°C), excessive biuret formation, or severe equipment corrosion. The control loops are rigorously defined in the P\&ID schemas, notably PID No. 105/1.

### **6.1 Flow and Level Control of the Urea Solution Pump (323P003 A/B)**

The 323P003 pump operates on a classic cascade flow-level control philosophy. The primary objective is to maintain a continuous, short-residence-time feed from the Urea Solution Tank (323D002) to Evaporator I (324E001).  
The liquid level in Compartment I of the 323D002 tank is continuously measured by a level indicating controller (LIC323507). Under steady-state operations, LIC323507 transmits a dynamic setpoint to the flow indicating controller (FIC324401), which is located on the primary discharge line of the 323P003 pump. The FIC324401 algorithm subsequently modulates the flow control valve (FV324401) to supply the exact quantity of urea solution to the evaporator, directly synchronizing the pump's hydraulic output with the upstream synthesis yield.  
To protect the centrifugal pump from dead-heading—which is highly probable given the fluid's high vapor pressure at 99°C—a minimum continuous flow bypass line is implemented. If the forward flow falls below the 35 m³/h threshold, or during start-up recirculation scenarios, the level control valve LV324501B opens via split-range control. This action establishes a recycle loop, routing the fluid back to the urea solution tank to dissipate the heat added by the pump impeller.

### **6.2 Temperature and Condensate Control of Evaporator I (324E001)**

The thermodynamic control of the falling-film/rising-film Evaporator I relies on closely monitoring the thermal input to guarantee the 95% concentration target without exceeding thermal degradation limits. The temperature of the urea solution exiting the evaporator is continuously measured and governed by the temperature indicating controller TIC324001, which is set to a strict operating point of 130°C.  
Because the shell side of 324E001 utilizes latent heat from condensing LP steam, the rate of heat transfer is modulated by altering the steam pressure and corresponding saturation temperature. Therefore, TIC324001 cascades its output to the pressure indicating controller PIC329203, which modulates the LP steam supply valve into the shell.  
Instead of utilizing a traditional, passive thermodynamic steam trap, Evaporator I features an active condensate level control system. **The level of the condensed steam on the shell side is measured at the bottom of the shell by LIC329505**. This controller commands the level control valve LV329505 on the condensate discharge line routed to the steam condensate tank (329D001). This active control allows operators to flood the lower tubes if necessary, effectively reducing the active heat transfer area to prevent overheating during low-load operations.

### **6.3 Vacuum Control and the Absence of Level Indication in Separator 324F001**

The primary control parameter for the Separator Evaporator is the profound vacuum required to boil the urea solution at 130°C. The operating pressure is targeted at 0.33 bar absolute. The pressure is measured directly at the separator vessel via a pressure transmitter (PT 324201), physically located on Nozzle N9 (DN 80, PN 40\) at the top of the vessel.  
To prevent the highly concentrated urea vapors from crystallizing inside the impulse lines of PT 324201 and rendering the transmitter blind, a continuous purge of instrument air is supplied into the impulse line via a flow indicator (FI324451). The pressure reading (PI324201) is linked to the vacuum control loop. The pressure indicating controller PIC324202 manages the vacuum not by throttling the motive steam to the downstream ejectors (which can cause ejector stall and complete loss of vacuum), but rather by modulating a false-air inlet valve (PV324202) located on the common vapor header leading to Condenser 324E002. By introducing controlled atmospheric air into the condenser, the overall condensation efficiency is suppressed, thereby governing the upstream vacuum pressure in 324F001.  
**Level Indication and Measurement Topology:** When interrogating how level is indicated and in which part of the 324F001 equipment the level is measured, the engineering datasheets reveal a critical design philosophy: **direct electronic level measurement instruments are deliberately omitted from the Separator Evaporator I vessel.** The datasheet explicitly marks the traditional level nozzles (N10A/B and N11A-D) as "Removed".  
In the Stamicarbon evaporation design, the level is not actively controlled within the first-stage separator via a modulating discharge valve. Instead, the highly concentrated, boiling 95% urea liquid is discharged via a gravity-driven barometric leg directly into the subsequent Evaporator II (324E003). Because the second-stage evaporator operates at an even deeper vacuum (0.13 bar absolute compared to 0.33 bar absolute), the hydraulic U-tube loop between the two vessels balances the differential pressure dynamically. By employing a passive barometric leg, the system brilliantly eliminates the need for level transmitters, floats, and control valves in a zone where the 95% urea melt is highly susceptible to rapid crystallization, scaling, and mechanical blockage.

## **7\. Predictive Modeling and Simulation Guidelines**

The synthesis of the documentation covering the 323P003 pump, 324E001 evaporator, and 324F001 separator establishes clear mathematical boundaries and parameters for simulating and optimizing the Stamicarbon urea evaporation process. Integrating this data into steady-state or dynamic process simulators (such as Aspen Plus, HYSYS, or Pro/II) requires specific thermodynamic and hydraulic framing.  
**Thermodynamic Property Packages:** The evaporation of water from an 80% to a 95% urea solution within 324E001 is a highly non-ideal thermodynamic process. The presence of high-concentration urea significantly depresses the vapor pressure of the water, elevating the boiling point beyond that of pure water at 0.33 bar absolute. Furthermore, the trace release of unreacted ammonia and carbon dioxide into the vapor phase impacts the partial pressure dynamics. Thermodynamic property packages capable of handling strong electrolytes and highly polar mixtures, such as the NRTL (Non-Random Two-Liquid) or specialized proprietary Stamicarbon equations of state, must be employed. Standard ideal gas or Peng-Robinson equations will drastically fail to predict the phase envelope and the 14,100 kW thermal duty required to achieve the 130°C outlet condition.  
**Hydraulic Modeling Considerations:** When constructing a dynamic model of this section, the barometric leg connecting the 324F001 separator to the downstream second-stage evaporator must be modeled as a pure hydraulic seal rather than a control valve. The elevation difference between the separator and the downstream vessel drives the flow against the deeper vacuum of the second stage without mechanical intervention. Simulation algorithms should compute the liquid column height based strictly on the 0.20 bar differential pressure ($\\Delta P \= 0.33 \- 0.13$ bar), accounting for the 1200 kg/m³ density of the 95% urea melt and the localized gravitational constant. The hydraulic equation $h \= \\frac{\\Delta P}{\\rho g}$ defines the baseline fluid height in the piping model.  
**Fouling and Heat Exchanger Degradation Modeling:** When modeling the thermal performance of the 324E001 evaporator over a multi-month operational campaign, the degradation of the Overall Heat Transfer Coefficient ($U$) must be simulated. The total thermal resistance ($R\_{total}$) is the sum of the convective resistances, the conductive resistance of the 1.60 mm stainless steel tube wall, and the respective fouling factors:  
$$\\frac{1}{U\_{dirty}} \= \\frac{1}{U\_{clean}} \+ R\_{f,tube} \+ R\_{f,shell}$$  
The operational guidelines mandate incorporating the specified fouling factors to ensure the exchanger is not theoretically undersized under mature operating conditions. For tube-side operations exceeding 115°C, the prescribed tube-side fouling factor ($R\_{f,tube}$) is 0.00034 m²K/W. Simultaneously, the shell-side fouling factor ($R\_{f,shell}$) is designated at 0.000086 m²K/W. Dynamic models should feature logic that penalizes the $U\_{clean}$ value of $1041.3 \\, \\text{W/m}^2\\text{K}$ by these specific resistance factors to accurately predict the maximum achievable throughput before a mechanical cleaning shutdown is mandated.  
By utilizing these rigorous mass transfer metrics, component specifications, and operational heuristics, process engineers can confidently replicate, monitor, and optimize the hydraulic and thermal performance of the Stamicarbon evaporation section, ensuring continuous delivery of high-purity urea melt to the downstream granulation facility.  
