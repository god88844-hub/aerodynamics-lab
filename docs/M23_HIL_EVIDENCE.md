# M23 — Read-only controller/HIL trajectory evidence audit

## Purpose

AeroForge's primary goal remains independently verified simulation agreement
with actual physical systems under predeclared decision limits. M23 adds
**software evidence comparison** for a registered multirotor controller,
not a verified hardware-in-the-loop laboratory or autonomous flight capability.
The independent physical campaign is still required by
[issue #27](https://github.com/god88844-hub/aeroforge/issues/27) and the global
[evidence blocker #16](https://github.com/god88844-hub/aeroforge/issues/16).

No hardware commands, actuator control, flight-qualification or certification
are implemented here.

## API and input

`POST /api/components/hil-evidence` accepts a frozen M20 `ValidationProtocol`,
a separately archived expected canonical SHA-256, a declared list of channels
from `altitude_m`, `vertical_speed_m_s`, `attitude_error_deg`, and one or
more complete experiment recordings (up to 16). Each includes source type,
calibration/holdout role, experiment/recording/airframe/battery IDs,
controller serial, firmware version, frozen controller-configuration hash,
operator-declared hardware match and calibration independence.

The **observed** and **predicted** trajectory files are distinct original
CSV strings with separately declared SHA-256 digests. Both must have identical
exact header `t_s,<selected channels in specified order>`, start at t=0,
contain six to 5,000 finite samples, have strictly increasing timestamps and
be aligned point-by-point at exactly the same times. AeroForge does **not**
invent clocks or interpolate missing samples.

Each held-out point is compared to the **externally supplied frozen model
prediction**; the model is not regenerated or fitted from observed trajectories
inside this endpoint. Reported residual MAE, RMSE and worst absolute error are
computed for each channel. A *samplewise reported compatibility* requires
the predeclared minimum sample count, maximum interval, error threshold
and the worst-case **hard absolute measurement-error** budget from M20.
Missing instrument calibration, positive clock uncertainty, correlation,
numerical error and other model discrepancy remain caveats, never evidence
of guaranteed continuous-time accuracy.

Calibration and holdout recordings must be disjoint by recording, experiment,
vehicle, battery, controller serial and observed source hash. An identical
source cannot be re-labelled as independent held-out evidence.

## Scientific limits

- Original files, prediction provenance, exact physical instruments and
  preregistration timing are **not independently authenticated**. SHA-256
  equality is only a comparison to operator-supplied digests.
- No real controller, ESC or sensor is operated by this feature.
- No ESC dynamic response, actuator saturation, motor/rotor RPM, temperature
  or electrical-safety state is independently measured or modeled.
- No time-alignment correction, hard clock-error enclosure, numerical solver
  error or model-form uncertainty is applied to the reported residual.
- Manufacturer or synthetic samples cannot certify physical controller
  behavior. Test fixtures are explicitly synthetic; even an adversarial
  fixture labelled physical cannot authenticate itself.
- The result always reports
  `HIL_CONTROLLER_PHYSICAL_VALIDATION_NOT_ESTABLISHED`;
  `independent_physical_flight_validation_established` and
  `flight_safety_certified` always remain false.

## Verification

```bash
python -m pytest tests/physics/test_hil_evidence.py tests/integration/test_hil_evidence_api.py -q
python -m pytest -q
cd apps/web && npm ci && npm audit --audit-level=moderate && npm run build && npm test
```

Software completion cannot close M23's physical campaign issue. Actual
hardware-in-the-loop tests require qualified equipment, calibrated independent
ground truth, controller/ESC firmware identity, synchronized unsmoothed logs,
independent repeated holdouts and applicable operational safety review.
