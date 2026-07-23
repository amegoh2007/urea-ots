# Master PID Tuning Constants Report

> **Single source of truth.** This is the sole authoritative copy (the former `Urea Simulation Docs/Audit/Master_PID_Tuning_Constants.md` duplicate has been removed). The as-designed plant DCS table (below) is authoritative for plant tuning; **Appendix A** (units 323-2 / 328-1 / 328-2) and **Appendix B** (the unit-324 evaporator temperature masters) are authoritative for the OTS sim (`backend/main.py`) velocity I-PD constants, which are deliberately re-derived for discrete stability and are **not** a copy of the plant table.
>
> **Read the appendices before quoting the plant table at the simulator.** 33 of the 46 controllers seeded in `State.__init__` differ from their plant row, and every one of those differences is intentional. The two largest are in Appendix B: **TIC-324001 and TIC-324002 run at Kc = 0.02 in the engine against 1.50 and 2.00 in the plant table** — a factor of 75 and 100 — because the simulated stage is not the plant's stage. Setting either loop to its plant gain drives the simulator into a multi-hour limit cycle; the derivation is in Appendix B.

This consolidated document contains all PID tuning parameters extracted from the various process sections across the facility.

## Consolidated Summary Table

| Controller Tag | Description | Proportional Gain (Gain) | Integral Time (TI) | Derivative Time (TD) | Filter Time (TF) | Deadband (DZ) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **AIC-335701** | US FROM SCRUB. PUMPS | 1.00 | 500.0 s | -1.0 s | 0.0 s | 2.0 % |
| **FFIC-321404A** | FFIC FOR 321P002A | 1.00 | 100.0 s | -1.0 s | 0.0 s | 2.0 % |
| **FFIC-321404B** | FFIC FOR 321P002B | 1.00 | 90.0 s | -1.0 s | 0.0 s | 2.0 % |
| **FIC-323401** | 328054,AW | 0.10 | 7.0 s | 0.0 s | 0.0 s | 2.0 % |
| **FIC-323402** | 328060,AW | 0.10 | 7.0 s | 0.0 s | 0.0 s | 2.0 % |
| **FIC-323418** | ACA FROM 323P8A/B | 1.00 | 100.0 s | -1.0 s | 0.0 s | 2.0 % |
| **FIC-324401** | US TO EVAPORATOR | 0.40 | 30.0 s | -1.0 s | 0.0 s | 2.0 % |
| **FIC-328402** | 328062,AW | 0.75 | 60.0 s | 0.0 s | 0.0 s | 2.0 % |
| **FIC-328405** | 328081,AW | 0.20 | 15.0 s | 0.0 s | 0.0 s | 2.0 % |
| **FIC-328406** | 328112,CPP | 0.75 | 80.0 s | 0.0 s | 0.0 s | 2.0 % |
| **FIC-329401** | 329375,STLS | 0.30 | 100.0 s | 0.0 s | 0.0 s | 2.0 % |
| **FIC-329402** | 329302,STMH | 0.40 | 200.0 s | -1.0 s | 0.0 s | 2.0 % |
| **FIC-329409** | 329064, WC | 0.60 | 250.0 s | 0.0 s | 0.0 s | 2.0 % |
| **FIC-335407** | 335108,US | 0.50 | 40.0 s | 0.0 s | 0.0 s | 2.0 % |
| **LIC-322501** | 322E001, US | 0.20 | 280.0 s | 1.0 s | 1.0 s | 1.0 % |
| **LIC-322502** | 322C001,AW | 1.00 | 100.0 s | 0.0 s | 0.0 s | 2.0 % |
| **LIC-323501** | 323C003,US | 1.20 | 100.0 s | 0.0 s | 0.0 s | 2.0 % |
| **LIC-323503** | 323D011,ACA | 1.80 | 120.0 s | 0.0 s | 0.0 s | 2.0 % |
| **LIC-323505** | 323F004,US | 1.00 | 100.0 s | 0.0 s | 0.0 s | 2.0 % |
| **LIC-324501** | 324020,US | 0.85 | 200.0 s | -1.0 s | 0.0 s | 2.0 % |
| **LIC-328501** | 328D001,ACA | 1.00 | 300.0 s | -1.0 s | 0.0 s | 2.0 % |
| **LIC-328503** | 328C002,AW | 1.50 | 180.0 s | 0.0 s | 0.0 s | 2.0 % |
| **LIC-328504** | 328C004,AW | 0.20 | 300.0 s | 0.0 s | 0.0 s | 2.0 % |
| **LIC-328505** | 328C003,CPP | 1.45 | 180.0 s | 0.0 s | 0.0 s | 2.0 % |
| **LIC-329503** | 329D009,CPL | 2.00 | 200.0 s | -1.0 s | 0.0 s | 2.0 % |
| **LIC-329504** | 329016,CPL | 2.50 | 500.0 s | -1.0 s | 1.0 s | 2.0 % |
| **LIC-329505** | 329011,CPL | 2.50 | 60.0 s | 0.0 s | 0.0 s | 2.0 % |
| **LIC-335501** | 335R001A/B,AII | 0.50 | 400.0 s | -1.0 s | 0.0 s | 2.0 % |
| **LIC-335505** | 309064,AL | 0.30 | 140.0 s | 0.0 s | 4.0 s | 2.0 % |
| **LIC-335508** | 335D002,US | 3.00 | 299.0 s | 1.5 s | 25.0 s | 2.0 % |
| **LIC-335509** | 335115,US | 2.99 | 149.0 s | 1.5 s | 25.0 s | 2.0 % |
| **PIC-322201** | 322C001,GCB | 6.00 | 30.0 s | 0.0 s | 0.0 s | 2.0 % |
| **PIC-323202B**| 329058,WC | 1.00 | 100.0 s | 0.0 s | 0.0 s | 2.0 % |
| **PIC-323203** | 323F004,GCB | 0.60 | 100.0 s | -1.0 s | 0.0 s | 2.0 % |
| **PIC-324202** | 324E002,VP | 2.00 | 200.0 s | -1.0 s | 0.0 s | 2.0 % |
| **PIC-324203** | 324E005,VP | 2.00 | 200.0 s | -1.0 s | 0.0 s | 2.0 % |
| **PIC-328202** | 328D001 GAS OUTLET | 2.50 | 200.0 s | 0.0 s | 0.0 s | 2.0 % |
| **PIC-328203** | 328C003,STMH | 1.50 | 50.0 s | -1.0 s | 0.0 s | 2.0 % |
| **PIC-329202** | 329358,STLS | 0.65 | 30.0 s | 0.0 s | 0.0 s | 2.0 % |
| **PIC-329203** | 329360,STLS | 0.30 | 75.0 s | -1.0 s | 0.0 s | 2.0 % |
| **PIC-329204** | 329D005,STMH | 1.80 | 100.0 s | -1.0 s | 0.0 s | 2.0 % |
| **PIC-329207A**| 329356,STLS | 6.00 | 150.0 s | -1.0 s | 0.0 s | 2.0 % |
| **PIC-329207B**| 329356,STLS | 4.00 | 150.0 s | 0.0 s | 0.0 s | 2.0 % |
| **PIC-329207C**| 329356,STLS | 4.00 | 200.0 s | -1.0 s | 0.0 s | 2.0 % |
| **PIC-329208** | 329433,STLS | 0.20 | 60.0 s | 0.0 s | 0.0 s | 2.0 % |
| **PIC-329212** | 329362,STLS | 0.65 | 130.0 s | -1.0 s | 0.0 s | 2.0 % |
| **PIC-335201** | 335R001 GRANULATOR | 0.65 | 40.0 s | 0.0 s | 0.0 s | 2.0 % |
| **PIC-335203** | 335R001B,AID | 0.22 | 18.0 s | 0.0 s | 0.0 s | 2.0 % |
| **PIC-335225** | STLS, 335E002 | 1.00 | 100.0 s | 0.0 s | 0.0 s | 2.0 % |
| **SIC-321950** | NH3 PUMP 321P002A | 4.00 | 35.0 s | -1.0 s | 0.0 s | 2.0 % |
| **SIC-321951** | NH3 PUMP 321P002B | 1.20 | 50.0 s | -1.0 s | 0.0 s | 2.0 % |
| **SIC-323901** | HP CARB.PUM.323P001A | 1.10 | 30.0 s | 0.0 s | 0.0 s | 2.0 % |
| **SIC-323902** | HP CARB.PUM.323P001B | 1.10 | 30.0 s | 0.0 s | 0.0 s | 2.0 % |
| **TIC-323007** | 323266,US | 2.00 | 500.0 s | -1.0 s | 0.0 s | 2.0 % |
| **TIC-323013** | 329058,CW | 1.00 | 100.0 s | 0.0 s | 0.0 s | 2.0 % |
| **TIC-324001** † | 324021,US | 1.50 | 320.0 s | 0.0 s | 0.0 s | 2.0 % |
| **TIC-324002** † | 324020,US | 2.00 | 300.0 s | 0.0 s | 0.0 s | 2.0 % |
| **TIC-328002** | LIQU.OUT REFLUX COND | 3.00 | 500.0 s | 0.0 s | 0.0 s | 2.0 % |
| **TIC-329005** | 329054, WC | 1.50 | 300.0 s | -1.0 s | 0.0 s | 2.0 % |
| **TIC-335001** | 335R001-N3,AID | 0.80 | 150.0 s | 0.0 s | 0.0 s | 2.0 % |
| **TIC-335003** | 335R001-N4A/B,AID | 1.80 | 150.0 s | -1.0 s | 0.0 s | 2.0 % |
| **TIC-335013** | 335365,STLS | 1.20 | 100.0 s | 0.0 s | 0.0 s | 2.0 % |
| **TIC-335015** | 335552,AI | 2.00 | 200.0 s | -1.0 s | 0.0 s | 2.0 % |
| **TIC-335017** | 335559,AI | 1.50 | 200.0 s | 0.0 s | 0.0 s | 2.0 % |
| **TIC-335020** | 335302,STLS | 1.15 | 375.0 s | 0.0 s | 0.0 s | 2.0 % |
| **TIC-335103** | 335365,STLS | 1.00 | 100.0 s | 0.0 s | 0.0 s | 2.0 % |

