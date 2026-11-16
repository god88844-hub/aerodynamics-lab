/** Design state for M10.2: selected physical parts, reversible edits, and
 * measurement anchors. The backend remains authoritative for mass/inertia.
 * Rotor component positions are locked: moving one without its matching rotor
 * and structural model would silently invalidate flight physics. */
import { create } from 'zustand'
import type { DroneDesign, FrameSpec, PowertrainConfig, PrimitiveGeometry, Vec3 } from '../types/api'

const ROTOR_SIGNS: [number, number][] = [[1, 1], [-1, 1], [-1, -1], [1, -1]]
const MOTOR_DZ = 0.02
const ESC_DZ = 0
const PROP_DZ = 0.045
const MAX_HISTORY = 40
type SimulationResult = import('../types/api').SimulationResult

/** Current editor supports uniformly scaling a conventional Quad-X only. */
export function applyArmLength(design: DroneDesign, armLength: number): DroneDesign {
  if (!Number.isFinite(armLength) || armLength <= 0 || design.rotors.length !== 4) return design
  const pos = (i: number, dz: number): Vec3 => {
    const [sx, sy] = ROTOR_SIGNS[i]
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
  return {
    ...design,
    parts,
    rotors: design.rotors.map((r, i) => ({ ...r, position_m: pos(i, MOTOR_DZ) })),
    frame: design.frame ? { ...design.frame, arm_length_m: armLength } : design.frame,
  }
}

/** Design coordinates are component centers of gravity (meters), not mesh vertices. */
export function computeCog(design: DroneDesign): Vec3 {
  let total = 0
  const weighted: Vec3 = [0, 0, 0]
  for (const part of design.parts) {
    if (!(part.mass_kg > 0) || !Number.isFinite(part.mass_kg)) continue
    total += part.mass_kg
    for (let i = 0; i < 3; i++) weighted[i] += part.mass_kg * part.position_m[i]
  }
  return total > 0 ? weighted.map((v) => v / total) as Vec3 : [0, 0, 0]
}

export function batteryPart(design: DroneDesign) {
  return design.parts.find((p) => p.name.toLowerCase().includes('battery'))
}

/** Only point-mass payloads and batteries may be repositioned independently.
 * Frame, motors, ESC and propeller coordinates encode coupled assumptions. */
export function canMovePart(name: string): boolean {
  return name.startsWith('payload_') || name.toLowerCase().includes('battery')
}

export function componentSeparationM(design: DroneDesign, a: string | null, b: string | null): number | null {
  if (!a || !b) return null
  const p = design.parts.find((part) => part.name === a)
  const q = design.parts.find((part) => part.name === b)
  if (!p || !q) return null
  return Math.hypot(...p.position_m.map((v, i) => v - q.position_m[i]))
}

interface DesignState {
  design: DroneDesign
  designId: number | null
  result: SimulationResult | null
  scenario: string
  selectedPart: string | null
  measureFrom: string | null
  measureTo: string | null
  /** Presentation-only settings: never included in a physics design snapshot. */
  gizmoEnabled: boolean
  gizmoDragging: boolean
  snapStepM: number
  setGizmoEnabled: (enabled: boolean) => void
  setGizmoDragging: (dragging: boolean) => void
  setSnapStepM: (step: number) => void
  past: DroneDesign[]
  future: DroneDesign[]
  setSnapshot: (snapshot: DroneDesign, id: number | null) => void
  setResult: (result: SimulationResult | null) => void
  setScenario: (scenario: string) => void
  selectPart: (name: string | null) => void
  setMeasureFrom: (name: string | null) => void
  setMeasureTo: (name: string | null) => void
  setPartPosition: (name: string, position: Vec3) => void
  setPartMass: (name: string, mass: number) => void
  setPartGeometry: (name: string, geometry: PrimitiveGeometry | null) => void
  addPayload: () => void
  removeSelectedPayload: () => void
  undo: () => void
  redo: () => void
  setName: (name: string) => void
  setArmLength: (m: number) => void
  setBatteryPosition: (pos: Vec3) => void
  setBatteryMass: (kg: number) => void
  setPowertrain: (p: PowertrainConfig) => void
  setFrame: (f: FrameSpec | null) => void
  setDrag: (cda: number | null) => void
}

function updateDesign(s: DesignState, apply: (d: DroneDesign) => DroneDesign): Partial<DesignState> {
  const next = apply(s.design)
  if (next === s.design) return {}
  return {
    design: next,
    result: null, // stale trajectory and metrics must never survive a design change
    past: [...s.past.slice(-(MAX_HISTORY - 1)), s.design],
    future: [],
  }
}

const initialDesign: DroneDesign = {
  schema_version: '0.1', name: 'new_quad', parts: [], rotors: [],
  drag_cd_a_m2: 0.02, rotor_torque_per_thrust_n_m_per_n: 0.015, notes: null,
}

export const useDesignStore = create<DesignState>((set) => ({
  design: initialDesign,
  designId: null,
  result: null,
  scenario: 'flight',
  selectedPart: null,
  measureFrom: null,
  measureTo: null,
  gizmoEnabled: true,
  gizmoDragging: false,
  snapStepM: 0.01,
  setGizmoEnabled: (enabled) => set({ gizmoEnabled: enabled, gizmoDragging: false }),
  setGizmoDragging: (dragging) => set({ gizmoDragging: dragging }),
  setSnapStepM: (step) => {
    if ([0, 0.005, 0.01, 0.05, 0.1].includes(step)) set({ snapStepM: step })
  },
  past: [],
  future: [],
  setSnapshot: (snapshot, id) => set({
    design: snapshot, designId: id, result: null,
    selectedPart: null, measureFrom: null, measureTo: null,
    gizmoDragging: false, past: [], future: [],
  }),
  setResult: (result) => set({ result }),
  setScenario: (scenario) => set({ scenario }),
  selectPart: (name) => set((s) => ({
    selectedPart: name && s.design.parts.some((p) => p.name === name) ? name : null,
  })),
  setMeasureFrom: (name) => set((s) => ({
    measureFrom: name && s.design.parts.some((p) => p.name === name) ? name : null,
  })),
  setMeasureTo: (name) => set((s) => ({
    measureTo: name && s.design.parts.some((p) => p.name === name) ? name : null,
  })),
  setPartPosition: (name, position) => set((s) => updateDesign(s, (d) => {
    if (!canMovePart(name) || !position.every(Number.isFinite)) return d
    const previous = d.parts.find((p) => p.name === name)
    if (!previous || position.every((v, i) => v === previous.position_m[i])) return d
    return { ...d, parts: d.parts.map((p) =>
      p.name === name ? { ...p, position_m: [...position] as Vec3 } : p) }
  })),
  setPartMass: (name, mass) => set((s) => updateDesign(s, (d) => {
    if (!canMovePart(name) || !Number.isFinite(mass) || mass <= 0) return d
    const previous = d.parts.find((p) => p.name === name)
    if (!previous || previous.mass_kg === mass ||
        previous.inertia_about_own_cog_kg_m2 != null) return d
    return { ...d, parts: d.parts.map((p) => p.name === name ? { ...p, mass_kg: mass } : p) }
  })),
  setPartGeometry: (name, geometry) => set((s) => updateDesign(s, (d) => {
    if (!canMovePart(name)) return d
    const previous = d.parts.find((p) => p.name === name)
    // Never silently replace, invalidate or synthesize a measured inertia.
    if (!previous || previous.inertia_about_own_cog_kg_m2 != null) return d
    if (geometry !== null) {
      const [x, y, z] = geometry.dimensions_m
      if (![x, y, z].every((v) => Number.isFinite(v) && v > 0)) return d
      if (geometry.shape !== 'box' && geometry.shape !== 'cylinder') return d
      if (geometry.shape === 'cylinder' && Math.abs(x - y) > 1e-9) return d
    }
    if (JSON.stringify(previous.geometry ?? null) === JSON.stringify(geometry)) return d
    return { ...d, parts: d.parts.map((p) =>
      p.name === name ? { ...p, geometry } : p) }
  })),
  addPayload: () => set((s) => {
    let index = 1
    while (s.design.parts.some((p) => p.name === `payload_${index}`)) index += 1
    const name = `payload_${index}`
    return {
      ...updateDesign(s, (d) => ({
        ...d, parts: [...d.parts, { name, mass_kg: 0.25, position_m: [0, 0, 0] }],
      })),
      selectedPart: name,
    }
  }),
  removeSelectedPayload: () => set((s) => {
    const name = s.selectedPart
    if (!name?.startsWith('payload_') || !s.design.parts.some((p) => p.name === name)) return {}
    return {
      ...updateDesign(s, (d) => ({ ...d, parts: d.parts.filter((p) => p.name !== name) })),
      selectedPart: null,
      measureFrom: s.measureFrom === name ? null : s.measureFrom,
      measureTo: s.measureTo === name ? null : s.measureTo,
    }
  }),
  undo: () => set((s) => {
    const previous = s.past[s.past.length - 1]
    if (!previous) return {}
    return {
      design: previous, result: null, past: s.past.slice(0, -1),
      future: [s.design, ...s.future].slice(0, MAX_HISTORY),
      selectedPart: s.selectedPart && previous.parts.some((p) => p.name === s.selectedPart)
        ? s.selectedPart : null,
      measureFrom: s.measureFrom && previous.parts.some((p) => p.name === s.measureFrom)
        ? s.measureFrom : null,
      measureTo: s.measureTo && previous.parts.some((p) => p.name === s.measureTo)
        ? s.measureTo : null,
    }
  }),
  redo: () => set((s) => {
    const next = s.future[0]
    if (!next) return {}
    return {
      design: next, result: null, future: s.future.slice(1),
      past: [...s.past.slice(-(MAX_HISTORY - 1)), s.design],
    }
  }),
  setName: (name) => set((s) => updateDesign(s, (d) => name === d.name ? d : { ...d, name })),
  setArmLength: (m) => set((s) => updateDesign(s, (d) => applyArmLength(d, m))),
  setBatteryPosition: (pos) => set((s) => updateDesign(s, (d) => {
    if (!pos.every(Number.isFinite)) return d
    return { ...d, parts: d.parts.map((p) =>
      p.name.toLowerCase().includes('battery') ? { ...p, position_m: [...pos] as Vec3 } : p) }
  })),
  setBatteryMass: (kg) => set((s) => updateDesign(s, (d) => {
    if (!Number.isFinite(kg) || kg <= 0 ||
        d.parts.some((p) => p.name.toLowerCase().includes('battery') &&
          p.inertia_about_own_cog_kg_m2 != null)) return d
    return { ...d, parts: d.parts.map((p) =>
      p.name.toLowerCase().includes('battery') ? { ...p, mass_kg: kg } : p) }
  })),
  setPowertrain: (p) => set((s) => updateDesign(s, (d) => ({ ...d, powertrain: p }))),
  setFrame: (f) => set((s) => updateDesign(s, (d) => ({ ...d, frame: f }))),
  setDrag: (cda) => set((s) => updateDesign(s, (d) => ({ ...d, drag_cd_a_m2: cda }))),
}))
