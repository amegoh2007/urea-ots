====================================================================================================
  DCS SYSTEM IDENTIFICATION REPORT — Simulator Calibration Audit
====================================================================================================


────────────────────────────────────────────────────────────────────────────────────────────────────
  HP Synthesis Loop Temperatures (Section 322)
────────────────────────────────────────────────────────────────────────────────────────────────────
MV Tag             PV Tag          θ_emp (s)  τ_emp (s)       K_p  r_xcorr      Sim τ/θ      Verdict
────────────────────────────────────────────────────────────────────────────────────────────────────
HIC-322605         TT-322004             0.0     3180.0   +0.3759   -0.010 STRIP_T_TAU_S = 180     SIM_FAST
HIC-322605         TT-322013             0.0     7800.0   +0.4568    0.789 STRIP_T_TAU_S = 180     SIM_FAST
HIC-322604         TT-322011             0.0     4020.0   +0.0000    0.469 OFFGAS_T_TAU_S = 120     SIM_FAST
HIC-322604         TT-322002          5280.0     2580.0   +0.0000   -0.026 SCRUB_T_TAU_S = 180     SIM_FAST
LV-322501          TT-322004             0.0     3180.0   +0.5725    0.381 STRIP_T_TAU_S = 180     SIM_FAST
UREA-LOAD          TT-322005             0.0    10650.0   -0.1428   -0.582 REACT_TAU_REC_MIN * 60 = 300     SIM_FAST
HIC-322605         TT-322010             0.0     7800.0   -0.0931   -0.450 HPCC_T_TAU_S = 240     SIM_FAST
PIC-329204         TT-322012             0.0     5520.0   +7.2796    0.758 EJ_T_TAU_S = 120     SIM_FAST
FYM-322403         TT-322005             0.0    10650.0   -0.2677   -0.604 FEED_TD_S=345 + thermal     SIM_FAST
LIC-322501         TT-322004          1008.0   208656.0  -52.3417    0.201 STRIP_T_TAU_S = 180     SIM_FAST
SIC-321951         TT-322002          1008.0    27216.0   -2.4290    0.171 FEED_TD_S=345 + SCRUB_T_TAU_S=180     SIM_FAST
FIC-320402         TT-322017             0.0   105840.0   -0.0953    0.601 FEED_TD_S = 345     SIM_FAST
PIC-322201         TT-322015             0.0   206640.0   -9.0290    0.012 R323_C003_P_TAU_S = 1     SIM_FAST
TIC-322021         TT-322002          2016.0    27216.0  +15.6983    0.099 SCRUB_T_TAU_S = 180     SIM_FAST

────────────────────────────────────────────────────────────────────────────────────────────────────
  Reactor Thermal Dynamics
────────────────────────────────────────────────────────────────────────────────────────────────────
MV Tag             PV Tag          θ_emp (s)  τ_emp (s)       K_p  r_xcorr      Sim τ/θ      Verdict
────────────────────────────────────────────────────────────────────────────────────────────────────
HIC-322605         TT-322014             0.0     7560.0   +0.0000   -0.390 REACT_THERM_TAU_MIN * 60 = 480     SIM_FAST
SIC-321951         TT-322014           450.0     7560.0   +0.0000    0.619 FEED_TD_S=345 + REACT_TAU_REC_MIN*60=300     SIM_FAST
HVGT-322605        TT-322014             0.0    28224.0   -2.8051    0.448 REACT_THERM_TAU_MIN * 60 = 480     SIM_FAST

────────────────────────────────────────────────────────────────────────────────────────────────────
  MP Decomposition (Section 323)
────────────────────────────────────────────────────────────────────────────────────────────────────
MV Tag             PV Tag          θ_emp (s)  τ_emp (s)       K_p  r_xcorr      Sim τ/θ      Verdict
────────────────────────────────────────────────────────────────────────────────────────────────────
LIC-322501         TT-323001          1008.0   219744.0  -12.5806    0.116 STRIP_T_TAU_S = 180     SIM_FAST
LIC-322501         TT-323002          2016.0   141120.0   -5.7985    0.097 R323_C003_M_TAU_S = 120     SIM_FAST
PIC-329202         TT-323004          7056.0   212688.0   -0.1951    0.360 R323_C003_M_TAU_S = 120     SIM_FAST
FIC-323401         TT-323005             0.0    20160.0   +5.6272    0.141 R323_F010_M_TAU_S = 240     SIM_FAST
PIC-323203         PT-323201          7056.0    39312.0   -0.0023    0.004 R323_F004_P_TAU_S = 90     SIM_FAST

