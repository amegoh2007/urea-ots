# OTS Directives Summary

## 1. Mandatory Skills & Standing Commands
* **Caveman Mode:** MUST be ON every sessio
* **Multiagents:** **MANDATORY** not to use multiagents

## 2. Core Physics & References
* **Strict Source:** `References/Combined_1750_MTPD_100% load_PFD TablesProcess_Data.md`.
* **Equipment Database:** Always look for equipment database in the folder: `D:\Work\Urea Simulation\References\Datasheets` for data related to datasheet (Eg. Dimensions, instrument position in equipment any other data required for modelling).

## 3. Autonomous Workflow & Testing
* **Execution:** Do not halt for approval;[cite: 1]
* **Scope:** One unit at a time with strict adherence to `ui_guidelines.md` when editing and generating new UI screens.[cite: 1]

## 4. Documentation & Version Control
* **Surgical Edits:** Modify specific lines/methods only.[cite: 1]
* **Auto-Updates:** `Urea OTS — As-Built Mathematical Reference` updated.[cite: 1]
* **Handoff:** Update `handoff.md` in the root directory at session end, retaining only open gaps (delete closed).[cite: 1]

---

## 5. Unit Auditing & Addition Rules
When auditing or adding new units, you must verify the mathematical framework modeling the operations, thermodynamic states, and downstream (D/S) flowsheet connectivity.

### Core MESH Equations
Ensure the physical and chemical reality is governed by the following constraints:
* **Mass Balance:** $$\sum_{in} F_j - \sum_{out} F_j = 0$$
* **Component Balance:** $$\sum_{in} (F_j x_{i,j}) - \sum_{out} (F_j x_{i,j}) + r_i V = 0$$
* **Energy Balance:** $$\sum_{in} (F_j H_j) - \sum_{out} (F_j H_j) + Q - W = 0$$
* **Phase Equilibrium:** $$y_i = K_i x_i$$ (calculated via Equations of State or Activity Models)
* **Chemical Equilibrium:** $$K_{eq}(T) = \prod a_i^{\nu_i}$$
* **Reaction Kinetics:** $$k = A \exp\left(\frac{-E_a}{RT}\right)$$
* **Heat Transfer:** $$Q = U A \Delta T_{lm}$$
* **Constitutive Constraints:** $$\sum x_i = 1$$ and $$\sum y_i = 1$$. Must include empirical property correlations and momentum/pressure drop calculations (e.g., Darcy-Weisbach, Ergun).

### Flowsheet Propagation (Ripple Effect)
Ensure upstream changes cascade accurately via the correct computational architecture:
* **Sequential Modular (SM):** Block-by-block forward propagation along the directed graph. Recycle loops must be resolved via "tearing" (guessing tear stream conditions, calculating the loop, comparing outputs, and iterating numerically to convergence).
* **Equation-Oriented (EO):** Simultaneous solving. All flowsheet equations are compiled into a sparse Jacobian matrix and solved via Newton-Raphson methods for instant global equilibrium shifts.

### Object-Oriented Implementation
* **Stream Objects:** Must hold state vectors (T, P, Mass Flow, compositions, Enthalpy). Any update must flag an `is_dirty` boolean.
* **Unit Operation Objects:** Must contain MESH equations and "listen" to input streams. If an input's `is_dirty` flag triggers, the unit must execute its solver, update output streams, and cascade `is_dirty` flags until steady-state convergence is reached.