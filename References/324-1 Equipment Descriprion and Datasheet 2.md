# **Process Engineering and Instrumentation Analysis of the First-Stage Evaporation and Vacuum Condensation System in Stamicarbon Urea Synthesis**

## **Introduction to the Evaporation Stage in Urea Synthesis**

In the commercial synthesis of urea via the Stamicarbon carbon dioxide stripping process, the concentration of the synthesized urea solution is a critical operation that dictates the final product quality, specifically concerning moisture content and the minimization of biuret formation. The evaporation section of a standard Stamicarbon unit, such as the implementation observed in the Helwan project (designed for 1,750 to 2,000 MTPD capacities), is meticulously engineered to achieve these thermodynamic separations under vacuum conditions. This report provides an exhaustive engineering analysis of the first-stage evaporation system, with a specific focus on the primary condenser (324E002), the associated vacuum steam ejector (324F002), and the urea solution feed pumps (323P003A/B).  
The primary objective of the first-stage evaporator (324E001) and its corresponding separator (324F001) is to increase the urea concentration from approximately 80.4 wt.% to roughly 95 wt.%. Because urea undergoes thermal degradation into biuret—an undesirable byproduct that is phytotoxic in agricultural applications—at elevated temperatures, this concentration must occur at a reduced boiling point. Consequently, the first-stage evaporation is strictly maintained at a normal operating temperature of $130^\\circ\\text{C}$ and a deep vacuum pressure of 0.33 bar absolute. The successful maintenance of this exact thermodynamic state relies entirely on the continuous extraction and condensation of the evolved vapours by the 324E002 condenser and the evacuation of non-condensable gases by the 324F002 ejector.

## **Fluid Dynamics, Mass Transfer, and Heat Transfer Mechanisms**

The internal fluid dynamics of the Stamicarbon first-stage evaporation system characterize a highly optimized multiphase separation process. The urea solution, pumped from the urea solution tank (323D002) by the centrifugal feed pumps (323P003A/B), enters the vertical falling-film evaporator (324E001). In falling-film evaporation, the liquid is distributed evenly across the inner circumference of the evaporator tubes, flowing downward as a thin film while absorbing latent heat from low-pressure (LP) steam condensing on the shell side. This geometry maximizes the heat transfer coefficient while minimizing the residence time of the urea melt, thereby kinetically starving the biuret formation reaction.  
As the solution boils, the resulting two-phase mixture discharges into the separator (324F001). The internal architecture of this separator features an inverted "Chinese hat" baffle at the bottom. This mechanical impingement device serves a dual purpose: it dissipates the kinetic energy of the violent boiling liquid, dampening fluid motion to maintain a stable liquid seal, and it forces a sharp directional change in the vapour phase to prevent the entrainment of urea droplets. The ascending vapours subsequently pass through a secondary demister or droplet separator—comprising vanes mounted on a ring—which captures micron-sized droplets before the vapour exits the vessel. To prevent crystallization and fouling on these internals, process condensate delivered by the LP absorber feed pump (322P002A/B) is injected through a full-cone sprayer and spray ring header every eight hours.  
The separated vapour, consisting primarily of steam, ammonia, carbon dioxide, and entrained inert gases, is routed to the shell side of the 324E002 condenser. Inside the condenser, mass transfer and heat transfer occur simultaneously as the vapour contacts the cold exterior of the tube bundle, which carries cooling water. The latent heat of vaporization is transferred through the tube walls, causing the water vapour to condense and absorb a significant portion of the free ammonia and carbon dioxide, forming a process condensate. The remaining non-condensable gases are actively extracted by the 324F002 steam ejector. The ejector utilizes the Venturi effect, where high-pressure motive steam accelerates through a converging-diverging nozzle, creating a low-pressure zone that entrains the non-condensables from the condenser, subsequently discharging the mixed stream to the atmospheric absorber (323C005).

## **Process Flow Stream Tracking and Mapping**

A rigorous mass and energy balance across the first-stage evaporation block requires tracking the exact thermodynamic states of the feed, discharge, utility, and vapour streams. Data extracted from the Process Flow Diagrams (PFD No. 21 and 28\) and process stream datasheets provide the specific compositions and conditions for the Helwan 1750 MTPD unit.

