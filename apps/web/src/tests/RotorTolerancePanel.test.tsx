import { afterEach, describe, expect, it, rs } from '@rstest/core'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { RotorTolerancePanel } from '../panels/RotorTolerancePanel'
import type { DroneDesign } from '../types/api'

afterEach(() => { cleanup(); rs.unstubAllGlobals() })

const design = {
  schema_version: '0.1', name: 'synthetic_quad', parts: [],
  rotor_torque_per_thrust_n_m_per_n: 0,
  rotors: [
    { position_m: [.25, .25, 0], spin_direction: 1 },
    { position_m: [-.25, .25, 0], spin_direction: -1 },
  ],
} as DroneDesign

const response = {
  status: 'ANALYTICAL_HARD_BOUND_PROJECTED_CLEARANCE_ONLY',
  analytical_screen_passed: true,
  source_hard_bounds_independently_authenticated: false,
  actual_3d_interference_validated: false,
  flightworthiness_established: false,
  minimum_worst_case_projected_tip_clearance_m: 0.114,
  pairs: [{ rotor_a: 0, rotor_b: 1, worst_case_lower_projected_tip_clearance_m: 0.114,
    guaranteed_declared_tip_gap_under_assumed_hard_bounds: true }],
}

describe('M28.4 rotor hard-bound geometry panel', () => {
  it('requires sources, reports only analytic results, and invalidates stale evidence', async () => {
    const send = rs.fn().mockResolvedValue({ok: true, json: async () => response})
    rs.stubGlobal('fetch', send)
    render(<RotorTolerancePanel design={design} />)
    for (const [name, value] of [
      ['Installed rotor diameters (m)', '.38,.38'],
      ['Rotor center XY hard bounds (m)', '.001,.001'],
      ['Rotor diameter hard bounds (m)', '.001,.001'],
      ['Geometry provenance', 'synthetic fixture only'],
      ['Hard-bound provenance', 'hypothetical numeric uncertainties'],
    ]) {
      fireEvent.change(screen.getByLabelText(name), {target: {value}})
    }
    fireEvent.click(screen.getByRole('button', {name: 'Evaluate bounded rotor clearances'}))
    expect(await screen.findByText('Actual 3D interference validated: no')).toBeDefined()
    expect(screen.getByText('Flightworthiness: no')).toBeDefined()
    const [url, options] = send.mock.calls[0]
    expect(url).toBe('/api/components/bounded-rotor-clearance')
    expect(JSON.parse((options as RequestInit).body as string).xy_center_position_hard_bounds_m).toEqual([.001, .001])
    fireEvent.change(screen.getByLabelText('Geometry provenance'), {target: {value: 'new synthetic geometry'}})
    expect(screen.queryByText('Flightworthiness: no')).toBeNull()
  })

  it('refuses missing bounds before posting', async () => {
    const send = rs.fn()
    rs.stubGlobal('fetch', send)
    render(<RotorTolerancePanel design={design} />)
    fireEvent.click(screen.getByRole('button', {name: 'Evaluate bounded rotor clearances'}))
    expect(await screen.findByRole('alert')).toBeDefined()
    expect(send).not.toHaveBeenCalled()
  })
})
