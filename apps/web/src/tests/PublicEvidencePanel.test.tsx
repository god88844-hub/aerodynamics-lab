import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { PublicEvidencePanel } from '../panels/PublicEvidencePanel'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

const response = {
  registry: {
    datasets: [
      {
        id: 'quadplane_px4_2022',
        name: 'Actual PX4 recorded VTOL battery trace',
        url: 'https://github.com/AdamDony/quadplane-px4-flight-data',
        source_status: 'CHECKSUM_VERIFIED_COPY_INCLUDED',
        ingestion_status: 'BATT_CSV_AUDIT_IMPLEMENTED',
        aircraft_model_match: false,
      },
    ],
  },
  quadplane_battery_audit: {
    benchmark_status: 'PUBLIC_PHYSICAL_OBSERVATIONS_AUDITED_NOT_MODEL_VALIDATION',
    source: {
      reported_physical_log: true,
      source_url: 'https://github.com/AdamDony/quadplane-px4-flight-data',
      license: 'CC BY 4.0',
      instrument_and_identity_authenticated_by_aeroforge: false,
    },
    quality: {
      rows_verified: 1442, per_row_timestamps_present: false,
      synchronized_with_aeroforge_simulation: false,
      hardware_model_match_verified: false,
    },
    observed: {
      voltage_range_v: [21.646976, 25.309713],
      current_range_a: [0.26357, 72.45196],
      difference_in_reported_discharge_counter_mah: 2640.931427,
      peak_sampled_pack_electrical_power_w: 1596.971943,
      power_time_integral_wh: null,
    },
    validated_flight_prediction_error: null,
    near_real_world_equivalence_established: false,
  },
  model_physically_validated_by_these_public_sources: false,
}

function renderWithClient() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}><PublicEvidencePanel /></QueryClientProvider>,
  )
}

describe('M16 public physical evidence panel', () => {
  it('reports physical measurement statistics but no aircraft validation', async () => {
    const send = vi.fn().mockResolvedValue({ ok: true, json: async () => response })
    vi.stubGlobal('fetch', send)
    renderWithClient()
    expect(await screen.findByText('Recorded third-party battery samples: 1442')).toBeDefined()
    expect(screen.getByText('Physical model equivalence established: no')).toBeDefined()
    expect(screen.getByText('Per-row timestamps: no')).toBeDefined()
    expect(screen.getByText(/PUBLIC PHYSICAL OBSERVATIONS AUDITED NOT MODEL VALIDATION/)).toBeDefined()
    expect(send.mock.calls[0][0]).toBe('/api/components/public-evidence')
    expect(send.mock.calls[0][1]?.method).toBeUndefined()
  })

  it('fails closed when the original physical dataset audit cannot be loaded', async () => {
    const send = vi.fn().mockResolvedValue({
      ok: false, status: 503, json: async () => ({ detail: 'integrity mismatch' }),
    })
    vi.stubGlobal('fetch', send)
    renderWithClient()
    expect(await screen.findByRole('alert')).toBeDefined()
    expect(screen.queryByText('Physical model equivalence established: yes')).toBeNull()
  })
})
