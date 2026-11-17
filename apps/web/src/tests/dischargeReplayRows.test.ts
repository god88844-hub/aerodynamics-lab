import { describe, expect, it } from 'vitest'
import { parseDischargeReplayRows } from '../editor/dischargeReplayRows'

const csv = [
  '0,5,24,25', '60,5,23.8,', '120,5,23.6,25',
  '180,5,23.4,25', '240,5,23.2,25', '300,5,23,25',
].join('\n')

describe('M15 discharge CSV parser', () => {
  it('parses six timestamped observations without synthesizing unknown temperature', () => {
    const rows = parseDischargeReplayRows(csv)
    expect(rows).toHaveLength(6)
    expect(rows[1].temperature_c).toBeNull()
    expect(rows[5].t_s).toBe(300)
    expect(rows[3].current_a).toBe(5)
  })
  it('accepts the documented header', () => {
    expect(parseDischargeReplayRows(
      't_s,current_a,terminal_voltage_v,temperature_c\n' + csv,
    )).toHaveLength(6)
  })
  it.each([
    '',
    csv.replace('60,5', '0,5'),
    csv.replace('300,5', '300,-5'),
    csv.replace('300,5,23', '300,5,Infinity'),
    csv.replace('300,5,23', '300,5,NaN'),
    csv.replace('300,5,23,25', '300,5,23'),
    csv.replace('300,5,23,25', '300,5,23,n/a'),
    csv.replace('0,5,24', '1,5,24'),
    csv.split('\n').slice(0, 5).join('\n'),
    csv.replaceAll(',5,', ',0,'),
  ])('rejects invalid or incomplete trace rows', (rows) => {
    expect(() => parseDischargeReplayRows(rows)).toThrow()
  })
})
