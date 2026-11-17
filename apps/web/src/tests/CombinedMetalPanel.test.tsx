import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { CombinedMetalPanel } from '../panels/CombinedMetalPanel'
import type { DroneDesign } from '../types/api'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

const design = {
  schema_version: '0.1',
  name: 'synthetic_quad',
  rotor_torque_per_thrust_n_m_per_n: 0,
  parts: [{ name: 'frame', mass_kg: 1, position_m: [0, 0, 0] }],
  rotors: [{ position_m: [.2, .2, 0], spin_direction: 1 }],
  frame: {
    arm_length_m: .25, tube_od_m: .012,
    tube_id_m: .01, material_id: 'alu_6061_t6',
  },
} as DroneDesign
const caseText = '[{"name":"synthetic","thrusts_n":[5],"axial_torques_n_m":[0.1]}]'

describe('M25 analytical metal stress panel', () => {
  it('reports an analytic screen without flightworthiness certification', async () => {
    const result = {
      status: 'ANALYTICAL_ISOTROPIC_STATIC_SCREEN_ONLY',
      material_id: 'alu_6061_t6',
      screen_passed: true,
      independent_structural_validation_established: false,
      flightworthiness_established: false,
      cases: [{ name: 'synthetic', rotors: [{
        rotor_index: 0, von_mises_pa: 1200000,
        static_margin_over_required_allowable: 3.5,
      }] }],
    }
    const send = vi.fn().mockResolvedValue({ ok: true, json: async () => result })
    vi.stubGlobal('fetch', send)
    render(<CombinedMetalPanel design={design} />)
    fireEvent.change(screen.getByLabelText('Combined stress load cases'), {
      target: { value: caseText },
    })
    fireEvent.change(screen.getByLabelText('Combined stress load provenance'), {
      target: { value: 'Synthetic calculation, not physical observation' },
    })
    fireEvent.click(screen.getByRole('button', {
      name: 'Screen metal arm combined stresses',
    }))
    expect(await screen.findByText('Independent structural validation: no')).toBeDefined()
    expect(screen.getByText('Flightworthiness: no')).toBeDefined()
    expect(send.mock.calls[0][0]).toBe('/api/components/combined-metal-screen')
    const body = JSON.parse((send.mock.calls[0][1] as RequestInit).body as string)
    expect(body.cases[0].axial_torques_n_m).toEqual([.1])
    expect(body.design.name).toBe('synthetic_quad')
    fireEvent.change(screen.getByLabelText('Combined stress safety factor'), {
      target: { value: '2' },
    })
    expect(screen.queryByText('Flightworthiness: no')).toBeNull()
  })

  it('blocks unsourced or missing load inputs before sending requests', async () => {
    const send = vi.fn()
    vi.stubGlobal('fetch', send)
    render(<CombinedMetalPanel design={design} />)
    fireEvent.click(screen.getByRole('button', {
      name: 'Screen metal arm combined stresses',
    }))
    expect(await screen.findByRole('alert')).toBeDefined()
    expect(send).not.toHaveBeenCalled()
  })
})
