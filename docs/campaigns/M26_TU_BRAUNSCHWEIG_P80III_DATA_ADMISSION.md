# M26 evidence lead — TU Braunschweig P80 III KV100 multicopter flight measurements

**Scientific state (17 Nov 2026): ARTICLE AND SOURCE LINK VERIFIED / ORIGINAL REPOSITORY FILES NOT ACCESSED / NONE OF THE DATA INGESTED.** This is an evidence acquisition plan, not the assertion of an accurate AeroForge model or flight approval.

## A high-relevance exact-model source

Falk Pätzold et al. (2023), [*Flight Experiments and Numerical Simulations for Investigating Multicopter Flow Field and Structure Deformation*](https://doi.org/10.3390/atmos14091336), *Atmosphere* 14(9):1336. The original publication is at [MDPI](https://www.mdpi.com/2073-4433/14/9/1336). Section 2.1 specifies a **P80III-KV100** motor (not just the earlier ambiguous generic P80 label), **CF-PROP 30 × 10.5**, blade radius 381 mm, approximately 2600 RPM in hover for its 25 kg class quadcopter, and a reported maximum rotor speed of 3747 RPM. It also reports 2 × 22 Ah 6S1P battery packs, a Pixhawk 2 controller and installed instrumentation.

The **aircraft is a 25 kg quadcopter, not AeroForge's 60 kg hexacopter**. Motor/propeller *model string* overlap improves source relevance but **does not verify motor serial, propeller exact material/manufacture, ESC model, mounting, installed geometry, power bus, environmental matching or identical controlled hardware**. M22's independent bench static thrust/current criteria are not automatically satisfied by an in-flight sensor dataset.

## Actual public acquisition pointer

The article's Data Availability Statement and reference 35 cite the high-resolution original research record:

> Pätzold, F.; Schlerf, A.; Bretschneider, L.; Bauknecht, A. *Multicopter In-Flight Measurement Data of Flow Field and Structure States*, Technische Universität Braunschweig.

**Original research data record:** https://leopard.tu-braunschweig.de/receive/dbbs_mods_00070168

The record redirected to a JavaScript proof-of-work security challenge when accessed from the research environment; no original data-file catalog, dataset license, downloadable file bytes, original hashes or original numeric time histories were obtained. It would be scientifically invalid to fill these unknowns from published graph images or interpolate nonexistent original rows. The candidate registry intentionally has an empty original file inventory and null source hash.

## Source-specific experimental coverage and limitations

The publication lists **16 flights conducted in March 2021** with high-rate instrumentation, an aggregate flight time of approximately 87 minutes, winds of about 4–8 m/s near the ground, and different sensor setups; the paper's main analysis predominantly selects short **quasi-stationary hover segments**, not blind complete-flight trajectories. Instrument configurations varied by flight. Some Table 1 sources are marked unusable (X). Do not count all 16 flights as complete clean observations for every channel or turn multiple windows from one flight into separate independent experiments.

Reported signal families include:
- Rotor speed and azimuth/phase, with an optical detector whose performance depends on photodiode lighting, motor markings and RPM; the old setup is weak near zero RPM, and rotor phase uncertainty for analyzed hover segments was estimated at up to ~2°.
- Pressure/temperature perturbations of rotor wakes, with inlet radial/axial sensor positions that vary between flights; raw voltage, reference calibration, drift corrections and filters affect the inferred physical pressure/temperature.
- Rotor-arm acceleration, vibration spectra and derived strain-gauge force. The paper cautions its force is **not necessarily equal to isolated propeller thrust** because rotor downwash interacts with the arm. Strain signal calibration was approximate, and low-pass filtering affects high-frequency amplitudes.
- Actual aircraft state, electrical power and control channels have **not yet been confirmed in the underlying original files**; no complete AeroForge six-DOF, battery/endurance or failure-recovery claim can be made.

A positive future comparison may validate a **narrow sensor/rotor wake/arm vibration** operating envelope after source validation, not a broad flight-safety or aircraft-generalization claim. The paper itself reports discrepancies in detailed wake effects and notes missing sensor geometry/modeling limitations.

## Acquisition and admission procedure

1. Obtain permissioned access to the TU Braunschweig original high-resolution record through its legitimate user-facing interface or the research authors. Resolve any security challenge normally; do not bypass repository access controls or manufacture file URLs.
2. Preserve a per-file **source-original hash, exact byte count, proper citation, rights/license, native format, sensor metadata, sample clock and recording/flight ID**. Keep original files immutable, separate from AeroForge-normalized sources. Absence of a license is **not** permission to redistribute.
3. Confirm actual original file identities for **Flight 1–16** and which channels are present, their sampling frequencies, calibration factors, original frame/units and instrument revisions. Reproduce Table 1's unusable labels, including aborts/faults. No “one-size-fits-all” assumption about the 51.2 kHz/204.8 kHz paper acquisition variants.
4. Build a per-flight and per-sensor data availability matrix *only from inspected original files*, tagging rotor phase/optical setup, radial/vertical probe position, drift compensation and filter configuration. Do not invent any missing 6-DOF, battery, ESC or control-command channel.
5. Freeze AeroForge's model SHA, installed hardware compatibility decision, **metric-specific acceptance thresholds, calibration versus whole-flight blind holdout assignments, uncertainty model and supported operating envelope** before looking at held-out signals. Source originally published in 2023 cannot be retroactively claimed as a pre-frozen blind test if current AeroForge physics was built using that same publication.
6. Admit compatible, independently usable subsets into the existing M19/M20 evidence system with a **separate source-specific parser** only after identifying the actual native format. There is no legitimate generic column conversion for unknown metadata. Missing clock calibration or sensor/camera phase information means the corresponding high-frequency prediction comparison is **INCONCLUSIVE**.
7. Compare frozen model predictions against original independent measurements, preserving failed flights, unsupported conditions and instrument uncertainty. Source-derived data pass and fail strictly **per declared channel and per-flight regime**. Any component physical limit violation must fail, regardless of pooled statistics.
8. An independent reviewer authenticates source custody, exact physical design and valid use before accepting an appropriately scoped M26 or M24/M25 result; prior software-only analytical gates cannot stand in for this.

## Status and project accounting

Candidate registry: [tu_braunschweig_p80iii_2023_candidate.json](../../data/benchmarks/flight/tu_braunschweig_p80iii_2023_candidate.json).

**M26 physical flight fidelity: NOT ESTABLISHED.** M21 exact-pack discharge and M22 exact installed motor–ESC–propeller remain separate blockers, and the 60 kg hexacopter simulated single-motor-out case remains unrecoverable. This document establishes a traceable experiment-source lead and an admission procedure, **not another scientifically completed major milestone**.

Related issues: [#16](https://github.com/god88844-hub/aeroforge/issues/16), [#23](https://github.com/god88844-hub/aeroforge/issues/23) and [#25](https://github.com/god88844-hub/aeroforge/issues/25).
