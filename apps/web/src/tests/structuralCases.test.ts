import { describe, expect, it } from 'vitest'
import { parseStructuralCases } from '../editor/structuralCases'

describe('operator-supplied structural load cases', () => {
  it('parses multiple explicitly named cases with SI thrusts', () => {
    expect(parseStructuralCases('hover: 1, 2, 3, 4\nmaneuver: 1.5, 0, 2, 6', 4))
      .toEqual([
        { name: 'hover', thrusts_n: [1, 2, 3, 4] },
        { name: 'maneuver', thrusts_n: [1.5, 0, 2, 6] },
      ])
  })
  it.each([
    ['', 4], ['hover: 1, 2', 4], ['hover: 1, 2, NaN, 4', 4],
    ['hover: 1, 2, -3, 4', 4], ['hover: 1, 2, Infinity, 4', 4],
    ['hover: 1, 2, , 4', 4], ['hover: 1, 2, 3, 4\nhover: 1, 2, 3, 4', 4],
    ['unnamed case', 4],
  ])('rejects bad input instead of synthesizing thrust data', (source, count) => {
    expect(() => parseStructuralCases(source, count)).toThrow()
  })
  it('parses optional signed arm-axis torque vectors, never inferred from thrust', () => {
    expect(parseStructuralCases('takeoff: 1,2 | -0.1,0.2', 2)).toEqual([
      { name: 'takeoff', thrusts_n: [1, 2], axial_torques_n_m: [-0.1, 0.2] },
    ])
  })
  it.each([
    'case: 1, 2 | 0.1',
    'case: 1, 2 | ',
    'case: 1, 2 | NaN, 1',
    'case: 1, 2 | Infinity, 1',
    'case: 1, 2 | 0.1,0.2 | 0.3,0.4',
  ])('rejects malformed advanced torque vectors', (source) => {
    expect(() => parseStructuralCases(source, 2)).toThrow()
  })
  it('rejects a design without rotors', () => {
    expect(() => parseStructuralCases('hover: 2', 0)).toThrow()
  })
})
