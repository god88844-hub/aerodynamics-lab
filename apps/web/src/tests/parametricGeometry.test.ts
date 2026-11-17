import { beforeEach, describe, expect, it } from '@rstest/core'
import { useDesignStore } from '../state/designStore'
import { analyzeGeometry } from '../editor/geometryChecks'
import type { DroneDesign } from '../types/api'

const base: DroneDesign = {
  schema_version: '0.1', name: 'primitives',
  parts: [
    { name: 'frame', mass_kg: 1, position_m: [0, 0, 0] },
    { name: 'battery', mass_kg: .5, position_m: [0, 0, 0] },
  ],
  rotors: [{ position_m: [.25, .25, 0], spin_direction: 1 }],
  rotor_torque_per_thrust_n_m_per_n: 0,
}
const s = () => useDesignStore.getState()
beforeEach(() => s().setSnapshot(structuredClone(base), null))

describe('M10.4 parametric primitive snapshots', () => {
  it('assigns and resizes a declared battery box and invalidates stale predictions', () => {
    s().setResult({ scenario: 'flight', status: 'completed' })
    s().setPartGeometry('battery', { shape: 'box', dimensions_m: [.2, .1, .05] })
    expect(s().result).toBeNull()
    expect(s().design.parts[1].geometry?.dimensions_m).toEqual([.2, .1, .05])
    s().setPartGeometry('battery', { shape: 'box', dimensions_m: [.3, .1, .05] })
    s().undo()
    expect(s().design.parts[1].geometry?.dimensions_m[0]).toBe(.2)
  })
  it('keeps mass constant on dimension-only edit', () => {
    s().setPartGeometry('battery', { shape: 'box', dimensions_m: [.2, .1, .05] })
    expect(s().design.parts[1].mass_kg).toBe(.5)
  })
  it('refuses impossible primitive dimensions and refuses edits to motor/frame', () => {
    s().setPartGeometry('battery', { shape: 'box', dimensions_m: [0, .1, .05] })
    expect(s().design.parts[1].geometry).toBeUndefined()
    s().setPartGeometry('frame', { shape: 'box', dimensions_m: [.1, .1, .1] })
    expect(s().design.parts[0].geometry).toBeUndefined()
  })
  it('enforces equal X/Y diameter for cylinder geometry', () => {
    s().setPartGeometry('battery', { shape: 'cylinder', dimensions_m: [.1, .2, .3] })
    expect(s().design.parts[1].geometry).toBeUndefined()
    s().setPartGeometry('battery', { shape: 'cylinder', dimensions_m: [.1, .1, .3] })
    expect(s().design.parts[1].geometry?.shape).toBe('cylinder')
  })
  it('protects measured inertia when editing geometry or mass', () => {
    const protectedDesign: DroneDesign = {
      ...base,
      parts: [base.parts[0], {
        ...base.parts[1],
        inertia_about_own_cog_kg_m2: [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
      }],
    }
    s().setSnapshot(protectedDesign, null)
    s().setPartGeometry('battery', { shape: 'box', dimensions_m: [.1, .1, .1] })
    s().setPartMass('battery', .7)
    expect(s().design.parts[1].geometry).toBeUndefined()
    expect(s().design.parts[1].mass_kg).toBe(.5)
  })
  it('reports broad-phase box overlaps without asserting physical collision', () => {
    s().setPartGeometry('battery', { shape: 'box', dimensions_m: [.2, .2, .2] })
    s().addPayload()
    s().setPartGeometry('payload_1', { shape: 'cylinder', dimensions_m: [.1, .1, .1] })
    expect(analyzeGeometry(s().design, null).some((x) =>
      x.code === 'primitive_aabb_interference' && x.severity === 'warning')).toBe(true)
    s().setPartPosition('payload_1', [2, 0, 0])
    expect(analyzeGeometry(s().design, null).some((x) =>
      x.code === 'primitive_aabb_interference')).toBe(false)
  })
})
