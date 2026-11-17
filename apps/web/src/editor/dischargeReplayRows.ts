/** M15: strict parsing of operator-supplied discharge trace rows (not measurements generated here). */
export interface DischargeReplayRow {
  t_s: number
  current_a: number
  terminal_voltage_v: number
  temperature_c: number | null
}

export function parseDischargeReplayRows(csv: string): DischargeReplayRow[] {
  const lines = csv.split(/\r?\n/).map((s) => s.trim()).filter(Boolean)
  const header = 't_s,current_a,terminal_voltage_v,temperature_c'
  if (lines[0]?.replaceAll(' ', '').toLowerCase() === header) lines.shift()
  if (lines.length < 6 || lines.length > 10000) {
    throw new Error('A discharge replay requires 6–10000 timestamped rows')
  }
  const numeric = (raw: string, label: string, row: number): number => {
    if (!raw || !Number.isFinite(Number(raw))) {
      throw new Error(`Row ${row}: ${label} must be a finite number`)
    }
    return Number(raw)
  }
  const rows = lines.map((line, i): DischargeReplayRow => {
    const fields = line.split(',').map((v) => v.trim())
    if (fields.length !== 4) throw new Error(`Row ${i + 1}: exactly four fields expected`)
    const t_s = numeric(fields[0], 'elapsed time', i + 1)
    const current_a = numeric(fields[1], 'pack current', i + 1)
    const terminal_voltage_v = numeric(fields[2], 'terminal voltage', i + 1)
    const temperature_c = fields[3] === '' ? null : numeric(fields[3], 'temperature', i + 1)
    if (t_s < 0 || current_a < 0 || terminal_voltage_v <= 0) {
      throw new Error(`Row ${i + 1}: time and current must be >=0, voltage >0`)
    }
    return { t_s, current_a, terminal_voltage_v, temperature_c }
  })
  if (rows[0].t_s !== 0) throw new Error('Discharge trace must start at t=0')
  if (rows.some((row, i) => i > 0 && row.t_s <= rows[i - 1].t_s)) {
    throw new Error('Discharge timestamps must strictly increase')
  }
  if (!rows.some((row) => row.current_a > 0)) {
    throw new Error('Discharge trace needs a positive current sample')
  }
  return rows
}
