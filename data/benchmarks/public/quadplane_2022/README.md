# Third-party real-flight battery log — CC BY 4.0 attribution

Original dataset: **Quadplane VTOL — Flight-Test Telemetry, CFD & Structural Data**.

- Authors: Md Azizul Islam; Md Nur-A-Adam Dony; Mehedi Hasan; S. G. M. Hossain
- Original project: https://github.com/AdamDony/quadplane-px4-flight-data
- Original source commit: `122ceb2cf3913725eef5cd9171a9779220c63335`
- Original file (verbatim): `data/telemetry/BATT.csv`
- Original Git blob SHA-1: `1e434d8edcc26d5dfc016a557e24d5c44cffff3c`
- Attribution license: **Creative Commons Attribution 4.0 International (CC BY 4.0)**
- License: https://creativecommons.org/licenses/by/4.0/
- Original license: https://github.com/AdamDony/quadplane-px4-flight-data/blob/122ceb2cf3913725eef5cd9171a9779220c63335/LICENSE
- Source's technical data dictionary: https://github.com/AdamDony/quadplane-px4-flight-data/blob/122ceb2cf3913725eef5cd9171a9779220c63335/docs/DATA_DICTIONARY.md
- Reported flight date: September 4, 2022
- Import date: November 17, 2026

**Alterations:** The CSV is copied byte-for-byte, without editing, resampling,
unit conversions or timestamp fabrication. The JSON manifest, validation
code, audit summary and AeroForge interface are original additions.
Retain this attribution and license when redistributing the copied CSV.
AeroForge source-code licensing does **not** replace the CC BY 4.0
attribution/conditions attached to the third-party dataset.

**Data limits:** The 1,442 `BATT` rows contain *filtered* pack voltage/current,
flight-controller cumulative discharged charge, and flight-controller
remaining-capacity estimates. **There is no per-row timestamp in this CSV**.
The original documentation indicates a ~24-minute logging session with
roughly six minutes of actual flight. Never use a fabricated uniform time
axis to calculate Wh, fit a transient response or synchronize the trace
to AeroForge's simulations.

The aircraft is a *hybrid quadplane*, not either AeroForge multirotor
reference vehicle. The exact pack serial, age, internal resistance, and
calibration uncertainties have not been independently established here.
Its values are real-world **reported measurements**, not independent
validation of any AeroForge aircraft or battery simulation.

Run: `python scripts/audit_public_flight_evidence.py`.
