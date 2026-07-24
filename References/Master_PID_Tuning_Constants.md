# Master PID Tuning Constants Report

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
| **LIC-328504** | 328C003,AW | 0.20 | 300.0 s | 0.0 s | 0.0 s | 2.0 % |
| **LIC-328505** | 328C004,CPP | 1.45 | 180.0 s | 0.0 s | 0.0 s | 2.0 % |
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
| **TIC-324001** | 324021,US | 1.50 | 320.0 s | 0.0 s | 0.0 s | 2.0 % |
| **TIC-324002** | 324020,US | 2.00 | 300.0 s | 0.0 s | 0.0 s | 2.0 % |
| **TIC-328002** | LIQU.OUT REFLUX COND | 3.00 | 500.0 s | 0.0 s | 0.0 s | 2.0 % |
| **TIC-329005** | 329054, WC | 1.50 | 300.0 s | -1.0 s | 0.0 s | 2.0 % |
| **TIC-335001** | 335R001-N3,AID | 0.80 | 150.0 s | 0.0 s | 0.0 s | 2.0 % |
| **TIC-335003** | 335R001-N4A/B,AID | 1.80 | 150.0 s | -1.0 s | 0.0 s | 2.0 % |
| **TIC-335013** | 335365,STLS | 1.20 | 100.0 s | 0.0 s | 0.0 s | 2.0 % |
| **TIC-335015** | 335552,AI | 2.00 | 200.0 s | -1.0 s | 0.0 s | 2.0 % |
| **TIC-335017** | 335559,AI | 1.50 | 200.0 s | 0.0 s | 0.0 s | 2.0 % |
| **TIC-335020** | 335302,STLS | 1.15 | 375.0 s | 0.0 s | 0.0 s | 2.0 % |
| **TIC-335103** | 335365,STLS | 1.00 | 100.0 s | 0.0 s | 0.0 s | 2.0 % |

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
* **Description:** 328C003,AW
* **Gain:** 0.20
* **TI (Integral Time):** 300.0 s
* **TD (Derivative Time):** 0.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

### 3. LIC-328505
* **Description:** 328C004,CPP
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

### 4. TIC-324002
* **Description:** 324020,US
* **Gain:** 2.00
* **TI (Integral Time):** 300.0 s
* **TD (Derivative Time):** 0.0 s
* **TF (Filter Time):** 0.0 s
* **DZ (Deadband):** 2.0 %

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