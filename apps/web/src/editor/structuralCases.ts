/** User-defined structural load-case grammar: one name and rotor loads per line.
 * This parser never invents operational loads or substitutes predictions for data. */
export interface StructuralCaseInput { name: string; thrusts_n: number[] }

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
    const raw = line.slice(colon + 1).split(',').map((x) => x.trim())
    if (raw.length !== rotorCount || raw.some((x) => x === '')) {
      throw new Error(`Line ${index + 1}: expected ${rotorCount} comma-separated thrust values`)
    }
    const thrusts_n = raw.map(Number)
    if (!thrusts_n.every((x) => Number.isFinite(x) && x >= 0)) {
      throw new Error(`Line ${index + 1}: thrust must be finite and >=0 N`)
    }
    return { name, thrusts_n }
  })
}
