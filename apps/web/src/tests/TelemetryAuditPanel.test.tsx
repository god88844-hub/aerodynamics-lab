import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { TelemetryAuditPanel } from '../panels/TelemetryAuditPanel'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

const manifest = {
  schema_version: '1.0',
  dataset_id: 'fixture_alpha',
  dataset_kind: 'synthetic_fixture',
  partition_role: 'unassigned',
  experiment_id: 'exp-1',
  recording_id: 'rec-1',
  vehicle_id: 'vehicle-1',
  battery_id: 'battery-1',
  source_reference: 'synthetic test only',
  license_or_permission: 'self-generated',
  filename: 'trace.csv',
  raw_sha256: '0'.repeat(64),
  expected_samples: 6,
  predeclared_max_sample_gap_s: 1,
  columns: ['t_s', 'terminal_voltage_v', 'current_a'],
}
const csv = 't_s,terminal_voltage_v,current_a\n' +
  Array.from({ length: 6 }, (_, i) => `${i},12,2`).join('\n') + '\n'

describe('M19 telemetry provenance audit panel', () => {
  it('submits original manifest and CSV and reports no physical validation', async () => {
    const report = {
      datasets: [{
        dataset_id: 'fixture_alpha', rows: 6, status: 'SYNTHETIC_VERIFICATION_ONLY',
        quality: { sampling_interval_within_predeclared_bound: true, max_gap_s: 1 },
        observations: {
          duration_s: 5, trapezoidal_reported_charge_ah: .0027778,
          trapezoidal_reported_energy_wh: .033333,
        },
      }],
      partition: {
        status: 'NO_COMPLETE_CALIBRATION_HOLDOUT_SPLIT',
        cross_partition_collisions: [],
      },
      near_real_world_simulation_accuracy_established: false,
    }
    const send = vi.fn().mockResolvedValue({ ok: true, json: async () => report })
    vi.stubGlobal('fetch', send)
    render(<TelemetryAuditPanel />)
    fireEvent.change(screen.getByLabelText('Telemetry manifest JSON'), {
      target: { value: JSON.stringify(manifest) },
    })
    fireEvent.change(screen.getByLabelText('Original telemetry CSV'), {
      target: { value: csv },
    })
    fireEvent.click(screen.getByRole('button', {
      name: /Audit telemetry without changing models/,
    }))
    expect(await screen.findByText(/fixture_alpha: SYNTHETIC VERIFICATION ONLY/)).toBeDefined()
    expect(screen.getByText(/Energy from reported V×I/)).toBeDefined()
    expect(send).toHaveBeenCalledTimes(1)
    expect(send.mock.calls[0][0]).toBe('/api/components/telemetry-audit')
    const payload = JSON.parse((send.mock.calls[0][1] as RequestInit).body as string)
    expect(payload.datasets[0].manifest.dataset_kind).toBe('synthetic_fixture')
    expect(payload.datasets[0].csv_text).toBe(csv)
    fireEvent.change(screen.getByLabelText('Original telemetry CSV'), {
      target: { value: csv + '\n' },
    })
    expect(screen.queryByText(/fixture_alpha: SYNTHETIC VERIFICATION ONLY/)).toBeNull()
  })

  it('requires source material and does not send a request for missing manifest', async () => {
    const send = vi.fn()
    vi.stubGlobal('fetch', send)
    render(<TelemetryAuditPanel />)
    fireEvent.click(screen.getByRole('button', {
      name: /Audit telemetry without changing models/,
    }))
    expect(await screen.findByRole('alert')).toBeDefined()
    expect(send).not.toHaveBeenCalled()
  })
})
