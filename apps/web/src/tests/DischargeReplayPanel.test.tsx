import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { DischargeReplayPanel } from '../panels/DischargeReplayPanel'
import type { DroneDesign } from '../types/api'

const design: DroneDesign = {
  schema_version: '0.1',
  name: 'synthetic_discharge_ui',
  rotor_torque_per_thrust_n_m_per_n: 0,
  parts: [{ name: 'frame', mass_kg: 1, position_m: [0, 0, 0] }],
  rotors: [{ position_m: [0.1, 0.1, 0], spin_direction: 1 }],
  powertrain: {
    motor_id: 'motor', propeller_id: 'prop', esc_id: 'esc',
    battery_id: 'generic_6s_lipo_16000mah',
  },
}

const csv = [
  '0,5,24,25', '60,5,23.8,25', '120,5,23.6,',
  '180,5,23.4,25', '240,5,23.2,25', '300,5,23.0,25',
].join('\n')

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

function fill() {
  fireEvent.change(screen.getByLabelText('Discharge evidence type'), {
    target: { value: 'synthetic_fixture' },
  })
  for (const [name, value] of [
    ['Battery serial or ID', 'synthetic-pack'],
    ['Discharge run ID', 'heldout-B'],
    ['Discharge data source', 'analytic synthetic verification'],
    ['Initial SOC percent', '100'],
    ['Predeclared maximum voltage error V', '.2'],
    ['Predeclared maximum warning-time error percent', '5'],
    ['Predeclared maximum sample gap seconds', '65'],
  ]) {
    fireEvent.change(screen.getByLabelText(name), { target: { value } })
  }
  fireEvent.change(screen.getByLabelText('Discharge trace CSV'), { target: { value: csv } })
}

describe('M15 discharge replay panel', () => {
  it('submits exact declared measurement trace and never promotes a pack model', async () => {
    const response = {
      verdict: 'SYNTHETIC_VERIFICATION_ONLY',
      accounting: {
        duration_s: 300, charge_consumed_ah: .417,
        measured_energy_delivered_wh: 9.75, modeled_final_soc_pct: 97.4,
        maximum_c_rate: .313, within_predeclared_sampling_gap: true,
      },
      prediction: {
        voltage_mae_v: .02, voltage_rmse_v: .03, voltage_max_abs_error_v: .05,
        voltage_tolerance_met: true, measured_warning_crossing_s: null,
        predicted_warning_crossing_s: null,
        endpoint_time_error_pct: null, endpoint_tolerance_met: false,
      },
    }
    const send = vi.fn().mockResolvedValue({ ok: true, json: async () => response })
    vi.stubGlobal('fetch', send)
    render(<DischargeReplayPanel design={design} />)
    fill()
    fireEvent.click(screen.getByRole('button', { name: /Replay held-out battery discharge/i }))
    expect(await screen.findByText('SYNTHETIC VERIFICATION ONLY')).toBeDefined()
    expect(screen.getByText('Measured delivered energy: 9.75 Wh')).toBeDefined()
    expect(send).toHaveBeenCalledTimes(1)
    expect(send.mock.calls[0][0]).toBe('/api/components/discharge-replay')
    const body = JSON.parse((send.mock.calls[0][1] as RequestInit).body as string)
    expect(body.dataset_kind).toBe('synthetic_fixture')
    expect(body.samples).toHaveLength(6)
    expect(body.samples[2].temperature_c).toBeNull()
    expect(body.predeclared_max_sample_gap_s).toBe(65)
    expect(body.model_unused_for_calibration).toBe(false)
    fireEvent.change(screen.getByLabelText('Discharge trace CSV'), { target: { value: csv + '\n' } })
    expect(screen.queryByText('SYNTHETIC VERIFICATION ONLY')).toBeNull()
  })

  it('refuses incomplete predeclared tolerance without sending network request', async () => {
    const send = vi.fn()
    vi.stubGlobal('fetch', send)
    render(<DischargeReplayPanel design={design} />)
    fill()
    fireEvent.change(screen.getByLabelText('Predeclared maximum voltage error V'),
      { target: { value: '' } })
    fireEvent.click(screen.getByRole('button', { name: /Replay held-out battery discharge/i }))
    expect(await screen.findByRole('alert')).toBeDefined()
    expect(send).not.toHaveBeenCalled()
  })

  it('blocks replay if design has no battery reference', () => {
    render(<DischargeReplayPanel design={{ ...design, powertrain: undefined }} />)
    expect(screen.getByRole('button', { name: /Replay held-out battery discharge/i })
      .hasAttribute('disabled')).toBe(true)
  })
})
