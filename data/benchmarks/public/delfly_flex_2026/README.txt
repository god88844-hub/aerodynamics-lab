README
================================================================================
Dataset for: Delfly Flex: A Flapping Wing Micro Air Vehicle with a
Bio-Inspired Unibody Composed of Compliant Joints
Published in: Bioinspiration & Biomimetics
DOI: https://doi.org/10.1088/1748-3190/ae5e10
License: Creative Commons Attribution 4.0 International (CC BY 4.0)
================================================================================

CONTACT
-------
Corresponding author: Dr. Salua Hamaza
Affiliation: Faculty of Aerospace Engineering, Delft University of Technology
Email: s.hamaza@tudelft.nl


--------------------------------------------------------------------------------
FILE DESCRIPTIONS
--------------------------------------------------------------------------------

1. fig_9_MAVBal_Data_240408_135552.tdms
   Format: TDMS (Technical Data Management Streaming)
   Description: Raw force and moment balance measurements for the Delfly Nimble. 
   Refer to the published manuscript for experiment conditions and details.

2. fig_9_MAVBal_Data_240411_185641.tdms
   Format: TDMS (Technical Data Management Streaming)
   Description: Raw force and moment balance measurements for the Delfly Flex. 
   Refer to the published manuscript for experiment conditions and details.

3. fig_9b_avg_forces_moments_nimble_62_5.txt
   Format: Plain text, whitespace-delimited
   Description: Cycle-averaged forces and moments measured on the Delfly Nimble
   at 62.5% throttle, across five maneuver conditions. Used to produce
   Figure 9b in the manuscript. See column and row definitions below.

4. fig_9b_avg_forces_moments_flex_62_5.txt
   Format: Plain text, whitespace-delimited
   Description: Cycle-averaged forces and moments measured on the Delfly Flex
   at 62.5% throttle, across five maneuver conditions. Used to produce
   Figure 9b in the manuscript. See column and row definitions below.

5. fig_10_processed_flight_data.mat
   Format: MATLAB binary data file (.mat)
   Description: Processed flight data used to produce Figure 10 in the
   manuscript. Refer to the published manuscript for details on the flight
   experiment and variables contained in this file.

--------------------------------------------------------------------------------
DATA-SPECIFIC INFORMATION FOR .TXT FILES
(fig_9b_avg_forces_moments_nimble_62_5.txt and
 fig_9b_avg_forces_moments_flex_62_5.txt)
--------------------------------------------------------------------------------

Each file contains 15 rows and 6 columns.
No header row is included. Values are whitespace-delimited.

Columns:
  Column 1: Fx  (force along x-axis)       [N]
  Column 2: Fy  (force along y-axis)       [N]
  Column 3: Fz  (force along z-axis)       [N]
  Column 4: Mx  (moment about x-axis)      [N·mm]
  Column 5: My  (moment about y-axis)      [N·mm]
  Column 6: Mz  (moment about z-axis)      [N·mm]

Row groupings (3 repeated measurements per condition):
  Rows  1-3:  Hover / neutral position
  Rows  4-6:  Pitch forward (maximum deflection)
  Rows  7-9:  Pitch backward (maximum deflection)
  Rows 10-12: Yaw clockwise (CW)
  Rows 13-15: Yaw counter-clockwise (CCW)

Refer to the published manuscript for axis conventions, units, and full
description of the experimental setup and maneuver conditions.


--------------------------------------------------------------------------------
SOFTWARE AND TOOLS
--------------------------------------------------------------------------------

- MATLAB R2021a or later is required to open the .mat file and run the .m
  script. No additional toolboxes are required.
- The TDMS files are read in MATLAB using the function TDMS_getStruct(),
  which is available as a free third-party package on MATLAB File Exchange
  (search: "TDMS Reader" or "TDMS_getStruct"). This package must be installed
  and added to the MATLAB path before running any TDMS-related processing.


--------------------------------------------------------------------------------
SHARING AND ACCESS
--------------------------------------------------------------------------------

This dataset is published under the Creative Commons Attribution 4.0
International License (CC BY 4.0).
Full license text: https://creativecommons.org/licenses/by/4.0/

When using this dataset, please cite the associated manuscript:
  DOI: https://doi.org/10.1088/1748-3190/ae5e10

================================================================================