────────────────────────────────────────────────────────────────────────────────────────────────────
  LP Decomposition (Section 328)
────────────────────────────────────────────────────────────────────────────────────────────────────
MV Tag             PV Tag          θ_emp (s)  τ_emp (s)       K_p  r_xcorr      Sim τ/θ      Verdict
────────────────────────────────────────────────────────────────────────────────────────────────────
TIC-328002         TT-328004             0.0    21168.0   -2.0028   -0.565 a328_c001_T: implicit holdup ODE     SIM_FAST
PIC-328202         FIC-328402            0.0   204624.0  +43.6115    0.016 None — implicit level dynamics          N/A

────────────────────────────────────────────────────────────────────────────────────────────────────
  Steam Network (Section 329)
────────────────────────────────────────────────────────────────────────────────────────────────────
MV Tag             PV Tag          θ_emp (s)  τ_emp (s)       K_p  r_xcorr      Sim τ/θ      Verdict
────────────────────────────────────────────────────────────────────────────────────────────────────
HV-322602          PT-329206             0.0     4830.0   +0.0467    0.938 C_LP = 25.0 → τ ≈ C_LP/flow     SIM_FAST
TIC-329005         TDY-329125         6390.0     2370.0   -0.1385    0.578 CCW_T_TAU_S = 25     SIM_FAST
FIC-329401         PT-329207          7056.0   189504.0   +0.0120   -0.523  C_LP = 25.0     SIM_FAST
PV-329204          PT-329201          3024.0   204624.0   -0.3080    0.916  C_MP = 25.0     SIM_FAST
TIC-329005         TT-329004          7056.0    27216.0 +2066.1508   -0.277 CCW_T_TAU_S = 25     SIM_FAST

────────────────────────────────────────────────────────────────────────────────────────────────────
  Analyzer & Instrument Dynamics
────────────────────────────────────────────────────────────────────────────────────────────────────
MV Tag             PV Tag          θ_emp (s)  τ_emp (s)       K_p  r_xcorr      Sim τ/θ      Verdict
────────────────────────────────────────────────────────────────────────────────────────────────────
UREA-LOAD          AY-322701             0.0     4170.0   +0.0253    0.514 AT_322701_TAU_S = 40     SIM_SLOW
UREA-LOAD          AY-322701          7056.0     1008.0   +0.0019    0.103 AT_322701_TAU_S = 40     SIM_SLOW

────────────────────────────────────────────────────────────────────────────────────────────────────
  Controller Response
────────────────────────────────────────────────────────────────────────────────────────────────────
MV Tag             PV Tag          θ_emp (s)  τ_emp (s)       K_p  r_xcorr      Sim τ/θ      Verdict
────────────────────────────────────────────────────────────────────────────────────────────────────
SIC-321950         PT-321202          1008.0    39312.0   +1.2589   -0.030 instantaneous (PD pump, no lag expected)          N/A

====================================================================================================
  DISCREPANCY SUMMARY — 30 parameter(s) require update
