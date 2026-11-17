import { afterEach, describe, expect, it, rs } from '@rstest/core'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { HILEvidencePanel } from '../panels/HILEvidencePanel'

afterEach(() => { cleanup(); rs.unstubAllGlobals() })

describe('M23 HIL panel', () => {
  it('displays no physical validation even when numerical screen is compatible', async () => {
    const result = {
      status: 'HIL_CONTROLLER_PHYSICAL_VALIDATION_NOT_ESTABLISHED',
      matches_supplied_preregistration_digest: false,
      all_reported_holdouts_compatible_declared_samplewise_bounds: true,
      independent_physical_flight_validation_established: false,
      flight_safety_certified: false,
      blockers: ['Unverified firmware and sensor'],
      runs: [{
        dataset_id: 'synthetic_run', role: 'holdout', rows: 6,
        channel_errors: {
          altitude_m: {
            unit: 'm', mae: 0, max_absolute_residual: 0,
            declared_samplewise_upper_bound: .01,
            within_declared_samplewise_tolerance: true,
          },
        }, blockers: [],
      }],
    }
    const send = rs.fn().mockResolvedValue({ ok: true, json: async () => result })
    rs.stubGlobal('fetch', send)
    render(<HILEvidencePanel />)
    fireEvent.change(screen.getByLabelText('Controller HIL campaign JSON'), {
      target: { value: '{"frozen_protocol":{},"runs":[]}' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Audit controller HIL evidence' }))
    expect(await screen.findByText('Independent physical flight validation: no')).toBeDefined()
    expect(screen.getByText('Flight safety certification: no')).toBeDefined()
    expect(send.mock.calls[0][0]).toBe('/api/components/hil-evidence')
    fireEvent.change(screen.getByLabelText('Controller HIL campaign JSON'), {
      target: { value: '{}' },
    })
    expect(screen.queryByText('Independent physical flight validation: no')).toBeNull()
  })

  it('fails closed on empty JSON before any request', async () => {
    const send = rs.fn()
    rs.stubGlobal('fetch', send)
    render(<HILEvidencePanel />)
    fireEvent.click(screen.getByRole('button', { name: 'Audit controller HIL evidence' }))
    expect(await screen.findByRole('alert')).toBeDefined()
    expect(send).not.toHaveBeenCalled()
  })
})
