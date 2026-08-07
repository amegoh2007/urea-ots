# Modeling Gaps

- **Missing Viscosity Values**: Flow friction models in `pressure_drop.py` require stream viscosity. Currently absent in the codebase. Using assumed values (0.001 Pa·s for liquid streams, 1.5e-5 Pa·s for gases).
- **Missing Dynamic Pressure Anchor**: Applying $\Delta P$ across the HP synthesis loop units replaces static scalars with dynamic outputs. However, if the loop forms a closed hydraulic cycle, calculating $P_{out} = P_{in} - \Delta P$ monotonically lowers pressure unless anchored by a feed compressor, pump, or a fixed set-point. Need to determine the authoritative reference point for synthesis pressure.
