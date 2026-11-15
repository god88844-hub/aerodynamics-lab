"""M9 Phase 5 — BLIND prediction comparisons against independent measured data.

Comparison A (genuinely blind): momentum-theory shaft-power prediction for the
UIUC APC Slow-Fly 10x5 wind-tunnel data.
  P_shaft_pred = T^1.5 / sqrt(2 rho A) / FM_declared
  FM_declared = 0.60 +/- 0.08, taken from the small-propeller literature
  (Deters & Selig 2014: static FM of small APC-class props ~0.5-0.7) BEFORE
  any comparison with the held-out measurements. The measured FM is NOT
  computed until after the prediction is frozen.

Comparison B (weak-form): same momentum prediction for the T-Motor P80 III +
G30*10.5 bench table (electrical power predicted as P_ideal/(FM*eta) with
FM = 0.80 +/- 0.05, eta = 0.80 +/- 0.05 declared from large-CF-prop
literature). The bench electrical power is held out from the prediction path;
the FM/eta priors are informed by typical large-prop literature — so this is
a plausibility cross-check, not a fully blind test (documented as such).

Acceptance tolerances declared BEFORE comparison: MAPE <= 15 % for both;
prediction interval = FM/eta prior bands.

Outputs: JSON + two plots (predicted vs measured on the same axes).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import numpy as np  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
RHO_SEA = 1.225
GF_TO_N = 9.80665e-3

UIUC_RHO_SLUG_FT3 = 0.002377
FT_TO_M = 0.3048
LBF_TO_N = 4.4482
FTLBS_TO_W = 1.3558


def uiuc_power_comparison() -> dict:
    """Comparison A: UIUC APC SF 10x5 — momentum theory vs measured power."""
    src = REPO_ROOT / "data" / "benchmarks" / "uiuc" / "apce_10x5_static_pg0819.txt"
    rows = []
    for line in src.read_text(encoding="utf-8").splitlines()[1:]:
        parts = line.split()
        if len(parts) == 3:
            rows.append({"rpm": float(parts[0]), "CT": float(parts[1]), "CP": float(parts[2])})

    d_ft = 10.0 / 12.0
    d_m = 10.0 * 0.0254
    area_m2 = math.pi * (d_m / 2.0) ** 2
    fm_declared, fm_band = 0.60, 0.08  # literature prior (declared before comparison)

    rpm, thrust_n, p_meas_w, p_pred_w = [], [], [], []
    for r in rows:
        n = r["rpm"] / 60.0
        t_lbf = r["CT"] * UIUC_RHO_SLUG_FT3 * n**2 * d_ft**4
        p_ftlbs = r["CP"] * UIUC_RHO_SLUG_FT3 * n**3 * d_ft**5
        t = t_lbf * LBF_TO_N
        p_m = p_ftlbs * FTLBS_TO_W
        p_ideal = t**1.5 / math.sqrt(2.0 * RHO_SEA * area_m2)
        rpm.append(r["rpm"])
        thrust_n.append(t)
        p_meas_w.append(p_m)
        p_pred_w.append(p_ideal / fm_declared)

    rpm_a, thrust_a, meas_a, pred_a = (np.array(x) for x in (rpm, thrust_n, p_meas_w, p_pred_w))
    err_pct = (pred_a - meas_a) / meas_a * 100.0
    mape = float(np.mean(np.abs(err_pct)))
    rmse = float(np.sqrt(np.mean((pred_a - meas_a) ** 2)))
    bias = float(np.mean(err_pct))
    in_band = float(np.mean(np.abs(err_pct) <= 15.0)) * 100.0

    # FM measured (computed ONLY after the prediction above is complete)
    fm_measured = [float(p_ideal / p_m) for p_ideal, p_m in
                   ((t**1.5 / math.sqrt(2.0 * RHO_SEA * area_m2), m)
                    for t, m in zip(thrust_a, meas_a))]

    _plot(rpm, meas_a, pred_a,
          "UIUC APC SF 10x5 (independent wind-tunnel data)",
          "shaft power [W]",
          "momentum theory, FM=0.60 (declared) vs UIUC measurement",
          REPO_ROOT / "outputs" / "audit" / "phase5_blind_uiuc.png")

    return {
        "comparison": "A: momentum-theory power vs UIUC measured (BLIND)",
        "independent_source": "UIUC PropDB apce_10x5_static_pg0819 (Brandt & Selig / Dantsker)",
        "n_points": len(rpm),
        "declared_prior": {"fm": fm_declared, "fm_band": fm_band,
                           "source": "small-propeller literature (Deters & Selig 2014)"},
        "metrics": {
            "mape_pct": round(mape, 2),
            "rmse_w": round(rmse, 2),
            "bias_pct": round(bias, 2),
            "max_abs_err_pct": round(float(np.max(np.abs(err_pct))), 2),
            "within_15pct_pct": round(in_band, 1),
            "tolerance_declared_before_comparison": "MAPE <= 15 %",
        },
        "fm_measured_after_freeze": [round(f, 3) for f in fm_measured],
        "pass": mape <= 15.0,
        "verdict_note": "genuinely blind: FM prior from literature; measured FM "
                        "computed only after prediction frozen",
    }


def p80_power_comparison() -> dict:
    """Comparison B: momentum theory vs the P80 III bench electrical power."""
    library = REPO_ROOT / "data" / "components"
    sys_path_guard()
    from physics.propulsion.dataset import PowertrainDataset  # noqa: E402
    from physics.propulsion.loader import ComponentLibrary  # noqa: E402

    lib = ComponentLibrary(library)
    motor = lib.motor("tmotor_p80iii_kv100")
    dataset = PowertrainDataset(motor, "T-MOTOR G30*10.5CF")
    rows = [r for r in motor.test_data if r.prop == "T-MOTOR G30*10.5CF"]

    d_m = 30.0 * 0.0254
    area_m2 = math.pi * (d_m / 2.0) ** 2
    fm_declared, fm_band = 0.80, 0.05
    eta_declared, eta_band = 0.80, 0.05

    rpm, thrust_n, p_meas, p_pred = [], [], [], []
    for r in rows:
        t = r.thrust_gf * GF_TO_N
        p_ideal = t**1.5 / math.sqrt(2.0 * RHO_SEA * area_m2)
        rpm.append(r.rpm)
        thrust_n.append(t)
        p_meas.append(r.power_w)
        p_pred.append(p_ideal / (fm_declared * eta_declared))

    rpm_a, thrust_a, meas_a, pred_a = (np.array(x) for x in (rpm, thrust_n, p_meas, p_pred))
    err_pct = (pred_a - meas_a) / meas_a * 100.0
    mape = float(np.mean(np.abs(err_pct)))
    rmse = float(np.sqrt(np.mean((pred_a - meas_a) ** 2)))
    bias = float(np.mean(err_pct))
    in_band = float(np.mean(np.abs(err_pct) <= 15.0)) * 100.0

    _plot(rpm, meas_a, pred_a,
          "T-Motor P80 III + G30*10.5 (manufacturer bench)",
          "electrical power [W]",
          "momentum theory, FM=0.80, eta=0.80 (declared) vs bench measurement",
          REPO_ROOT / "outputs" / "audit" / "phase5_weak_p80.png")

    return {
        "comparison": "B: momentum-theory electrical power vs P80 bench (WEAK-FORM)",
        "independent_source": "T-Motor P80 III bench table (held out from prediction path; "
        "priors informed by large-prop literature — not fully blind)",
        "n_points": len(rpm),
        "declared_prior": {"fm": fm_declared, "eta": eta_declared,
                           "source": "large-CF-prop literature"},
        "metrics": {
            "mape_pct": round(mape, 2),
            "rmse_w": round(rmse, 2),
            "bias_pct": round(bias, 2),
            "max_abs_err_pct": round(float(np.max(np.abs(err_pct))), 2),
            "within_15pct_pct": round(in_band, 1),
            "tolerance_declared_before_comparison": "MAPE <= 15 %",
        },
        "pass": mape <= 15.0,
        "verdict_note": "weak-form: priors informed by typical large-prop values; "
                        "documented as plausibility cross-check, not full blind test",
    }


def _plot(rpm, measured, predicted, title, ylabel, subtitle, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(rpm, measured, "o-", label="measured (independent)", color="#0f766e")
    ax.plot(rpm, predicted, "s--", label="predicted (blind)", color="#b91c1c")
    ax.set_xlabel("RPM")
    ax.set_ylabel(ylabel)
    ax.set_title(f"{title}\n{subtitle}", fontsize=9)
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)


def sys_path_guard() -> None:
    for _p in (REPO_ROOT / "packages", REPO_ROOT / "packages" / "shared-schemas"):
        _s = str(_p)
        if _p.is_dir() and _s not in sys.path:
            sys.path.insert(0, _s)


import sys  # noqa: E402


def main() -> int:
    a = uiuc_power_comparison()
    b = p80_power_comparison()
    report = {"audit": "M9 Phase 5 — blind prediction comparisons",
              "tolerance_declared_before_comparison": "MAPE <= 15 % for both comparisons",
              "comparisons": [a, b]}
    out = REPO_ROOT / "outputs" / "audit" / "phase5_blind_predictions.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    md = ["# M9 Phase 5 — blind prediction comparisons", "",
          "Tolerance declared before comparison: **MAPE <= 15 %** for both.", ""]
    for c in report["comparisons"]:
        m = c["metrics"]
        md.append(f"## {c['comparison']}")
        md.append(f"- source: {c['independent_source']}")
        md.append(f"- n = {c['n_points']}, MAPE {m['mape_pct']} %, bias {m['bias_pct']} %, "
                  f"RMSE {m['rmse_w']} W, max {m['max_abs_err_pct']} %, "
                  f"within ±15 %: {m['within_15pct_pct']} %")
        md.append(f"- pass: {c['pass']}")
        md.append(f"- {c['verdict_note']}")
        md.append("")
    (out.parent / "phase5_blind_predictions.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
