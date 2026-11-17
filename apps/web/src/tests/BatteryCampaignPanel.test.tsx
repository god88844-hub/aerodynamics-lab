import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { BatteryCampaignPanel } from '../panels/BatteryCampaignPanel'
import type { DroneDesign } from '../types/api'

const design: DroneDesign = {
  schema_version: '0.1',
  name: 'synthetic_battery_campaign_ui',
  rotor_torque_per_thrust_n_m_per_n: 0,
  parts: [{ name: 'frame', mass_kg: 1, position_m: [0, 0, 0] }],
  rotors: [{ position_m: [0.1, 0.1, 0], spin_direction: 1 }],
  powertrain: {
    motor_id: 'motor', propeller_id: 'prop', esc_id: 'esc',
    battery_id: 'generic_6s_lipo_16000mah',
  },
}
const fakePayload = { frozen_protocol: { protocol_id: 'fake_heldout' }, runs: [{ evidence: {} }] }
const fakeResult = {
  battery_model_id: 'generic_6s_lipo_16000mah',
  campaign_status: 'PHYSICAL_BATTERY_VALIDATION_NOT_ESTABLISHED',
  partition_status: 'SYNTHETIC_OR_MIXED_DATASET_NO_PHYSICAL_VALIDATION',
  source_count: 1, holdout_count: 1,
  claimed_voltage_compatibility_only_samplewise: false,
  blockers: ['No independently authenticated battery hardware evidence'],
  runs: [{
    dataset_id: 'synthetic_fixture',
    partition_role: 'holdout',
    blockers: ['Synthetic data cannot physically validate the model'],
    conditional_voltage_replay: {
      status: 'SAMPLEWISE_COMPATIBLE_DECLARED_BOUNDS_ONLY',
      voltage_mae_v: 0.03, voltage_max_abs_error_v: 0.05,
      measured_delivered_energy_wh: 2, highest_c_rate: 1,
    },
  }],
  decision_equivalent_to_physical_testing: false,
  independently_authenticated_physical_pack_test: false,
}

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('M21 battery campaign review', () => {
  it('reports uncertainty and physical blockers without a false approval', async () => {
    const send = vi.fn().mockResolvedValue({ ok: true, json: async () => fakeResult })
    vi.stubGlobal('fetch', send)
    render(<BatteryCampaignPanel design={design} />)
    fireEvent.change(screen.getByLabelText('Battery campaign JSON'), {
      target: { value: JSON.stringify(fakePayload) },
    })
    fireEvent.click(screen.getByRole('button', { name: /Audit held-out battery campaign/i }))
    expect(await screen.findByText('PHYSICAL BATTERY VALIDATION NOT ESTABLISHED')).toBeDefined()
    expect(screen.getByText('Decision-equivalent physical evidence: no')).toBeDefined()
    expect(screen.getByText('Measured delivered energy: 2.00 Wh')).toBeDefined()
    expect(send).toHaveBeenCalledTimes(1)
    expect(send.mock.calls[0][0]).toBe('/api/components/battery-campaign-audit')
    const body = JSON.parse((send.mock.calls[0][1] as RequestInit).body as string)
    expect(body.battery_model_id).toBe('generic_6s_lipo_16000mah')
    expect(body.runs).toHaveLength(1)
    fireEvent.change(screen.getByLabelText('Battery campaign JSON'), {
      target: { value: JSON.stringify({ ...fakePayload, runs: [] }) },
    })
    expect(screen.queryByText('PHYSICAL BATTERY VALIDATION NOT ESTABLISHED')).toBeNull()
  })

  it('prevents requests for absent battery or mismatched model', async () => {
    const send = vi.fn()
    vi.stubGlobal('fetch', send)
    const { rerender } = render(<BatteryCampaignPanel design={design} />)
    fireEvent.change(screen.getByLabelText('Battery campaign JSON'), {
      target: { value: JSON.stringify({ ...fakePayload, battery_model_id: 'wrong_pack' }) },
    })
    fireEvent.click(screen.getByRole('button', { name: /Audit held-out battery campaign/i }))
    expect(await screen.findByRole('alert')).toBeDefined()
    expect(send).not.toHaveBeenCalled()
    rerender(<BatteryCampaignPanel design={{ ...design, powertrain: undefined }} />)
    expect(screen.getByRole('button', { name: /Audit held-out battery campaign/i })
      .hasAttribute('disabled')).toBe(true)
  })
})
