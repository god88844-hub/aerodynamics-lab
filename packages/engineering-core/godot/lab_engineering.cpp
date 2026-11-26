#include "lab/mass_properties.hpp"

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