### **Liquid Process Streams**

The primary feed to the first-stage evaporation system originates as Stream 314, representing the urea solution fed from the tank (323D002) via pump 323P003A/B. As it passes through the evaporation cycle, moisture is flashed off, resulting in the concentrated discharge melt.

| Property | Stream 314 (Feed to Evap) | Stream 315 (Evap Discharge) | Stream 317 (Concentrated Melt) |
| :---- | :---- | :---- | :---- |
| **Stream Description** | Urea Solution | Urea Solution | Urea Solution |
| **Mass Flow (kg/h)** | 106,000 | 92,820 | 92,820 |
| **Temperature ($^\\circ\\text{C}$)** | 135 | 99 | 99 |
| **Pressure (bar a)** | 4.1 | 0.5 | 3.0 |
| **Density ($kg/m^3$)** | 1106 | 1151 | 1151 |
| **Urea (wt. %)** | 68.74 | 80.00 | 80.00 |
| **Water (wt. %)** | 27.72 | 19.47 | 19.47 |
| **Ammonia (wt. %)** | 2.13 | 0.08 | 0.08 |
| **Carbon Dioxide (wt. %)** | 1.05 | 0.02 | 0.02 |
| **Biuret (wt. %)** | 0.36 | 0.42 | 0.42 |

The data indicates a clear mass transfer of water from the liquid phase to the vapour phase, increasing the urea mass fraction from 68.74% to 80.00% across this specific boundary. Notably, the biuret concentration increases marginally from 0.36% to 0.42%, an unavoidable consequence of the thermal exposure during evaporation, underscoring the necessity of stringent vacuum control.

### **Vapour and Condensate Streams**

The vapours evolved in the separator (324F001) are directed to the condenser (324E002). The heat exchanger condenses the majority of the water vapour, which absorbs a fraction of the unreacted ammonia and carbon dioxide.

| Property | Stream 703 (Vapour Feed) | Stream 705 (Vapour Feed) | Stream 719 (Process Condensate) |
| :---- | :---- | :---- | :---- |
| **Mass Flow (kg/h)** | 26,840 | 14,799 | 26,768 |
| **Temperature ($^\\circ\\text{C}$)** | 116 | 130 | 45 |
| **Pressure (bar a)** | 0.3 | 0.3 | 0.3 |
| **Water (wt. %)** | 93.78 | 96.77 | 91.75 |
| **Ammonia (wt. %)** | 4.45 | 2.07 | 4.08 |
| **Carbon Dioxide (wt. %)** | 1.47 | 0.82 | 3.50 |
| **Urea (wt. %)** | 0.20 | 0.25 | 0.66 |
| **Density ($kg/m^3$)** | 0.19 | 0.18 | 999.1 |

Stream 719 represents the liquid process condensate draining from the condenser 324E002 at $45^\\circ\\text{C}$ via a barometric leg to the ammonia water tank (328D003). The minute quantities of urea present in these vapour streams (0.20% to 0.25%) highlight the entrainment that occurs despite the internal baffling of the separator.

### **Utility Streams (Steam and Cooling Water)**

The thermal energy required to drive the endothermic evaporation is provided by Low-Pressure (LP) steam (Streams 924, 927, 929), which enters the shell side of the 324E001 evaporator at $146^\\circ\\text{C}$ and 4.1 bar a. Conversely, the sensible and latent heat removal in the 324E002 condenser is facilitated by the cooling water circuit (Streams 1008 and 1009). The total cooling water mass flow is 1,095 metric tons per hour, entering at $30^\\circ\\text{C}$ and 3.6 bar a (Stream 1008), and discharging at $40^\\circ\\text{C}$ and 2.2 bar a (Stream 1009).

## **Equipment Specification and Heat Transfer Modeling: Condenser 324E002**

The 324E002 condenser is a critical pressure-setting vessel in the plant's topology. According to the technical specification datasheet (UD-AU-324-EC-0002), the unit is a vertically oriented shell-and-tube heat exchanger governed by AD-Merkblätter and TEMA design codes, and conforms to Stamicarbon material specification 18005 Rev. S.

### **Mechanical and Dimensional Design**

