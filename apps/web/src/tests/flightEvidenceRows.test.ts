import { describe, expect, it } from 'vitest'
import { parseFlightEvidenceRows } from '../editor/flightEvidenceRows'

const csv = [
  '0,0,,24,5', '2,4,,23.8,5', '4,8,,23.6,5',
  '6,12,,23.4,5', '8,16,,23.2,5', '10,20,,23.0,5',
].join('\n')

describe('M13 flight evidence CSV import', () => {
  it('preserves unknown channels as null and unitful numeric values', () => {
    const rows = parseFlightEvidenceRows(csv)
    expect(rows).toHaveLength(6)
    expect(rows[0].vertical_speed_m_s).toBeNull()
    expect(rows[1].altitude_m).toBe(4)
    expect(rows[5].battery_current_a).toBe(5)
  })
  it('accepts the exact declared header', () => {
    expect(parseFlightEvidenceRows(
      't_s,altitude_m,vertical_speed_m_s,bus_voltage_v,battery_current_a\n' + csv,
    )).toHaveLength(6)
  })
  it.each([
    '', '0,0,,24,5',
    csv.replace('2,4', '0,4'),
    csv.replace('4,8', '4,Infinity'),
    csv.replace('4,8', '4,NaN'),
    csv.replace('2,4,,23.8', '2,4,,0'),
    csv.replace('2,4,,23.8,5', '2,4,,23.8,-1'),
    csv.replace('2,4,,23.8,5', '2,,,,'),
    csv.replace('2,4,,23.8,5', '2,4,,23.8'),
  ])('rejects invalid or incomplete evidence rows', (raw) => {
    expect(() => parseFlightEvidenceRows(raw)).toThrow()
  })
})
