import math

class Equipment:
    def __init__(self, name):
        self.name = name

class Reactor(Equipment):
    def __init__(self, name, diameter, height, num_trays):
        super().__init__(name)
        self.diameter = diameter  # meters
        self.height = height      # meters
        self.num_trays = num_trays

    def calc_pressure_drop(self, mass_flow_kg_s, density_kg_m3, viscosity_pa_s):
        """
        Calculates the pressure drop across the reactor.
        Includes hydrostatic head (since flow is upward) and sieve tray frictional pressure drop.
        """
        area = math.pi * (self.diameter / 2)**2
        velocity = mass_flow_kg_s / (density_kg_m3 * area)
        
        # Hydrostatic head
        static_head_pa = density_kg_m3 * 9.81 * self.height
        
        # Sieve tray pressure drop (empirical estimate: orifice velocity head loss)
        # Assuming ~10% free area for sieve trays
        hole_velocity = velocity / 0.10
        tray_dp_pa = self.num_trays * (0.5 * density_kg_m3 * hole_velocity**2) * 1.5 
        
        total_dp_pa = static_head_pa + tray_dp_pa
        # Convert Pa to bar
        return total_dp_pa / 100000.0

class ShellAndTubeExchanger(Equipment):
    def __init__(self, name, num_tubes, tube_length, tube_id, tube_od):
        super().__init__(name)
        self.num_tubes = num_tubes
        self.tube_length = tube_length  # meters
        self.tube_id = tube_id          # meters
        self.tube_od = tube_od          # meters

    def calc_tube_side_dp(self, mass_flow_kg_s, density_kg_m3, viscosity_pa_s):
        """
        Calculates the tube-side pressure drop using the Darcy-Weisbach equation.
        """
        area_per_tube = math.pi * (self.tube_id / 2)**2
        total_flow_area = self.num_tubes * area_per_tube
        
        velocity = mass_flow_kg_s / (density_kg_m3 * total_flow_area)
        
        # Reynolds Number
        re = (density_kg_m3 * velocity * self.tube_id) / viscosity_pa_s if viscosity_pa_s > 0 else 1e5
        
        # Darcy Friction Factor
        if re < 2300:
            f = 64.0 / re
        else:
            # Colebrook approximation (Haaland equation for smooth tubes)
            f = (1.8 * math.log10(6.9 / re)) ** -2
            
        # Frictional pressure drop
        dp_friction_pa = f * (self.tube_length / self.tube_id) * (0.5 * density_kg_m3 * velocity**2)
        
        # Minor losses (inlet + outlet to tube sheet)
        # K_inlet ~ 0.5, K_outlet ~ 1.0 -> Total K = 1.5
        dp_minor_pa = 1.5 * (0.5 * density_kg_m3 * velocity**2)
        
        total_dp_pa = dp_friction_pa + dp_minor_pa
        # Convert Pa to bar
        return total_dp_pa / 100000.0

# ==========================================
# Initialize Equipment with Datasheet Values
# ==========================================

# R01: 322R001 Reactor
# Dim: ID = 2950mm, Length ~ 25m, 11 sieve trays
reactor_r01 = Reactor(name="R01 (322R001) Urea Reactor", diameter=2.95, height=25.0, num_trays=11)

# E01: 322E001 CO2 Stripper
# Dim: 2600 tubes, L = 6000mm, Tube OD=31mm, Wall=3mm (ID=25mm)
stripper_e01 = ShellAndTubeExchanger(name="E01 (322E001) CO2 Stripper", num_tubes=2600, tube_length=6.0, tube_id=0.025, tube_od=0.031)

# E02: 322E002 HP Carbamate Condenser
# Dim: 2929 tubes, L = 11208mm, Tube OD=25mm, Wall=2.5mm (ID=20mm)
condenser_e02 = ShellAndTubeExchanger(name="E02 (322E002) HP Condenser", num_tubes=2929, tube_length=11.208, tube_id=0.020, tube_od=0.025)

# E03: 322E003 HP Scrubber
# Dim: 525 tubes, L = 2170mm, Tube OD=25mm, Wall=2.5mm (ID=20mm)
scrubber_e03 = ShellAndTubeExchanger(name="E03 (322E003) HP Scrubber", num_tubes=525, tube_length=2.170, tube_id=0.020, tube_od=0.025)
