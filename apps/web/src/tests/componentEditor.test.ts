import { beforeEach, describe, expect, it } from 'vitest'
import { useDesignStore, applyArmLength, componentSeparationM, computeCog } from '../state/designStore'
import type { DroneDesign } from '../types/api'

const reference: DroneDesign = {
  schema_version: '0.1',
  name: 'reference',
  parts: [
    { name: 'frame', mass_kg: 1, position_m: [0, 0, 0] },
    { name: 'battery', mass_kg: 1, position_m: [0, 0, 0] },
    { name: 'motor_front_right', mass_kg: 0.1, position_m: [0.25, 0.25, 0.02] },
    { name: 'motor_front_left', mass_kg: 0.1, position_m: [-0.25, 0.25, 0.02] },
    { name: 'motor_rear_left', mass_kg: 0.1, position_m: [-0.25, -0.25, 0.02] },
    { name: 'motor_rear_right', mass_kg: 0.1, position_m: [0.25, -0.25, 0.02] },
  ],
  rotors: [
    { position_m: [0.25, 0.25, 0.02], spin_direction: 1 },
    { position_m: [-0.25, 0.25, 0.02], spin_direction: -1 },
    { position_m: [-0.25, -0.25, 0.02], spin_direction: 1 },
    { position_m: [0.25, -0.25, 0.02], spin_direction: -1 },
  ],
  rotor_torque_per_thrust_n_m_per_n: 0.015,
}
const get = () => useDesignStore.getState()

beforeEach(() => get().setSnapshot(structuredClone(reference), null))

describe('component editor', () => {
  it('adds a point-mass payload and updates center of gravity', () => {
    get().addPayload()
    expect(get().selectedPart).toBe('payload_1')
    get().setPartPosition('payload_1', [1, 0, 0])
    expect(computeCog(get().design)[0]).toBeGreaterThan(0)
    expect(get().design.parts.find((p) => p.name === 'payload_1')?.position_m).toEqual([1, 0, 0])
  })
  it('rejects invalid masses and non-finite component positions', () => {
    get().addPayload()
    get().setPartMass('payload_1', -1)
    get().setPartMass('payload_1', Number.NaN)
    get().setPartPosition('payload_1', [Number.POSITIVE_INFINITY, 1, 2])
    expect(get().design.parts.find((p) => p.name === 'payload_1')).toMatchObject({
      mass_kg: 0.25, position_m: [0, 0, 0],
    })
  })
  it('refuses edits to coupled motor, ESC, propeller and frame parts', () => {
    const before = structuredClone(get().design)
    get().setPartPosition('motor_front_right', [9, 9, 9])
    get().setPartMass('frame', 999)
    expect(get().design).toEqual(before)
    expect(get().past).toHaveLength(0)
  })
  it('undoes and redoes coordinate changes and clears stale simulation result', () => {
    get().setResult({ scenario: 'flight', status: 'completed' })
    get().setPartPosition('battery', [0.1, 0.2, 0.3])
    expect(get().result).toBeNull()
    get().undo()
    expect(get().design.parts.find((p) => p.name === 'battery')?.position_m).toEqual([0, 0, 0])
    get().redo()
    expect(get().design.parts.find((p) => p.name === 'battery')?.position_m).toEqual([0.1, 0.2, 0.3])
  })
  it('measures exact center spacing and handles missing anchors', () => {
    get().addPayload()
    get().setPartPosition('payload_1', [3, 4, 0])
    expect(componentSeparationM(get().design, 'battery', 'payload_1')).toBeCloseTo(5)
    expect(componentSeparationM(get().design, null, 'payload_1')).toBeNull()
    expect(componentSeparationM(get().design, 'bogus', 'payload_1')).toBeNull()
  })
  it('deletes payload safely and resets measurement anchors', () => {
    get().addPayload()
    get().setMeasureFrom('payload_1')
    get().setMeasureTo('battery')
    get().removeSelectedPayload()
    expect(get().design.parts.some((p) => p.name === 'payload_1')).toBe(false)
    expect(get().measureFrom).toBeNull()
    get().undo()
    expect(get().design.parts.some((p) => p.name === 'payload_1')).toBe(true)
  })
  it('does not distort a non-Quad-X layout via Quad-X scaling', () => {
    const hexa: DroneDesign = { ...reference,
      rotors: [...reference.rotors, ...reference.rotors.slice(0, 2)] }
    expect(applyArmLength(hexa, 0.9)).toBe(hexa)
  })
  it('keeps rotor and part placements coupled for Quad-X scaling', () => {
    get().setArmLength(0.4)
    expect(get().design.rotors[0].position_m[0]).toBeCloseTo(0.4 / Math.SQRT2)
    expect(get().design.rotors[0].position_m[1]).toBeCloseTo(0.4 / Math.SQRT2)
    expect(get().design.parts.find((p) => p.name === 'motor_front_right')?.position_m[0]).toBeCloseTo(0.4 / Math.SQRT2)
  })
})
