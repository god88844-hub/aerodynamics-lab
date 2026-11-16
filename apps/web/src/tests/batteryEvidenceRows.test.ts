import { describe, expect, it } from 'vitest'
import { parseBatteryEvidenceRows } from '../editor/batteryEvidenceRows'

const csv = [
  'c1,calibration,40,10,23.2,25',
  'c2,calibration,50,20,22.9,',
  'c3,calibration,60,30,22.5,25',
  'h1,held_out,45,15,23.0,',
  'h2,held_out,55,25,22.7,24',
].join('\n')

describe('M12 evidence CSV parsing', () => {
  it('accepts separate declared runs without inventing missing temperature', () => {
    const parsed = parseBatteryEvidenceRows(csv)
    expect(parsed).toHaveLength(5)
    expect(parsed[1].temperature_c).toBeNull()
    expect(parsed[0].temperature_c).toBe(25)
    expect(parsed[4].split).toBe('held_out')
    expect(parsed[4].current_a).toBe(25)
  })
  it('accepts an exact CSV header', () => {
    const rows = parseBatteryEvidenceRows(
      'id,split,soc_pct,current_a,terminal_voltage_v,temperature_c\n' + csv,
    )
    expect(rows).toHaveLength(5)
  })
  it.each([
    '', 'c1,calibration,40,10,23.2,',
    csv.replace('h2,held_out', 'c1,held_out'),
    csv.replace('h2,held_out', 'h2,unproven'),
    csv.replace('h2,held_out,55,25', 'h2,held_out,55,-25'),
    csv.replace('h2,held_out,55,25', 'h2,held_out,55,Infinity'),
    csv.replace('h2,held_out,55,25', 'h2,held_out,55,NaN'),
    csv.replace('h2,held_out,55,25', 'h2,held_out,101,25'),
    csv.replace('h2,held_out,55,25,22.7,24', 'h2,held_out,55,25,22.7'),
    csv.replace('h2,held_out,55,25,22.7,24', 'h2,held_out,55,25,22.7,no'),
  ])('rejects malformed or inadequate observations', (source) => {
    expect(() => parseBatteryEvidenceRows(source)).toThrow()
  })
})