The condenser shell is constructed from carbon steel (AA01/BB.01), possessing an inside diameter of 1,850 mm, while the process-wetted tube side utilizes stainless steel to withstand the highly corrosive combination of ammonia and carbon dioxide condensate. The internal tube bundle consists of 2,329 tubes, each with an outer diameter of 25.00 mm, a wall thickness of 1.60 mm, and an effective length of 5,900 mm. The tubes are arranged with a 35 mm pitch and are supported by five internal support grids.  
The vessel features several large-bore nozzles to accommodate the high-volume, low-density vacuum vapours. The primary vapour inlet (N1) is uniquely large at 1,100 mm (DN 1100), while the cooling water inlet and outlet (N5 and N4) are both 600 mm (DN 600). The condensate outlet (N3) is 250 mm, and the non-condensable inert gas outlet (N2) to the ejector is 100 mm. The total delivery weight of the unit is 22,900 kg, which increases to 47,200 kg during active operation with process fluids.

### **Thermal Duty and Overall Heat Transfer Coefficient ($U$)**

The thermal sizing of the 324E002 condenser is designed to handle a total thermal duty of 25,720 kW. Under normal operating parameters, the shell-side process vapours enter at $115.0^\\circ\\text{C}$ and are subcooled to a condensate exit temperature of $45.0^\\circ\\text{C}$. The tube-side cooling water enters at $30^\\circ\\text{C}$ and exits at $40^\\circ\\text{C}$.  
The Logarithmic Mean Temperature Difference (LMTD) for this heat exchange profile is calculated as follows:  
$$\\Delta T\_1 \= T\_{h,in} \- T\_{c,out} \= 115^\\circ\\text{C} \- 40^\\circ\\text{C} \= 75^\\circ\\text{C}$$  
$$\\Delta T\_2 \= T\_{h,out} \- T\_{c,in} \= 45^\\circ\\text{C} \- 30^\\circ\\text{C} \= 15^\\circ\\text{C}$$  
$$\\text{LMTD} \= \\frac{\\Delta T\_1 \- \\Delta T\_2}{\\ln(\\Delta T\_1 / \\Delta T\_2)} \= \\frac{75 \- 15}{\\ln(75 / 15)} \= 37.28^\\circ\\text{C}$$  
With a specified total heat exchange surface area of 1,079 $m^2$ (which includes a 20% safety/fouling margin), the operating Overall Heat Transfer Coefficient ($U\_{total}$) is calculated using the fundamental heat transfer equation $Q \= U \\cdot A \\cdot \\text{LMTD}$:  
$$U\_{total} \= \\frac{25,720 \\times 10^3 \\text{ W}}{1079 \\text{ m}^2 \\times 37.28\\text{ K}} \= 639.40 \\text{ W}/(m^2\\cdot\\text{K})$$  
When considering the theoretical bare area without the 20% margin (approximately 899.17 $m^2$), the bare overall heat transfer coefficient ($U\_{bare}$) is $767.28 \\text{ W}/(m^2\\cdot\\text{K})$. The system is designed with a relatively low tube-side velocity of 1.40 m/s and incorporates a tube-side fouling factor of $0.00018 \\text{ m}^2\\text{K/W}$ to account for potential biological or particulate fouling from the cooling water circuit.

## **Vacuum Extraction and Ejector (324F002) Performance**

To continuously remove the non-condensable gases (e.g., passivating air, reaction byproducts) that accumulate in the condenser and blanket the heat transfer surfaces, the system employs the 324F002 steam ejector. Constructed primarily from 1.4571 (316Ti) stainless steel to resist corrosion, this ejector is designed for a mass flow normal capacity of 94.00 kg/h of suction vapour at $45^\\circ\\text{C}$ and 0.2 bar a. The density of this highly rarefied suction gas is a mere $0.21 \\text{ kg}/m^3$.  
The ejector operates using 650.00 kg/h of saturated LP motive steam, introduced at $146^\\circ\\text{C}$ and 4.1 bar a through a 50 mm nozzle (N2). The momentum transfer within the ejector's converging-diverging throat mixes the motive steam and the suction vapour, yielding a mixed discharge stream of 744.00 kg/h at $123^\\circ\\text{C}$ and an elevated pressure of 1.0 bar a, which is subsequently exhausted to the atmospheric absorber.

