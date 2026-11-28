# Bird-inspired reflexive morphing enables rudderless flight

[https://doi.org/10.5061/dryad.zkh1893h5](https://doi.org/10.5061/dryad.zkh1893h5)

## Description of the data and file structure

### PigeonBotII.STEP

PigeonBotII.STEP is a STEP AP214 3D CAD file of PigeonBot II.

Software: Prepared in Solidworks 2023. Compatible with most CAD software. A free web-based alternative to view this file is [Autodesk Viewer.](https://viewer.autodesk.com/) 

### PigeonBot\_II\_datasupplement.xfl

PigeonBot_II_datasupplement.xfl is a xflr5 project file for simulating open-loop dynamic stability of PigeonBot II's three-by-three wing and tail morph combinations. 

Software: Prepared in xflr5 v6.61. [xflr5](https://www.xflr5.tech/) is free. 

### WindTunnelTrials.mat

WindTunnelTrials.mat is a MATLAB data file containing PigeonBot II virtual flight data in the wind tunnel.

Software: Prepared in MATLAB R2018b. Free alternatives are [HDF5 for Python](https://www.h5py.org/) or [GNU Octave](https://octave.org/). 

Its contents are described below:

The `Freq` struct contains data for 15deg roll amplitude tracking data over a frequency sweep with yaw damper and roll PID control.

* The variables `[VAR]` contained within `Freq` are:
  * `ATT`: 3D vehicle attitude
  * `RCOU`: raw servo outputs
  * `ARSP`: airspeed
  * `IMU`: IMU data
  * `PIDY`: Yaw PID loop values
  * `PIDP`: Pitch PID loop values
  * `PIDR`: Roll PID loop values
* Further definitions of each variable format can be found in `[VAR]_label`.
* The variables are 4D cells, and corresponding data can be accessed by specifying experimental parameters from 1 to 3 as follows:
  * `Freq.[VAR](Devidx,AoAidx,wingidx,tailidx)`
* The index mapping is as follows:
  * `Devidx`: 1, K_dev = 1, K_tilt = 0.125; 2, K_dev = 2, K_tilt = 0.25; 3, K_dev = 4, K_tilt = 0.5.
  * `AoAidx`: 1, AoA = cruise-3deg; 2, AoA = cruise; 3, AoA = cruise+3deg.
  * `wingidx`: 1, tucked wing; 2, middle wing; 3, spread wing.
  * `tailidx`: 1, tucked tail; 2, middle tail; 3, spread tail.

The `Static` struct contains data for open loop (`Static.NoCtrl`) and yaw damper only (`Static.YawDamp`) dynamics. Access the data the same indexing as with the `Freq` struct.

The `Turb` struct contains data for tests in varying turbulence levels. Access the data similarly as with the `Freq` struct, except add an index to define the turbulence level:

* `Turb.VAR(Devidx,AoAidx,wingidx,tailidx,turbidx)`
  * where `turbidx` refers to a mapping of turbulence intensity (TI%) levels: 1, 3%; 2, 6%; 3, 9%; 4, 12%; 5, 15%; 6, 18%; 7, 21%.

The `Tune` struct contains data for the tuned gains for each trial. Access the data with the same indexing as with the `Freq` struct

* `Tune.YawDamp` contains the K_D gain for the yaw damper mapped to tail tilt.
* `Tune.P`, `Tune.I`, and `Tune.D` contain PID gains for the roll controller.
* `Tune.Elev` contains the tail elevation for each trial.

