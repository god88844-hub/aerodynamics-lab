#pragma once

#include <string>
#include <vector>

namespace lab {

enum class StandardPartShape {
    MotorCan = 0,
    Turbine = 1,
    Propeller = 2,
    BatteryBox = 3,
    PcbModule = 4,
    FastenerBolt = 5,
    BallBearing = 6,
    StructuralTube = 7,
    ServoBlock = 8,
};

struct StandardPartSpec {
    std::string id;
    std::string category;
    std::string name;
    StandardPartShape shape = StandardPartShape::MotorCan;
    double mass_kg = 0.01;
    double od_mm = 20.0;
    double id_mm = 5.0;
    double length_mm = 20.0;
    double width_mm = 20.0;
    double height_mm = 10.0;
    double kv = 0.0;
    int voltage_s = 0;
    double capacity_ah = 0.0;
    double r0_ohm = 0.025;
    double max_thrust_n = 0.0;
    double max_power_w = 0.0;
    double pitch_deg = 15.0;
    int blades = 2;
    int screw_size_idx = -1;
    double shear_capacity_n = 0.0;
    double dynamic_load_cr_n = 0.0;
    double ei_nm2 = 0.0;
    double stall_torque_nm = 0.0;
    std::string provenance = "UNVERIFIED_ESTIMATE";
};

const std::vector<StandardPartSpec> &standard_library_catalog();
const std::vector<std::string> &standard_library_categories();
std::vector<const StandardPartSpec *> search_standard_library(const std::string &category, const std::string &query);
const StandardPartSpec *find_standard_part_by_id(const std::string &id);

} // namespace lab
