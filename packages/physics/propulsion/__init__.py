"""Propulsion chain models: battery -> ESC -> motor -> propeller.

Models are driven by sourced component data (data/components/**) — thrust
curves, efficiency maps, discharge characteristics — each tagged with source
and uncertainty. Unknown parameters must be provided by the user with an
explicit uncertainty, never guessed silently.
"""