† **The OTS simulator does not use these two rows.** `backend/main.py` seeds TIC-324001 and
TIC-324002 at **Kc = 0.02, Ti = 360 s** — see **Appendix B**, which records the measured process
gain the retune was derived from. The plant values above are unchanged and remain correct *for the
plant*.

---

## Detailed Controller Parameters

### 4. AIC-335701
* **Description:** US FROM SCRUB. PUMPS
* **Gain:** 1.00
* **TI (Integral Time):** 500.0 s
* **TD (Derivative Time):** -1.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 5. FIC-323401
* **Description:** 328054,AW
* **Gain:** 0.10
* **TI (Integral Time):** 7.0 s
* **TD (Derivative Time):** 0.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 3. FIC-323402
* **Description:** 328060,AW
* **Gain:** 0.10
* **TI (Integral Time):** 7.0 s
* **TD (Derivative Time):** 0.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 6. FIC-323418
* **Description:** ACA FROM 323P8A/B
* **Gain:** 1.00
* **TI (Integral Time):** 100.0 s
* **TD (Derivative Time):** -1.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 8. FIC-324401
* **Description:** US TO EVAPORATOR
* **Gain:** 0.40
* **TI (Integral Time):** 30.0 s
* **TD (Derivative Time):** -1.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 8. FIC-328402
* **Description:** 328062,AW
* **Gain:** 0.75
* **TI (Integral Time):** 60.0 s
* **TD (Derivative Time):** 0.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 2. FIC-328405
* **Description:** 328081,AW
* **Gain:** 0.20
* **TI (Integral Time):** 15.0 s
* **TD (Derivative Time):** 0.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 4. FIC-328406
* **Description:** 328112,CPP
* **Gain:** 0.75
* **TI (Integral Time):** 80.0 s
* **TD (Derivative Time):** 0.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 5. FIC-329401
* **Description:** 329375,STLS
* **Gain:** 0.30
* **TI (Integral Time):** 100.0 s
* **TD (Derivative Time):** 0.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 10. FIC-329402
* **Description:** 329302,STMH
* **Gain:** 0.40
* **TI (Integral Time):** 200.0 s
* **TD (Derivative Time):** -1.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 3. FIC-329409
* **Description:** 329064, WC
* **Gain:** 0.60
* **TI (Integral Time):** 250.0 s
* **TD (Derivative Time):** 0.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 7. FIC-335407
* **Description:** 335108,US
* **Gain:** 0.50
* **TI (Integral Time):** 40.0 s
* **TD (Derivative Time):** 0.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 1. LIC-322501
* **Description:** 322E001, US
* **Gain:** 0.20
* **TI (Integral Time):** 280.0 s
* **TD (Derivative Time):** 1.0 s
* **TF (Filter Time):** 1.0 s
* **DZ (Deadband):** 1.0 %

