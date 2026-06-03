# Stamicarbon Urea Production Process Equipment Documentation

## Equipment Overview

This documentation covers two critical pieces of equipment in the Stamicarbon CO₂ stripping urea production process:

1. **Intermediate Tank (321D003)**
2. **HP Ammonia Pump (321P002 A/B)** - Reciprocating pump with variable controllable speed

---

## 1. Intermediate Tank (321D003)

### Role in the Process

The intermediate tank (321D003) serves as an **ammonia buffer/storage vessel** in the high-pressure (HP) synthesis section of the Stamicarbon urea plant. This equipment plays a crucial role in maintaining process continuity and stability by providing a reservoir of liquid ammonia between the ammonia supply source and the HP ammonia pumps.

### Operating Principle

The intermediate tank operates as a **pressure buffering and flow stabilization device**. It receives liquid ammonia from the ammonia production plant or storage facilities and maintains it under controlled conditions suitable for feeding the downstream HP ammonia pumps. The tank ensures:

- **Continuous ammonia availability** to the synthesis section, even during fluctuations in ammonia plant output
- **Pressure stabilization** between the ammonia supply system (typically 20-24 bar) and the high-pressure synthesis loop (140-160 bar)
- **Phase separation** to ensure only liquid ammonia (free from vapor or non-condensables) is fed to the HP pumps
- **Flow dampening** to smooth out variations in ammonia demand from the reactor

### Process Integration

In the Stamicarbon process flow, the intermediate tank is positioned strategically:

\[ \text{Ammonia Plant} \rightarrow \text{Ammonia Buffer Drum (321D003)} \rightarrow \text{HP Ammonia Pump (321P002 A/B)} \rightarrow \text{Heat Exchanger} \rightarrow \text{Pool Reactor} \]

The tank receives ammonia at approximately **20-24 bar** and **40°C** from the ammonia production facility. It provides a stable suction source for the reciprocating HP ammonia pumps, which then boost the pressure to synthesis conditions (approximately 140-160 bar).

### Key Process Functions

**Inventory Management**: The tank maintains sufficient ammonia inventory to accommodate short-term mismatches between ammonia production rates and urea synthesis consumption rates. This prevents process interruptions during normal production variations.

**Suction Stabilization**: Reciprocating pumps like the 321P002 A/B require stable suction conditions to prevent cavitation and ensure smooth operation. The intermediate tank provides the necessary Net Positive Suction Head (NPSH) and dampens pressure pulsations.

**Quality Control**: The tank design typically includes provisions for venting non-condensable gases (hydrogen, nitrogen, inerts) that may be present in the ammonia feed. This ensures high-purity liquid ammonia is supplied to the synthesis section, improving reactor performance.

**Operational Flexibility**: During startup, shutdown, or turndown operations, the intermediate tank provides buffer capacity that allows operators to manage the synthesis section independently from ammonia plant operations.

### Technical Considerations

The intermediate tank must be designed for:

- **Pressure rating**: Typically 25-30 bar design pressure to handle normal operating pressure of 20-24 bar with safety margin
- **Temperature range**: Ambient to 50°C, with provisions for cooling if necessary
- **Material compatibility**: Stainless steel or carbon steel with appropriate corrosion resistance for anhydrous ammonia service
- **Level control**: Instrumentation to monitor ammonia inventory and trigger alarms or corrective actions
- **Safety systems**: Pressure relief devices, emergency venting, and NH₃ detection systems

---

## 2. HP Ammonia Pump (321P002 A/B)

### Role in the Process

The HP ammonia pump (321P002 A/B) is a **critical prime mover** in the Stamicarbon urea synthesis process. It pressurizes liquid ammonia from storage conditions (20-24 bar) to synthesis pressure (140-160 bar), enabling the high-pressure carbamate formation and urea synthesis reactions to occur efficiently.

### Equipment Configuration

This equipment is installed in a **redundant A/B configuration** (twin pumps):

- **321P002 A**: Primary/duty pump
- **321P002 B**: Standby/redundant pump

This redundancy ensures **100% process availability** even during maintenance, repair, or unexpected failure of one pump. The configuration allows continuous urea production while one pump is serviced.

### Pump Type and Operating Principle

The 321P002 A/B are **reciprocating positive displacement pumps**, specifically designed for high-pressure ammonia service. Unlike centrifugal pumps, reciprocating pumps deliver:

- **Fixed volumetric flow** per stroke, independent of discharge pressure
- **Very high pressure capability** (up to 250+ bar) suitable for synthesis conditions
- **Excellent suction characteristics** with lower NPSH requirements
- **Precise flow control** through speed variation

