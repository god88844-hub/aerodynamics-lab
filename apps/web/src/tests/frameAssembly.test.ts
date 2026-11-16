import { beforeEach, describe, expect, it } from 'vitest'
import { useDesignStore } from '../state/designStore'
import { analyzeGeometry } from '../editor/geometryChecks'
import type { DroneDesign } from '../types/api'

const design: DroneDesign = {
  schema_version: '0.1', name: 'mount_test',
  parts: [
    { name: 'frame', mass_kg: 2, position_m: [0, 0, 0] },
    { name: 'battery', mass_kg: .5, position_m: [0, 0, -.02] },
  ],
  rotors: [{ position_m: [.2, .2, 0], spin_direction: 1 }],
  frame: { arm_length_m: .3, tube_od_m: .012, tube_id_m: .009,
    material_id: 'cfrp_quasi_iso' },
  rotor_torque_per_thrust_n_m_per_n: 0,
}
const state = () => useDesignStore.getState()
beforeEach(() => {
  state().setSnapshot(structuredClone(design), null)
  state().selectPart('battery')
})

describe('M10.5 attached component placement', () => {
  it('mounts a battery and updates mount + mass position together', () => {
    state().setResult({ scenario: 'flight', status: 'completed' })
    state().addMountForSelectedPart()
    expect(state().result).toBeNull()
    expect(state().design.parts[1].mount_id).toBe('mount_1')
    expect(state().design.frame?.mount_points?.[0].position_m).toEqual([0, 0, -.02])
    state().setMountPosition('mount_1', [.1, .2, -.04])
    expect(state().design.parts[1].position_m).toEqual([.1, .2, -.04])
    expect(state().past).toHaveLength(2)
    state().undo()
    expect(state().design.parts[1].position_m).toEqual([0, 0, -.02])
  })
  it('locks independent translation of mounted parts', () => {
    state().addMountForSelectedPart()
    state().setPartPosition('battery', [9, 0, 0])
    state().setBatteryPosition([8, 0, 0])
    expect(state().design.parts[1].position_m).toEqual([0, 0, -.02])
    expect(state().past).toHaveLength(1)
  })
  it('allows independent movement after detach', () => {
    state().addMountForSelectedPart()
    state().detachSelectedPart()
    expect(state().design.parts[1].mount_id).toBeNull()
    state().setPartPosition('battery', [.1, 0, 0])
    expect(state().design.parts[1].position_m).toEqual([.1, 0, 0])
  })
  it('removes mount but preserves its component', () => {
    state().addMountForSelectedPart()
    state().removeMount('mount_1')
    expect(state().design.parts[1].mount_id).toBeNull()
    expect(state().design.parts[1].position_m).toEqual([0, 0, -.02])
    expect(state().design.frame?.mount_points).toEqual([])
  })
  it('plate size edits are reversible and keep physical mass unchanged', () => {
    state().setPlateDimensions([.18, .12, .02])
    expect(state().design.frame?.plate_dimensions_m).toEqual([.18, .12, .02])
    expect(state().design.parts[0].mass_kg).toBe(2)
    state().undo()
    expect(state().design.frame?.plate_dimensions_m).toBeUndefined()
  })
  it('detects missing and misaligned references in geometry preflight', () => {
    state().addMountForSelectedPart()
    let invalid = structuredClone(state().design)
    invalid.parts[1].position_m = [.1, 0, 0]
    expect(analyzeGeometry(invalid, null).some((x) =>
      x.code === 'misaligned_frame_mount')).toBe(true)
    invalid = structuredClone(state().design)
    invalid.frame!.mount_points = []
    expect(analyzeGeometry(invalid, null).some((x) =>
      x.code === 'missing_frame_mount')).toBe(true)
  })
  it('flags arm-span optimism in old quad geometry', () => {
    const bad: DroneDesign = { ...design,
      frame: { ...design.frame!, arm_length_m: .2 } }
    expect(analyzeGeometry(bad, null).some((x) =>
      x.code === 'arm_span_underestimate')).toBe(true)
  })
})
