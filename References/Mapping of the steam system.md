Steam Feed and Branches 1 & 2
•	Mapping of the steam system.
•	Steam feed from 320MT02 (stream 901).
•	Steam branches:
o	
1.	328C003 stream no. 911.
o	
2.	To 329D005 through PV-329204.
	PIC-329204 on 329D005 controls and indicates pressure inside 329D005 by opening/closing PV-329204.
	329D005 supplies steam to 322E001.
	Condensate from 322E001 returns back to 329D005.
	LIC-329502 on 329D005 indicates and controls level inside 329D005.
	Excess condensate is flashed to 329D009 through LV-329502 (stream 904 before LV-329502, stream 905 liquid phase and 906 gas phase after LV-329502).
Image 2: Branch 3 (329D009 Cascade)
•	
3.	To 329D009 through PV-329205A.
o	PIC-329205 indicates and controls pressure inside 329D009 by open/close PV-329205A and PV-329205B.
o	PV-329205B vents steam to LP steam header (steam discharged from 322D001) (stream no. 960).
o	Condensate level inside 329D009 is indicated and controlled by LIC-329503 by open/close LV-329503.
o	Excess condensate is flashed to 322D001 through LV-329503 (stream no. 913 before LV-329503, stream nos 914 (liquid phase) and 915 (gas phase) after LV-329503).
o	329D009 supplies steam to its consumers.
o	Condensate from LV-329502 add to steam and condensate of 329D009 after being flashed (streams 904, 905 and 906).
Image 3: Branch 4 (322D001 Cascade)
•	
4.	Steam to 322D001 through PV-329207C (stream 963).
o	HV-329602 could be used to supply steam to 322D001 if required (default closed).
o	Condensate from LV-329503 adds to steam and condensate of 322D001 after being flashed (streams 913, 914, 915).
o	Condensate is supplied to 322D001 through LV-329504 (stream 916).
o	LIC-329504 indicates and controls level inside 322D001 by open/close LV-329504.
o	Condensate is supplied to 322E002 shell side to absorb heat of condensation occuring in 322E002 tube side. The produced steam in the shell side is supplied back to 322D001.
o	Constant blowdown from 322E002 (stream 959) (static).
o	Discharge steam from 322D001 is supplied to its consumers through the LP steam header.
•	NOTES:
o	PT-329206 and PT-329207 are on LP steam header indicating its pressure.
•	For consumers which are not in the simulation environment should consume steam as per PFD figures untill added in future units.
•	For consumers which are in the simulation environment, consumption value to be dynamic according to the modelling equation of this equipment.
•	FT-329403 and FT-329407 to be calculated according to the following data.
•	335E001A/B/C can consume from 329D009 or 322D001 (according to users choice) (to be added with granulation units.).
Steam Consumers List:
•	A) 329D005 :- 322E001 (shell side).
•	B) 329D009 :-
1.	324E003 (shell side) stream no. 920
2.	335E002 (to be added with granulation unit) stream no. 882
3.	335E001A stream no. 885 (to be added with granulation unit)
4.	335E001B stream no. 886 (to be added with granulation unit)
5.	335E001C stream no. 887 (to be added with granulation unit)
•	C) 322D001 consumers
1.	324F002 (stream no. 924)
2.	324F004 (stream no. 927)
3.	324F005 (stream no. 929)
4.	323E010 (stream no. 926) (7.05 MW)
5.	323E002 (stream no. 918) (5.46 MW)
6.	324E001 (stream no. 919) (11.23 MW)
7.	Melt line (stream no. 965)
8.	Steam tracing (stream no. 923)
9.	328C004 (stream no. 931)
10.	335E001A (stream no. 883)
11.	335E001B (stream no. 884)
12.	335E001C (stream no. 881) NOTES:
13.	Granulation steam tracing (stream no. 878)
14.	335D004 steam injection (stream no. 877)
15.	335E004 (stream no. 875)
16.	335E009 (stream no. 876)
17.	LP to storage (consider B.L.) (stream no. 999)
•	D) 328C003 (stream no. 911)

