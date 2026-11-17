import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { RotorClearancePanel } from '../panels/RotorClearancePanel'
import type { DroneDesign } from '../types/api'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

const design = {
  schema_version: '0.1', name: 'synthetic_quad',
  rotor_torque_per_thrust_n_m_per_n: 0,
  parts: [{ name: 'frame', mass_kg: 1, position_m: [0, 0, 0] }],
  rotors: [
    { position_m: [.25, .25, 0], spin_direction: 1 },
    { position_m: [-.25, .25, 0], spin_direction: -1 },
  ],
} as DroneDesign

describe('M28.2 projected rotor clearance panel', () => {
  it('sends exact current design and declared dimensions and displays limitations', async () => {
    const response = {
      status: 'ANALYTIC_PROJECTED_TIP_CLEARANCE_ONLY',
      screen_passed: true,
      independently_measured_geometry_validated: false,
      physical_interference_or_flightworthiness_established: false,
      minimum_observed_projected_tip_clearance_m: .12,
      pairs: [{
        rotor_a: 0, rotor_b: 1, projected_tip_clearance_m: .12,
        projected_disk_touch_or_overlap: false, below_declared_tip_clearance: false,
        center_vertical_separation_m: 0,
      }],
      limitations: [],
    }
    const send = vi.fn().mockResolvedValue({ ok: true, json: async () => response })
    vi.stubGlobal('fetch', send)
    render(<RotorClearancePanel design={design} />)
    fireEvent.change(screen.getByLabelText('Installed rotor diameters'), {
      target: { value: '.38, .38' },
    })
    fireEvent.change(screen.getByLabelText('Rotor geometry source'), {
      target: { value: 'synthetic numerical fixture not real assembly' },
    })
    fireEvent.change(screen.getByLabelText('Minimum rotor tip clearance'), {
      target: { value: '.02' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Screen rotor tip clearances' }))
    expect(await screen.findByText('Physical interference validated: no')).toBeDefined()
    expect(screen.getByText('Geometry independently measured: no')).toBeDefined()
    expect(screen.getByText('Projected screen: within declared gap')).toBeDefined()
    expect(send.mock.calls[0][0]).toBe('/api/components/rotor-clearance-screen')
    const body = JSON.parse((send.mock.calls[0][1] as RequestInit).body as string)
    expect(body.installed_propeller_diameters_m).toEqual([.38, .38])
    expect(body.design.name).toBe('synthetic_quad')
    fireEvent.change(screen.getByLabelText('Minimum rotor tip clearance'), {
      target: { value: '.05' },
    })
    expect(screen.queryByText('Physical interference validated: no')).toBeNull()
  })

  it('fails closed for missing geometry and nonexistent measured dimensions', async () => {
    const send = vi.fn()
    vi.stubGlobal('fetch', send)
    render(<RotorClearancePanel design={design} />)
    fireEvent.click(screen.getByRole('button', { name: 'Screen rotor tip clearances' }))
    expect(await screen.findByRole('alert')).toBeDefined()
    expect(send).not.toHaveBeenCalled()
    fireEvent.change(screen.getByLabelText('Rotor geometry source'), {
      target: { value: 'synthetic' },
    })
    fireEvent.change(screen.getByLabelText('Installed rotor diameters'), {
      target: { value: '.38' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Screen rotor tip clearances' }))
    expect(screen.getByRole('alert').textContent).toMatch(/exactly one installed/)
    expect(send).not.toHaveBeenCalled()
  })
})