### 8. LIC-322502
* **Description:** 322C001,AW
* **Gain:** 1.00
* **TI (Integral Time):** 100.0 s
* **TD (Derivative Time):** 0.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 3. LIC-323501
* **Description:** 323C003,US
* **Gain:** 1.20
* **TI (Integral Time):** 100.0 s
* **TD (Derivative Time):** 0.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 4. LIC-323503
* **Description:** 323D011,ACA
* **Gain:** 1.80
* **TI (Integral Time):** 120.0 s
* **TD (Derivative Time):** 0.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 5. LIC-323505
* **Description:** 323F004,US
* **Gain:** 1.00
* **TI (Integral Time):** 100.0 s
* **TD (Derivative Time):** 0.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 6. LIC-324501
* **Description:** 324020,US
* **Gain:** 0.85
* **TI (Integral Time):** 200.0 s
* **TD (Derivative Time):** -1.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 7. LIC-328501
* **Description:** 328D001,ACA
* **Gain:** 1.00
* **TI (Integral Time):** 300.0 s
* **TD (Derivative Time):** -1.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 9. LIC-328503
* **Description:** 328C002,AW
* **Gain:** 1.50
* **TI (Integral Time):** 180.0 s
* **TD (Derivative Time):** 0.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 2. LIC-328504
* **Description:** 328C004,AW
* **Gain:** 0.20
* **TI (Integral Time):** 300.0 s
* **TD (Derivative Time):** 0.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 3. LIC-328505
* **Description:** 328C003,CPP
* **Gain:** 1.45
* **TI (Integral Time):** 180.0 s
* **TD (Derivative Time):** 0.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 2. LIC-329503
* **Description:** 329D009,CPL
* **Gain:** 2.00
* **TI (Integral Time):** 200.0 s
* **TD (Derivative Time):** -1.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 3. LIC-329504
* **Description:** 329016,CPL
* **Gain:** 2.50
* **TI (Integral Time):** 500.0 s
* **TD (Derivative Time):** -1.0 s
* **TF (Filter Time):** 1.0 s
* **DZ (Deadband):** 2.0 %

