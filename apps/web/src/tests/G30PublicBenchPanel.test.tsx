import { afterEach, describe, expect, it, rs } from '@rstest/core'
import { cleanup, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { G30PublicBenchPanel } from '../panels/G30PublicBenchPanel'

afterEach(() => { cleanup(); rs.unstubAllGlobals() })
function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}>
    <G30PublicBenchPanel />
  </QueryClientProvider>)
}
const report = {
  verdict: 'REAL_EXPERIMENTAL_PROP_DATA_BUT_INSTALLATION_AND_MOTOR_MISMATCH',
  source: {
    paper: 'Measured G30 install effects',
    url: 'https://www.mdpi.com/2227-7080/13/12/542',
    source_test_motor: 'T-MOTOR MN1010 KV135',
    source_test_mount: '350 x 250 mm plate',
  },
  reference: {
    motor_id: 'tmotor_p80iii_kv100',
    same_propeller_geometry: true,
    same_motor: false,
    same_mounting_configuration_verified: false,
  },
  data_quality: {
    published_measurement_count: 9, reported_power_inconsistency_count: 1,
    reported_power_anomalies: [{
      case: 2, source_reported_power_w: 3234, voltage_times_current_w: 32.34,
    }],
  },
  comparison: {
    in_envelope_count: 3, out_of_envelope_count: 6,
    mean_absolute_relative_difference_pct_descriptive_only: 8,
    rows: [
      { case: 7, rpm: 1900, force_n: 37.96,
        aeroforge_reference_thrust_n: 34.7, relative_difference_pct_vs_reference: 9.3 },
    ],
  },
  independent_physical_validation_of_aeroforge_reference: false,
  physical_equivalence_established: false,
}

describe('M17 external G30 test-bench display', () => {
  it('preserves published anomalous reading and visible model mismatch', async () => {
    const send = rs.fn().mockResolvedValue({ ok: true, json: async () => report })
    rs.stubGlobal('fetch', send)
    mount()
    expect(await screen.findByText('Published operating points: 9')).toBeDefined()
    expect(screen.getByText(/REAL EXPERIMENTAL PROP DATA BUT INSTALLATION AND MOTOR MISMATCH/)).toBeDefined()
    expect(screen.getByText(/reported 3234 W/)).toBeDefined()
    expect(screen.getByText(/Different physical motor: T-MOTOR MN1010 KV135/)).toBeDefined()
    expect(send.mock.calls[0][0]).toBe('/api/components/public-g30-benchmark')
  })
  it('refuses physical conclusions if the source audit fails', async () => {
    rs.stubGlobal('fetch', rs.fn().mockResolvedValue({
      ok: false, status: 503, json: async () => ({ detail: 'source mismatch' }),
    }))
    mount()
    expect(await screen.findByRole('alert')).toBeDefined()
    expect(screen.queryByText('Published operating points: 9')).toBeNull()
  })
})
