import { describe, expect, it } from '@rstest/core'
import { parsePropulsionEvidenceRows } from '../editor/propulsionEvidenceRows'

const csv = [
  'r1,1100,11,550,1.9', 'r2,1200,11,600,2', 'r3,1300,11,650,2.1',
  'r4,1400,11,700,2.2', 'r5,1500,11,750,2.3',
].join('\n')

describe('M14 static bench CSV parser', () => {
  it('parses the exact measurements and optional header', () => {
    const result = parsePropulsionEvidenceRows('id,rpm,voltage_v,thrust_gf,current_a\n' + csv)
    expect(result).toHaveLength(5)
    expect(result[0].rpm).toBe(1100)
    expect(result[4].current_a).toBe(2.3)
  })
  it.each([
    '', csv.split('\n').slice(0, 4).join('\n'),
    csv.replace('r5,1500', 'r1,1500'),
    csv.replace('r5,1500', 'r5,1400'),
    csv.replace('r5,1500', 'r5,-1500'),
    csv.replace('r5,1500', 'r5,NaN'),
    csv.replace('r5,1500', 'r5,Infinity'),
    csv.replace('r5,1500,11,750,2.3', 'r5,1500,11,750'),
  ])('rejects missing, duplicate or invalid observations', (bad) => {
    expect(() => parsePropulsionEvidenceRows(bad)).toThrow()
  })
})