### 9. LIC-329505
* **Description:** 329011,CPL
* **Gain:** 2.50
* **TI (Integral Time):** 60.0 s
* **TD (Derivative Time):** 0.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 8. LIC-335501
* **Description:** 335R001A/B,AII
* **Gain:** 0.50
* **TI (Integral Time):** 400.0 s
* **TD (Derivative Time):** -1.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 1. LIC-335505
* **Description:** 309064,AL
* **Gain:** 0.30
* **TI (Integral Time):** 140.0 s
* **TD (Derivative Time):** 0.0 s
* **TF (Filter Time):** 4.0 s
* **DZ (Deadband):** 2.0 %

### 2. LIC-335508
* **Description:** 335D002,US
* **Gain:** 3.00
* **TI (Integral Time):** 299.0 s
* **TD (Derivative Time):** 1.5 s
* **TF (Filter Time):** 25.0 s
* **DZ (Deadband):** 2.0 %

### 3. LIC-335509
* **Description:** 335115,US
* **Gain:** 2.99
* **TI (Integral Time):** 149.0 s
* **TD (Derivative Time):** 1.5 s
* **TF (Filter Time):** 25.0 s
* **DZ (Deadband):** 2.0 %

### 7. PIC-322201
* **Description:** 322C001,GCB
* **Gain:** 6.00
* **TI (Integral Time):** 30.0 s
* **TD (Derivative Time):** 0.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 3. PIC-323202B
* **Description:** 329058,WC
* **Gain:** 1.00
* **TI (Integral Time):** 100.0 s
* **TD (Derivative Time):** 0.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 4. PIC-323203
* **Description:** 323F004,GCB
* **Gain:** 0.60
* **TI (Integral Time):** 100.0 s
* **TD (Derivative Time):** -1.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 2. PIC-324202
* **Description:** 324E002,VP
* **Gain:** 2.00
* **TI (Integral Time):** 200.0 s
* **TD (Derivative Time):** -1.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 5. PIC-324203
* **Description:** 324E005,VP
* **Gain:** 2.00
* **TI (Integral Time):** 200.0 s
* **TD (Derivative Time):** -1.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 6. PIC-328202
* **Description:** 328D001 GAS OUTLET
* **Gain:** 2.50
* **TI (Integral Time):** 200.0 s
* **TD (Derivative Time):** 0.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 1. PIC-328203
* **Description:** 328C003,STMH
* **Gain:** 1.50
* **TI (Integral Time):** 50.0 s
* **TD (Derivative Time):** -1.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 1. PIC-329202
* **Description:** 329358,STLS
* **Gain:** 0.65
* **TI (Integral Time):** 30.0 s
* **TD (Derivative Time):** 0.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 10. PIC-329203
* **Description:** 329360,STLS
* **Gain:** 0.30
* **TI (Integral Time):** 75.0 s
* **TD (Derivative Time):** -1.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 1. PIC-329204
* **Description:** 329D005,STMH
* **Gain:** 1.80
* **TI (Integral Time):** 100.0 s
* **TD (Derivative Time):** -1.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 5. PIC-329207A
* **Description:** 329356,STLS
* **Gain:** 6.00
* **TI (Integral Time):** 150.0 s
* **TD (Derivative Time):** -1.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 6. PIC-329207B
* **Description:** 329356,STLS
* **Gain:** 4.00
* **TI (Integral Time):** 150.0 s
* **TD (Derivative Time):** 0.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 4. PIC-329207C
* **Description:** 329356,STLS
* **Gain:** 4.00
* **TI (Integral Time):** 200.0 s
* **TD (Derivative Time):** -1.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 6. PIC-329208
* **Description:** 329433,STLS
* **Gain:** 0.20
* **TI (Integral Time):** 60.0 s
* **TD (Derivative Time):** 0.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 3. PIC-329212
* **Description:** 329362,STLS
* **Gain:** 0.65
* **TI (Integral Time):** 130.0 s
* **TD (Derivative Time):** -1.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 7. PIC-335201
* **Description:** 335R001 GRANULATOR
* **Gain:** 0.65
* **TI (Integral Time):** 40.0 s
* **TD (Derivative Time):** 0.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 1. PIC-335203
* **Description:** 335R001B,AID
* **Gain:** 0.22
* **TI (Integral Time):** 18.0 s
* **TD (Derivative Time):** 0.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 2. PIC-335225
* **Description:** STLS, 335E002
* **Gain:** 1.00
* **TI (Integral Time):** 100.0 s
* **TD (Derivative Time):** 0.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 1. SIC-323901
* **Description:** HP CARB.PUM.323P001A
* **Gain:** 1.10
* **TI (Integral Time):** 30.0 s
* **TD (Derivative Time):** 0.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 2. SIC-323902
* **Description:** HP CARB.PUM.323P001B
* **Gain:** 1.10
* **TI (Integral Time):** 30.0 s
* **TD (Derivative Time):** 0.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 2. TIC-323007
* **Description:** 323266,US
* **Gain:** 2.00
* **TI (Integral Time):** 500.0 s
* **TD (Derivative Time):** -1.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 4. TIC-323013
* **Description:** 329058,CW
* **Gain:** 1.00
* **TI (Integral Time):** 100.0 s
* **TD (Derivative Time):** 0.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 1. TIC-324001
* **Description:** 324021,US
* **Gain:** 1.50
* **TI (Integral Time):** 320.0 s
* **TD (Derivative Time):** 0.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %
* **OTS sim:** Kc = **0.02**, Ti = **360.0 s** (Appendix B) — not these values.

