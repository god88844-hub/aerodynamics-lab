/** Frontend unit tests: design store edit operations and the results panel. */

import { describe, expect, it } from '@rstest/core'
import { applyArmLength, computeCog } from '../state/designStore'
import type { DroneDesign } from '../types/api'

const baseDesign: DroneDesign = {
  schema_version: '0.1',
  name: 'test_quad',
  parts: [
    { name: 'frame', mass_kg: 1.0, position_m: [0, 0, 0] },
    { name: 'battery', mass_kg: 0.5, position_m: [0, 0, -0.03] },
    { name: 'motor_front_right', mass_kg: 0.1, position_m: [0.25, 0.25, 0.02] },
    { name: 'motor_front_left', mass_kg: 0.1, position_m: [-0.25, 0.25, 0.02] },
    { name: 'motor_rear_left', mass_kg: 0.1, position_m: [-0.25, -0.25, 0.02] },
    { name: 'motor_rear_right', mass_kg: 0.1, position_m: [0.25, -0.25, 0.02] },
    { name: 'prop_front_right', mass_kg: 0.02, position_m: [0.25, 0.25, 0.045] },
    { name: 'prop_front_left', mass_kg: 0.02, position_m: [-0.25, 0.25, 0.045] },
    { name: 'prop_rear_left', mass_kg: 0.02, position_m: [-0.25, -0.25, 0.045] },
    { name: 'prop_rear_right', mass_kg: 0.02, position_m: [0.25, -0.25, 0.045] },
  ],
  rotors: [
    { position_m: [0.25, 0.25, 0.02], spin_direction: -1 },
    { position_m: [-0.25, 0.25, 0.02], spin_direction: 1 },
    { position_m: [-0.25, -0.25, 0.02], spin_direction: -1 },
    { position_m: [0.25, -0.25, 0.02], spin_direction: 1 },
  ],
  drag_cd_a_m2: 0.02,
  rotor_torque_per_thrust_n_m_per_n: 0.015,
}

describe('applyArmLength', () => {
  it('moves motors, props and rotors to the new arm length', () => {
    const scaled = applyArmLength(baseDesign, 0.4)
    const motor = scaled.parts.find((p) => p.name === 'motor_front_right')!
    expect(motor.position_m[0]).toBeCloseTo(0.4 / Math.SQRT2)
    expect(motor.position_m[1]).toBeCloseTo(0.4 / Math.SQRT2)
    expect(motor.position_m[2]).toBeCloseTo(0.02)
    const prop = scaled.parts.find((p) => p.name === 'prop_rear_left')!
    expect(prop.position_m[0]).toBeCloseTo(-0.4 / Math.SQRT2)
    expect(prop.position_m[1]).toBeCloseTo(-0.4 / Math.SQRT2)
    expect(scaled.rotors[1].position_m[0]).toBeCloseTo(-0.4 / Math.SQRT2)
    expect(scaled.rotors[1].position_m[1]).toBeCloseTo(0.4 / Math.SQRT2)
    // frame arm length follows when present
    if (scaled.frame) expect(scaled.frame.arm_length_m).toBe(0.4)
  })

  it('leaves the battery and frame untouched in position', () => {
    const scaled = applyArmLength(baseDesign, 0.3)
    const battery = scaled.parts.find((p) => p.name === 'battery')!
    expect(battery.position_m).toEqual([0, 0, -0.03])
  })
})

describe('computeCog', () => {
  it('returns the mass-weighted centroid', () => {
    const cog = computeCog(baseDesign)
    // symmetric layout -> origin in x/y; z slightly negative from battery
    expect(cog[0]).toBeCloseTo(0, 6)
    expect(cog[1]).toBeCloseTo(0, 6)
    expect(cog[2]).toBeLessThan(0)
  })
})
