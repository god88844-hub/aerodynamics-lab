/** Simple, explicit CSV row parser. No synthetic or inferred measurements. */
export type BatterySplit = 'calibration' | 'held_out'
export interface BatteryObservationInput {
  id: string
  split: BatterySplit
  soc_pct: number
  current_a: number
  terminal_voltage_v: number
  temperature_c: number | null
}

/** Rows: id,split,soc_pct,current_a,terminal_voltage_v,temperature_c(optional). */
export function parseBatteryEvidenceRows(source: string): BatteryObservationInput[] {
  const lines = source.split(/\r?\n/).map((l) => l.trim()).filter(Boolean)
  const header = 'id,split,soc_pct,current_a,terminal_voltage_v,temperature_c'
  if (lines[0]?.replaceAll(' ', '').toLowerCase() === header) lines.shift()
  if (lines.length < 5 || lines.length > 500) {
    throw new Error('Enter 5–500 discharge rows (minimum 3 calibration and 2 held-out)')
  }
  const ids = new Set<string>()
  let calibration = 0
  let held = 0
  const result = lines.map((line, i): BatteryObservationInput => {
    const fields = line.split(',').map((x) => x.trim())
    if (fields.length !== 6) throw new Error(`Row ${i + 1}: exactly 6 comma-separated fields required`)
    const [id, split, soc, current, terminal, temp] = fields
    if (!/^[A-Za-z0-9_.-]{1,80}$/.test(id) || ids.has(id)) {
      throw new Error(`Row ${i + 1}: observation ID invalid or repeated`)
    }
    ids.add(id)
    if (split !== 'calibration' && split !== 'held_out') {
      throw new Error(`Row ${i + 1}: split must be calibration or held_out`)
    }
    if (split === 'calibration') calibration += 1
    else held += 1
    const parseNumber = (value: string, name: string): number => {
      if (!value || !Number.isFinite(Number(value))) {
        throw new Error(`Row ${i + 1}: ${name} must be a finite number`)
      }
      return Number(value)
    }
    const soc_pct = parseNumber(soc, 'SOC')
    const current_a = parseNumber(current, 'current')
    const terminal_voltage_v = parseNumber(terminal, 'loaded voltage')
    const temperature_c = temp === '' ? null : parseNumber(temp, 'temperature')
    if (soc_pct < 0 || soc_pct > 100 || current_a <= 0 || terminal_voltage_v <= 0) {
      throw new Error(`Row ${i + 1}: SOC [0–100], current >0 A and pack voltage >0 V required`)
    }
    return {
      id, split, soc_pct, current_a, terminal_voltage_v, temperature_c,
    }
  })
  if (calibration < 3 || held < 2) {
    throw new Error('Use at least 3 calibration and 2 held-out samples')
  }
  return result
}
