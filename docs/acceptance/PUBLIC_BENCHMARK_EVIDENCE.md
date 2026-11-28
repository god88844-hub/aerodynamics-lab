# Public Open Benchmark Evidence Report (DEVELOPMENT)

This document summarizes the 4 newly acquired, checksum-pinned, permissively licensed open public experimental datasets ingested under `data/benchmarks/public/` and `data/local/source-physical/public_open_benchmarks/`, evaluated by [`public_benchmark_eval.py`](../../packages/physics/validation/public_benchmark_eval.py).

All evaluations carry explicit **`DEVELOPMENT`** policy status (`physical_acceptance_granted = False`). They provide real measured wind-tunnel and flight-test comparison baselines across Fixed-Wing, Helicopter Rotor, VTOL Transition, and Icing physics while preserving all open custodian/reviewer/hardware gates (`P0A`–`P0D`).

## Ingested Open Benchmarks

| Domain | Dataset & Source | License | Exact Original Hash Pin | Model Comparison Scope |
| :--- | :--- | :--- | :--- | :--- |
| Fixed-Wing Airfoils | [Kent State Airfoil 360 v2022](https://data.mendeley.com/datasets/dz4bv26ncd/1) (`NACA 0012`, `NACA 2412` Re=50K/100K) | `CC BY 4.0` | `f04e63e0...` (`39,244 B` zip) | Attached-flow $C_L, C_D$ wind tunnel comparison vs `generate_airfoil_polar` |
| Helicopter Hover Rotor | [NASA TM-81232 Caradonna & Tung](https://github.com/PuddingTower/rotor-propeller-benchmarks/tree/main/05_%E7%BB%8F%E5%85%B8%E6%82%AC%E5%81%9C%E6%A8%A1%E5%9E%8B%E6%97%8B%E7%BF%BC_Caradonna_Tung) | `NASA Public Domain` / `MIT` | `5c205772...` (`782 B` CSV) | Subsonic hover $C_T, C_P$ trend vs `solve_helicopter_bemt_rotor` with Prandtl tip-loss $F$ |
| VTOL Transition Flight | [PX4 Flight Review VTOL 2572d282](https://review.px4.io/plot_app?log=2572d282-1b13-4666-88bd-d33893fda64a) | `CC BY 4.0` | `bcd0c2be...` (`8,948,522 B` `.ulg`) | Transition mode timeline (`t=29.6..46.8 s`), `32.09 m/s` max airspeed, `21.05..25.00 V` bus range vs `run_vtol_transition_corridor` |
| Icing Tunnel Mass | [NASA Glenn CRM IRT Midspan](https://commonresearchmodel.larc.nasa.gov/home-2/icing-research/ice-accretion-database-2/irt-test-campaign-experimental-results-2/) (`TH2450`, `TH2459`, `TH2464`) | `NASA Public Domain` | `9fbdc212...`, `c7049f38...` | Glaze (`-1.4 C`: `1.058 kg`) vs rime (`-23.8 C`: `1.651 kg`) freezing-fraction scaling vs `evaluate_icing_and_shedding` |

## Verification Command
```text
python -m pytest tests/acceptance/test_public_open_benchmarks.py tests/acceptance -k p0c -v
```
