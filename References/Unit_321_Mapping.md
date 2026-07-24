# Unit 321 mapping [cite: 1]

## 1. Ammonia Liquid Supply and Intermediate Tank
Ammonia liquid comes from “309E005” (consider BL “Battery Limit”) to the intermediate tank “321D003” [cite: 2].
U/S “321D003” there is a flowmeter “FT-321401” [cite: 3].
The properties of the feed line to “321D003” is as follows [cite: 4]:

### Feed Line Properties to 321D003 [cite: 5]
| Component | Mol. Wt. | Value |
| :--- | :--- | :--- |
| Biuret | 103.0810 | 0.15 |
| Methane | 16.0430 | |
| Carbon Dioxide | 44.0098 | 0.01 |
| Hydrogen | 2.0158 | 0.08 |
| Water | 18.0152 | 0.04 |
| Nitrogen | 28.0134 | 99.67 |
| Ammonia | 17.0304 | |
| Oxygen | 31.9988 | |
| Urea | 60.0560 | |

| Parameter | Unit | Value |
| :--- | :--- | :--- |
| Molar Flow total | kmol/h | 2,411.48 |
| Mass Flow total | kg/h | 41,042 |
| Volume Flow | m3/h | 67.90 |
| Average Molar Weight | kg/kmol | 17.02 |
| Density eff. | kg/m3 | 604.80 |
| Operating Temperature | CEL | 25 |
| Operating Pressure | bar a | 26.0 |

On “321D003” is always fully filled with ammonia, The following transmitters are on “”321D003” [cite: 6]:
* 1- level switch “LSL-321501” which is green when full and turns red when empty [cite: 7].
* 2- Temperature transmitter “TT-321001” (left side of “321D003” [cite: 8].
* 3- Temperature transmitter “TT-321002” (right side of “321D003”) [cite: 9]. This temperature is used to calculate the saturated vapore pressure of NH3 at this temperature [cite: 9].

The result of this calculation is placed in 2 calculated parameter boxes “PY-321202” at the top and “PY-321201” at the bottom [cite: 10].
D/S “321D003” there is an “XV-321901” which is open during normal operation [cite: 11].

## 2. Pumps and Associated Transmitters
Pressure transmitter on suction of pump “321P002A” is “PT-321201” [cite: 12].
Pressure transmitter on suction of pump “321P002B” is “PT-321202” [cite: 13].
“PDY-321203” is a calculated box (PDY-321203 = PT-321201 – PY-321201) (must be positive to ensure that the NH3 is in liquid form) [cite: 14].
“PDY-321204” is a calculated box (PDY-321204 = PT-321202 – PY-321202) (must be positive to ensure that the NH3 is in liquid form) [cite: 15].

The properties of the streams U/S pumps “321P002 A” and “321P002 B” is as follows [cite: 16]:

### Streams U/S Pumps Properties [cite: 17]
| Component | Mol. Wt. | Value |
| :--- | :--- | :--- |
| Biuret | 103.0810 | 0.15 |
| Methane | 16.0430 | |
| Carbon Dioxide | 44.0098 | 0.01 |
| Hydrogen | 2.0158 | 0.08 |
| Water | 18.0152 | 0.04 |
| Nitrogen | 28.0134 | 99.67 |
| Ammonia | 17.0304 | |
| Oxygen | 31.9988 | |
| Urea | 60.0560 | |

| Parameter | Unit | Value |
| :--- | :--- | :--- |
| Molar Flow total | kmol/h | 2,394.66 |
| Mass Flow total | kg/h | 40,756 |
| Volume Flow | m3/h | 67.40 |
| Average Molar Weight | kg/kmol | 17.02 |
| Density eff. | kg/m3 | 604.80 |
| Operating Temperature | CEL | 25 |
| Operating Pressure | bar a | 26.0 |

“IT-321961” measures “321P002A” amperes [cite: 27].
“IT-321962” measures "321P002B” amperes [cite: 28].
D/S both pumps there is a temperature transmitter “TT-321-020” then “XV-322001” [cite: 29].

## 3. Pump Control Modes
Speed of pump “321P002 A” is controlled by speed controller “SIC-321950” [cite: 18].
Speed of pump “321P002 B” is controlled by speed controller “SIC-321951” [cite: 19].
Both pumps speed control modes as follows [cite: 20]:
* MAN: Set the pumps torque converter valve [cite: 21].
* Auto: The SP is the pumps speed (RPM) to control the pumps torque converter valve [cite: 22].
* CAS: The SP is the N/C molar ratio between NH3 feed and CO2 feed [cite: 23].

The pump speed is calculated according to CO2 feed flow “FT-322403” (not in this screen) [cite: 24].
CO2 feed properties is as follows [cite: 25]:

### CO2 Feed Properties [cite: 26]
| Component | Mol. Wt. | Value |
| :--- | :--- | :--- |
| Biuret | 103.0810 | |
| Methane | 16.0430 | 95.24 |
| Carbon Dioxide | 44.0098 | |
| Hydrogen | 2.0158 | 0.61 |
| Water | 18.0152 | 3.55 |
| Nitrogen | 28.0134 | |
| Ammonia | 17.0304 | 0.60 |
| Oxygen | 31.9988 | |
| Urea | 60.0560 | |

| Parameter | Unit | Value |
| :--- | :--- | :--- |
| Molar Flow total | kmol/h | 1,264.00 |
| Mass Flow total | kg/h | 54,618 |
| Volume Flow | m3/h | 225.00 |
| Average Molar Weight | kg/kmol | 43.21 |
| Density eff. | kg/m3 | 242.70 |
| Operating Temperature | CEL | 120 |
| Operating Pressure | bar a | 144.2 |