### 4. TIC-324002
* **Description:** 324020,US
* **Gain:** 2.00
* **TI (Integral Time):** 300.0 s
* **TD (Derivative Time):** 0.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %
* **OTS sim:** Kc = **0.02**, Ti = **360.0 s** (Appendix B) — not these values.

### 9. TIC-328002
* **Description:** LIQU.OUT REFLUX COND
* **Gain:** 3.00
* **TI (Integral Time):** 500.0 s
* **TD (Derivative Time):** 0.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 2. TIC-329005
* **Description:** 329054, WC
* **Gain:** 1.50
* **TI (Integral Time):** 300.0 s
* **TD (Derivative Time):** -1.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 5. TIC-335001
* **Description:** 335R001-N3,AID
* **Gain:** 0.80
* **TI (Integral Time):** 15.0 s
* **TD (Derivative Time):** 0.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 7. TIC-335003
* **Description:** 335R001-N4A/B,AID
* **Gain:** 1.80
* **TI (Integral Time):** 150.0 s
* **TD (Derivative Time):** -1.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 6. TIC-335013
* **Description:** 335365,STLS
* **Gain:** 1.20
* **TI (Integral Time):** 100.0 s
* **TD (Derivative Time):** 0.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 3. TIC-335015
* **Description:** 335552,AI
* **Gain:** 2.00
* **TI (Integral Time):** 200.0 s
* **TD (Derivative Time):** -1.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 9. TIC-335017
* **Description:** 335559,AI
* **Gain:** 1.50
* **TI (Integral Time):** 200.0 s
* **TD (Derivative Time):** 0.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 10. TIC-335020
* **Description:** 335302,STLS
* **Gain:** 1.15
* **TI (Integral Time):** 375.0 s
* **TD (Derivative Time):** 0.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 4. TIC-335103
* **Description:** 335365,STLS
* **Gain:** 1.00
* **TI (Integral Time):** 100.0 s
* **TD (Derivative Time):** 0.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

---

## Appendix A — OTS Sim Velocity I-PD Constants (Units 323-2 / 328-1 / 328-2)

The tables above are the **as-designed plant DCS** constants (parallel PID). The OTS
simulation (`backend/main.py`) implements a **discrete velocity-form I-PD** with a 0.1 s
step and a 5 s first-order flow lag, so its `Kc`/`Ti` are re-derived for numerical
stability, **not** copied from the plant table. This appendix records the constants
actually seeded in `State.__init__` for every controller added for the LP Recirculation
& Desorption units, and documents the stability audit.

### Discrete stability of the flow (`_fic_flow`) loops

