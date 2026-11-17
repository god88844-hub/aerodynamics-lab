import { afterEach, describe, expect, it, rs } from '@rstest/core'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { SourcePinnedHoldoutPanel } from '../panels/SourcePinnedHoldoutPanel'

afterEach(() => { cleanup(); rs.unstubAllGlobals() })

const campaign = {
  frozen_protocol_sha256: 'a'.repeat(64), runs: [{run_id: 'a'}, {run_id: 'b'}],
}
const response = {
  status: 'REPORTED_HOLDOUT_CONSISTENT_EXTERNAL_AUTHENTICATION_REQUIRED',
  source_bytes_integrity_verified_against_operator_supplied_digests: true,
  source_identity_or_preregistration_externally_authenticated: false,
  actual_independent_physical_validation_established: false,
  decision_equivalent_to_physical_testing: false,
  blockers: [],
  runs: [{run_id: 'a', sample_count: 6, robust_coverage_fraction: 1,
    worst_conservative_absolute_residual: .2, error_gate_passed: true, interval_gate_passed: true}],
}

describe('M27.3 paired original holdout source audit', () => {
  it('shows numerical consistency without independent physical certification', async () => {
    const send = rs.fn().mockResolvedValue({ok: true, json: async () => response})
    rs.stubGlobal('fetch', send)
    render(<SourcePinnedHoldoutPanel />)
    fireEvent.change(screen.getByLabelText('Original source holdout JSON'), {
      target: {value: JSON.stringify(campaign)},
    })
    fireEvent.click(screen.getByRole('button', {name: 'Audit original source holdouts'}))
    expect(await screen.findByText('Actual independent physical validation: no')).toBeDefined()
    expect(screen.getByText('Physical-test decision equivalence: no')).toBeDefined()
    expect(send.mock.calls[0][0]).toBe('/api/components/source-pinned-holdout-audit')
    expect(JSON.parse((send.mock.calls[0][1] as RequestInit).body as string)).toEqual(campaign)
    fireEvent.change(screen.getByLabelText('Original source holdout JSON'), {
      target: {value: '{"runs":[]}'},
    })
    expect(screen.queryByText('Actual independent physical validation: no')).toBeNull()
  })

  it('rejects absent frozen protocol and source inputs before server call', async () => {
    const send = rs.fn()
    rs.stubGlobal('fetch', send)
    render(<SourcePinnedHoldoutPanel />)
    fireEvent.click(screen.getByRole('button', {name: 'Audit original source holdouts'}))
    expect(await screen.findByRole('alert')).toBeDefined()
    expect(send).not.toHaveBeenCalled()
  })
})
