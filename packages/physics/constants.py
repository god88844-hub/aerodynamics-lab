"""Physical constants used across AeroForge models.

Every constant carries its source; models import these instead of embedding
literal numbers (no magic numbers anywhere in the codebase).
"""

# Standard acceleration of gravity — defined exact value (BIPM, SI Brochure).
# Models use this constant; experimental g at a specific site differs and must
# be passed explicitly when precision matters.
STANDARD_GRAVITY = 9.80665  # m/s^2

# ISA standard atmosphere at mean sea level, 15 °C, 101325 Pa (ICAO Doc 7488).
SEA_LEVEL_AIR_DENSITY = 1.225  # kg/m^3