Velocity I-PD law (per `_ctrl_ipd`):
$$\Delta u_k = \mathrm{act}\cdot K_c\left[-(pv_k-pv_{k-1}) + \tfrac{\Delta t}{T_i}(sp-pv_k) - T_d\tfrac{pv_k-2pv_{k-1}+pv_{k-2}}{\Delta t}\right]$$

For a `_fic_flow` loop the PV is the **delivered flow** (kg/h), fed back through the lag
$pv = \mathrm{lag1}(design\cdot op/op_{des})$ with $a=\tfrac{\Delta t}{\tau+\Delta t}=\tfrac{0.1}{5.1}=0.019608$.
Linearising about the design fixed point, the op self-recursion coefficient is
$$1 - K_c\,a\,g,\qquad g=\frac{design}{op_{des}}\ \text{(kg/h per \%op)}.$$
Define the stability index $M = K_c\,g$. The pole is $1-aM$, so:

| regime | condition | index $M=K_c g$ |
| :--- | :--- | :---: |
| monotone, non-oscillatory | $aM<1$ | $M<51$ |
| damped oscillation | $1<aM<2$ | $51<M<102$ |
| **unstable (growing 0↔100 limit cycle)** | $aM>2$ | $M>102$ |

At the seed, $pv=sp$ bit-exact $\Rightarrow \Delta u=0$ for **any** $K_c$, so a mis-tuned
loop is quiescent until a disturbance (a moving cascade SP or a live upstream tie-in)
perturbs it — then it diverges if $M>102$. All `_fic_flow` loops are therefore held at
$M\lesssim40$ (≥2.5× margin) to survive the Domino live tie-ins.

### Flow controllers (`_fic_flow`, PV in kg/h)

| Tag | Unit | Loop (service) | Mode | act | Kc | Ti (s) | design (kg/h) | op_des | g | **M=Kc·g** | regime |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **FIC-323401** | 323-2 | 328D003 Comp-I flush 401 | AUTO | +1 | 1.20 | 25.0 | 823 | 50.0 | 16.5 | 19.8 | monotone |
| **FIC-323402** | 323-2 | 328D003 Comp-I wash 402 | AUTO | +1 | **0.50** | 25.0 | 2931 | 50.0 | 58.6 | 29.3 | monotone ¹ |
| **FIC-323418** | 323-2 | 323C005 makeup water | AUTO | +1 | 1.20 | 25.0 | 480 | 50.0 | 9.6 | 11.5 | monotone |
| **FIC-326402** | 328-1 | 328C003 hydrolyser MP-steam 911 | CAS | +1 | 1.20 | 25.0 | 1105 | 50.0 | 22.1 | 26.5 | monotone |
| **FIC-328401** | 328-1 | 328C004 desorber-II LP-steam 931 (slave) | CAS | +1 | **0.30** | 25.0 | 6495 | 50.0 | 129.9 | 39.0 | monotone ² |
| **FIC-328402** | 328-1 | 328D003 Comp-I→II transfer 744 | AUTO | +1 | **0.06** | 25.0 | 31478 | 50.0 | 629.6 | 37.8 | monotone ³ |
| **FIC-328404** | 328-1 | 328D001 reflux 775 | CAS | +1 | **0.50** | 25.0 | 1675 | 30.2 | 55.5 | 27.7 | monotone ¹ |
| FIC-328406 | 328-1 | 328D003 standby pump (spare) | MAN | +1 | 1.20 | 25.0 | — | — | — | — | inactive (op=0) |

### Ratio master (`FFIC`, PV = m931/m738 ratio)

| Tag | Unit | Loop | Mode | act | Kc | Ti (s) | note |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :--- |
| **FFIC-328401** | 328-1 | 328C004 steam/feed ratio master → FIC-328401 cas_sp | AUTO | +1 | 0.80 | 40.0 | PV is dimensionless ratio; effective $M\approx5\times10^{-7}$ (g=1/31114) → effectively frozen, stable. Output = LP-steam demand (kg/h), op_hi=12000. |

### Level / pressure / temperature controllers (PV in engineering units, standard I-PD)

These have small process gains (PV in %, bar a, or °C) and use conventional tuning; the
flow-loop stability index does not apply.