#### Reciprocating Pump Operation

The pump operates through a **piston or plunger mechanism**:

\[ Q = n \times V_d \times \eta_v \]

Where:
- \( Q \) = volumetric flow rate (m³/h)
- \( n \) = pump speed (strokes/min or RPM)
- \( V_d \) = displacement per stroke (m³)
- \( \eta_v \) = volumetric efficiency (typically 0.90-0.98)

**Stroke Cycle**:

1. **Suction stroke**: Piston retracts, creating vacuum that opens suction valve and draws ammonia from intermediate tank (321D003)
2. **Discharge stroke**: Piston advances, closing suction valve and opening discharge valve, forcing ammonia into high-pressure discharge line
3. **Pressure development**: The mechanical action directly converts shaft power into fluid pressure energy

### Variable Speed Control System

A key feature of the 321P002 A/B pumps is **variable controllable speed** for precise flow regulation. This is achieved through:

**Control Method**: Variable Frequency Drive (VFD) on electric motor, or variable speed hydraulic/mechanical drive

**Flow Control Equation**:

\[ Q_{actual} = \frac{n_{actual}}{n_{design}} \times Q_{design} \]

This linear relationship allows operators and control systems to modulate ammonia flow by simply adjusting pump speed, providing:

- **Turndown ratio**: Typically 30% to 110% of design capacity
- **Precise stoichiometric control**: NH₃/CO₂ ratio optimization in the reactor
- **Energy efficiency**: Flow matches demand without throttling losses
- **Process stability**: Smooth, gradual flow adjustments

### Process Integration and Control

The HP ammonia pump integrates into the synthesis section control strategy:

**Upstream**: Receives liquid ammonia at 20-24 bar, 40°C from intermediate tank (321D003) with stable suction pressure

**Downstream**: Delivers ammonia at 140-160 bar, elevated temperature (due to compression heating) to the ammonia-CO₂ heat exchanger

**Control Loop**: The pump speed is modulated based on:

- **NH₃/CO₂ molar ratio setpoint** (typically 2.8-4.0 for optimal conversion)
- **Reactor ammonia flow measurement** (feedback control)
- **Urea production rate demand** (feedforward control)
- **Reactor pressure and temperature** (cascade control)

### Heat Generation and Cooling

Reciprocating pump compression generates heat according to:

\[ \Delta T \approx \frac{(P_2 - P_1)}{\rho \times C_p} \times \eta_{inefficiency} \]

For ammonia compression from 24 bar to 160 bar, temperature rise can be 10-20°C. This heat is typically:

- **Partially beneficial**: Preheats ammonia before reactor feed heating
- **Managed through**: Heat exchanger with hot CO₂ stream (cold NH₃ absorbs heat from hot compressed CO₂)
- **Monitored**: High discharge temperature can indicate mechanical issues or insufficient cooling

### Technical Specifications (Typical)

**Operating Parameters**:

- **Suction pressure**: 20-24 bar (from 321D003)
- **Discharge pressure**: 140-160 bar (to synthesis loop)
- **Suction temperature**: 40°C
- **Discharge temperature**: 49-60°C (after compression heating)
- **Flow rate**: Varies with plant capacity (e.g., 50-200 m³/h for 1500-3000 MTPD urea plants)
- **Speed range**: 60-180 RPM (typical for large reciprocating pumps)
- **Power**: 200-800 kW depending on capacity

**Mechanical Features**:

- **Plunger/piston material**: Hardened stainless steel or ceramic for wear resistance
- **Seals**: High-pressure packed gland or mechanical seal with leak detection
- **Valves**: Spring-loaded disc or ball-type suction and discharge check valves
- **Lubrication**: Forced lubrication system for crankshaft and crosshead
- **Pulsation dampener**: Installed on discharge to reduce pressure pulsations and protect downstream equipment

**Control and Instrumentation**:

- **Speed control**: VFD or variable speed drive with 4-20mA input
- **Flow measurement**: Magnetic or Coriolis flowmeter on discharge
- **Pressure transmitters**: Suction and discharge pressure monitoring
- **Temperature sensors**: Suction, discharge, and bearing temperature
- **Vibration monitoring**: Accelerometers for predictive maintenance
- **Level switch**: Low-level alarm from 321D003 for suction protection

### Safety and Reliability Considerations

**Cavitation Prevention**: Adequate NPSH from intermediate tank is critical. Minimum suction pressure must be maintained above ammonia vapor pressure at operating temperature to prevent vapor formation in pump cylinders.

