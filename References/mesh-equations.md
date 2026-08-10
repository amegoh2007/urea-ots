# MESH Equations & Process Architecture Reference

## 1. Core Modelling Equations

### A. Conservation Laws (Mass & Energy)
The fundamental equations dictating the behavior of every node (unit operations, tanks, and junctions):

- **Overall Mass Balance:**  
  $$ \frac{dM}{dt} = \sum_{in} \dot{m}_{in} - \sum_{out} \dot{m}_{out} $$
  *Current Implementation:* The simulator uses explicit Euler integration for lumped capacitances (e.g., vessel holdups, steam header pressures). For instance, `dP = (sum(m_in) - sum(m_out)) / C_cap`.

- **Component Mass Balance:**  
  $$ \frac{d(M x_i)}{dt} = \sum_{in} (\dot{m}_{in} x_{i,in}) - \sum_{out} (\dot{m}_{out} x_{i,out}) + r_i V $$
  *Current Implementation:* Explicit component integrators exist in solution trains, though some HP vessels treat inventories as scalars.

- **Energy Balance (First Law):**  
  $$ \frac{dU}{dt} = \sum_{in} (\dot{m}_{in} H_{in}) - \sum_{out} (\dot{m}_{out} H_{out}) + Q - W + \sum (\xi_r \Delta H_r) $$
  *Current Implementation:* Often reduced to sensible and latent duty forms. Absolute species enthalpy formulation is currently being phased in alongside the IAPWS-IF97 steam boundaries.

### B. Thermodynamic & Phase Equilibrium Equations
- **Phase Equilibrium (Fugacity/K-Values):**  
  $$ y_i = K_i x_i \quad \text{or} \quad f_i^V(T,P,y) = f_i^L(T,P,x) $$
  *Current Implementation:* Employs Extended UNIQUAC for liquid phases (urea-carbamate-water-ammonia systems) coupled with Raoult's/Henry's laws for specific components. High-pressure steam uses strict IAPWS-IF97 bounds.

- **Chemical Equilibrium:**  
  $$ K_{eq}(T) = \prod a_i^{\nu_i} $$

### C. Rate & Transport Equations
- **Reaction Kinetics (Arrhenius):**  
  $$ k = A \exp\left(\frac{-E_a}{RT}\right) $$
  *Current Implementation:* Applied for urea conversion (e.g., Inoue-Kanai models) and carbamate formation rates.

- **Heat Transfer:**  
  $$ Q = U A \Delta T_{lm} $$
  *Current Implementation:* Present across main condensers and exchangers; duties are commonly design-anchored or tied to effectiveness-NTU methods.

- **Momentum/Hydraulics:**  
  Valve flow uses the orifice law: $ \dot{m} = K_v (\theta/100) \sqrt{\max(P_{up} - P_{dn}, 0)} $.

### D. Constraint & Constitutive Equations
- **Summation:** $ \sum x_i = 1 $ and $ \sum y_i = 1 $.
- **Property Correlations:** Empirical laws predicting density, $C_p$, etc., evaluated locally (e.g. molten urea density fits).

## 2. Flowsheet Propagation & "Ripple Effect"

The propagation of disturbances (e.g. changing feed NH3/CO2 ratios or steam pressures) dictates how downstream (D/S) units react.

### A. The Sequential Modular (SM) Approach
- Flowsheet is a directed graph (Unit Modules = nodes, Streams = edges).
- Recycles are "torn"; calculations loop and converge via Wegstein or Direct Substitution until the error is within tolerance.
- *Status:* The current simulator handles specific tears via algebraic direct substitution (e.g., 328C002/C004) or dynamic time-lagging.

### B. The Equation-Oriented (EO) Approach
- All equations combined into a sparse non-linear system (Jacobian matrix).
- Simultaneous solving (Newton-Raphson) yields an "Instant Ripple."

### C. Object-Oriented Practical Implementation
- **Ideal Structure:**
  - `Stream Objects`: House $[T, P, \text{Mass}, x_i, H]$ and broadcast `is_dirty` flags.
  - `Unit Objects`: Listen to stream flags, re-solve MESH equations, and cascade updates dynamically.
- *Current Audit Finding:* The Urea simulator evaluates the plant mostly via a massive monolithic `_tick()` cycle using explicit time integration. A true event-driven, Object-Oriented steady-state SM or EO architecture utilizing `Stream/Unit` objects with `is_dirty` flags is **not yet implemented**. This architectural gap is noted for future structural refactoring.
- *Closed Gaps:*
  - Condenser Duty vs. Pressure Coupling: Cooling duty (e.g., via TV-328002) now alters non-condensable gas generation (mass balance), which drives reflux drum pressure, cascading back to the desorption column (e.g., 328C002) via orifice-law hydraulic coupling ($\Delta P$ driven flow).
  - Synthesis Loop Pressure vs. Steam Dynamics: The HP loop pressure ODE now rigorously couples to HPCC condensation capacity (driven by LP steam drum pressure) and HP Stripper boiling capacity (driven by MP steam pressure). Increased HPCC cooling collapses vapor space, reducing loop pressure, while increased Stripper heating swells vapor space, increasing loop pressure.