| Tag | Unit | Loop (service) | Mode | act | Kc | Ti (s) |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: |
| LIC-328501 | 328-1 | 328D001 reflux-drum level → LV-328501 | AUTO | −1 | 2.0 | 150.0 |
| PIC-328202 | 328-1 | 328D001 vent pressure → PV-328202 | AUTO | −1 | 5.0 | 40.0 |
| TIC-328002 | 328-1 | 328E004 CW to reflux condenser (hold 61 °C) | AUTO | −1 | 3.0 | 200.0 |
| PIC-328203 | 328-1 | 328C003 hydrolyser OVHD pressure (16.8 bar a) | AUTO | −1 | 4.0 | 60.0 |
| TIC-328008 | 328-1 | 328E007 effluent outlet temp (display trim) | AUTO | −1 | 3.0 | 250.0 |
| TIC-328012 | 328-1 | 328E021 cold-side outlet temp (display trim) | AUTO | −1 | 3.0 | 250.0 |
| LIC-328503 | 328-1 | 328C002 desorber-I bottoms level → LV-328503 | AUTO | −1 | 2.0 | 150.0 |
| LIC-328504 | 328-1 | 328C004 desorber-II bottoms level → LV-328504 | AUTO | −1 | 2.0 | 150.0 |
| LIC-328505 | 328-1 | 328C003 hydrolyser bottoms level → LV-328505 | AUTO | −1 | 2.0 | 150.0 |
| FIC-323405 | 323-2 | 323E003 wash-water trim (display only, not `_fic_flow`) | AUTO | +1 | 1.2 | 25.0 |
| PIC-322201 | 328-2 | 322C001 LP-absorber vent pressure (3.9 bar a) | AUTO | −1 | 5.0 | 40.0 |
| LIC-322502 | 328-2 | 322C001 sump level → LV-322502 | AUTO | −1 | 2.0 | 150.0 |

### Footnotes — stability retunes applied this revision

1. **FIC-323402, FIC-328404** — reduced Kc 1.20 → **0.50**. Both sat in the
   damped-oscillatory band ($M=70$ and $67$); they ring on any disturbance and would
   couple oscillation into the D003/D001 recycle tears once live tie-ins move their SPs.
   Kc=0.50 moves both to $M\approx28$ (coef ≈0.45, monotone).
2. **FIC-328401** — reduced Kc 1.20 → **0.30**. Root cause of the observed steam-cascade
   0↔100 limit cycle: with the FFIC master injecting a moving cascade SP, the $M=156$
   loop had pole $1-aM=-2.06$ (growing oscillation, eigenvalue ≈ −2.1/tick confirmed by
   per-tick trace). Kc=0.30 → $M=39$, pole +0.24 (monotone, 2.6× margin). This is the
   fix that restores 100 % steady-state H&MB closure (c004_T drift 5.2e-3 → 5.6e-9 °C).
3. **FIC-328402** — reduced Kc 1.20 → **0.06**. Latent instability: the 31478 kg/h
   transfer gives $g=630$, so $M=756$ (pole $1-aM=-13.8$, violently unstable). Quiescent
   only because it runs AUTO at a bit-exact fixed-point seed with no disturbance; a live
   Comp-I→II tie-in in the Domino phase would detonate it. Kc=0.06 → $M=38$, pole +0.26
   (monotone). Defensive — no steady-state effect (Δu=0 at the fixed point for any Kc).

Verification: `smoke_323_328.py` to t=3600 s (true steady state) → 323-1 anchors
135/106/99 °C bit-exact (drift 4.9e-9 / 7.3e-9 / 1.6e-11), all new-state drift ≤1e-5,
no non-finite, all flow loops hold design with no oscillation.

### Note — the flow-loop `Kc` column above is on the MASS basis

`FIC-323401/323402/323418`, `FIC-328402/328404/328406` were later converted to **volumetric**
loops: the operator enters SP in m³/h, and `Kc` is seeded in the engine as `Kc_mass · ρ` precisely
so the loop coefficient $1-K_c a g$ — and therefore the stability index $M$ and every conclusion in
the footnotes above — is **identical** to the mass-basis tune recorded here. So the engine reads
`FIC-323401 Kc = 1190.88` against `1.20` in the table (= $1.20 \times \rho_{401} = 1.20 \times 992.4$)
and `FIC-328402 Kc = 60.149` against `0.06`. Those are the same tuning in different units, not a
regression. The table is kept on the mass basis because that is the basis the stability analysis
above is written in; **do not "correct" the engine to these numbers.**

---

## Appendix B — OTS Sim: Unit-324 Evaporator Temperature Masters (retuned 2026-07-23, TD-015)

Authoritative for `backend/main.py` on these four loops. The plant DCS rows for TIC-324001 and
TIC-324002 are **not** used by the simulator and must not be copied into it.

### Constants as seeded in `State.__init__`

