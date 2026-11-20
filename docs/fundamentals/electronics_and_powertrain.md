# Electronics and powertrain

Canonical model scope and future equation basis. Implementation remains held during
spec-lock review. Use [V&V](vv_and_pirt.md) and declared SI/measurement conventions.

## Existing implementation

`packages/physics/propulsion/battery.py` implements tabulated OCV, fixed pack resistance
and Coulomb counting; `powertrain.py` iterates a common bus voltage against the
static manufacturer-derived motor/propeller load. `esc.py` applies declared limits.
This static path is not a complete dynamic electro-thermal BLDC/ESC model.
Separate campaign scripts fit effective replay/thermal/lag models; their coefficients
and measurement-conditioned inputs do not establish a coupled prospective plant.

## Candidate battery model (not a new implemented capability)

For discharge-positive current `I`, fractional SOC `z`, capacity `Q_Ah`, ideal charge
efficiency one and a chosen RC equivalent circuit:

```text
dz/dt = −I / (3600 Q_Ah)
V_terminal = U_OC(z,T) − I R0 − sum(v_j)
dv_j/dt = −v_j/(R_j C_j) + I/C_j
```

The fixed-resistance model is the zero-RC case. Parameters depend on temperature,
SOC, age and experiment bandwidth where identified; a fitted RC time constant at
sample cadence is not necessarily an identified physical mechanism. Charging,
hysteresis, high-C capacity loss and aging require separately supported extensions.
This standard equivalent-circuit topology is described in the
[MathWorks Battery Equivalent Circuit documentation](https://www.mathworks.com/help/simscape-battery/ref/batteryequivalentcircuit.html).
Its broader features are not claims about this repository.

## Motor, ESC and bus coupling

A declared **DC-equivalent approximation**, not general three-phase commutation:

```text
V_motor = L di/dt + R i + K_e omega
tau_e = K_t i
J d(omega)/dt = tau_e − tau_load − b omega
P_loss_ESC = P_DC_in − P_motor_electrical_out
```

`K_e = K_t` requires consistent coherent SI and the same electrical/mechanical
conventions with lossless electromagnetic conversion. Advertised BLDC KV cannot
silently be converted across line/phase, peak/RMS or commutation definitions.
Only for a compatible DC-equivalent `K_V` in RPM/V is `K_e = 60/(2π K_V)`.
See [MathWorks DC motor equations](https://www.mathworks.com/help/simscape-electrical/ref/dcmotor.html).
ESC loss is nonnegative for the declared motoring, negligible-storage case; regenerative
operation needs an explicitly supported signed energy balance. A constant efficiency
is an assumption requiring measured support, not a universal electronic law.

Bus voltage, current, actuator feasibility and demanded torque must be solved
consistently. No command can create unavailable electrical/mechanical power.
Current limits, saturation, latency and supported derating propagate to the plant;
known limit violations remain FAIL rather than warnings beside a success verdict.

## Thermal approximation and fault limits

For a supported lumped thermal model, `C_th dT/dt = P_heat − (T−T_ambient)/R_th`,
with `C_th = m c_p`. The thermal storage law is documented by
[MathWorks Thermal Mass](https://www.mathworks.com/help/simscape/ref/thermalmass.html).
The linear heat-transfer term is a project lumped-resistance approximation requiring
identification. `I²R` is irreversible resistive heat, not the entire battery thermal
balance: reversible/entropic heat, contact losses and heat paths need separate support.
This equation does not imply runaway, cell-core temperature or fire prediction.

Unsourced `R`, `L`, `K_e`, `K_t`, thermal resistance/capacity, efficiency, derating
and geometry-dependent heat transfer must be marked `UNVERIFIED_ESTIMATE`.
Unknown instrument calibration, component identity or safe limits precludes acceptance.
The QDrone **14 V study line** is not a universal manufacturer cutoff; SIT's 80 V
module termination applies to its registered 24S experiment. Never transplant either
threshold into another aircraft without applicable evidence.

First planned corrections are M21 cutoff, M25 detector failures and M26 causal
voltage/control coupling in [ROADMAP](../ROADMAP.md). New independent whole-experiment
confirmatory data are needed after correction; inspected data stay DEVELOPMENT.
