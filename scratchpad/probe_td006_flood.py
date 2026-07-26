"""TD-006 phase 0: the HP stripper's flooding envelope, from the licensor DDS.

Everything here comes from Uhde DDS 322E001 (UD-AU-322-DZ-0003-003 rev 00, page 3, "DESIGN DATA
SHEET FOR SHELL AND TUBE HEAT EXCHANGERS") plus the flooding figure from Brouwer, "How to Solve
Stripper Efficiency Issues", UreaKnowHow 2025, citing IFS Proceeding 166.

The point of this probe is that THREE independent documents agree, so nothing has to be fabricated:

  * the DDS tube count is confirmed by the DDS's own surface area:  N*pi*d_o*L = 1519.3 m2 against
    a tabulated 1519.00;
  * the DDS tube ID works out at 25.0 mm = 0.984 inch, which IS the "1 inch tube" the 145 kg/h
    flooding figure is quoted for -- so the figure applies directly, with no scaling;
  * the DDS effective tube length is 6000 mm, and Brouwer states that a 6 m effective tube length is
    what gives a Stamicarbon CO2 stripper its 80 % design stripping efficiency.

Consequence: the design liquid load is 108.0 kg/h per tube, i.e. 74.5 % of the flooding limit, and
the flooding term is therefore IDENTICALLY INACTIVE at the design point.  That is the whole pin
story for the flooding half of TD-006 -- it is a one-sided constraint that does not bind at the
seed, so it cannot move a single bit of the design state.

Run:  python probe_td006_flood.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
import main as m  # noqa: E402

# ---- licensor DDS 322E001, page 3 --------------------------------------------------------------
N_TUBE   = 2600            # line 34, number of tubes
D_O      = 0.031           # line 36, tube O.D. 31 mm
T_WALL   = 0.003           # line 36, wall thickness 3.0 mm
L_EFF    = 6.000           # line 35, tube length 6000 mm "eff."
A_DDS    = 1519.00         # line 25, exchange surface per exchanger, m2
RHO_L_IN = 989.88          # line 13, tube-side liquid density in
RHO_L_OUT = 1133.55        # line 13, tube-side liquid density out
RHO_G    = 10.28           # line 14, gas density
T_TUBE_IN, T_TUBE_OUT = 187.0, 172.0     # line 20
P_TUBE   = 144.0           # line 21, bar a
T_SHELL, P_SHELL = 214.0, 20.5           # lines 20/21, MP steam saturated

# ---- the flooding figure, Brouwer / IFS Proceeding 166 -----------------------------------------
FLOOD_PER_TUBE = 145.0     # kg/h of solution, 1" tube, 183 C / 140 bar
FLOOD_PRACTICE = 0.70      # "in practice, an upper limit of 70 % of this value is applied"
FLOOD_T_REF, FLOOD_P_REF = 183.0, 140.0

D_I = D_O - 2.0 * T_WALL
G = 9.80665

print("=" * 78)
print("1. the DDS is self-consistent -- the tube count is confirmed by the surface area")
print("=" * 78)
a_chk = N_TUBE * math.pi * D_O * L_EFF
print(f"  tubes           {N_TUBE}")
print(f"  tube OD x wall  {D_O*1000:.0f} x {T_WALL*1000:.1f} mm  ->  ID {D_I*1000:.1f} mm "
      f"= {D_I/0.0254:.3f} inch")
print(f"  effective length{L_EFF*1000:.0f} mm")
print(f"  N*pi*d_o*L      {a_chk:.2f} m2   vs DDS line 25 {A_DDS:.2f}   err {(a_chk-A_DDS)/A_DDS:+.3%}")
print(f"\n  ID {D_I*1000:.1f} mm is a 1-inch tube to within 1.6 %, so the 145 kg/h figure applies")
print(f"  directly.  L_eff {L_EFF:.0f} m is exactly the length Brouwer ties to 80 % efficiency.")

print()
print("=" * 78)
print("2. where the design point sits in the flooding envelope")
print("=" * 78)
feed = m.STRIP_FEED_DES_KGH
per_tube = feed / N_TUBE
frac = per_tube / FLOOD_PER_TUBE
print(f"  design feed             {feed:12,.0f} kg/h   (STRIP_FEED_DES_KGH)")
print(f"  per tube                {per_tube:12.2f} kg/h")
print(f"  flooding limit per tube {FLOOD_PER_TUBE:12.2f} kg/h")
print(f"  DESIGN FLOODING FRACTION{frac:12.4f}   ({frac:.1%} of the limit)")
print(f"  industry practice cap   {FLOOD_PRACTICE:12.2f}   ({FLOOD_PRACTICE:.0%})")
print(f"\n  plant-level limit       {FLOOD_PER_TUBE*N_TUBE:12,.0f} kg/h")
print(f"  flooding onset at       {FLOOD_PER_TUBE*N_TUBE/feed:12.1%} of design plant load")
print("  (Brouwer: a stripper typically floods at 110 % of load when new, 120 % at end of life,")
print("   the limit rising as the tube ID grows by passive corrosion.)")
print(f"\n  >>> the flooding term is INACTIVE at design ({frac:.3f} < 1.0), so it cannot move the pin.")

print()
print("=" * 78)
print("3. Wallis dimensionless velocities at the TOP of the tube, where flooding starts")
print("=" * 78)
a_t = math.pi / 4.0 * D_I ** 2
mdot_l = per_tube / 3600.0
den = G * D_I * (RHO_L_IN - RHO_G)
j_l = mdot_l / (RHO_L_IN * a_t)
jls = j_l * math.sqrt(RHO_L_IN / den)
print(f"  tube flow area {a_t*1e6:.1f} mm2      liquid {mdot_l:.5f} kg/s per tube")
print(f"  j_l {j_l:.4f} m/s   sqrt(j*_l) {math.sqrt(jls):.4f}")
print(f"\n  {'gas load assumption':<30} {'j_g m/s':>9} {'sqrt(j*g)':>10} {'Wallis sum':>11}")
for tag, m_gas_kgh in (("CO2 feed only (~55 t/h)", 55000.0),
                       ("CO2 + stripped gas (~121 t/h)", 121000.0),
                       ("half the feed evaporated", 0.5 * feed)):
    mdot_g = m_gas_kgh / N_TUBE / 3600.0
    j_g = mdot_g / (RHO_G * a_t)
    jgs = j_g * math.sqrt(RHO_G / den)
    print(f"  {tag:<30} {j_g:9.2f} {math.sqrt(jgs):10.4f} {math.sqrt(jgs)+math.sqrt(jls):11.4f}")
print("\n  Classic Wallis constant C is 0.7-1.0 for a vertical tube with a sharp-edged inlet, so the")
print("  design point straddles the correlation's own threshold band depending on which gas load is")
print("  taken.  That ambiguity is exactly why the MODEL should anchor on the licensor-specific")
print("  145 kg/h empirical limit and use the Wallis form only for the SHAPE of the off-design")
print("  response (how the limit shifts with gas density, i.e. with pressure and temperature),")
print("  written so it returns 145.0 exactly at the 183 C / 140 bar reference.")