### **Vacuum System Pull Curves**

The performance of an ejector is typically characterized by its "pull curve," which defines the relationship between the suction load (mass flow of entrained gas) and the absolute suction pressure it can maintain. Based on the operational design point (94 kg/h at 0.2 bar a) and typical single-stage ejector physics (shut-off pressure near 0.06 bar a, overload at 150 kg/h yielding \~0.35 bar a), the resulting polynomial pull curve model takes the form $P\_{suc} \= 0.06 \+ c\_1 W \+ c\_2 W^2$.

| Suction Load (kg/h) | Suction Pressure (bar a) |
| :---- | :---- |
| 0.0 | 0.0600 |
| 20.0 | 0.0781 |
| 40.0 | 0.1024 |
| 60.0 | 0.1332 |
| 80.0 | 0.1703 |
| 94.0 | 0.2000 (Design Point) |
| 100.0 | 0.2137 |
| 120.0 | 0.2635 |
| 140.0 | 0.3196 |
| 160.0 | 0.3820 |

This pull curve demonstrates the system's sensitivity to inert gas loading. If air leakage into the vacuum system increases the load to 140 kg/h, the ejector's suction pressure will rise to nearly 0.32 bar a, fundamentally altering the boiling point of the urea solution in the upstream evaporator and risking severe biuret formation.

## **Instrumentation, Control Loops, and Level Measurement**

The control architecture of the evaporation stage, as depicted on P\&ID 105/1 and detailed in the operating manuals, represents a sophisticated balance of interconnected cascade loops. The physical locations of these instruments and their interaction with the process equipment dictate the stability of the plant.

### **Level Indication and Control in the Evaporator**

A critical challenge in vacuum evaporation is accurate liquid level measurement. The urea melt inside separator 324F001 is undergoing violent boiling. Utilizing a standard differential pressure (DP) transmitter directly on the vessel body would result in erratic, noisy signals due to the fluctuating froth and two-phase fluid layers. Consequently, Stamicarbon engineering practices dictate that the liquid level is *not* measured directly on the vessel shell.  
Instead, the level is measured hydrostatically at the suction line of the downstream urea feed pump. A barometric leg drops from the bottom of the evaporator to the pump suction, providing a stable, non-boiling column of fluid. The level controller **LIC324501** is installed on this suction line, indicating the hydrostatic head of the melt. This controller features high and low-level alarms (**LAH324501** and **LAL324501**) and manipulates the discharge flow of the melt pumps.  
The primary control action of LIC324501 is a split-range configuration over two valves: **LV324501A** (the forward flow valve directing concentrated melt to the granulator) and **LV324501B** (the recycle valve directing melt back to the urea solution tank 323D002). During normal operation, LV324501A modulates to maintain the level. During start-up or a downstream granulation trip, the controller closes LV324501A and opens LV324501B, placing the evaporation section into full internal circulation to prevent solidification and maintain thermal equilibrium.

### **Pressure and Vacuum Control**

The exact operating pressure of the first-stage system (0.33 bar in the separator, 0.31 bar in the condenser) is governed by the pressure controller **PIC324202**. The pressure transmitter for this loop is physically located on the main vapour line or condenser shell. Due to the crystallization risks of urea and carbamate vapours, the impulse lines to the pressure transmitters (PI324201 and PIC324202) are continuously purged with instrument air via flow indicators **FI324451** and **FI324452**. Furthermore, PI324201 is traced with specific steam heating controlled by a restriction orifice (**FO329461**) to prevent pluggage.  
The control mechanism utilized by PIC324202 is a highly effective, indirect thermodynamic control known as a "false air" bleed. The controller actuates valve **PV324202**, which is connected to an atmospheric vent. When the system vacuum becomes too deep (pressure falls below the setpoint), PV324202 opens, admitting a controlled volume of non-condensable atmospheric air into the vapour inlet line of the 324E002 condenser. This air blankets a portion of the condenser tubes, artificially degrading the overall heat transfer coefficient ($U$). This reduces the condensation rate, allowing vapour to build up and raising the pressure precisely back to the setpoint. Conversely, if pressure is too high, the valve closes, the ejector clears the inerts, and maximum condensation efficiency is restored.

