import math

class ThermoModel:
    def bubble_p(self, T_c: float, nc_ratio: float, hc_ratio: float) -> float:
        raise NotImplementedError

    def viscosity_liq_pas(self, T_c: float) -> float:
        raise NotImplementedError

    def viscosity_gas_pas(self, T_c: float) -> float:
        raise NotImplementedError

class EmpiricalThermo(ThermoModel):
    def bubble_p(self, T_c: float, nc_ratio: float, hc_ratio: float) -> float:
        """Bubble-point pressure calculation.

        NOT IMPLEMENTED — this method has no callers in the live engine.
        All ionic-section VLE uses IAPWS-IF97 pure-water saturation plus design offset.
        Raise NotImplementedError to prevent silent fallback to placeholder logic.
        """
        raise NotImplementedError(
            "EmpiricalThermo.bubble_p is not implemented. "
            "Live engine uses IAPWS-IF97 + design offset for all VLE calculations."
        )

    def viscosity_liq_pas(self, T_c: float) -> float:
        """
        Empirical Andrade equation for Urea/Carbamate liquid viscosity (Pa s).
        Typical range: 1.0 to 3.0 cP (0.001 to 0.003 Pa s) in the synthesis loop.
        """
        T_k = T_c + 273.15
        A = 1.2e-5
        B = 2200.0
        mu = A * math.exp(B / T_k)
        return max(mu, 1e-4)
        
    def viscosity_gas_pas(self, T_c: float) -> float:
        """
        Empirical polynomial for process gas viscosity (Pa s).
        Typical range: ~0.015 cP (1.5e-5 Pa s).
        """
        T_k = T_c + 273.15
        mu_ref = 1.5e-5
        return mu_ref * (T_k / 450.0)**0.8
