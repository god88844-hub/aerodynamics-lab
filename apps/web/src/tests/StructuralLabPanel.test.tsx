import { afterEach, describe, expect, it, rs } from '@rstest/core'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { StructuralLabPanel } from '../panels/StructuralLabPanel'
import type { DroneDesign } from '../types/api'

const sample: DroneDesign = {
  schema_version: '0.1',
  name: 'structural_screen_ui',
  rotor_torque_per_thrust_n_m_per_n: 0,
  parts: [{ name: 'frame', mass_kg: 1, position_m: [0, 0, 0] }],
  rotors: [
    { position_m: [0.2, 0.2, 0], spin_direction: 1 },
    { position_m: [-0.2, -0.2, 0], spin_direction: -1 },
  ],
  frame: {
    arm_length_m: 0.3, tube_od_m: 0.012, tube_id_m: 0.01,
    material_id: 'alu_6061_t6',
  },
}
afterEach(() => {
  cleanup()
  rs.unstubAllGlobals()
})

describe('M10.8 user-defined load-case form', () => {
  it('preserves explicit torque vectors and joint allowable provenance in request', async () => {
    const result = {
      verdict: 'ANALYTICAL_STATIC_SCREEN_ONLY',
      material_id: 'alu_6061_t6',
      material_source: 'fixture',
      material_uncertainty_pct: 2,
      governing: null,
      cases: [],
      limitations: [],
      advanced_loads: {
        screening_verdict: 'INCOMPLETE_EVIDENCE',
        axial_torque_cases_with_data: 1,
        axial_torque_cases_total: 1,
        tube_torsion_screen: null,
        joint_bending_screen: null,
        joint_axial_torque_screen: null,
        combined_interaction: 'NOT_MODELED',
        limitations: [],
      },
    }
    const send = rs.fn().mockResolvedValue({ ok: true, json: async () => result })
    rs.stubGlobal('fetch', send)
    render(<StructuralLabPanel design={sample} />)

    fireEvent.change(screen.getByLabelText('Named structural load cases'), {
      target: { value: 'case_1: 1,2 | -0.1,0.2' },
    })
    fireEvent.click(screen.getByText('Optional torsion and joint inputs'))
    fireEvent.change(screen.getByLabelText('Tube shear allowable MPa'), {
      target: { value: '30' },
    })
    fireEvent.change(screen.getByLabelText('Shear evidence source'), {
      target: { value: 'external test' },
    })
    fireEvent.change(screen.getByLabelText('Joint bending capacity'), {
      target: { value: '5' },
    })
    fireEvent.change(screen.getByLabelText('Joint arm-axis torque capacity'), {
      target: { value: '1' },
    })
    fireEvent.change(screen.getByLabelText('Joint evidence source'), {
      target: { value: 'joint report' },
    })
    fireEvent.click(screen.getByRole('button', { name: /Evaluate static load cases/i }))
    expect(await screen.findByText(/Advanced: INCOMPLETE EVIDENCE/)).toBeDefined()
    const payload = JSON.parse((send.mock.calls[0][1] as RequestInit).body as string)
    expect(payload.cases).toEqual([
      { name: 'case_1', thrusts_n: [1, 2], axial_torques_n_m: [-0.1, 0.2] },
    ])
    expect(payload.shear_allowable_pa).toBe(30e6)
    expect(payload.shear_allowable_source).toBe('external test')
    expect(payload.joint_allowables).toEqual({
      bending_moment_n_m: 5, axial_torque_n_m: 1, evidence_source: 'joint report',
    })
    fireEvent.change(screen.getByLabelText('Named structural load cases'), {
      target: { value: 'case_2: 2,3' },
    })
    expect(screen.queryByText(/Advanced: INCOMPLETE EVIDENCE/)).toBeNull()
  })

  it('rejects a half-entered shear allowable without submitting', async () => {
    const send = rs.fn()
    rs.stubGlobal('fetch', send)
    render(<StructuralLabPanel design={sample} />)
    fireEvent.change(screen.getByLabelText('Named structural load cases'), {
      target: { value: 'case: 2,3' },
    })
    fireEvent.click(screen.getByText('Optional torsion and joint inputs'))
    fireEvent.change(screen.getByLabelText('Tube shear allowable MPa'), {
      target: { value: '40' },
    })
    fireEvent.click(screen.getByRole('button', { name: /Evaluate static load cases/i }))
    expect(await screen.findByRole('alert')).toBeDefined()
    expect(send).not.toHaveBeenCalled()
  })
})
