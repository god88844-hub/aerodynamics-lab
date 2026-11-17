/** Strict CSV ingestion: never fill absent measurements or assume provenance. */
export interface PropulsionObservationInput {
  id: string
  rpm: number
  voltage_v: number
  thrust_gf: number
  current_a: number
}

const EXPECTED = 'id,rpm,voltage_v,thrust_gf,current_a'

export function parsePropulsionEvidenceRows(csv: string): PropulsionObservationInput[] {
  const lines = csv.split(/\r?\n/).map((line) => line.trim()).filter(Boolean)
  if (lines[0]?.replaceAll(' ', '').toLowerCase() === EXPECTED) lines.shift()
  if (lines.length < 5 || lines.length > 500) throw new Error('Enter 5–500 observations')
  const ids = new Set<string>()
  const rpms = new Set<number>()
  const rows = lines.map((line, idx): PropulsionObservationInput => {
    const fields = line.split(',').map((value) => value.trim())
    if (fields.length !== 5) throw new Error(`Row ${idx + 1}: exactly five CSV fields required`)
    const [id, rpmText, voltageText, thrustText, currentText] = fields
    if (!/^[a-zA-Z0-9_.-]{1,80}$/.test(id) || ids.has(id)) {
      throw new Error(`Row ${idx + 1}: duplicate or invalid sample ID`)
    }
    ids.add(id)
    const numbers = [rpmText, voltageText, thrustText, currentText]
    if (numbers.some((value) => !value || !Number.isFinite(Number(value)) || Number(value) <= 0)) {
      throw new Error(`Row ${idx + 1}: RPM, bus voltage, thrust and current must be positive finite measurements`)
    }
    const [rpm, voltage_v, thrust_gf, current_a] = numbers.map(Number)
    rpms.add(rpm)
    return { id, rpm, voltage_v, thrust_gf, current_a }
  })
  if (rpms.size < 5) throw new Error('At least five distinct RPM operating points are required')
  return rows
}
