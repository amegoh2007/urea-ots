class ThermoModel:
    def bubble_p(self, T_c: float, nc_ratio: float, hc_ratio: float) -> float:
        raise NotImplementedError

class EmpiricalThermo(ThermoModel):
    def bubble_p(self, T_c: float, nc_ratio: float, hc_ratio: float) -> float:
        # Placeholder empirical logic to return a positive pressure
        return 140.0 + (T_c - 170.0) * 0.5
