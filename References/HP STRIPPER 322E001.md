## 3. High-Pressure (HP) Stripper (322-E-001)

The High-Pressure (HP) Stripper (typically tagged as **322-E-001**) is the defining technological advancement of the Stamicarbon $CO_2$ stripping process. Operating at the full synthesis loop pressure (approximately 140 to 145 bar), it eliminates the need to depressurize the reactor effluent to separate the unconverted reactants from the urea product.

Its primary role is to thermally decompose unconverted ammonium carbamate and aggressively strip the resulting ammonia ($NH_3$) and carbon dioxide ($CO_2$) out of the liquid phase, returning them to the high-pressure loop.

### 3.1 Hydrodynamics and Material Transfer

The HP Stripper operates as a **vertical falling-film shell-and-tube heat exchanger** utilizing two-phase counter-current flow.

* **Liquid Phase (Downwards):** The reactor effluent (a mixture of urea, water, unconverted carbamate, and free ammonia) enters the top liquid divider. It is distributed uniformly to form a thin liquid film falling down the inner walls of the tubes (typically Sandvik 2RE69 or Safurex material to withstand the extreme corrosivity).
* **Gas Phase (Upwards):** Fresh, high-pressure $CO_2$ gas from the compressor enters the bottom of the stripper and flows upward through the hollow core of the tubes, acting as the stripping agent.
* **Heating Medium (Shell Side):** High-pressure saturated steam (typically 20-25 bar) condenses on the outside of the tubes.

#### The Chemical Reaction (Material Transfer)
As the liquid film heats up, the unconverted ammonium carbamate undergoes an endothermic decomposition reaction within the liquid phase:

$$NH_2COONH_4 (l) \rightleftharpoons 2NH_3 (aq) + CO_2 (aq) \quad \Delta H > 0$$

*Note: A secondary, much slower reaction (urea hydrolysis and biuret formation) also occurs, but carbamate decomposition dominates the material balances in this vessel.*

![Heat and mass transfer interfaces in a falling film tube.](falling_film_cross_section.png)

---

### 3.2 Coupled Heat and Mass Transfer

The stripper's efficiency relies on the precise synchronization of heat flux from the shell and mass transfer at the gas-liquid interface.

#### Heat Transfer
Heat flows from the condensing steam on the shell, through the tube wall, and into the liquid film. This heat flux ($q$) serves three purposes:
1.  **Sensible Heat:** Raises the liquid effluent temperature to ≈ 205-210°C.
2.  **Heat of Reaction:** Provides the substantial energy required to break the carbamate bonds.
3.  **Latent Heat of Vaporization:** Vaporizes the generated $NH_3$ and $CO_2$, as well as a significant amount of $H_2O$.

#### Mass Transfer (The "Stripping" Effect)
The genius of the Stamicarbon design is the use of $CO_2$ as a stripping agent.
1.  As fresh $CO_2$ flows upward, it acts as a diluent for the $NH_3$ in the vapor phase, drastically lowering the partial pressure of $NH_3$ in the gas core.
2.  According to Henry's Law, this maximizes the concentration gradient (driving force) between the dissolved $NH_3$ in the liquid film and the gas core.
3.  As $NH_3$ aggressively desorbs into the gas phase, Le Chatelier's principle dictates that the liquid-phase carbamate equilibrium must shift to the right, driving further decomposition without requiring a drop in total system pressure.

---

### 3.3 Modelling Equations (1D Boundary Value Problem)

To mathematically model 322-E-001, the tube bundle is treated as a 1D distributed-parameter system along the axial coordinate $z$ (from $z=0$ at the top to $z=L$ at the bottom).

#### A. Mass and Species Balances
For a given component $i$ (Urea, $H_2O$, $NH_3$, $CO_2$, Carbamate) in the liquid phase ($L$) and gas phase ($G$):

**Liquid Phase:**
$$\frac{d(\dot{m}_L x_i)}{dz} = \left( r_i M_{w,i} \frac{\pi D^2}{4} \epsilon_L \right) - J_i \pi D$$

**Gas Phase (Counter-current, so flows opposite to $z$):**
$$-\frac{d(\dot{m}_G y_i)}{dz} = J_i \pi D$$

*Where:*
* $\dot{m}$ = Mass flow rate (kg/s)
* $x_i, y_i$ = Mass fractions in liquid and gas
* $r_i$ = Net reaction generation rate (mol/m³·s)
* $M_{w,i}$ = Molecular weight
* $J_i$ = Interfacial mass transfer flux (kg/m²·s)
* $D$ = Tube inner diameter (m)
* $\epsilon_L$ = Liquid holdup fraction (cross-sectional area occupied by film)

#### B. Mass Transfer Flux ($J_i$)
The mass transfer is typically modeled using the two-film theory. Because $CO_2$ and $NH_3$ transfer simultaneously, a Maxwell-Stefan approach is highly accurate, but a simplified driving force equation is often used for real-time simulation:

$$J_i = K_{G,i} M_{w,i} (P_{i}^* - P_{i, bulk})$$

*Where:*
* $K_{G,i}$ = Overall gas-phase mass transfer coefficient.
* $P_{i}^*$ = Equilibrium partial pressure of component $i$ at the interface (calculated via thermodynamic models like the Extended UNIQUAC or PC-SAFT for the urea-carbamate-water system).
* $P_{i, bulk}$ = Actual partial pressure in the bulk gas core.

#### C. Energy Balances
The heat integration requires tracking the enthalpy ($h$) profiles of both phases.

**Liquid Phase Energy Balance:**
$$\frac{d(\dot{m}_L h_L)}{dz} = U \pi D (T_{steam} - T_L) - \sum_{i} (J_i \Delta H_{vap,i}) + \left( \sum r_j \Delta H_{rxn,j} \right) \frac{\pi D^2}{4} \epsilon_L$$

**Gas Phase Energy Balance:**
$$-\frac{d(\dot{m}_G h_G)}{dz} = h_c \pi D (T_L - T_G) + \sum_{i} (J_i h_{i,vap})$$

*Where:*
* $U$ = Overall heat transfer coefficient from the steam, through the wall, to the bulk liquid film.
* $h_c$ = Convective heat transfer coefficient at the gas-liquid interface.
* $\Delta H_{vap}$ and $\Delta H_{rxn}$ = Enthalpies of vaporization and reaction.

> **Key Modeling Insight:** The boundary conditions for this BVP are "split." The liquid feed conditions are known at $z=0$ (top), while the gas feed conditions ($CO_2$ flow and temp) are known at $z=L$ (bottom). Simulating this requires an iterative shooting method or orthogonal collocation techniques to converge the profiles.

---
*End of Technical Reference*