| Tag | Role | Mode | act | Kc | Ti (s) | Td | op range | seed op |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **TIC-324001** | 324E001 melt temp (130 °C) → PIC-329203 cas_sp | AUTO | +1 | **0.02** | **360.0** | 0.0 | 0 – 4.4 bar a | 3.96 bar a |
| PIC-329203 | 324E001 steam-chest pressure (slave) | CAS | +1 | 1.5 | 20.0 | 0.0 | 0 – 100 % | 90.0 % |
| **TIC-324002** | 324E003 melt temp (140 °C) → PIC-329212 cas_sp | AUTO | +1 | **0.02** | **360.0** | 0.0 | 0 – 4.4 bar a | 3.96 bar a |
| PIC-329212 | 324E003 steam-chest pressure (slave) | CAS | +1 | 1.5 | 20.0 | 0.0 | 0 – 100 % | 90.0 % |

`act = +1` in the velocity I-PD form is DCS **REVERSE** action: PV below SP ⇒ $(sp-pv)>0$ ⇒ Δu > 0
⇒ more chest pressure ⇒ more heat. Correct for a heater, and confirmed by the sign of the measured
gain below.

### Why the plant numbers do not transfer

Kc = 1.50 / 2.00 was not merely "a different plant" — until TD-015 was closed the simulated stage
had **no temperature dynamics at all**. `R324_Q1_DES_KW` is the design *latent* load and
`R324_LAM_V1` its back-solved latent heat, so on the duty branch $\dot m_{vap}\lambda/3600$ cancelled
$q_{avail}$ term for term and the net power was identically zero at every load. The controller was
integrating against a plant of **zero gain**. Any Kc was equally defensible, because none of them
did anything; the loop simply walked its valve down forever. So the inherited tuning carried no
information about the real process and could not be retained once the process became real.

### The measurement

Open-loop step test, master in **MAN**, ±0.05 bar on the chest-pressure demand, evaluated as a
**central difference over 1 h means** so the stage's own slow wander cancels rather than being read
as gain:

| Loop | base (°C) | +0.05 bar | −0.05 bar | $K_p$ |
| :--- | :---: | :---: | :---: | :---: |
| TIC-324001 | 130.0033 | 130.4231 | 129.5916 | **+8.32 °C/bar** |
| TIC-324002 | 140.0169 | 140.4353 | 139.6000 | **+8.35 °C/bar** |

At Kc = 2.0 that is a loop gain of $2.0 \times 8.3 = 16.6$ — which is exactly the multi-hour limit
cycle that was observed on the closed loop (T_e003 ±1.2 °C, PV-329212 swinging 81–90 %).

> **Do not reuse the first step test.** An earlier run reported $K_p \approx -17.5$ °C/bar for
> TIC-324002 — a *negative* gain, which would have meant the controller action was backwards. It was
> contaminated: the loops had already diverged within the same run, so the "step response" was
> mostly the divergence. The number is wrong. Both gains are positive.

### The derivation

Lambda tuning on the separator's own dynamics. $\tau \approx 360$ s (180 s liquid residence plus the
180 s bubble-point holdup lag), $\lambda = 3\tau = 1080$ s, and $\theta \approx 0$ because the
chest-pressure slave is fast at Ti = 20 s:

$$K_c = \frac{\tau}{K_p(\lambda + \theta)} = \frac{360}{8.3 \times 1080} = 0.0402 \;\rightarrow\; 0.04$$

**then halved to 0.02** (loop gain 0.166). The extra factor of two is not conservatism for its own
sake. `v_m = min(v_conc, v_duty)` is a **relay nonlinearity**, and the branch switching sustains a
slow limit cycle that no linear tuning removes. Halving the gain measurably shrinks it — 16 h
envelope T_e001 0.42 → **0.25 °C**, T_e003 1.33 → **0.88 °C** — and that response to gain is itself
the evidence that the residual is controller-driven rather than a plant instability.

Ti = 360 s follows the lambda rule's $T_i = \tau$.

### Residual, and what would remove it

The 0.25 / 0.88 °C envelope is **not zero and is not claimed to be**. It is bounded, and it replaces
a valve that previously walked without limit, but closing it means replacing the concentration cap
with a smooth equilibrium relation — **not** deleting the cap. Deleting it was tested: the melt runs
away and `psat(T)` underflows to a `ZeroDivisionError` in `conc_infer_324`. The cap is doing real
physical work. That replacement is a modelling change of its own and is not attempted.

### Seed invariance

The velocity form means $pv = sp = pv_1 \Rightarrow \Delta u = 0$ for **any** Kc/Ti, so this retune
cannot move the design pin — and does not: `leaves 25 / keys 15 / diffs 0`.

Gates: `backend/test_equation_audit_td014.py::test_the_unit_324_stages_carry_the_same_closure`
(asserts Kc = 0.02 and Ti = 360.0 directly, so drifting these constants fails the suite) and
`::test_the_324_evaporator_temperatures_stay_bounded`.