#include "lab/mass_properties.hpp"
#include "lab/flight_rk4.hpp"

#include <godot_cpp/classes/ref_counted.hpp>
#include <godot_cpp/core/class_db.hpp>
#include <godot_cpp/godot.hpp>
#include <godot_cpp/variant/array.hpp>
#include <godot_cpp/variant/dictionary.hpp>
#include <godot_cpp/variant/vector3.hpp>
#include <stdexcept>
#include <vector>

namespace godot {

class LabEngineering : public RefCounted {
    GDCLASS(LabEngineering, RefCounted)

protected:
    static void _bind_methods() {
        ClassDB::bind_method(D_METHOD("mass_properties", "parts"), &LabEngineering::mass_properties);
        ClassDB::bind_method(D_METHOD("check_clearance", "rotors", "minimum_required_m"), &LabEngineering::check_clearance);
        ClassDB::bind_method(D_METHOD("simulate_rk4", "config"), &LabEngineering::simulate_rk4);
    }

public:
    Dictionary mass_properties(const Array &parts) const {
        Dictionary output;
        try {
            std::vector<lab::MassPoint> values;
            for (int64_t index = 0; index < parts.size(); ++index) {
                if (parts[index].get_type() != Variant::DICTIONARY) {
                    throw std::invalid_argument("Each part must be a dictionary");
                }
                const Dictionary part = parts[index];
                const Variant mass = part.get("mass_kg", Variant());
                const Variant coordinates = part.get("position_m", Variant());
                if ((mass.get_type() != Variant::FLOAT && mass.get_type() != Variant::INT)
                    || coordinates.get_type() != Variant::ARRAY) {
                    throw std::invalid_argument("A part needs mass_kg and position_m");
                }
                const Array position = coordinates;
                if (position.size() != 3) {
                    throw std::invalid_argument("A position needs three coordinates");
                }
                lab::Vector3 point;
                for (int axis = 0; axis < 3; ++axis) {
                    if (position[axis].get_type() != Variant::FLOAT && position[axis].get_type() != Variant::INT) {
                        throw std::invalid_argument("Coordinates must be numbers");
                    }
                    point[axis] = double(position[axis]);
                }
                values.push_back({double(mass), point});
            }
            const auto result = lab::combine_mass_points(values);
            Array center;
            for (const double coordinate : result.center_of_mass_m) {
                center.push_back(coordinate);
            }
            output["ok"] = true;
            output["mass_kg"] = result.mass_kg;
            output["center_of_mass_m"] = center;
        } catch (const std::exception &error) {
            output["ok"] = false;
            output["error"] = String(error.what());
        }
        return output;
    }

    Dictionary check_clearance(const Array &rotors, double minimum_required_m) const {
        Dictionary output;
        try {
            std::vector<lab::RotorDisk> disks;
            for (int64_t index = 0; index < rotors.size(); ++index) {
                if (rotors[index].get_type() != Variant::DICTIONARY) {
                    throw std::invalid_argument("Each rotor must be a dictionary");
                }
                const Dictionary r = rotors[index];
                const Variant rad = r.get("radius_m", Variant());
                const Variant coords = r.get("position_m", Variant());
                if ((rad.get_type() != Variant::FLOAT && rad.get_type() != Variant::INT)
                    || coords.get_type() != Variant::ARRAY) {
                    throw std::invalid_argument("A rotor needs radius_m and position_m");
                }
                const Array pos = coords;
                if (pos.size() != 3) {
                    throw std::invalid_argument("A position needs three coordinates");
                }
                lab::Vector3 p;
                for (int axis = 0; axis < 3; ++axis) {
                    p[axis] = double(pos[axis]);
                }
                disks.push_back({p, double(rad)});
            }
            const auto res = lab::evaluate_rotor_pair_clearance(disks, minimum_required_m);
            output["ok"] = true;
            output["clear"] = res.clear;
            output["minimum_tip_clearance_m"] = res.minimum_tip_clearance_m;
        } catch (const std::exception &error) {
            output["ok"] = false;
            output["error"] = String(error.what());
        }
        return output;
    }

    Dictionary simulate_rk4(const Dictionary &config) const {
        Dictionary output;
        try {
            lab::MultirotorSimConfig cfg;
            cfg.mass_kg = double(config.get("mass_kg", 1.5));
            cfg.n_rotors = int(config.get("n_rotors", 4));
            cfg.max_total_thrust_n = double(config.get("max_total_thrust_n", 56.0));
            cfg.cd_a_m2 = double(config.get("cd_a_m2", 0.05));
            cfg.air_density_kg_m3 = double(config.get("air_density_kg_m3", 1.225));
            cfg.initial_altitude_m = double(config.get("initial_altitude_m", 2.0));
            cfg.target_altitude_m = double(config.get("target_altitude_m", 2.0));
            cfg.dt_s = double(config.get("dt_s", 0.004));
            cfg.duration_s = double(config.get("duration_s", 0.4));
            cfg.min_bus_voltage_v = double(config.get("min_bus_voltage_v", 19.2));
            const Variant wind = config.get("wind_world_m_s", Variant());
            if (wind.get_type() == Variant::ARRAY) {
                const Array w = wind;
                if (w.size() == 3) {
                    cfg.wind_world_m_s = {double(w[0]), double(w[1]), double(w[2])};
                }
            }
            const auto res = lab::run_multirotor_rk4(cfg);
            Array pos_arr;
            for (const double c : res.final_position_m) {
                pos_arr.push_back(c);
            }
            Array t_arr;
            Array x_arr;
            Array y_arr;
            Array z_arr;
            Array q_arr;
            for (std::size_t i = 0; i < res.times_s.size(); ++i) {
                t_arr.push_back(res.times_s[i]);
                x_arr.push_back(res.positions_m[i][0]);
                y_arr.push_back(res.positions_m[i][1]);
                z_arr.push_back(res.positions_m[i][2]);
                Array q;
                for (double qc : res.quaternions_wxyz[i]) q.push_back(qc);
                q_arr.push_back(q);
            }
            Dictionary telemetry;
            telemetry["t"] = t_arr;
            telemetry["x"] = x_arr;
            telemetry["y"] = y_arr;
            telemetry["z"] = z_arr;
            telemetry["q_wxyz"] = q_arr;
            output["ok"] = true;
            output["aborted"] = res.aborted;
            output["reason"] = String(res.error_or_reason.c_str());
            output["step_count"] = res.step_count;
            output["max_altitude_m"] = res.max_altitude_m;
            output["min_bus_voltage_v"] = res.min_bus_voltage_v;
            output["final_position_m"] = pos_arr;
            output["telemetry"] = telemetry;
        } catch (const std::exception &error) {
            output["ok"] = false;
            output["error"] = String(error.what());
        }
        return output;
    }
};

void initialize_lab(ModuleInitializationLevel level) {
    if (level == MODULE_INITIALIZATION_LEVEL_SCENE) {
        ClassDB::register_class<LabEngineering>();
    }
}

extern "C" {
GDExtensionBool GDE_EXPORT lab_library_init(GDExtensionInterfaceGetProcAddress get_proc_address,
                                          GDExtensionClassLibraryPtr library,
                                          GDExtensionInitialization *initialization) {
    GDExtensionBinding::InitObject init(get_proc_address, library, initialization);
    init.register_initializer(initialize_lab);
    init.set_minimum_library_initialization_level(MODULE_INITIALIZATION_LEVEL_SCENE);
    return init.init();
}
}

} // namespace godot
