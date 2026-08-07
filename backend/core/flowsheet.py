from typing import List
from core.unit import UnitOperation
import logging

logger = logging.getLogger(__name__)

class Flowsheet:
    """
    Topology manager for the Sequential Modular architecture.
    Registers UnitOperations and orchestrates their evaluation sequence.
    """
    def __init__(self, name: str):
        self.name = name
        self.units: List[UnitOperation] = []
        self.max_iter = 50
        
    def add_unit(self, unit: UnitOperation):
        self.units.append(unit)
        
    def solve(self, dt: float = 0.0):
        """
        Evaluate all units in the flowsheet until convergence or max_iter.
        Convergence is achieved when no streams remain dirty after a pass.
        """
        # Distribute the global clock tick to units that need it
        for unit in self.units:
            if hasattr(unit, "dt"):
                unit.dt = dt
                
        converged = False
        iteration = 0
        
        # Force a first pass on all units to kickstart the tick
        for unit in self.units:
            unit.solve()
            
        # Tearing resolution loop
        while not converged and iteration < self.max_iter:
            iteration += 1
            converged = True
            
            for unit in self.units:
                # If any input to this unit is dirty, it must re-solve
                if any(stream.is_dirty for stream in unit.inputs):
                    unit.solve()
                    converged = False
                    
        if not converged:
            logger.warning(f"Flowsheet '{self.name}' failed to converge after {self.max_iter} iterations.")
