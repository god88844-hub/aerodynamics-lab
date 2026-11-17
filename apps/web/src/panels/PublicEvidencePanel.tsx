import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'

interface PhysicalAudit {
  benchmark_status: string
  source: {
    reported_physical_log: boolean
    source_url: string
    license: string
    instrument_and_identity_authenticated_by_aeroforge: boolean
  }
  quality: {
    rows_verified: number
    per_row_timestamps_present: boolean
    synchronized_with_aeroforge_simulation: boolean
    hardware_model_match_verified: boolean
  }
  observed: {
    voltage_range_v: [number, number]
    current_range_a: [number, number]
    difference_in_reported_discharge_counter_mah: number
    peak_sampled_pack_electrical_power_w: number
    power_time_integral_wh: number | null
  }
  validated_flight_prediction_error: number | null
  near_real_world_equivalence_established: boolean
}
interface SourceEntry {
  id: string
  name: string
  url: string
  source_status: string
  ingestion_status: string
  aircraft_model_match: boolean
}
interface PublicEvidenceReport {
  registry: { datasets: SourceEntry[] }
  quadplane_battery_audit: PhysicalAudit
  model_physically_validated_by_these_public_sources: boolean
}

/** Read-only reporting of physically recorded third-party evidence and model gaps. */
export function PublicEvidencePanel() {
  const query = useQuery({
    queryKey: ['independent-public-evidence-v16'],
    queryFn: () => api.get<PublicEvidenceReport>('/components/public-evidence'),
    staleTime: 5 * 60 * 1000,
    retry: false,
  })
  const report = query.data
  const physical = report?.quadplane_battery_audit

  return (
    <section aria-label="Independent physical evidence audit" className="space-y-2 p-3">
      <h3 className="text-[11px] font-semibold uppercase tracking-wider text-cyan-500">
        Independent physical evidence
      </h3>
      <p className="text-[10px] text-slate-400">
        Third-party recorded flight data and model compatibility checks.
        Source integrity does not prove model prediction accuracy.
      </p>
      {query.isLoading && <p className="text-xs">Checking physical evidence…</p>}
      {query.isError && <p role="alert" className="text-xs text-rose-400">
        Physical evidence audit unavailable; do not infer validation.
      </p>}
      {physical && report && (
        <div className="space-y-1 text-xs">
          <p className="font-semibold text-amber-300">
            {physical.benchmark_status.replaceAll('_', ' ')}
          </p>
          <p>Recorded third-party battery samples: {physical.quality.rows_verified}</p>
          <p>Pack voltage range: {physical.observed.voltage_range_v[0].toFixed(2)}–
            {physical.observed.voltage_range_v[1].toFixed(2)} V</p>
          <p>Current range: {physical.observed.current_range_a[0].toFixed(2)}–
            {physical.observed.current_range_a[1].toFixed(2)} A</p>
          <p>Highest sampled electrical power: {
            physical.observed.peak_sampled_pack_electrical_power_w.toFixed(1)
          } W</p>
          <p>Change in recorded discharged-charge counter: {
            physical.observed.difference_in_reported_discharge_counter_mah.toFixed(1)
          } mAh</p>
          <p>Per-row timestamps: {physical.quality.per_row_timestamps_present ? 'yes' : 'no'}</p>
          <p>Matching simulated hardware: {
            physical.quality.hardware_model_match_verified ? 'verified' : 'not verified'
          }</p>
          <p>Physical model equivalence established: {
            report.model_physically_validated_by_these_public_sources ? 'yes' : 'no'
          }</p>
          <a href={physical.source.source_url} target="_blank" rel="noreferrer"
            className="inline-block text-cyan-400 underline">
            Original CC BY 4.0 flight dataset
          </a>
          <details>
            <summary className="cursor-pointer">Other independent research datasets</summary>
            <div className="space-y-2 pt-1">
              {report.registry.datasets.map((entry) => (
                <p key={entry.id} className="text-[10px] text-slate-400">
                  <a href={entry.url} target="_blank" rel="noreferrer"
                    className="text-cyan-400 underline">{entry.name}</a>
                  {' · '}{entry.ingestion_status.replaceAll('_', ' ')}
                  {' · Hardware match: '}{entry.aircraft_model_match ? 'reported' : 'not verified'}
                </p>
              ))}
            </div>
          </details>
          <p className="text-[10px] text-amber-400">
            The original PX4 CSV has no per-row timestamps, so flight energy
            and time-aligned simulation errors cannot be computed from it.
            No AeroForge airframe, pack, controller or flight mode has thereby been validated.
          </p>
        </div>
      )}
    </section>
  )
}
