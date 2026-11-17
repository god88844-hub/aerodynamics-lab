import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'

interface BenchReport {
  verdict: string
  source: {
    paper: string
    url: string
    source_test_motor: string
    source_test_mount: string
  }
  reference: {
    motor_id: string
    same_propeller_geometry: boolean
    same_motor: boolean
    same_mounting_configuration_verified: boolean
  }
  data_quality: {
    published_measurement_count: number
    reported_power_inconsistency_count: number
    reported_power_anomalies: Array<{
      case: number
      source_reported_power_w: number
      voltage_times_current_w: number
    }>
  }
  comparison: {
    in_envelope_count: number
    out_of_envelope_count: number
    mean_absolute_relative_difference_pct_descriptive_only: number | null
    rows: Array<{
      case: number
      rpm: number
      force_n: number
      aeroforge_reference_thrust_n: number | null
      relative_difference_pct_vs_reference: number | null
    }>
  }
  independent_physical_validation_of_aeroforge_reference: boolean
  physical_equivalence_established: boolean
}

/** Published static measurements with incompatible motor+mount: trend only. */
export function G30PublicBenchPanel() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['g30-third-party-installation-benchmark'],
    queryFn: () => api.get<BenchReport>('/components/public-g30-benchmark'),
    staleTime: 5 * 60 * 1000,
    retry: false,
  })
  return (
    <section aria-label="G30 real propeller bench comparison" className="space-y-2 p-3">
      <h3 className="text-[11px] font-semibold uppercase tracking-wider text-cyan-500">
        G30 propeller physical benchmark
      </h3>
      {isLoading && <p className="text-xs">Auditing independent propeller data…</p>}
      {isError && <p role="alert" className="text-xs text-rose-400">
        External G30 benchmark unavailable or source integrity check failed
      </p>}
      {data && (
        <div className="space-y-1 text-xs">
          <p className="font-semibold text-amber-300">{data.verdict.replaceAll('_', ' ')}</p>
          <p>Published operating points: {data.data_quality.published_measurement_count}</p>
          <p>Inside existing P80 rpm envelope: {data.comparison.in_envelope_count}</p>
          <p>Different physical motor: {data.source.source_test_motor}</p>
          <p>Source power-data anomalies: {data.data_quality.reported_power_inconsistency_count}</p>
          {data.data_quality.reported_power_anomalies.map((a) => (
            <p key={a.case} className="text-[10px] text-amber-400">
              Published row {a.case}: reported {a.source_reported_power_w} W,
              but V×I = {a.voltage_times_current_w.toFixed(2)} W; source not corrected
            </p>
          ))}
          <details>
            <summary className="cursor-pointer">Observed vs reference thrust (not validated)</summary>
            <div className="space-y-1 pt-1 font-mono text-[10px]">
              {data.comparison.rows.filter((row) => row.aeroforge_reference_thrust_n !== null)
                .map((row) => (
                  <p key={row.case}>
                    {row.rpm} rpm: source {row.force_n.toFixed(2)} N;
                    P80 reference {row.aeroforge_reference_thrust_n!.toFixed(2)} N;
                    relative difference {row.relative_difference_pct_vs_reference!.toFixed(2)}%
                  </p>
                ))}
            </div>
          </details>
          <a href={data.source.url} target="_blank" rel="noreferrer"
            className="inline-block text-cyan-400 underline">
            Original peer-reviewed experimental measurements
          </a>
          <p className="text-[10px] text-amber-400">
            Same G30 propeller, but different motor and nearby mounting plate.
            Residuals are descriptive only; no fitted correction, propulsion
            validation, predicted mission success, or physical equivalence.
          </p>
        </div>
      )}
    </section>
  )
}
