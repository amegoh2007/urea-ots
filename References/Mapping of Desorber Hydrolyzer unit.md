
	Pump 328P004 discharges tank 328D003 and pumps the solution to 328E007 through FV-328402 (stream 735).
	328E007 heats the feed and then it flows to 328C002 (stream 738). This stream have temp indicator TT-328010.
	The feed enters 328C002 between the 2^"nd"  and the 3^"rd"  tray.
	PIC-328202 indicates and controls pressure in 328C002 by open/close PV-328202
	328C002 have a level indicator at the bottom LIC-328503 which indicates and controls level in the bottom of 1^"st"  desorber 328C002.
	Gases rise up from 328C004 to the bottom of 328C002 (stream 750) to desorb gases from the feed.
	Solution is discharged from the bottom of 328C002 to 328P006. This stream have temp indicator TT-328007 (Stream 743).
	The pump 328P006 pumps the solution to 328E021 A/B to be heated.
	The solution then flows from 328E021 A/B to the top of the 1^"st"  tray of the hydrolyzer 328C003 through LV-328503 (stream 746).
	The solution is hydrolyzer in 328C003 where urea is converted to 〖"NH" 〗_3 and 〖"CO" 〗_2.
	On 328C003, there is a level indicator LIC-328504 which indicates and controls solution level above the 1^"st"  top tray by open/close LV-328504.
	On the 3^"rd"  tray of 328C003 there is a temp indicator TT-328012.
	Hydrolyzed Solution is discharged from the bottom of 328C003 to 328E021 A/B (stream 747). This line has temp indicator TT-328013.
	Hydrolyzed solution is then discharged from 328E021 A/B to LV-328504 (stream 749).
	Solution flows from LV-328504 to the top of the 1^"st"  tray of 328C004 to be desorbed (Stream 779 Liquid phase, stream 780 Gas phase).
	Gases from 328C003 is discharged from the top (stream 748) and flows to 5^"th"  tray of 328C002 through PV-328203. TT-328011 indicates temp of this line.
	Steam from the main feed steam header is injected on the bottom of 328C003 through FV-329402. FIC-329402 on this line indicates and controls the flow of steam to 328C003 by open/close FV-329402 (stream 911).
	PIC-328203: Pressure controller on the steam line to 328C003 after FV-329402. PIC-328203 indicates and controls pressure inside 328C003 by open/close PV-328203.
	Gases evolving from the top tray of 328C004 (stream 781).
	TT-328004 is on the 2^"nd"  tray of 328C004 indicating its temp.
	LP steam is injected to the bottom of 328C004 through FV-329401 to desorb 〖"NH" 〗_3+〖"CO" 〗_2 from the solution.
	FIC-329401 measures and controls steam flow to 328C004 by open/close FV-329401 (stream 931).
	If FIC-328404 is put on CAS mode, TIC-328008 open/close FV-328404 to adjust TIC-328008 to its SP.
	FFIC-329401 is FIC-329401 : FIC-328402 ratio Ton/"m" ^3.
	If FIC-329401 is put on CAS mode (default), FFIC-329401 open/close FV-329401 to adjust FFIC-329401 to its SP.
	Gases flowing from 328C004 top to 328C002 bottom (stream 750).
	LIC-328505 is on the bottom of 328C004 indicates and controls its level by open/close LV-328505.
	Process condensate is discharged from the bottom of 328C004 to 328E007 to heat 328C002 feed (stream 739). This stream have TT-328005 that indicates its temperature.
	Process condensate is discharged from 328E007 to pump 328P007 (stream 740). (TT-328006) indicates line temp. AT-328701 indicates stream conductivity
	The discharge of the pump 328P007 flows in 2 lines:
	To cooling tower (consider B.L) through LV-328505.
	To 328E001 then recycled back to 2^"nd"  compartment of 328D003 through FV-328406. FIC-328406 indicates and controls this flow by open/close FV-328406. (FV-328406 is closed during normal operation. If FIC-328406 is set on CAS, controls LIC-328505 and LV-328406 is closed.
	Gases of 328C002 is discharged from the top of 328C002 to 328E004 shell side (stream 737): 2 more stream are injected to this stream:
	Stream from 328P008 discharge line (stream 718A) through FV-328405. FIC-328405 indicates and controls flow in this stream by open/close FV-328405
	Stream from discharge of 328P003 (stream 793).
	328E004 is cooled by cooling water in the tube side.
	Condensed solution is collected from the top of 328E004 shell side and discharged to 328D001.
	328D001 separates Liquid from gases.
	328D001 have LIC-328501 which indicates and controls level inside 328D001 by open/close LV-328501
	Gases of 328D001 is discharged from top of 328D001 to 328E011 (stream 786) through PV-328202.
	Solution of 328D001 is discharged from bottom of 328D001 to pump 328P002 (stream 774) (TIC-328008 / TIC-328002).
	Discharge of 328P002 flows to:
	323E003 (stream 776) through LV-328501. FT-328401 indicates the flow of this stream
	Reflux flows back to the top tray of 328C002 through FV-328404. FIC-328404 controls reflux flow by open/close FV-328404.
	TIC-328008 calculates water content in gases from 328C002 to 328E004 using TT-328008 and PIC-328202.
