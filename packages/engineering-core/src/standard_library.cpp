#include "lab/standard_library.hpp"

#include <algorithm>
#include <cctype>

namespace lab {

namespace {
std::string to_lower_copy(const std::string &s) {
    std::string out = s;
    for (char &ch : out) ch = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
    return out;
}
} // namespace

const std::vector<std::string> &standard_library_categories() {
    static const std::vector<std::string> kCats = {
        "All",
        "Motors",
        "Turbines & EDFs",
        "Propellers",
        "Batteries & Tanks",
        "ESCs & Avionics",
        "Fasteners",
        "Bearings & Guides",
        "Tubes & Structures",
    };
    return kCats;
}

const std::vector<StandardPartSpec> &standard_library_catalog() {
    static const std::vector<StandardPartSpec> kCatalog = {
        // Motors (11)
        {"motor_1103_8000kv", "Motors", "1103 8000KV Micro Brushless", StandardPartShape::MotorCan, 0.0038, 13.8, 1.5, 9.5, 13.8, 9.5, 8000, 2, 0.0, 0.04, 1.45, 55.0, 0, 2, -1, 0, 0, 0, 0, "MANUFACTURER_NOMINAL_UNVERIFIED_ESTIMATE"},
        {"motor_1404_4600kv", "Motors", "1404 4600KV Ultralight", StandardPartShape::MotorCan, 0.0092, 18.2, 1.5, 12.2, 18.2, 12.2, 4600, 3, 0.0, 0.03, 3.80, 160.0, 0, 2, -1, 0, 0, 0, 0, "MANUFACTURER_NOMINAL_UNVERIFIED_ESTIMATE"},
        {"motor_2207_1950kv", "Motors", "2207 1950KV Freestyle", StandardPartShape::MotorCan, 0.0325, 27.6, 5.0, 19.2, 27.6, 19.2, 1950, 6, 0.0, 0.02, 15.8, 880.0, 0, 2, -1, 0, 0, 0, 0, "MANUFACTURER_NOMINAL_UNVERIFIED_ESTIMATE"},
        {"motor_ecoii_2807_1300kv", "Motors", "ECOII 2807 1300KV Long-Range", StandardPartShape::MotorCan, 0.0485, 33.9, 5.0, 21.5, 33.9, 21.5, 1300, 4, 0.0, 0.018, 21.2, 920.0, 0, 2, -1, 0, 0, 0, 0, "MANUFACTURER_NOMINAL_UNVERIFIED_ESTIMATE"},
        {"motor_3115_900kv", "Motors", "3115 900KV Cinelifter", StandardPartShape::MotorCan, 0.1140, 37.8, 5.0, 28.0, 37.8, 28.0, 900, 6, 0.0, 0.018, 38.5, 1560.0, 0, 2, -1, 0, 0, 0, 0, "MANUFACTURER_NOMINAL_UNVERIFIED_ESTIMATE"},
        {"motor_mn3508_kv380", "Motors", "T-Motor MN3508 KV380", StandardPartShape::MotorCan, 0.1030, 41.8, 4.0, 26.0, 41.8, 26.0, 380, 6, 0.0, 0.025, 24.5, 520.0, 0, 2, -1, 0, 0, 0, 0, "DEVELOPMENT_BENCH_NOMINAL"},
        {"motor_mn501s_kv300", "Motors", "T-Motor MN501-S KV300", StandardPartShape::MotorCan, 0.1650, 55.6, 6.0, 25.4, 55.6, 25.4, 300, 6, 0.0, 0.022, 41.0, 980.0, 0, 2, -1, 0, 0, 0, 0, "MANUFACTURER_NOMINAL_UNVERIFIED_ESTIMATE"},
        {"motor_u8ii_kv100", "Motors", "T-Motor U8II Lite KV100", StandardPartShape::MotorCan, 0.2420, 87.2, 8.0, 24.5, 87.2, 24.5, 100, 12, 0.0, 0.022, 76.0, 1850.0, 0, 2, -1, 0, 0, 0, 0, "MANUFACTURER_NOMINAL_UNVERIFIED_ESTIMATE"},
        {"motor_p80iii_kv100", "Motors", "T-Motor P80III KV100", StandardPartShape::MotorCan, 0.6300, 89.2, 12.0, 40.5, 89.2, 40.5, 100, 12, 0.0, 0.018, 174.0, 4600.0, 0, 2, -1, 0, 0, 0, 0, "DEVELOPMENT_BENCH_NOMINAL"},
        {"motor_x11_coax_10kw", "Motors", "Heavy Agri X11+ Coaxial Unit", StandardPartShape::MotorCan, 1.6800, 116.0, 16.0, 68.0, 116.0, 68.0, 78, 14, 0.0, 0.016, 310.0, 10200.0, 0, 2, -1, 0, 0, 0, 0, "MANUFACTURER_NOMINAL_UNVERIFIED_ESTIMATE"},
        {"motor_coreless_7x20_1s", "Motors", "Micro Coreless 7x20mm Geared", StandardPartShape::MotorCan, 0.0040, 7.0, 1.0, 20.0, 7.0, 20.0, 14500, 1, 0.0, 0.065, 0.34, 7.5, 0, 2, -1, 0, 0, 0, 0, "MANUFACTURER_NOMINAL_UNVERIFIED_ESTIMATE"},

        // Turbines & EDFs (7)
        {"edf_50mm_11b_4s", "Turbines & EDFs", "50mm 11-Blade 4S EDF", StandardPartShape::Turbine, 0.0880, 52.0, 50.0, 64.0, 52.0, 52.0, 4300, 4, 0.0, 0.020, 8.90, 620.0, 0, 11, -1, 0, 0, 0, 0, "MANUFACTURER_NOMINAL_UNVERIFIED_ESTIMATE"},
        {"edf_70mm_12b_6s", "Turbines & EDFs", "FMS 70mm 12-Blade 6S EDF", StandardPartShape::Turbine, 0.2420, 72.0, 70.0, 98.0, 72.0, 72.0, 1850, 6, 0.0, 0.015, 21.58, 1510.0, 0, 12, -1, 0, 0, 0, 0, "DEVELOPMENT_BENCH_NOMINAL"},
        {"edf_90mm_12b_8s", "Turbines & EDFs", "90mm 12-Blade 8S-12S EDF", StandardPartShape::Turbine, 0.5600, 92.5, 90.0, 124.0, 92.5, 92.5, 1450, 8, 0.0, 0.015, 44.50, 3600.0, 0, 12, -1, 0, 0, 0, 0, "MANUFACTURER_NOMINAL_UNVERIFIED_ESTIMATE"},
        {"edf_120mm_14s", "Turbines & EDFs", "120mm High-Thrust 14S EDF", StandardPartShape::Turbine, 1.1800, 123.0, 120.0, 158.0, 123.0, 123.0, 690, 14, 0.0, 0.014, 94.00, 8200.0, 0, 12, -1, 0, 0, 0, 0, "MANUFACTURER_NOMINAL_UNVERIFIED_ESTIMATE"},
        {"turbine_kingtech_k45g4", "Turbines & EDFs", "KingTech K-45G4+ Micro Turbojet", StandardPartShape::Turbine, 0.4500, 62.9, 40.0, 158.0, 62.9, 62.9, 0, 3, 0.0, 0.020, 44.15, 42000.0, 0, 1, -1, 0, 0, 0, 0, "DEVELOPMENT_BENCH_NOMINAL"},
        {"turbine_jetcat_p100rx", "Turbines & EDFs", "JetCat P100-RX Micro Turbojet", StandardPartShape::Turbine, 1.0800, 97.0, 58.0, 243.0, 97.0, 97.0, 0, 3, 0.0, 0.020, 100.0, 96000.0, 0, 1, -1, 0, 0, 0, 0, "DEVELOPMENT_BENCH_NOMINAL"},
        {"turbine_jetcat_p220rxi", "Turbines & EDFs", "JetCat P220-RXi Turbojet", StandardPartShape::Turbine, 1.8500, 116.8, 72.0, 298.0, 116.8, 116.8, 0, 3, 0.0, 0.020, 220.0, 210000.0, 0, 1, -1, 0, 0, 0, 0, "MANUFACTURER_NOMINAL_UNVERIFIED_ESTIMATE"},

        // Propellers (12)
        {"prop_3030x3", "Propellers", "3x3x3 Polycarbonate Tri-Blade", StandardPartShape::Propeller, 0.0018, 76.2, 5.0, 6.5, 76.2, 6.5, 0, 0, 0, 0, 0, 0, 24.0, 3, -1, 0, 0, 0, 0, "MANUFACTURER_NOMINAL_UNVERIFIED_ESTIMATE"},
        {"prop_51433x3", "Propellers", "5.1x4.3x3 FPV Freestyle Prop", StandardPartShape::Propeller, 0.0046, 129.5, 5.0, 8.0, 129.5, 8.0, 0, 0, 0, 0, 0, 0, 21.0, 3, -1, 0, 0, 0, 0, "MANUFACTURER_NOMINAL_UNVERIFIED_ESTIMATE"},
        {"prop_7040x2", "Propellers", "7x4x2 Glass-Nylon LR Prop", StandardPartShape::Propeller, 0.0078, 177.8, 5.0, 9.5, 177.8, 9.5, 0, 0, 0, 0, 0, 0, 16.0, 2, -1, 0, 0, 0, 0, "MANUFACTURER_NOMINAL_UNVERIFIED_ESTIMATE"},
        {"prop_1045_mr", "Propellers", "10x4.5 MR Multirotor Prop", StandardPartShape::Propeller, 0.0135, 254.0, 6.0, 12.0, 254.0, 12.0, 0, 0, 0, 0, 0, 0, 14.0, 2, -1, 0, 0, 0, 0, "MANUFACTURER_NOMINAL_UNVERIFIED_ESTIMATE"},
        {"prop_10x5_apce", "Propellers", "APC 10x5E Thin Electric", StandardPartShape::Propeller, 0.0210, 254.0, 6.35, 13.0, 254.0, 13.0, 0, 0, 0, 0, 0, 0, 15.0, 2, -1, 0, 0, 0, 0, "DEVELOPMENT_BENCH_NOMINAL"},
        {"prop_11x7_sport", "Propellers", "11x7E Fixed-Wing Pusher/Tractor", StandardPartShape::Propeller, 0.0250, 279.4, 6.35, 14.0, 279.4, 14.0, 0, 0, 0, 0, 0, 0, 19.0, 2, -1, 0, 0, 0, 0, "MANUFACTURER_NOMINAL_UNVERIFIED_ESTIMATE"},
        {"prop_15x5_cf", "Propellers", "T-Motor P15x5 Carbon Prop", StandardPartShape::Propeller, 0.0210, 381.0, 4.0, 11.0, 381.0, 11.0, 0, 0, 0, 0, 0, 0, 16.0, 2, -1, 0, 0, 0, 0, "DEVELOPMENT_BENCH_NOMINAL"},
        {"prop_18x61_cf", "Propellers", "18x6.1 Carbon Fiber Folding", StandardPartShape::Propeller, 0.0360, 457.2, 6.0, 14.0, 457.2, 14.0, 0, 0, 0, 0, 0, 0, 15.0, 2, -1, 0, 0, 0, 0, "MANUFACTURER_NOMINAL_UNVERIFIED_ESTIMATE"},
        {"prop_22x66_cf", "Propellers", "22x6.6 Heavy Lift CF", StandardPartShape::Propeller, 0.0580, 558.8, 8.0, 16.0, 558.8, 16.0, 0, 0, 0, 0, 0, 0, 14.5, 2, -1, 0, 0, 0, 0, "MANUFACTURER_NOMINAL_UNVERIFIED_ESTIMATE"},
        {"prop_30x105_cf", "Propellers", "T-Motor G30x10.5 CF", StandardPartShape::Propeller, 0.1450, 762.0, 12.0, 22.0, 762.0, 22.0, 0, 0, 0, 0, 0, 0, 15.5, 2, -1, 0, 0, 0, 0, "DEVELOPMENT_BENCH_NOMINAL"},
        {"prop_heli_750mm_blade", "Propellers", "750mm Symmetrical NACA0012 Heli Rotor", StandardPartShape::Propeller, 0.2150, 1480.0, 10.0, 62.0, 1480.0, 16.0, 0, 0, 0, 0, 0, 0, 10.0, 2, -1, 0, 0, 0, 0, "MANUFACTURER_NOMINAL_UNVERIFIED_ESTIMATE"},
        {"prop_crm_turbofan", "Propellers", "Wide-Chord Bypass Fan Rotor", StandardPartShape::Propeller, 0.3400, 220.0, 24.0, 48.0, 220.0, 48.0, 0, 0, 0, 0, 0, 0, 32.0, 6, -1, 0, 0, 0, 0, "MANUFACTURER_NOMINAL_UNVERIFIED_ESTIMATE"},

        // Batteries & Tanks (9)
        {"bat_1s_500mah", "Batteries & Tanks", "1S 500mAh LiHV Micro Pack", StandardPartShape::BatteryBox, 0.0120, 58.0, 0, 58.0, 18.0, 7.5, 0, 1, 0.50, 0.065, 0, 0, 0, 0, -1, 0, 0, 0, 0, "MANUFACTURER_NOMINAL_UNVERIFIED_ESTIMATE"},
        {"bat_3s_2200mah", "Batteries & Tanks", "3S 2200mAh 45C LiPo", StandardPartShape::BatteryBox, 0.1880, 106.0, 0, 106.0, 35.0, 24.0, 0, 3, 2.20, 0.021, 0, 0, 0, 0, -1, 0, 0, 0, 0, "MANUFACTURER_NOMINAL_UNVERIFIED_ESTIMATE"},
        {"bat_4s_4000_liion", "Batteries & Tanks", "4S 4000mAh Molicel P42A Li-Ion", StandardPartShape::BatteryBox, 0.2820, 72.0, 0, 72.0, 44.0, 44.0, 0, 4, 4.00, 0.032, 0, 0, 0, 0, -1, 0, 0, 0, 0, "MANUFACTURER_NOMINAL_UNVERIFIED_ESTIMATE"},
        {"bat_4s_4500_lipo", "Batteries & Tanks", "4S 4500mAh 50C LiPo", StandardPartShape::BatteryBox, 0.4450, 138.0, 0, 138.0, 44.0, 36.0, 0, 4, 4.50, 0.018, 0, 0, 0, 0, -1, 0, 0, 0, 0, "MANUFACTURER_NOMINAL_UNVERIFIED_ESTIMATE"},
        {"bat_6s_5000_60c", "Batteries & Tanks", "6S 5000mAh 60C EDF LiPo", StandardPartShape::BatteryBox, 0.7800, 156.0, 0, 156.0, 48.0, 52.0, 0, 6, 5.00, 0.015, 0, 0, 0, 0, -1, 0, 0, 0, 0, "MANUFACTURER_NOMINAL_UNVERIFIED_ESTIMATE"},
        {"bat_6s_10000_hv", "Batteries & Tanks", "6S 10000mAh Solid-State UAV", StandardPartShape::BatteryBox, 1.1500, 168.0, 0, 168.0, 64.0, 54.0, 0, 6, 10.0, 0.025, 0, 0, 0, 0, -1, 0, 0, 0, 0, "DEVELOPMENT_BENCH_NOMINAL"},
        {"bat_6s_16000_lipo", "Batteries & Tanks", "6S 16000mAh Endurance LiPo", StandardPartShape::BatteryBox, 1.9200, 192.0, 0, 192.0, 74.0, 68.0, 0, 6, 16.0, 0.014, 0, 0, 0, 0, -1, 0, 0, 0, 0, "DEVELOPMENT_BENCH_NOMINAL"},
        {"bat_12s_22000_semi", "Batteries & Tanks", "12S 22000mAh Industrial Semi-Solid", StandardPartShape::BatteryBox, 5.3500, 225.0, 0, 225.0, 148.0, 86.0, 0, 12, 22.0, 0.022, 0, 0, 0, 0, -1, 0, 0, 0, 0, "DEVELOPMENT_BENCH_NOMINAL"},
        {"tank_jeta1_2500ml", "Batteries & Tanks", "Kevlar Jet-A1 Fuel Cell 2.5L", StandardPartShape::BatteryBox, 2.1500, 210.0, 0, 210.0, 115.0, 110.0, 0, 3, 3.00, 0.020, 0, 0, 0, 0, -1, 0, 0, 0, 0, "MANUFACTURER_NOMINAL_UNVERIFIED_ESTIMATE"},

        // ESCs & Avionics (12)
        {"esc_15a_4in1", "ESCs & Avionics", "15A 2-4S 16x16mm 4-in-1 ESC", StandardPartShape::PcbModule, 0.0042, 24.0, 0, 24.0, 24.0, 5.0, 0, 4, 0, 0, 0, 220.0, 0, 0, -1, 0, 0, 0, 0, "MANUFACTURER_NOMINAL_UNVERIFIED_ESTIMATE"},
        {"esc_35a_blheli32", "ESCs & Avionics", "35A 6S Single Arm BLHeli32 ESC", StandardPartShape::PcbModule, 0.0085, 32.0, 0, 32.0, 16.0, 6.0, 0, 6, 0, 0, 0, 770.0, 0, 0, -1, 0, 0, 0, 0, "MANUFACTURER_NOMINAL_UNVERIFIED_ESTIMATE"},
        {"esc_60a_opto_6s", "ESCs & Avionics", "60A 6S Heavy Lift OPTO ESC", StandardPartShape::PcbModule, 0.0440, 68.0, 0, 68.0, 28.0, 14.0, 0, 6, 0, 0, 0, 1450.0, 0, 0, -1, 0, 0, 0, 0, "MANUFACTURER_NOMINAL_UNVERIFIED_ESTIMATE"},
        {"esc_80a_12s_can", "ESCs & Avionics", "80A 12S Industrial FOC CAN ESC", StandardPartShape::PcbModule, 0.0950, 78.0, 0, 78.0, 40.0, 18.0, 0, 12, 0, 0, 0, 3800.0, 0, 0, -1, 0, 0, 0, 0, "DEVELOPMENT_BENCH_NOMINAL"},
        {"esc_160a_14s_hv", "ESCs & Avionics", "160A 14S High-Voltage OPTO ESC", StandardPartShape::PcbModule, 0.2150, 96.0, 0, 96.0, 52.0, 24.0, 0, 14, 0, 0, 0, 8200.0, 0, 0, -1, 0, 0, 0, 0, "MANUFACTURER_NOMINAL_UNVERIFIED_ESTIMATE"},
        {"fc_pixhawk_6x", "ESCs & Avionics", "Pixhawk 6X STM32H7 + Triple IMU", StandardPartShape::PcbModule, 0.0730, 84.8, 0, 84.8, 44.0, 18.0, 0, 0, 0, 0, 0, 0, 0, 0, -1, 0, 0, 0, 0, "STANDARD_AUTOPILOT_NOMINAL"},
        {"fc_cube_orange_plus", "ESCs & Avionics", "CubePilot Cube Orange+ ADS-B", StandardPartShape::PcbModule, 0.0750, 94.5, 0, 94.5, 44.3, 22.0, 0, 0, 0, 0, 0, 0, 0, 0, -1, 0, 0, 0, 0, "STANDARD_AUTOPILOT_NOMINAL"},
        {"gnss_rtk_dual", "ESCs & Avionics", "F9P Dual-Antenna RTK GNSS Module", StandardPartShape::PcbModule, 0.0420, 54.0, 0, 54.0, 54.0, 16.0, 0, 0, 0, 0, 0, 0, 0, 0, -1, 0, 0, 0, 0, "MANUFACTURER_NOMINAL_UNVERIFIED_ESTIMATE"},
        {"lidar_livox_mid360", "ESCs & Avionics", "Solid-State 3D Dome LiDAR", StandardPartShape::MotorCan, 0.2650, 65.0, 0, 60.0, 65.0, 60.0, 0, 0, 0, 0, 0, 0, 0, 0, -1, 0, 0, 0, 0, "MANUFACTURER_NOMINAL_UNVERIFIED_ESTIMATE"},
        {"pitot_ms4525do", "ESCs & Avionics", "MS4525DO Differential Airspeed Sensor", StandardPartShape::StructuralTube, 0.0180, 8.0, 4.0, 85.0, 8.0, 8.0, 0, 0, 0, 0, 0, 0, 0, 0, -1, 0, 0, 0, 0, "MANUFACTURER_NOMINAL_UNVERIFIED_ESTIMATE"},
        {"servo_mg90s_micro", "ESCs & Avionics", "MG90S Metal-Gear 9g Servo", StandardPartShape::ServoBlock, 0.0134, 22.8, 0, 22.8, 12.2, 28.5, 0, 0, 0, 0, 0, 0, 0, 0, -1, 0, 0, 0, 0.216, "MANUFACTURER_NOMINAL_UNVERIFIED_ESTIMATE"},
        {"servo_bls177sv_hv", "ESCs & Avionics", "BLS177SV High-Torque Digital Servo", StandardPartShape::ServoBlock, 0.0680, 40.5, 0, 40.5, 20.5, 37.5, 0, 0, 0, 0, 0, 0, 0, 0, -1, 0, 0, 0, 3.630, "MANUFACTURER_NOMINAL_UNVERIFIED_ESTIMATE"},

        // Fasteners (12)
        {"bolt_iso4762_m16", "Fasteners", "ISO 4762 M1.6x6 Socket Cap (12.9)", StandardPartShape::FastenerBolt, 0.00014, 3.0, 1.6, 6.0, 3.0, 6.0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 940.0, 0, 0, 0, "STANDARD_ISO_DIN"},
        {"bolt_iso4762_m2", "Fasteners", "ISO 4762 M2x8 Socket Cap (12.9)", StandardPartShape::FastenerBolt, 0.000255, 3.98, 2.0, 8.0, 3.98, 8.0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1490.0, 0, 0, 0, "STANDARD_ISO_DIN"},
        {"bolt_iso4762_m25", "Fasteners", "ISO 4762 M2.5x10 Socket Cap (12.9)", StandardPartShape::FastenerBolt, 0.000525, 4.68, 2.5, 10.0, 4.68, 10.0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 2440.0, 0, 0, 0, "STANDARD_ISO_DIN"},
        {"bolt_iso4762_m3", "Fasteners", "ISO 4762 M3x12 Socket Cap (12.9)", StandardPartShape::FastenerBolt, 0.00100, 5.68, 3.0, 12.0, 5.68, 12.0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 3620.0, 0, 0, 0, "STANDARD_ISO_DIN"},
        {"bolt_iso4762_m3_ti", "Fasteners", "ISO 4762 M3x12 Titanium Ti-6Al-4V", StandardPartShape::FastenerBolt, 0.00057, 5.68, 3.0, 12.0, 5.68, 12.0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2867.0, 0, 0, 0, "STANDARD_ISO_DIN"},
        {"bolt_iso4762_m4", "Fasteners", "ISO 4762 M4x16 Socket Cap (12.9)", StandardPartShape::FastenerBolt, 0.00230, 7.22, 4.0, 16.0, 7.22, 16.0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 6320.0, 0, 0, 0, "STANDARD_ISO_DIN"},
        {"bolt_iso4762_m5", "Fasteners", "ISO 4762 M5x20 Socket Cap (12.9)", StandardPartShape::FastenerBolt, 0.00400, 8.72, 5.0, 20.0, 8.72, 20.0, 0, 0, 0, 0, 0, 0, 0, 0, 4, 10220.0, 0, 0, 0, "STANDARD_ISO_DIN"},
        {"bolt_iso4762_m6", "Fasteners", "ISO 4762 M6x25 Socket Cap (12.9)", StandardPartShape::FastenerBolt, 0.00760, 10.22, 6.0, 25.0, 10.22, 25.0, 0, 0, 0, 0, 0, 0, 0, 0, 5, 14470.0, 0, 0, 0, "STANDARD_ISO_DIN"},
        {"bolt_iso4762_m8", "Fasteners", "ISO 4762 M8x30 Socket Cap (12.9)", StandardPartShape::FastenerBolt, 0.01720, 13.27, 8.0, 30.0, 13.27, 30.0, 0, 0, 0, 0, 0, 0, 0, 0, 5, 26350.0, 0, 0, 0, "STANDARD_ISO_DIN"},
        {"bolt_iso4762_m10", "Fasteners", "ISO 4762 M10x35 Heavy Wing Bolt (12.9)", StandardPartShape::FastenerBolt, 0.03200, 16.27, 10.0, 35.0, 16.27, 35.0, 0, 0, 0, 0, 0, 0, 0, 0, 5, 41760.0, 0, 0, 0, "STANDARD_ISO_DIN"},
        {"nut_iso4032_m3", "Fasteners", "ISO 7040 M3 Nyloc Hex Locknut", StandardPartShape::BallBearing, 0.00042, 5.5, 3.0, 4.0, 5.5, 4.0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0, "STANDARD_ISO_DIN"},
        {"standoff_m3x25_alu", "Fasteners", "M3x25mm Anodized Alu 6061 Standoff", StandardPartShape::StructuralTube, 0.00090, 5.0, 3.0, 25.0, 5.0, 25.0, 0, 0, 0, 0, 0, 0, 0, 0, -1, 0, 0, 0, 0, "STANDARD_ISO_DIN"},

        // Bearings & Guides (10)
        {"bearing_mr85zz", "Bearings & Guides", "DIN 625 MR85ZZ (5x8x2.5mm)", StandardPartShape::BallBearing, 0.0006, 8.0, 5.0, 2.5, 8.0, 2.5, 0, 0, 0, 0, 0, 0, 0, 0, -1, 0, 218.0, 0, 0, "STANDARD_ISO_DIN"},
        {"bearing_mr105zz", "Bearings & Guides", "DIN 625 MR105ZZ (5x10x4mm)", StandardPartShape::BallBearing, 0.0013, 10.0, 5.0, 4.0, 10.0, 4.0, 0, 0, 0, 0, 0, 0, 0, 0, -1, 0, 475.0, 0, 0, "STANDARD_ISO_DIN"},
        {"bearing_6700zz", "Bearings & Guides", "DIN 625 6700ZZ Thin Section (10x15x4mm)", StandardPartShape::BallBearing, 0.0022, 15.0, 10.0, 4.0, 15.0, 4.0, 0, 0, 0, 0, 0, 0, 0, 0, -1, 0, 855.0, 0, 0, "STANDARD_ISO_DIN"},
        {"bearing_6800zz", "Bearings & Guides", "DIN 625 6800ZZ (10x19x5mm)", StandardPartShape::BallBearing, 0.0052, 19.0, 10.0, 5.0, 19.0, 5.0, 0, 0, 0, 0, 0, 0, 0, 0, -1, 0, 1710.0, 0, 0, "STANDARD_ISO_DIN"},
        {"bearing_6802zz", "Bearings & Guides", "DIN 625 6802ZZ (15x24x5mm)", StandardPartShape::BallBearing, 0.0070, 24.0, 15.0, 5.0, 24.0, 5.0, 0, 0, 0, 0, 0, 0, 0, 0, -1, 0, 2080.0, 0, 0, "STANDARD_ISO_DIN"},
        {"bearing_6804zz", "Bearings & Guides", "DIN 625 6804ZZ Gimbal (20x32x7mm)", StandardPartShape::BallBearing, 0.0180, 32.0, 20.0, 7.0, 32.0, 7.0, 0, 0, 0, 0, 0, 0, 0, 0, -1, 0, 4020.0, 0, 0, "STANDARD_ISO_DIN"},
        {"bearing_608zz", "Bearings & Guides", "DIN 625 608ZZ Rotor Hub (8x22x7mm)", StandardPartShape::BallBearing, 0.0120, 22.0, 8.0, 7.0, 22.0, 7.0, 0, 0, 0, 0, 0, 0, 0, 0, -1, 0, 3350.0, 0, 0, "STANDARD_ISO_DIN"},
        {"bearing_6900zz", "Bearings & Guides", "DIN 625 6900ZZ (10x22x6mm)", StandardPartShape::BallBearing, 0.0095, 22.0, 10.0, 6.0, 22.0, 6.0, 0, 0, 0, 0, 0, 0, 0, 0, -1, 0, 2700.0, 0, 0, "STANDARD_ISO_DIN"},
        {"bearing_6201_2rs", "Bearings & Guides", "DIN 625 6201-2RS High-Load (12x32x10mm)", StandardPartShape::BallBearing, 0.0370, 32.0, 12.0, 10.0, 32.0, 10.0, 0, 0, 0, 0, 0, 0, 0, 0, -1, 0, 6890.0, 0, 0, "STANDARD_ISO_DIN"},
        {"guide_lm8uu", "Bearings & Guides", "LM8UU Linear Ball Bushing (8x15x24mm)", StandardPartShape::BallBearing, 0.0160, 15.0, 8.0, 24.0, 15.0, 24.0, 0, 0, 0, 0, 0, 0, 0, 0, -1, 0, 265.0, 0, 0, "STANDARD_ISO_DIN"},

        // Structural Tubes & Extrusions (8)
        {"tube_cf_8x6_300", "Tubes & Structures", "Carbon CF Tube OD 8x6mm x 300mm", StandardPartShape::StructuralTube, 0.0102, 8.0, 6.0, 300.0, 8.0, 8.0, 0, 0, 0, 0, 0, 0, 0, 0, -1, 0, 0, 18.4, 0, "STANDARD_COMPOSITE_NOMINAL"},
        {"tube_cf_12x10_350", "Tubes & Structures", "Carbon CF Tube OD 12x10mm x 350mm", StandardPartShape::StructuralTube, 0.0188, 12.0, 10.0, 350.0, 12.0, 12.0, 0, 0, 0, 0, 0, 0, 0, 0, -1, 0, 0, 66.2, 0, "STANDARD_COMPOSITE_NOMINAL"},
        {"tube_cf_16x14_400", "Tubes & Structures", "Carbon CF Boom OD 16x14mm x 400mm", StandardPartShape::StructuralTube, 0.0294, 16.0, 14.0, 400.0, 16.0, 16.0, 0, 0, 0, 0, 0, 0, 0, 0, -1, 0, 0, 163.5, 0, "STANDARD_COMPOSITE_NOMINAL"},
        {"tube_cf_20x18_450", "Tubes & Structures", "Carbon CF Boom OD 20x18mm x 450mm", StandardPartShape::StructuralTube, 0.0418, 20.0, 18.0, 450.0, 20.0, 20.0, 0, 0, 0, 0, 0, 0, 0, 0, -1, 0, 0, 328.0, 0, "STANDARD_COMPOSITE_NOMINAL"},
        {"tube_cf_25x22_500", "Tubes & Structures", "Carbon CF Arm OD 25x22mm x 500mm", StandardPartShape::StructuralTube, 0.0865, 25.0, 22.0, 500.0, 25.0, 25.0, 0, 0, 0, 0, 0, 0, 0, 0, -1, 0, 0, 945.0, 0, "STANDARD_COMPOSITE_NOMINAL"},
        {"tube_cf_30x27_600", "Tubes & Structures", "Carbon Heavy Spar OD 30x27mm x 600mm", StandardPartShape::StructuralTube, 0.1250, 30.0, 27.0, 600.0, 30.0, 30.0, 0, 0, 0, 0, 0, 0, 0, 0, -1, 0, 0, 1680.0, 0, "STANDARD_COMPOSITE_NOMINAL"},
        {"extrusion_alu_2020_300", "Tubes & Structures", "Alu 6061-T6 2020 T-Slot Extrusion 300mm", StandardPartShape::BatteryBox, 0.1350, 300.0, 0, 300.0, 20.0, 20.0, 0, 0, 0, 0, 0, 0, 0, 0, -1, 0, 0, 780.0, 0, "STANDARD_ISO_DIN"},
        {"spar_ti_7075_800", "Tubes & Structures", "7075-T6 Wing Carry-Through Box Spar 800mm", StandardPartShape::BatteryBox, 0.4200, 800.0, 0, 800.0, 28.0, 22.0, 0, 0, 0, 0, 0, 0, 0, 0, -1, 0, 0, 4200.0, 0, "STANDARD_ISO_DIN"},
    };
    return kCatalog;
}

std::vector<const StandardPartSpec *> search_standard_library(const std::string &category, const std::string &query) {
    const std::string cat_l = to_lower_copy(category);
    const std::string q_l = to_lower_copy(query);
    std::vector<const StandardPartSpec *> out;
    for (const auto &item : standard_library_catalog()) {
        if (!cat_l.empty() && cat_l != "all" && to_lower_copy(item.category) != cat_l) continue;
        if (!q_l.empty() && to_lower_copy(item.name).find(q_l) == std::string::npos &&
            to_lower_copy(item.id).find(q_l) == std::string::npos) {
            continue;
        }
        out.push_back(&item);
    }
    return out;
}

const StandardPartSpec *find_standard_part_by_id(const std::string &id) {
    for (const auto &item : standard_library_catalog()) {
        if (item.id == id) return &item;
    }
    return nullptr;
}

} // namespace lab
