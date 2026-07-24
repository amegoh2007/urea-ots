Steam Condensate unit 329 mapping
Stream from 320E006 (consider BL) (MB Stream no.901) have flow meter “FT-329403”, temperature “TT-329101” and pressure “PT-329251”. The stream pressure is divided into 4 streams:
1-	(MB Stream no. 902) to “329D005” (HP steam drum) through PV=329204 that controls the amount of steam to 329D005
2-	(MB Stream no. 903) to “329D009” (MP steam drum) through PV-329205A that controls the amount of steam to 329D009
3-	(MB Stream no. 963) to “322D001 A/B” (LP steam drums) through PV-329207C and HV-329602 that controls the amount of steam to 322D001A/B
4-	(MB Stream no. 911) to “328C003” (Hydrolyzer)

“329D005” The HP Steam Saturator (Item 329D005) functions as a critical desuperheating vessel designed to condition medium-pressure (MP) steam before it is used as the heating medium in the High-Pressure (HP) Stripper (322E001). Operating as a $13.0\text{ m}^3$ horizontal vessel at approximately $212^\circ\text{C}$ and $19.9\text{ bar(a)}$, it receives superheated steam through a submerged, perforated sparger pipe (N1) featuring hundreds of finely machined distribution holes and saw-cuts. As this superheated steam forcefully bubbles through a liquid pool of hot steam condensate returning from the HP Stripper (entering via dip-pipe N3), it rapidly cools and absorbs moisture until it reaches full saturation. This fully saturated steam then exits through the top nozzle (N2) to drive the stripper, ensuring the maximum possible heat transfer coefficient (via latent heat of condensation) while protecting the stripper's heat exchange tubes from localized thermal shock or overheating.
On 329D005 there are:
    1- PIC=329204 pressure indicator controls the pressure inside 329D005 by controlling PV-329204 opening (steam pressure inside 329D005 = steam pressure in shell side of 322E001) 
    2- LIC-329502 level of 329D005 indicator that controls the level of condensate inside 329D005 by controling the LV-329502 on the discharge condensate stream to 329D009 (MP steam Drum) (MB stream no.904 before LV-329502) (MB stream no.905 for liquid phase and 906 for gas phase after LV-329502)
    3- A vent to atmoshphere controlled by a handvalve HV-329601 controlled by HIC-329601 to control the flow of HP steam through the vent
    4- Stream to HP-stripper 322E001 shell side with the same steam pressure as PIC-329204
    5- Condensate back from HP-stripper 322E001 shell side

The MP Steam Drum (Item 329D009) functions as a vital liquid-vapor separation and distribution vessel within the utilities network of the Stamicarbon urea process. Operating safely at $9.0\text{ bar(g)}$ and $175^\circ\text{C}$ with an $8.16\text{ m}^3$ capacity, it receives and manages the plant's saturated steam and condensate inventory. Internally, it utilizes a submerged distributor pipe equipped with precise $3\text{ mm}$ saw-cuts and internal baffle plates to ensure uniform flow distribution and efficient phase separation. By effectively decoupling the liquid condensate from the vapor phase, the drum provides a stable, continuous supply of high-quality saturated steam required to drive downstream process heaters while maintaining a liquid buffer to optimize the overall thermal recovery of the plant.
On 329D009 there are:
    1- PIC=329205 pressure indicator controls the pressure inside 329D09 by controlling PV-329205A and PV-329205B openings. "Control logic: A) If pressure inreases inside 329D009 over SP, PV-329205A closes untill it reaches 0%, then PV-329205B starts to open to discharge excess steam to 4bar steam header until SP is reached. B) If 329D009 pressure drop below SP, PV-329205B closes till it reaches 0% then PV-329205A starts to open to introduce steam from feed till SP is reached)
    2- LIC-329503 level of 329D009 indicator that controls the level of condensate inside 329D009 by controling the LV-329503 on the discharge condensate stream to 322D001A/b (LP steam Drums) (MB stream no.913 before LV-329503) (MB stream no.914 for liquid phase and 915 for gas phase after LV-329503)
    3- 9 bar Steam header that goes to the following:
                A) 2nd Evaporator H.Ex. 324E003 (2.46MW) PV-329212 (to be added to simulation environment in later units)
                B) Atomization Air Heater through PV-335225 (to be added to simulation environment in later units)
                C) Line to 4 bar steam header with PV-329205B to control steam pressure in 335D009 as discussed above

The LP Steam Drums serve as the central liquid-vapor separation vessels for the low-pressure steam generation system, designed to recover waste heat of condensation of Ammonia and CO2 in the HPCC (High Pressure Carbamate condenser). Operating at 4 barg  and 150°C , these vertical vessels function within a natural circulation loop (thermosyphon), where a steam-condensate mixture enters through a large inlet and saturated water recirculates back to the heat source via the bottom outlet. As the steam rises, it passes through a stainless steel demister pad to remove entrained water droplets before exiting to the LP header, while an internal MP steam sparger allows for pressure maintenance and heating during start-up phases
On 322D001A/B:
    1- LIC-329504 to control level inside 322001A/B by conntoling LV-329504 opening which controls the amount of condensate from 329P001A/B pumps (condensate pumps)
    2- Condensate line discharged to 322E002 (39.63MW)
    3- Steam line feed from 322E002 (39.63MW)
    4- TT-329001 indicatind temperature inside 322D001A/B
    5- Steam discharge to 4bar steam header with 2 pressure indicators PI-329206 and PI-329207. The pressure of the 4bar steam header controls condensation in HPCC On the 4bar steam header there are the following
                              A) H.Ex that consumes 4bar steam (will be added to the simulation in later stages)
                              B) LP steam to turbine 320MT02 through FV-329407 to indicate the steam flow to 320MT02 and PV-329207B to control pressure in 4bar header   
                              C) Vent to atmosphere through PV-329207A that controls pressure in 4bar header
     Control logic of pressure of 4bar steam header by MASTER SP. 
           MASTER SP logic: ON/OFF
                      OFF: PIC-329207A controls PV-329207A opening, 329207B controls PV-329207B opening and 329207C controls PV-329207C opening (All 3 controllers are controlled and set by user)
                      ON: User sets the SP. all 3 controllers are set according to the MASTER SP automatically and cannot be changed individually by user: PIC-329207A = MASTER SP + 0.1bar, PIC-329207B = MASTER SP and PIC-329207C = MASTER SP - 0.1bar