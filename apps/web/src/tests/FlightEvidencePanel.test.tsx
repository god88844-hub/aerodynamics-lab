import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { FlightEvidencePanel } from '../panels/FlightEvidencePanel'
import type { SimulationResult } from '../types/api'

const result: SimulationResult = {
  simulation_id: 42, design_id: 11, scenario: 'flight (M4 takeoff-hover-land, powertrain in the loop)',
  status: 'completed',
}
const csv = ['0,0,,24,5', '2,4,,23.8,5', '4,8,,23.6,5',
  '6,12,,23.4,5', '8,16,,23.2,5', '10,20,,23.0,5'].join('\n')
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

function completeForm() {
  fireEvent.change(screen.getByLabelText('Flight evidence type'), {
    target: { value: 'synthetic_fixture' },
  })
  for (const [name, value] of [
    ['Vehicle ID', 'fixture_quad'], ['Flight log ID', 'independent-B'],
    ['Flight log source', 'synthetic mathematical fixture'],
    ['Declared measurement-to-simulation time offset (s)', '0'],
    ['Altitude error limit (m)', '.2'], ['Bus-voltage error limit (V)', '.1'],
    ['Pack-current error limit (A)', '.5'],
  ]) {
    fireEvent.change(screen.getByLabelText(name), { target: { value } })
  }
  fireEvent.change(screen.getByLabelText('Flight log CSV'), { target: { value: csv } })
}

describe('M13 Flight Evidence Lab UI', () => {
  it('submits only operator supplied data to a particular saved flight run', async () => {
    const response = {
      simulation_id: 42, verdict: 'SYNTHETIC_VERIFICATION_ONLY',
      stored_prediction_sha256: 'abcd', simulation_modified: false,
      coverage: { mission_fraction: 1, adequate: true,
        interpolation_supported: true, max_interpolation_spacing_s: .05 },
      channels: {
        altitude_m: { unit: 'm', metrics: { count: 6, mae: .1, rmse: .1,
          bias: 0, max_absolute_error: .2, predeclared_max_absolute_error: .2,
          meets_predeclared_tolerance: true } },
      },
    }
    const send = vi.fn().mockResolvedValue({ ok: true, json: async () => response })
    vi.stubGlobal('fetch', send)
    render(<FlightEvidencePanel result={result} />)
    completeForm()
    fireEvent.click(screen.getByRole('button', { name: /Compare held-out flight telemetry/ }))
    expect(await screen.findByText('SYNTHETIC VERIFICATION ONLY')).toBeDefined()
    expect(screen.getByText('Mission coverage: 100.0%')).toBeDefined()
    expect(send).toHaveBeenCalledTimes(1)
    expect(send.mock.calls[0][0]).toBe('/api/simulations/42/flight-evidence')
    const body = JSON.parse((send.mock.calls[0][1] as RequestInit).body as string)
    expect(body.dataset_kind).toBe('synthetic_fixture')
    expect(body.observations).toHaveLength(6)
    expect(body.observations[0].vertical_speed_m_s).toBeNull()
    expect(body.tolerances).toEqual({ altitude_m: .2, bus_voltage_v: .1, battery_current_a: .5 })
    fireEvent.change(screen.getByLabelText('Flight log CSV'), { target: { value: csv + '\n' } })
    expect(screen.queryByText('SYNTHETIC VERIFICATION ONLY')).toBeNull()
  })

  it('rejects missing predeclared limits without a network call', async () => {
    const send = vi.fn()
    vi.stubGlobal('fetch', send)
    render(<FlightEvidencePanel result={result} />)
    completeForm()
    fireEvent.change(screen.getByLabelText('Altitude error limit (m)'), { target: { value: '' } })
    fireEvent.click(screen.getByRole('button', { name: /Compare held-out flight telemetry/ }))
    expect(await screen.findByRole('alert')).toBeDefined()
    expect(send).not.toHaveBeenCalled()
  })

  it('requires an actually saved, completed flight simulation', () => {
    render(<FlightEvidencePanel result={{ scenario: 'hover-static', status: 'completed' }} />)
    expect(screen.queryByRole('button', { name: /Compare held-out flight telemetry/ })).toBeNull()
    expect(screen.getByText(/Complete a Flight simulation first/)).toBeDefined()
  })
})
