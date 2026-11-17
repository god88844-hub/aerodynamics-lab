import { describe, expect, it } from '@rstest/core'
import { applyArmLength, quadXRadius } from '../state/designStore'
import { analyzeGeometry } from '../editor/geometryChecks'
import type { DroneDesign } from '../types/api'

function quad(): DroneDesign {
  const points: [number, number, number][] = [
    [.25, .25, .02], [-.25, .25, .02],
    [-.25, -.25, .02], [.25, -.25, .02],
  ]
  return {
    schema_version: '0.1',
    name: 'quad_x',
    parts: [
      { name: 'frame', mass_kg: 1, position_m: [0, 0, 0] },
      { name: 'motor_front_right', mass_kg: .1, position_m: points[0] },
      { name: 'motor_front_left', mass_kg: .1, position_m: points[1] },
      { name: 'motor_rear_left', mass_kg: .1, position_m: points[2] },
      { name: 'motor_rear_right', mass_kg: .1, position_m: points[3] },
      { name: 'esc_front_right', mass_kg: .03, position_m: [.15, .15, .0] },
      { name: 'prop_front_right', mass_kg: .02, position_m: [.25, .25, .045] },
    ],
    rotors: points.map((position_m, index) => ({
      position_m, spin_direction: (index % 2 ? 1 : -1) as 1 | -1,
    })),
    frame: {
      arm_length_m: .25, tube_od_m: .012, tube_id_m: .01,
      material_id: 'cfrp_quasi_iso',
    },
    rotor_torque_per_thrust_n_m_per_n: .015,
  }
}

describe('M10.6 structural geometry synchronization', () => {
  it('reports actual radial distance instead of a single XY coordinate', () => {
    expect(quadXRadius(quad())).toBeCloseTo(Math.sqrt(2) * .25)
  })
  it('scales rotor + motor + ESC + prop together and preserves their z offsets', () => {
    const original = quad()
    const changed = applyArmLength(original, .4)
    const expectedXY = .4 / Math.sqrt(2)
    expect(quadXRadius(changed)).toBeCloseTo(.4, 9)
    expect(changed.frame?.arm_length_m).toBe(.4)
    expect(changed.rotors[0].position_m[0]).toBeCloseTo(expectedXY, 10)
    expect(changed.rotors[0].position_m[1]).toBeCloseTo(expectedXY, 10)
    expect(changed.parts.find((p) => p.name === 'motor_front_right')?.position_m[0]).toBeCloseTo(expectedXY)
    expect(changed.parts.find((p) => p.name === 'esc_front_right')?.position_m[0]).toBeCloseTo(.15 * .4 / (Math.SQRT2 * .25))
    expect(changed.parts.find((p) => p.name === 'prop_front_right')?.position_m[2]).toBe(.045)
    expect(original.rotors[0].position_m[0]).toBe(.25) // input unchanged
  })
  it('synchronizes legacy frame field even when rotor radius is unchanged', () => {
    const old = quad()
    const r = quadXRadius(old)!
    const fixed = applyArmLength(old, r)
    expect(fixed.frame?.arm_length_m).toBeCloseTo(r)
    expect(fixed.rotors[0].position_m[0]).toBeCloseTo(.25)
  })
  it('refuses non-X and asymmetric rotor layouts', () => {
    const skew = quad()
    skew.rotors[0].position_m = [.3, .25, .02]
    expect(quadXRadius(skew)).toBeNull()
    expect(applyArmLength(skew, .4)).toBe(skew)
    const hex = quad()
    hex.rotors.push(hex.rotors[0])
    expect(quadXRadius(hex)).toBeNull()
    expect(applyArmLength(hex, .5)).toBe(hex)
  })
  it('warns on both shorter and longer legacy declarations', () => {
    const old = quad()
    expect(analyzeGeometry(old, null).some((x) => x.code === 'arm_span_underestimate')).toBe(true)
    old.frame!.arm_length_m = .8
    expect(analyzeGeometry(old, null).some((x) => x.code === 'arm_span_overestimate')).toBe(true)
  })
})