====================================================================================================

  ▸ HIC-322605 → TT-322004: HV-322605 spindle → stripper bottom T
    Empirical: θ = 0.0 s,  τ = 3180.0 s
    Simulator: STRIP_T_TAU_S = 180
    Ratio τ_emp/τ_sim = 17.67  →  Sim too fast
    Mechanism: thermal inertia (stripper falling-film + sump + shell metal)

  ▸ HIC-322605 → TT-322013: HV-322605 spindle → stripper top T
    Empirical: θ = 0.0 s,  τ = 7800.0 s
    Simulator: STRIP_T_TAU_S = 180
    Ratio τ_emp/τ_sim = 43.33  →  Sim too fast
    Mechanism: thermal inertia (stripper reflux + tube bundle)

  ▸ HIC-322604 → TT-322011: HV-322604 off-gas valve → off-gas T
    Empirical: θ = 0.0 s,  τ = 4020.0 s
    Simulator: OFFGAS_T_TAU_S = 120
    Ratio τ_emp/τ_sim = 33.50  →  Sim too fast
    Mechanism: thermal inertia (offgas line + thermowell metal)

  ▸ HIC-322604 → TT-322002: HV-322604 off-gas valve → scrubber overflow T
    Empirical: θ = 5280.0 s,  τ = 2580.0 s
    Simulator: SCRUB_T_TAU_S = 180
    Ratio τ_emp/τ_sim = 14.33  →  Sim too fast
    Mechanism: thermal inertia (scrubber liquid pool + shell metal)

  ▸ LV-322501 → TT-322004: LV-322501 drain → stripper bottom T
    Empirical: θ = 0.0 s,  τ = 3180.0 s
    Simulator: STRIP_T_TAU_S = 180
    Ratio τ_emp/τ_sim = 17.67  →  Sim too fast
    Mechanism: thermal inertia (flash + sump + pipe)

  ▸ UREA-LOAD → TT-322005: Load % → reactor liquid T (TT-322005)
    Empirical: θ = 0.0 s,  τ = 10650.0 s
    Simulator: REACT_TAU_REC_MIN * 60 = 300
    Ratio τ_emp/τ_sim = 177.50  →  Sim too fast
    Mechanism: synthesis loop recycle lag

  ▸ HIC-322605 → TT-322010: HV-322605 spindle → HPCC product T
    Empirical: θ = 0.0 s,  τ = 7800.0 s
    Simulator: HPCC_T_TAU_S = 240
    Ratio τ_emp/τ_sim = 32.50  →  Sim too fast
    Mechanism: thermal inertia (HPCC tube bundle + liquid holdup)

  ▸ PIC-329204 → TT-322012: HP steam chest P → ejector discharge T
    Empirical: θ = 0.0 s,  τ = 5520.0 s
    Simulator: EJ_T_TAU_S = 120
    Ratio τ_emp/τ_sim = 46.00  →  Sim too fast
    Mechanism: thermal inertia (ejector + suction carbamate)

  ▸ FYM-322403 → TT-322005: CO₂ feed flow → reactor liquid T
    Empirical: θ = 0.0 s,  τ = 10650.0 s
    Simulator: FEED_TD_S=345 + thermal
    Ratio τ_emp/τ_sim = 30.87  →  Sim too fast
    Mechanism: transport (CO₂ pipe) + reactor thermal inertia

  ▸ LIC-322501 → TT-322004: LV-322501 → stripper bottom T
    Empirical: θ = 1008.0 s,  τ = 208656.0 s
    Simulator: STRIP_T_TAU_S = 180
    Ratio τ_emp/τ_sim = 1159.20  →  Sim too fast
    Mechanism: thermal inertia (flash + sump)

  ▸ SIC-321951 → TT-322002: NH₃ pump speed → scrubber overflow T
    Empirical: θ = 1008.0 s,  τ = 27216.0 s
    Simulator: FEED_TD_S=345 + SCRUB_T_TAU_S=180
    Ratio τ_emp/τ_sim = 78.89  →  Sim too fast
    Mechanism: transport + thermal (loop recycle + scrubber)

  ▸ FIC-320402 → TT-322017: CO₂ feed control → 322 line T
    Empirical: θ = 0.0 s,  τ = 105840.0 s
    Simulator: FEED_TD_S = 345
    Ratio τ_emp/τ_sim = 306.78  →  Sim too fast
    Mechanism: transport delay (feed pipe + compressor)

  ▸ PIC-322201 → TT-322015: Absorber pressure → absorber off-gas T
    Empirical: θ = 0.0 s,  τ = 206640.0 s
    Simulator: R323_C003_P_TAU_S = 1
    Ratio τ_emp/τ_sim = 639.75  →  Sim too fast
    Mechanism: gas holdup lag (322C001 volume)

  ▸ TIC-322021 → TT-322002: Temp controller → scrubber overflow T
    Empirical: θ = 2016.0 s,  τ = 27216.0 s
    Simulator: SCRUB_T_TAU_S = 180
    Ratio τ_emp/τ_sim = 151.20  →  Sim too fast
    Mechanism: thermal (scrubber inventory + CCW shell)

  ▸ HIC-322605 → TT-322014: HV-322605 spindle → reactor overflow T
    Empirical: θ = 0.0 s,  τ = 7560.0 s
    Simulator: REACT_THERM_TAU_MIN * 60 = 480
    Ratio τ_emp/τ_sim = 126.00  →  Sim too fast
    Mechanism: thermal inertia (reactor liquid holdup + metal mass)

  ▸ SIC-321951 → TT-322014: NH₃ pump speed → reactor overflow T
    Empirical: θ = 450.0 s,  τ = 7560.0 s
    Simulator: FEED_TD_S=345 + REACT_TAU_REC_MIN*60=300
    Ratio τ_emp/τ_sim = 21.91  →  Sim too fast
    Mechanism: transport delay (NH₃ pipe + reactor residence) + thermal

  ▸ HVGT-322605 → TT-322014: HV-322605 travel → reactor overflow T
    Empirical: θ = 0.0 s,  τ = 28224.0 s
    Simulator: REACT_THERM_TAU_MIN * 60 = 480
    Ratio τ_emp/τ_sim = 470.40  →  Sim too fast
    Mechanism: thermal inertia (reactor liquid holdup)

  ▸ LIC-322501 → TT-323001: LV-322501 drain → column feed T (TT-323001)
    Empirical: θ = 1008.0 s,  τ = 219744.0 s
    Simulator: STRIP_T_TAU_S = 180
    Ratio τ_emp/τ_sim = 1220.80  →  Sim too fast
    Mechanism: flash lag (LV → column entry)

  ▸ LIC-322501 → TT-323002: LV-322501 drain → column sump T (TT-323002)
    Empirical: θ = 2016.0 s,  τ = 141120.0 s
    Simulator: R323_C003_M_TAU_S = 120
    Ratio τ_emp/τ_sim = 436.90  →  Sim too fast
    Mechanism: holdup lag (column liquid residence)

  ▸ PIC-329202 → TT-323004: MP steam chest P → C003 column T
    Empirical: θ = 7056.0 s,  τ = 212688.0 s
    Simulator: R323_C003_M_TAU_S = 120
    Ratio τ_emp/τ_sim = 658.48  →  Sim too fast
    Mechanism: thermal inertia (reboiler + column holdup)

  ▸ FIC-323401 → TT-323005: LP steam to E010 → pre-evap T
    Empirical: θ = 0.0 s,  τ = 20160.0 s
    Simulator: R323_F010_M_TAU_S = 240
    Ratio τ_emp/τ_sim = 62.41  →  Sim too fast
    Mechanism: thermal inertia (323E010 shell + holdup)

  ▸ PIC-323203 → PT-323201: Flash drum PIC → column overhead P
    Empirical: θ = 7056.0 s,  τ = 39312.0 s
    Simulator: R323_F004_P_TAU_S = 90
    Ratio τ_emp/τ_sim = 121.71  →  Sim too fast
    Mechanism: gas holdup (flash vaporization + piping)

  ▸ TIC-328002 → TT-328004: 328 temp controller → LP decomposer T
    Empirical: θ = 0.0 s,  τ = 21168.0 s
    Simulator: a328_c001_T: implicit holdup ODE
    Ratio τ_emp/τ_sim = 64.54  →  Sim too fast
    Mechanism: thermal inertia (decomposer compartments)

  ▸ HV-322602 → PT-329206: HV-322602 steam valve → LP header P
    Empirical: θ = 0.0 s,  τ = 4830.0 s
    Simulator: C_LP = 25.0 → τ ≈ C_LP/flow
    Ratio τ_emp/τ_sim = 193.20  →  Sim too fast
    Mechanism: header capacitance (322D001A/B)

  ▸ TIC-329005 → TDY-329125: CCW temp controller → CCW return ΔT
    Empirical: θ = 6390.0 s,  τ = 2370.0 s
    Simulator: CCW_T_TAU_S = 25
    Ratio τ_emp/τ_sim = 94.80  →  Sim too fast
    Mechanism: tempered water shell return lag

  ▸ FIC-329401 → PT-329207: BL steam makeup → LP header P
    Empirical: θ = 7056.0 s,  τ = 189504.0 s
    Simulator: C_LP = 25.0
    Ratio τ_emp/τ_sim = 7580.16  →  Sim too fast
    Mechanism: header capacitance

  ▸ PV-329204 → PT-329201: PV-329204 stroke → HP steam drum P
    Empirical: θ = 3024.0 s,  τ = 204624.0 s
    Simulator: C_MP = 25.0
    Ratio τ_emp/τ_sim = 8184.96  →  Sim too fast
    Mechanism: header capacitance (329D005)

  ▸ TIC-329005 → TT-329004: CCW temp controller → cooling water T
    Empirical: θ = 7056.0 s,  τ = 27216.0 s
    Simulator: CCW_T_TAU_S = 25
    Ratio τ_emp/τ_sim = 1088.64  →  Sim too fast
    Mechanism: shell-side thermal mass

  ▸ UREA-LOAD → AY-322701: Load % → N/C analyzer reading
    Empirical: θ = 0.0 s,  τ = 4170.0 s
    Simulator: AT_322701_TAU_S = 40
    Ratio τ_emp/τ_sim = 0.01  →  Sim too slow
    Mechanism: analyzer sampling + measurement lag

  ▸ UREA-LOAD → AY-322701: Load → N/C analyzer
    Empirical: θ = 7056.0 s,  τ = 1008.0 s
    Simulator: AT_322701_TAU_S = 40
    Ratio τ_emp/τ_sim = 0.00  →  Sim too slow
    Mechanism: analyzer sampling + measurement lag