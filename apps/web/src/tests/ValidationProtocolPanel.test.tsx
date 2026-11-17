import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { ValidationProtocolPanel } from '../panels/ValidationProtocolPanel'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

const minimal = { schema_version: '1.0', protocol_id: 'synthetic_protocol' }
const report = {
  protocol_id: 'synthetic_protocol',
  canonical_protocol_sha256: 'a'.repeat(64),
  matches_supplied_frozen_sha256: false,
  readiness_status: 'PREREGISTRATION_GAPS',
  blockers: ['No independently archived pre-commit protocol hash supplied'],
  independent_physical_accuracy_demonstrated: false,
  decision_equivalent_to_physical_testing: false,
  independently_approved: false,
}

describe('M20 physical validation preregistration panel', () => {
  it('submits JSON and reports evidence blockers, not aircraft validation', async () => {
    const send = vi.fn().mockResolvedValue({ ok: true, json: async () => report })
    vi.stubGlobal('fetch', send)
    render(<ValidationProtocolPanel />)
    fireEvent.change(screen.getByLabelText('Validation protocol JSON'), {
      target: { value: JSON.stringify(minimal) },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Audit physical validation protocol' }))
    expect(await screen.findByText('Blocking gaps: 1')).toBeDefined()
    expect(screen.getByText('Independent physical accuracy demonstrated: no')).toBeDefined()
    expect(screen.getByText(/No independently archived pre-commit/)).toBeDefined()
    expect(send.mock.calls[0][0]).toBe('/api/components/validation-protocol-audit')
    const body = JSON.parse((send.mock.calls[0][1] as RequestInit).body as string)
    expect(body.protocol.protocol_id).toBe('synthetic_protocol')
    expect(body.expected_frozen_sha256).toBeNull()
    expect(body.imported_manifests).toEqual([])
    fireEvent.change(screen.getByLabelText('Frozen protocol SHA-256'), {
      target: { value: 'b'.repeat(64) },
    })
    expect(screen.queryByText('Blocking gaps: 1')).toBeNull()
  })

  it('refuses missing protocol or invalid hash without sending anything', async () => {
    const send = vi.fn()
    vi.stubGlobal('fetch', send)
    render(<ValidationProtocolPanel />)
    fireEvent.click(screen.getByRole('button', { name: 'Audit physical validation protocol' }))
    expect(await screen.findByRole('alert')).toBeDefined()
    fireEvent.change(screen.getByLabelText('Validation protocol JSON'), {
      target: { value: JSON.stringify(minimal) },
    })
    fireEvent.change(screen.getByLabelText('Frozen protocol SHA-256'), {
      target: { value: 'bad' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Audit physical validation protocol' }))
    expect(await screen.findByRole('alert')).toBeDefined()
    expect(send).not.toHaveBeenCalled()
  })
})
