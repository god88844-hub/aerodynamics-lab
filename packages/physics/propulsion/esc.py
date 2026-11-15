"""ESC limit checks (M2: static current/voltage limits; thermal model in M4)."""

from __future__ import annotations

from aeroforge_schemas.component import EscSpec


class Esc:
    def __init__(self, spec: EscSpec) -> None:
        self.spec = spec

    def check(self, current_a: float, voltage_v: float) -> list[str]:
        issues: list[str] = []
        if current_a > self.spec.max_continuous_current_a:
            issues.append(
                f"ESC over-current: {current_a:.1f} A > limit "
                f"{self.spec.max_continuous_current_a:.1f} A"
            )
        if self.spec.max_voltage_v is not None and voltage_v > self.spec.max_voltage_v:
            issues.append(
                f"ESC over-voltage: {voltage_v:.1f} V > limit {self.spec.max_voltage_v:.1f} V"
            )
        return issues