### **Temperature and Flow Cascades**

The temperature in the first-stage evaporator is strictly controlled at $130^\\circ\\text{C}$ by **TIC324001**. Rather than directly modulating a valve, TIC324001 functions as the master controller in a cascade loop, outputting a dynamic setpoint to the slave controller **PIC329203**, which regulates the pressure of the LP steam entering the evaporator shell.  
Feed flow into the evaporation block is driven by the urea solution pumps (323P003A/B) and controlled by **FIC324401** actuating valve **FV324401**. Under steady-state conditions, this flow loop is also cascaded, receiving its setpoint from the level controller **LIC323507** installed on the small compartment of the upstream urea solution tank (323D002). This ensures that the evaporation section automatically throttles its throughput to match the upstream production rate of the synthesis and recirculation sections.

## **Pump Performance and Hydraulic Efficiency: Urea Solution Pump (323P003)**

The 323P003A/B pumps are critical rotating equipment tasked with delivering the urea solution from the storage tank into the vacuum environment of the evaporator. Operating continuously, these centrifugal pumps must handle a fluid with an elevated density of $1,151 \\text{ kg}/m^3$ at $99^\\circ\\text{C}$.  
The mechanical and hydraulic performance curve dictates the efficiency and power consumption of the pump across varying operational loads. The design normal feed rate for the system is $80.6 \\text{ m}^3\\text{/h}$. Assuming a standard centrifugal pump curve profile for a design head of 22.14 meters and a shut-off head of 28.0 meters, the pump's mechanical efficiency reaches a peak near the design point.

| Flow Rate (m3/h) | Differential Head (m) | Hydraulic Efficiency (%) | Hydraulic Power (kW) | Shaft Power (kW) |
| :---- | :---- | :---- | :---- | :---- |
| 0.0 | 28.00 | 0.00 | 0.00 | 1.50 |
| 20.0 | 27.64 | 29.90 | 1.73 | 5.80 |
| 40.0 | 26.56 | 51.82 | 3.33 | 6.43 |
| 60.0 | 24.75 | 65.77 | 4.66 | 7.08 |
| 80.6 (Design Point) | 22.14 | 71.75 | 5.58 | 7.77 |
| 100.0 | 18.98 | 69.76 | 5.95 | 8.53 |
| 120.0 | 15.01 | 59.79 | 5.65 | 9.45 |

Operating the pump near its Best Efficiency Point (BEP) of 71.75% ensures that the shaft power remains stable at approximately 7.77 kW. If the downstream flow control valve (FV324401) severely throttles the flow back to 40 $m^3$/h during a partial turndown, the efficiency drops sharply to 51.82%, causing a disproportionate amount of kinetic energy to dissipate as heat into the urea fluid. In highly concentrated urea solutions, this localized internal heating within the pump volute can accelerate corrosion or initiate premature crystallization if the fluid boils against the low-pressure suction side. Consequently, operational procedures mandate maintaining steady forward flow, utilizing the aforementioned split-range recycle valve (LV324501B) during low-throughput scenarios to artificially load the pump and keep it operating on the stable, high-efficiency portion of its hydraulic curve.

## **Conclusion**

The first-stage evaporation section of the Stamicarbon urea process represents an intricate thermodynamic system requiring precise physical and mechanical controls to ensure product purity. The structural parameters and heat transfer physics of the 324E002 condenser (with an overall heat transfer coefficient of $639.40 \\text{ W}/(m^2\\cdot\\text{K})$ operating against a 25,720 kW load) define the operational boundaries of the unit. Furthermore, the system's reliance on the 324F002 steam ejector for non-condensable gas extraction necessitates strict monitoring of air ingress, as demonstrated by the ejector pull curve.  
The instrumentation mapping reveals an advanced control philosophy explicitly designed to mitigate the physical challenges of boiling urea solutions. By measuring liquid levels via stable barometric legs, protecting pressure impulse lines with instrument air purges, and utilizing false-air thermodynamics to regulate vacuum levels, the control loops ensure continuous, reliable operation. Understanding these interactions between the fluid dynamics, the physical equipment capacities, and the cascading automation logic is fundamentally essential for the successful optimization, modeling, and troubleshooting of modern urea evaporation units.  
