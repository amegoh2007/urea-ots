"""probe_wf_if97.py -- READ ONLY.
Self-contained IAPWS-IF97 Region 1 (compressed & saturated liquid) + Region 4 (saturation line).
Source: IAPWS R7-97(2012), "Revised Release on the IAPWS Industrial Formulation 1997 for the
Thermodynamic Properties of Water and Steam", Tables 2 (Region 1 coefficients) and 34 (Region 4).
Region 1 validity: 273.15 K <= T <= 623.15 K, Psat(T) <= p <= 100 MPa.  Covers 0-250 C entirely.

Verification targets published in R7-97 Table 5 are checked at the bottom.
"""
import math

R = 0.461526          # kJ/kg.K   specific gas constant of water (IF97)
Tc = 647.096          # K
Pc = 22.064           # MPa

# ---- Region 1: Table 2 of R7-97 --------------------------------------------------------------
_R1 = [
    (0,  -2, 0.14632971213167), (0,  -1, -0.84548187169114), (0, 0, -0.37563603672040e1),
    (0,   1, 0.33855169168385e1), (0,  2, -0.95791963387872), (0, 3, 0.15772038513228),
    (0,   4, -0.16616417199501e-1), (0, 5, 0.81214629983568e-3),
    (1,  -9, 0.28319080123804e-3), (1, -7, -0.60706301565874e-3),
    (1,  -1, -0.18990068218419e-1), (1, 0, -0.32529748770505e-1),
    (1,   1, -0.21841717175414e-1), (1, 3, -0.52838357969930e-4),
    (2,  -3, -0.47184321073267e-3), (2, 0, -0.30001780793026e-3),
    (2,   1, 0.47661393906987e-4), (2, 3, -0.44141845330846e-5),
    (2,  17, -0.72694996297594e-15),
    (3,  -4, -0.31679644845054e-4), (3, 0, -0.28270797985312e-5), (3, 6, -0.85205128120103e-9),
    (4,  -5, -0.22425281908000e-5), (4, -2, -0.65171222895601e-6),
    (4,  10, -0.14341729937924e-12),
    (5,  -8, -0.40516996860117e-6),
    (8, -11, -0.12734301741641e-8), (8, -6, -0.17424871230634e-9),
    (21, -29, -0.68762131295531e-18),
    (23, -31, -0.14478307828521e-19), (29, -38, 0.26335781662795e-22),
    (30, -39, -0.11947622640071e-22), (31, -40, 0.18228094581404e-23),
    (32, -41, -0.93537087292458e-25),
]
_P1s = 16.53   # MPa
_T1s = 1386.0  # K


def _r1(T_K, p_MPa):
    """Return (v m3/kg, cp kJ/kg.K, rho kg/m3) from IF97 Region 1."""
    pi = p_MPa / _P1s
    tau = _T1s / T_K
    g_pi = g_tt = g_pipi = g_pitau = g_tau = 0.0
    for I, J, n in _R1:
        a = (7.1 - pi)
        b = (tau - 1.222)
        g_pi += -n * I * a ** (I - 1) * b ** J
        g_tau += n * a ** I * J * b ** (J - 1)
        g_tt += n * a ** I * J * (J - 1) * b ** (J - 2)
    v = R * T_K * pi * g_pi / (p_MPa * 1000.0)      # kJ/(kg) / kPa -> m3/kg
    cp = -R * tau * tau * g_tt
    return v, cp, 1.0 / v


def psat_MPa(T_K):
    """IF97 Region 4 saturation pressure, MPa."""
    n = [0.11670521452767e4, -0.72421316703206e6, -0.17073846940092e2,
         0.12020824702470e5, -0.32325550322333e7, 0.14915108613530e2,
         -0.48232657361591e4, 0.40511340542057e6, -0.23855557567849,
         0.65017534844798e3]
    th = T_K + n[8] / (T_K - n[9])
    A = th * th + n[0] * th + n[1]
    B = n[2] * th * th + n[3] * th + n[4]
    C = n[5] * th * th + n[6] * th + n[7]
    return (2.0 * C / (-B + math.sqrt(B * B - 4.0 * A * C))) ** 4


def sat_liq(T_C):
    T = T_C + 273.15
    p = psat_MPa(T)
    v, cp, rho = _r1(T, p)
    return rho, cp, p * 10.0     # rho kg/m3, cp kJ/kg.K, Psat bar


def liq_at_p(T_C, P_bara):
    T = T_C + 273.15
    p = P_bara / 10.0
    v, cp, rho = _r1(T, p)
    return rho, cp


if __name__ == "__main__":
    print("--- R7-97 Table 5 verification (Region 1) ---")
    for T, p, v_ref, cp_ref in [(300.0, 3.0, 0.100215168e-2, 0.417301218e1),
                                (300.0, 80.0, 0.971180894e-3, 0.401008987e1),
                                (500.0, 3.0, 0.120241800e-2, 0.465580682e1)]:
        v, cp, rho = _r1(T, p)
        print(f"  T={T} K p={p} MPa  v={v:.9e} (ref {v_ref:.9e})  cp={cp:.9f} (ref {cp_ref:.9f})")
    print()
    print("--- Region 4 verification (R7-97 Table 35) ---")
    for T, ref in [(300.0, 0.353658941e-2), (500.0, 0.263889776e1), (600.0, 0.123443146e2)]:
        print(f"  T={T} K  psat={psat_MPa(T):.9e} MPa (ref {ref:.9e})")
