/** Import a strict, unquoted numeric flight-log CSV. No inferred measurements. */
export const flightChannels = [
  'altitude_m', 'vertical_speed_m_s', 'bus_voltage_v', 'battery_current_a',
] as const
export type FlightChannel = typeof flightChannels[number]
export const flightChannelLabels: Record<FlightChannel, string> = {
  altitude_m: 'Altitude error limit (m)',
  vertical_speed_m_s: 'Vertical-speed error limit (m/s)',
  bus_voltage_v: 'Bus-voltage error limit (V)',
  battery_current_a: 'Pack-current error limit (A)',
}
export interface FlightEvidenceRow {
  t_s: number
  altitude_m: number | null
  vertical_speed_m_s: number | null
  bus_voltage_v: number | null
  battery_current_a: number | null
}

export function parseFlightEvidenceRows(raw: string): FlightEvidenceRow[] {
  const lines = raw.split(/\r?\n/).map((line) => line.trim()).filter(Boolean)
  const header = 't_s,altitude_m,vertical_speed_m_s,bus_voltage_v,battery_current_a'
  if (lines[0]?.replaceAll(' ', '').toLowerCase() === header) lines.shift()
  if (lines.length < 5 || lines.length > 1000) {
    throw new Error('Provide 5–1000 real or explicitly synthetic flight observations')
  }
  let previousTime = -1
  const rows = lines.map((line, index): FlightEvidenceRow => {
    const fields = line.split(',').map((field) => field.trim())
    if (fields.length !== 5) throw new Error(`Row ${index + 1}: exactly 5 CSV fields required`)
    const number = (value: string, required: boolean): number | null => {
      if (!value && !required) return null
      if (!value || !Number.isFinite(Number(value))) {
        throw new Error(`Row ${index + 1}: expected finite SI number`)
      }
      return Number(value)
    }
    const t_s = number(fields[0], true) as number
    if (t_s < 0 || t_s <= previousTime) {
      throw new Error(`Row ${index + 1}: timestamps must strictly increase from zero or later`)
    }
    previousTime = t_s
    const row: FlightEvidenceRow = {
      t_s,
      altitude_m: number(fields[1], false),
      vertical_speed_m_s: number(fields[2], false),
      bus_voltage_v: number(fields[3], false),
      battery_current_a: number(fields[4], false),
    }
    if (flightChannels.every((key) => row[key] === null)) {
      throw new Error(`Row ${index + 1}: no measurements`)
    }
    if ((row.bus_voltage_v !== null && row.bus_voltage_v <= 0) ||
        (row.battery_current_a !== null && row.battery_current_a < 0)) {
      throw new Error(`Row ${index + 1}: voltage must be positive and current nonnegative`)
    }
    return row
  })
  for (const key of flightChannels) {
    const count = rows.filter((row) => row[key] !== null).length
    if (count > 0 && count < 5) throw new Error(`${key} needs at least 5 observations`)
  }
  return rows
}
