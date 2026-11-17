import { beforeEach, describe, expect, it } from '@rstest/core'
import { analyzeGeometry, bodyPointToScene, scenePointToBody, snapBodyPoint } from '../editor/geometryChecks'
import { useDesignStore } from '../state/designStore'
import type { DroneDesign } from '../types/api'

const design: DroneDesign = {
  schema_version: '0.1', name: 'geom',
  parts: [
    { name: 'frame', mass_kg: 1, position_m: [0, 0, 0] },
    { name: 'battery', mass_kg: 0.6, position_m: [0, 0, -0.03] },
  ],
  rotors: [
    { position_m: [0.2, 0, 0.02], spin_direction: 1 },
    { position_m: [-0.2, 0, 0.02], spin_direction: -1 },
  ],
  rotor_torque_per_thrust_n_m_per_n: 0.01,
}

describe('M10.3 transform geometry and constraints', () => {
  beforeEach(() => useDesignStore.getState().setSnapshot(structuredClone(design), null))

  it('round-trips body z-up and Three.js Y-up coordinates', () => {
    const body: [number, number, number] = [1.2, -3.4, 5.6]
    expect(bodyPointToScene(body)).toEqual([1.2, 5.6, 3.4])
    expect(scenePointToBody(bodyPointToScene(body))).toEqual(body)
  })
  it('snaps positions reproducibly with millimeter-resolution steps', () => {
    expect(snapBodyPoint([0.012, -0.026, 0.004], 0.01)).toEqual([0.01, -0.03, 0])
    expect(snapBodyPoint([0.014, -0.006, 0.019], 0)).toEqual([0.014, -0.006, 0.019])
    expect(() => snapBodyPoint([Number.NaN, 0, 0], 0.01)).toThrow()
    expect(() => snapBodyPoint([0, 0, 0], -0.01)).toThrow()
  })
  it('warns about projected propeller-disc overlap from supplied diameter', () => {
    expect(analyzeGeometry(design, 18).some((x) => x.code === 'rotor_planform_overlap')).toBe(true)
    expect(analyzeGeometry(design, 12).some((x) => x.code === 'rotor_planform_overlap')).toBe(false)
    expect(analyzeGeometry(design, null).some((x) => x.code === 'unknown_prop_diameter')).toBe(true)
  })
  it('flags degenerate tubes, duplicate component identifiers, and invalid masses', () => {
    const broken: DroneDesign = {
      ...design,
      parts: [...design.parts, { name: 'battery', mass_kg: -1, position_m: [0, 0, 0] }],
      frame: { arm_length_m: 0.2, tube_od_m: 0.01, tube_id_m: 0.012, material_id: 'x' },
    }
    const codes = analyzeGeometry(broken, 12).map((x) => x.code)
    expect(codes).toContain('duplicate_part_name')
    expect(codes).toContain('invalid_part')
    expect(codes).toContain('invalid_frame_tube')
  })
  it('stores snap controls without mutating the physical design snapshot', () => {
    const before = structuredClone(useDesignStore.getState().design)
    useDesignStore.getState().setSnapStepM(0.05)
    useDesignStore.getState().setGizmoEnabled(false)
    useDesignStore.getState().setSnapStepM(0.002)
    expect(useDesignStore.getState().snapStepM).toBe(0.05)
    expect(useDesignStore.getState().gizmoEnabled).toBe(false)
    expect(useDesignStore.getState().design).toEqual(before)
  })
  it('commits a simulated dragged battery coordinate as one undoable design edit', () => {
    const s = useDesignStore.getState()
    s.setPartPosition('battery', snapBodyPoint(scenePointToBody([0.036, 0.08, -0.014]), 0.01))
    expect(useDesignStore.getState().design.parts.find((p) => p.name === 'battery')?.position_m).toEqual([0.04, 0.01, 0.08])
    expect(useDesignStore.getState().past).toHaveLength(1)
    useDesignStore.getState().undo()
    expect(useDesignStore.getState().design.parts.find((p) => p.name === 'battery')?.position_m).toEqual([0, 0, -0.03])
  })
})