**Overpressure Protection**: Discharge relief valve set at maximum allowable working pressure (typically 1.1 × design pressure) protects pump and downstream equipment from deadhead conditions.

**Leak Management**: Ammonia is toxic and flammable. Seal leakage is routed to a safe collection system with vapor detection and alarm.

**Mechanical Integrity**: Regular inspection of valves, seals, and wear parts is essential. Reciprocating pumps require more maintenance than centrifugal types but offer superior performance at high pressure.

**Redundancy**: The A/B configuration ensures one pump can be isolated and maintained while the other maintains production, typically with each pump sized for 100% capacity.

---

## Process Flow Summary

The complete ammonia feed system in the Stamicarbon process operates as follows:

\[ \text{NH}_3 \text{ Plant (20 bar, 40°C)} \rightarrow \text{321D003 Buffer} \rightarrow \text{321P002 A/B Pump (to 145 bar)} \rightarrow \text{NH}_3\text{/CO}_2 \text{ Heat Exchanger} \rightarrow \text{Pool Reactor (145 bar, 185°C)} \]

The CO₂ stream is compressed separately (1.5 bar to 160 bar) and preheated, then combined with the high-pressure ammonia. The two streams react to form ammonium carbamate, which subsequently dehydrates to urea in the pool reactor.

After reaction, the urea solution (containing unreacted carbamate, NH₃, CO₂, and water) proceeds to the **HP stripper** operating at 140-145 bar and 185-190°C, where CO₂ gas strips out carbamate decomposition products, increasing urea concentration to approximately 85%.

---

## Maintenance and Operating Best Practices

### For Intermediate Tank (321D003)

- **Daily**: Monitor ammonia level, pressure, and temperature
- **Weekly**: Check safety valve integrity and vent system function
- **Monthly**: Inspect for external corrosion, insulation damage, and instrument calibration
- **Annually**: Internal inspection during plant turnaround, NDT examination of vessel shell

### For HP Ammonia Pump (321P002 A/B)

- **Daily**: Monitor flow, suction/discharge pressure, temperature, vibration, and seal leakage
- **Weekly**: Check lubrication oil level and condition, inspect pulsation dampener
- **Monthly**: Valve performance check (efficiency calculation), speed control calibration
- **Quarterly**: Seal replacement or repacking, valve internals inspection
- **Annually**: Complete pump overhaul including plunger/piston replacement, bearing inspection, alignment verification

---

## Technical Data from Attached Datasheets

**[SECTION TO BE COMPLETED WITH DATA FROM YOUR TECHNICAL SHEETS]**

### Intermediate Tank (321D003) Technical Data

- **Tag Number**: 321D003
- **Service**: 
- **Design Pressure**: 
- **Operating Pressure**: 
- **Design Temperature**: 
- **Operating Temperature**: 
- **Volume**: 
- **Dimensions** (Diameter × Height): 
- **Material of Construction**: 
- **Nozzle Connections**: 
- **Level Instrumentation**: 
- **Pressure Relief Device**: 
- **Insulation**: 
- **Weight** (Empty/Operating): 

### HP Ammonia Pump (321P002 A/B) Technical Data

- **Tag Number**: 321P002 A/B
- **Service**: 
- **Pump Type**: Reciprocating (Plunger/Piston)
- **Rated Capacity**: 
- **Suction Pressure**: 
- **Discharge Pressure**: 
- **Differential Pressure**: 
- **Suction Temperature**: 
- **Number of Plungers/Cylinders**: 
- **Plunger Diameter**: 
- **Stroke Length**: 
- **Speed Range**: 
- **Driver Type**: 
- **Driver Power**: 
- **Material of Construction** (Wetted Parts): 
- **Seal Type**: 
- **NPSH Required**: 
- **Control System**: 
- **Manufacturer**: 
- **Model**: 

---

## References and Additional Information

This documentation is based on:

1. Stamicarbon CO₂ stripping urea process technology (2000plus design)
2. Process flow diagrams and operational data for typical 1500-2500 MTPD urea plants
3. Technical literature on reciprocating pump design and high-pressure ammonia handling

**Note**: Specific technical data from equipment datasheets should be added to the Technical Data section above once available. This will include exact dimensions, materials, manufacturer specifications, and design codes applicable to your specific plant.

---

*Document prepared for chemical engineering process documentation*  
*Format: Markdown with embedded LaTeX*  
*Compatible with Claude Code environment and technical documentation systems*

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
