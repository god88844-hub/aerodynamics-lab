/** Conservative geometric preflight; no claims of airworthiness or
 * guaranteed clearance are made from a schematic drone representation. */
import type { DroneDesign, Vec3 } from '../types/api'

export type ConstraintSeverity = 'error' | 'warning' | 'info'
export interface DesignConstraint {
  code: string
  severity: ConstraintSeverity
  message: string
}
const INCH_M = 0.0254

/** Deterministic snap in body-frame meters, not Three.js scene units. */
export function snapBodyPoint(point: Vec3, stepM: number): Vec3 {
  if (!point.every(Number.isFinite) || !Number.isFinite(stepM) || stepM < 0) {
    throw new Error('Point and grid step must be finite and nonnegative')
  }
  if (stepM === 0) return [...point]
  return point.map((v) => {
    const snapped = Math.round(v / stepM) * stepM
    return Math.abs(snapped) < stepM * 1e-10 ? 0 : Number(snapped.toFixed(9))
  }) as Vec3
}

export function bodyPointToScene(point: Vec3): Vec3 {
  return [point[0], point[2], -point[1]]
}
export function scenePointToBody(point: Vec3): Vec3 {
  return [point[0], -point[2], point[1]]
}

/** Planform rotor-disc proximity is only a conservative warning, because
 * blade thickness, vertical displacement, flex and downwash are not modeled. */
export function analyzeGeometry(
  design: DroneDesign,
  propDiameterIn: number | null | undefined,
): DesignConstraint[] {
  const issues: DesignConstraint[] = []
  const known = new Set<string>()
  for (const p of design.parts) {
    if (known.has(p.name)) issues.push({
      code: 'duplicate_part_name', severity: 'error',
      message: `Duplicate part identifier: ${p.name}`,
    })
    known.add(p.name)
    if (!Number.isFinite(p.mass_kg) || p.mass_kg <= 0 ||
        !p.position_m.every(Number.isFinite)) issues.push({
      code: 'invalid_part', severity: 'error',
      message: `Invalid mass or position for part: ${p.name}`,
    })
  }
  if (design.frame && (!Number.isFinite(design.frame.tube_od_m) ||
      !Number.isFinite(design.frame.tube_id_m) ||
      design.frame.tube_id_m <= 0 ||
      design.frame.tube_od_m <= design.frame.tube_id_m)) {
    issues.push({
      code: 'invalid_frame_tube', severity: 'error',
      message: 'Frame tube inner diameter must be positive and smaller than outer diameter.',
    })
  }
  if (propDiameterIn == null || !Number.isFinite(propDiameterIn) || propDiameterIn <= 0) {
    issues.push({
      code: 'unknown_prop_diameter', severity: 'info',
      message: 'Propeller diameter unavailable; rotor-disc planform proximity not evaluated.',
    })
    return issues
  }
  const diameterM = propDiameterIn * INCH_M
  for (let i = 0; i < design.rotors.length; i += 1) {
    for (let j = i + 1; j < design.rotors.length; j += 1) {
      const p = design.rotors[i]?.position_m
      const q = design.rotors[j]?.position_m
      if (!p || !q || !p.every(Number.isFinite) || !q.every(Number.isFinite)) {
        issues.push({
          code: 'invalid_rotor', severity: 'error',
          message: `Rotor ${i + 1} or ${j + 1} has invalid coordinates.`,
        })
        continue
      }
      const horizontalM = Math.hypot(p[0] - q[0], p[1] - q[1])
      const gapM = horizontalM - diameterM
      if (gapM < -1e-8) {
        issues.push({
          code: 'rotor_planform_overlap', severity: 'warning',
          message: `Rotors ${i + 1} and ${j + 1}: projected propeller discs overlap by ${Math.abs(gapM).toFixed(3)} m; verify actual geometry and wake interaction.`,
        })
      } else if (gapM < 0.01) {
        issues.push({
          code: 'low_rotor_planform_gap', severity: 'warning',
          message: `Rotors ${i + 1} and ${j + 1}: projected disc gap ${gapM.toFixed(3)} m (< 0.010 m). Inspect clearance and rotor interaction.`,
        })
      }
    }
  }
  return issues
}
