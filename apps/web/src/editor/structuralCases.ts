/** User-defined structural load-case grammar: one name and rotor loads per line.
 * This parser never invents operational loads or substitutes predictions for data. */
export interface StructuralCaseInput {
  name: string
  thrusts_n: number[]
  /** Optional, explicit torque about each radial arm's own longitudinal axis. */
  axial_torques_n_m?: number[]
}

export function parseStructuralCases(text: string, rotorCount: number): StructuralCaseInput[] {
  if (!Number.isSafeInteger(rotorCount) || rotorCount < 1) {
    throw new Error('A design with at least one rotor is required')
  }
  const lines = text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean)
  if (!lines.length || lines.length > 32) {
    throw new Error('Enter 1–32 named load cases')
  }
  const seen = new Set<string>()
  return lines.map((line, index) => {
    const colon = line.indexOf(':')
    if (colon < 1) throw new Error(`Line ${index + 1}: use "case name: rotor thrusts in N"`)
    const name = line.slice(0, colon).trim()
    if (!name || name.length > 80 || seen.has(name)) {
      throw new Error(`Line ${index + 1}: case name must be unique and at most 80 characters`)
    }
    seen.add(name)
    const sections = line.slice(colon + 1).split('|')
    if (sections.length > 2) throw new Error(`Line ${index + 1}: at most one | torque delimiter`)
    const parseVector = (text: string, label: string) => {
      const raw = text.split(',').map((x) => x.trim())
      if (raw.length !== rotorCount || raw.some((x) => x === '')) {
        throw new Error(`Line ${index + 1}: expected ${rotorCount} comma-separated ${label}`)
      }
      const values = raw.map(Number)
      if (!values.every(Number.isFinite)) {
        throw new Error(`Line ${index + 1}: ${label} must be finite`)
      }
      return values
    }
    const thrusts_n = parseVector(sections[0], 'thrust values')
    if (!thrusts_n.every((x) => x >= 0)) {
      throw new Error(`Line ${index + 1}: thrust must be >=0 N`)
    }
    if (sections.length === 1) return { name, thrusts_n }
    const axial_torques_n_m = parseVector(sections[1], 'arm-axis torques')
    return { name, thrusts_n, axial_torques_n_m }
  })
}
