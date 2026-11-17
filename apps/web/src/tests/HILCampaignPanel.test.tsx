import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { HILCampaignPanel } from '../panels/HILCampaignPanel'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

const response = {
  status: 'HIL_PHYSICAL_VALIDATION_NOT_ESTABLISHED',
  matches_supplied_frozen_digest: false,
  run_count: 1, holdout_count: 1,
  reported_samplewise_tracking_compatible_only: false,
  simulation_prediction_error_measured: false,
  independent_controller_hardware_validation: false,
  aircraft_flight_readiness: false,
  blockers: ['Independent simulator time-aligned predictions missing'],
  runs: [{
    dataset_id: 'synthetic_hil', partition_role: 'holdout',
    count: 6, maximum_gap_s: .01,
    max_roll_or_pitch_tracking_error_deg: .1,
    tracking_rmse_deg: .1,
    saturation_count: 1, samplewise_tracking_upper_bound_deg: null,
    blockers: ['Actuator saturation'],
  }],
}
const body = { frozen_protocol: { protocol_id: 'synthetic' }, recordings: [{}] }

describe('M23 control-loop source evidence panel', () => {
  it('shows reported tracking errors but does not claim physical flight prediction', async () => {
    const send = vi.fn().mockResolvedValue({ ok: true, json: async () => response })
    vi.stubGlobal('fetch', send)
    render(<HILCampaignPanel />)
    fireEvent.change(screen.getByLabelText('HIL controller campaign JSON'), {
      target: { value: JSON.stringify(body) },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Audit controller test evidence' }))
    expect(await screen.findByText('HIL PHYSICAL VALIDATION NOT ESTABLISHED')).toBeDefined()
    expect(screen.getByText('Flight-model prediction error measured: no')).toBeDefined()
    expect(screen.getByText('Flight readiness established: no')).toBeDefined()
    expect(screen.getByText('Saturation flags: 1')).toBeDefined()
    expect(send.mock.calls[0][0]).toBe('/api/components/hil-campaign-audit')
    expect(JSON.parse((send.mock.calls[0][1] as RequestInit).body as string)).toEqual(body)
    fireEvent.change(screen.getByLabelText('HIL controller campaign JSON'), {
      target: { value: JSON.stringify({ ...body, recordings: [] }) },
    })
    expect(screen.queryByText('HIL PHYSICAL VALIDATION NOT ESTABLISHED')).toBeNull()
  })

  it('blocks malformed campaign before calling the API', async () => {
    const send = vi.fn()
    vi.stubGlobal('fetch', send)
    render(<HILCampaignPanel />)
    fireEvent.click(screen.getByRole('button', { name: 'Audit controller test evidence' }))
    expect(await screen.findByRole('alert')).toBeDefined()
    expect(send).not.toHaveBeenCalled()
  })
})
