/** Design store (Zustand): holds the current design snapshot and edit
  actions. Regenerating rotor placement from the arm length is the core
  editor operation (spec M5: "editing arm length, propeller size, and
  battery location"). */

import { create } from 'zustand'
import type { DroneDesign, FrameSpec, PowertrainConfig, Vec3 } from '../types/api'

/** Quad-X layout: arm_length_m is the X/Y offset of each rotor axis
  (matches the reference designs in data/designs). */
const ROTOR_SIGNS: [number, number][] = [
  [1, 1],
  [-1, 1],
  [-1, -1],
  [1, -1],
]
const MOTOR_DZ = 0.02
const ESC_DZ = 0.0
const PROP_DZ = 0.045

export function applyArmLength(design: DroneDesign, armLength: number): DroneDesign {
  const pos = (i: number, dz: number): Vec3 => {
    const [sx, sy] = ROTOR_SIGNS[i % 4]
    return [sx * armLength, sy * armLength, dz]
  }
  const suffixes = ['front_right', 'front_left', 'rear_left', 'rear_right']
  const parts = design.parts.map((p) => {
    const idx = suffixes.findIndex((s) => p.name.endsWith(s))
    if (idx < 0) return p
    if (p.name.startsWith('motor_')) return { ...p, position_m: pos(idx, MOTOR_DZ) }
    if (p.name.startsWith('esc_')) return { ...p, position_m: pos(idx, ESC_DZ) }
    if (p.name.startsWith('prop_')) return { ...p, position_m: pos(idx, PROP_DZ) }
    return p
  })
  const rotors = design.rotors.map((r, i) => ({ ...r, position_m: pos(i, MOTOR_DZ) }))
  const frame = design.frame ? { ...design.frame, arm_length_m: armLength } : design.frame
  return { ...design, parts, rotors, frame }
}

/** Client-side CoG for the viewport marker (authoritative preview comes
  from the API's /designs/preview). */
export function computeCog(design: DroneDesign): Vec3 {
  let m = 0
  const acc: Vec3 = [0, 0, 0]
  for (const p of design.parts) {
    m += p.mass_kg
    acc[0] += p.mass_kg * p.position_m[0]
    acc[1] += p.mass_kg * p.position_m[1]
    acc[2] += p.mass_kg * p.position_m[2]
  }
  if (m === 0) return [0, 0, 0]
  return [acc[0] / m, acc[1] / m, acc[2] / m]
}

export function batteryPart(design: DroneDesign) {
  return design.parts.find((p) => p.name.toLowerCase().includes('battery'))
}

interface DesignState {
  design: DroneDesign
  designId: number | null
  result: import('../types/api').SimulationResult | null
  scenario: string
  setSnapshot: (snapshot: DroneDesign, id: number | null) => void
  setResult: (result: import('../types/api').SimulationResult | null) => void
  setScenario: (s: string) => void
  setName: (name: string) => void
  setArmLength: (m: number) => void
  setBatteryPosition: (pos: Vec3) => void
  setBatteryMass: (kg: number) => void
  setPowertrain: (p: PowertrainConfig) => void
  setFrame: (f: FrameSpec | null) => void
  setDrag: (cda: number | null) => void
}

export const useDesignStore = create<DesignState>((set) => ({
  design: {
    schema_version: '0.1',
    name: 'new_quad',
    parts: [],
    rotors: [],
    drag_cd_a_m2: 0.02,
    rotor_torque_per_thrust_n_m_per_n: 0.015,
    notes: null,
  },
  designId: null,
  result: null,
  scenario: 'flight',
  setSnapshot: (snapshot, id) => set({ design: snapshot, designId: id, result: null }),
  setResult: (result) => set({ result }),
  setScenario: (scenario) => set({ scenario }),
  setName: (name) => set((s) => ({ design: { ...s.design, name } })),
  setArmLength: (m) => set((s) => ({ design: applyArmLength(s.design, m) })),
  setBatteryPosition: (pos) =>
    set((s) => ({
      design: {
        ...s.design,
        parts: s.design.parts.map((p) =>
          p.name.toLowerCase().includes('battery') ? { ...p, position_m: pos } : p,
        ),
      },
    })),
  setBatteryMass: (kg) =>
    set((s) => ({
      design: {
        ...s.design,
        parts: s.design.parts.map((p) =>
          p.name.toLowerCase().includes('battery') ? { ...p, mass_kg: kg } : p,
        ),
      },
    })),
  setPowertrain: (p) => set((s) => ({ design: { ...s.design, powertrain: p } })),
  setFrame: (f) => set((s) => ({ design: { ...s.design, frame: f } })),
  setDrag: (cda) => set((s) => ({ design: { ...s.design, drag_cd_a_m2: cda } })),
}))
