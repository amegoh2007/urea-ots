from typing import Callable, Dict, List

class Stream:
    def __init__(self, name: str):
        self.name = name
        self.T = 25.0
        self.P = 1.0
        self.mass_flow = 0.0
        self.comp: Dict[str, float] = {}
        self.enthalpy = 0.0
        self.density = 1000.0   # kg/m^3
        self.viscosity = 0.001  # Pa.s
        self.is_dirty = False
        self._subscribers: List[Callable[['Stream'], None]] = []

    def subscribe(self, callback: Callable[['Stream'], None]):
        self._subscribers.append(callback)

    def set_state(self, T: float = None, P: float = None, mass_flow: float = None, density: float = None, viscosity: float = None):
        if T is not None: self.T = T
        if P is not None: self.P = P
        if mass_flow is not None: self.mass_flow = mass_flow
        if density is not None: self.density = density
        if viscosity is not None: self.viscosity = viscosity
        self.is_dirty = True
        self._notify()

    def _notify(self):
        for callback in self._subscribers:
            callback(self)
