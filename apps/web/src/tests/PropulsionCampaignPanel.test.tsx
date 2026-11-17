import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { PropulsionCampaignPanel } from '../panels/PropulsionCampaignPanel'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

const body = {
  motor_id: 'tmotor_p80iii_kv100', propeller_id: 'tmotor_g30x105_cf',
  frozen_protocol: { protocol_id: 'synthetic_bench' },
  runs: [{ dataset_id: 'fake_test' }],
}
const result = {
  status: 'PHYSICAL_PROPULSION_VALIDATION_NOT_ESTABLISHED',
  motor_id: 'tmotor_p80iii_kv100', propeller_id: 'tmotor_g30x105_cf',
  run_count: 1, holdout_count: 1,
  matches_supplied_frozen_protocol_digest: false,
  manufacturer_reference_is_calibration_not_validation: true,
  all_holdout_samples_compatible_declared_bounds_only: false,
  independent_static_propulsion_validation_established: false,
  flight_readiness_established: false,
  blockers: ['Independent instrument calibration and actual test missing'],
  runs: [{
    dataset_id: 'fake_test', role: 'holdout',
    original_point_count: 6, scored_count: 4,
    samplewise_compatible: false,
    blockers: ['Hardware mismatch'],
    unsupported: [{ index: 0, reason: 'outside RPM envelope' }],
  }],
}

describe('M22 static propulsion physical evidence panel', () => {
  it('submits predeclared sources and refuses unsupported flight claims', async () => {
    const send = vi.fn().mockResolvedValue({ ok: true, json: async () => result })
    vi.stubGlobal('fetch', send)
    render(<PropulsionCampaignPanel />)
    fireEvent.change(screen.getByLabelText('Static propulsion campaign JSON'), {
      target: { value: JSON.stringify(body) },
    })
    fireEvent.click(screen.getByRole('button', { name: /Audit static propulsion campaign/i }))
    expect(await screen.findByText('PHYSICAL PROPULSION VALIDATION NOT ESTABLISHED')).toBeDefined()
    expect(screen.getByText('Static physical validation independently established: no')).toBeDefined()
    expect(screen.getByText('Aircraft flight readiness: no')).toBeDefined()
    expect(screen.getByText('Manufacturer calibration points and a different motor are not independent validation.')).toBeDefined()
    expect(send.mock.calls[0][0]).toBe('/api/components/propulsion-campaign-audit')
    expect(JSON.parse((send.mock.calls[0][1] as RequestInit).body as string)).toEqual(body)
    fireEvent.change(screen.getByLabelText('Static propulsion campaign JSON'), {
      target: { value: JSON.stringify({ ...body, runs: [] }) },
    })
    expect(screen.queryByText('PHYSICAL PROPULSION VALIDATION NOT ESTABLISHED')).toBeNull()
  })

  it('rejects malformed source JSON without sending', async () => {
    const send = vi.fn()
    vi.stubGlobal('fetch', send)
    render(<PropulsionCampaignPanel />)
    fireEvent.click(screen.getByRole('button', { name: /Audit static propulsion campaign/i }))
    expect(await screen.findByRole('alert')).toBeDefined()
    expect(send).not.toHaveBeenCalled()
  })
})
