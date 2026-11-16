import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { BatteryEvidencePanel } from '../panels/BatteryEvidencePanel'
import type { DroneDesign } from '../types/api'

const design: DroneDesign = {
  schema_version: '0.1',
  name: 'evidence_panel_fixture',
  rotor_torque_per_thrust_n_m_per_n: 0,
  parts: [{ name: 'frame', mass_kg: 1, position_m: [0, 0, 0] }],
  rotors: [{ position_m: [0.1, 0.1, 0], spin_direction: 1 }],
  powertrain: {
    motor_id: 'motor', propeller_id: 'prop',
    esc_id: 'esc', battery_id: 'generic_6s_lipo_16000mah',
  },
}
const csv = [
  'c1,calibration,40,10,23.2,',
  'c2,calibration,50,20,22.9,25',
  'c3,calibration,60,30,22.5,25',
  'h1,held_out,45,15,23.0,',
  'h2,held_out,55,25,22.7,24',
].join('\n')
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function enterCompleteEvidence() {
  fireEvent.change(screen.getByLabelText('Battery evidence type'), {
    target: { value: 'synthetic_fixture' },
  })
  for (const [field, value] of [
    ['Calibration run ID', 'test_A'], ['Held-out run ID', 'test_B'],
    ['Calibration data source', 'synthetic equations A'],
    ['Held-out data source', 'synthetic equations B'],
    ['Predeclared maximum voltage error percent', '5'],
  ]) {
    fireEvent.change(screen.getByLabelText(field), { target: { value } })
  }
  fireEvent.change(screen.getByLabelText('Battery discharge CSV rows'), {
    target: { value: csv },
  })
}

describe('M12 Battery Evidence Lab UI', () => {
  it('submits exact operator inputs, reports fitted resistance, clears stale results', async () => {
    const response = {
      battery_id: 'generic_6s_lipo_16000mah',
      dataset_kind: 'synthetic_fixture',
      verdict: 'SYNTHETIC_VERIFICATION_ONLY',
      simulation_battery_modified: false,
      sources: { self_reported_not_authenticated: true },
      fit: {
        fitted_pack_resistance_ohm: 0.02,
        declared_pack_resistance_ohm: 0.022,
        calibration_metrics: { count: 3 },
        calibration_current_range_a: [10, 30],
        calibration_soc_range_pct: [40, 60],
      },
      heldout: {
        metrics: { count: 2, mape_pct: 1, rmse_v: .1,
          max_abs_percentage_error_pct: 2 },
        rows: [
          { id: 'h1', soc_pct: 45, current_a: 15, c_rate: .94,
            temperature_c: null, measured_voltage_v: 23,
            predicted_voltage_v: 22.9, absolute_percentage_error_pct: .43 },
        ],
        nominal_model_metrics: null,
        nominal_model_status: 'UNKNOWN_RESISTANCE',
        within_calibration_envelope: true,
        meets_predeclared_error_tolerance: true,
        max_observed_c_rate: 1.56,
        above_declared_c_rate_limit: null,
      },
      temperature: { recorded_count: 3, missing_count: 2, modeled: false },
      limitations: [],
    }
    const send = vi.fn().mockResolvedValue({ ok: true, json: async () => response })
    vi.stubGlobal('fetch', send)
    render(<BatteryEvidencePanel design={design} />)
    enterCompleteEvidence()
    fireEvent.click(screen.getByRole('button', {
      name: /Evaluate held-out battery evidence/i,
    }))
    expect(await screen.findByText('SYNTHETIC VERIFICATION ONLY')).toBeDefined()
    expect(screen.getByText(/unknown \(no rating supplied\)/)).toBeDefined()
    expect(send).toHaveBeenCalledTimes(1)
    const payload = JSON.parse((send.mock.calls[0][1] as RequestInit).body as string)
    expect(payload.battery_id).toBe('generic_6s_lipo_16000mah')
    expect(payload.dataset_kind).toBe('synthetic_fixture')
    expect(payload.samples).toHaveLength(5)
    expect(payload.samples[0].current_a).toBe(10)
    expect(payload.samples[0].temperature_c).toBeNull()
    expect(payload.calibration_run_id).toBe('test_A')
    expect(payload.heldout_run_id).toBe('test_B')
    expect(payload.predeclared_max_abs_percentage_error_pct).toBe(5)
    fireEvent.change(screen.getByLabelText('Battery discharge CSV rows'), {
      target: { value: csv + '\n' },
    })
    expect(screen.queryByText('SYNTHETIC VERIFICATION ONLY')).toBeNull()
  })

  it('requires distinct run identifiers and fails closed before network request', async () => {
    const send = vi.fn()
    vi.stubGlobal('fetch', send)
    render(<BatteryEvidencePanel design={design} />)
    enterCompleteEvidence()
    fireEvent.change(screen.getByLabelText('Held-out run ID'), {
      target: { value: 'test_A' },
    })
    fireEvent.click(screen.getByRole('button', {
      name: /Evaluate held-out battery evidence/i,
    }))
    expect(await screen.findByRole('alert')).toBeDefined()
    expect(send).not.toHaveBeenCalled()
  })
})
