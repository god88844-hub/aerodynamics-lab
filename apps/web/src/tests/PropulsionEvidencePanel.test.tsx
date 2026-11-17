import { afterEach, describe, expect, it, rs } from '@rstest/core'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { PropulsionEvidencePanel } from '../panels/PropulsionEvidencePanel'
import type { DroneDesign } from '../types/api'

const design: DroneDesign = {
  schema_version: '0.1', name: 'fixture',
  parts: [{ name: 'frame', mass_kg: 1, position_m: [0, 0, 0] }],
  rotors: [{ position_m: [0, 0, 0.1], spin_direction: 1 }],
  rotor_torque_per_thrust_n_m_per_n: 0,
  powertrain: {
    motor_id: 'tmotor_mn3508_kv380', propeller_id: 'tmotor_p15x5_cf',
    esc_id: 'esc', battery_id: 'battery',
  },
}
const csv = [
  'r1,4000,14.8,900,5.5', 'r2,4100,14.8,960,6.0',
  'r3,4200,14.8,1000,6.4', 'r4,4300,14.8,1030,6.9',
  'r5,4400,14.8,1070,7.2',
].join('\n')

afterEach(() => { cleanup(); rs.unstubAllGlobals() })

function enter() {
  fireEvent.change(screen.getByLabelText('Propulsion evidence dataset type'), {
    target: { value: 'synthetic_fixture' },
  })
  for (const [field, value] of [
    ['Independent test run ID', 'math_B'],
    ['Evidence source / raw data reference', 'generated for test'],
    ['Predeclared maximum thrust error (%)', '5'],
    ['Predeclared maximum current error (%)', '7'],
  ]) fireEvent.change(screen.getByLabelText(field), { target: { value } })
  fireEvent.click(screen.getByLabelText('Matching motor prop hardware'))
  fireEvent.click(screen.getByLabelText('Unused for calibration'))
  fireEvent.change(screen.getByLabelText('Propulsion bench CSV rows'), {
    target: { value: csv },
  })
}

describe('M14 propulsion held-out evidence user interface', () => {
  it('sends exact evidence and invalidates stale results on input edit', async () => {
    const response = {
      verdict: 'SYNTHETIC_VERIFICATION_ONLY', simulation_modified: false,
      evidence: {
        observation_count: 5, scored_count: 5, unsupported_count: 0,
        unsupported_samples: [], thrust_metrics: { n: 5, mape_pct: .4,
          rmse_pct: .4, max_abs_error_pct: 1, threshold_met: true },
        current_metrics: { n: 5, mape_pct: .6, rmse_pct: .6,
          max_abs_error_pct: 2, threshold_met: true },
        current_voltage_extrapolated: false,
        calibration_knot_operating_point_overlap_count: 0,
      },
    }
    const send = rs.fn().mockResolvedValue({ ok: true, json: async () => response })
    rs.stubGlobal('fetch', send)
    render(<PropulsionEvidencePanel design={design} />)
    enter()
    fireEvent.click(screen.getByRole('button', { name: /Compare independent static bench data/i }))
    expect(await screen.findByText('SYNTHETIC VERIFICATION ONLY')).toBeDefined()
    const payload = JSON.parse((send.mock.calls[0][1] as RequestInit).body as string)
    expect(payload.motor_id).toBe('tmotor_mn3508_kv380')
    expect(payload.propeller_id).toBe('tmotor_p15x5_cf')
    expect(payload.predeclared_max_thrust_error_pct).toBe(5)
    expect(payload.predeclared_max_current_error_pct).toBe(7)
    expect(payload.hardware_matches_selected_components).toBe(true)
    expect(payload.unused_for_model_calibration).toBe(true)
    expect(payload.observations).toHaveLength(5)
    fireEvent.change(screen.getByLabelText('Evidence source / raw data reference'), {
      target: { value: 'updated source' },
    })
    expect(screen.queryByText('SYNTHETIC VERIFICATION ONLY')).toBeNull()
  })
  it('requires explicit provenance before any request', async () => {
    const send = rs.fn()
    rs.stubGlobal('fetch', send)
    render(<PropulsionEvidencePanel design={design} />)
    fireEvent.click(screen.getByRole('button', { name: /Compare independent static bench data/i }))
    expect(await screen.findByRole('alert')).toBeDefined()
    expect(send).not.toHaveBeenCalled()
  })
})
