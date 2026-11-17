import { useEffect, useRef, useState } from 'react'
import { api } from '../services/api'
import type { DroneDesign } from '../types/api'

type RunResult = {
  dataset_id: string
  partition_role: string
  conditional_voltage_replay: null | {
    status: string
    voltage_mae_v: number
    voltage_max_abs_error_v: number
    measured_delivered_energy_wh: number | null
    highest_c_rate: number
  }
  blockers: string[]
}

type CampaignResult = {
  battery_model_id: string
  campaign_status: string
  partition_status: string
  source_count: number
  holdout_count: number
  claimed_voltage_compatibility_only_samplewise: boolean
  blockers: string[]
  runs: RunResult[]
  decision_equivalent_to_physical_testing: boolean
  independently_authenticated_physical_pack_test: boolean
}

/** M21: source-pinned, read-only voltage-model comparison, never flight validation. */
export function BatteryCampaignPanel({ design }: { design: DroneDesign }) {
  const batteryId = design.powertrain?.battery_id ?? ''
  const [campaign, setCampaign] = useState('')
  const [result, setResult] = useState<CampaignResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const version = useRef(0)
  const invalidate = () => {
    version.current += 1
    setResult(null)
    setError(null)
    setBusy(false)
  }
  useEffect(() => { invalidate() }, [batteryId])

  const evaluate = async () => {
    const current = ++version.current
    setResult(null)
    setError(null)
    try {
      if (!batteryId) throw new Error('Select a battery before auditing its campaign')
      if (!campaign.trim()) throw new Error('Provide the frozen protocol and source-pinned discharge runs')
      const parsed = JSON.parse(campaign) as unknown
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        throw new Error('Campaign input must be a JSON object')
      }
      const obj = parsed as Record<string, unknown>
      if (!obj.frozen_protocol || !Array.isArray(obj.runs)) {
        throw new Error('Campaign requires frozen_protocol and runs')
      }
      if (obj.battery_model_id && obj.battery_model_id !== batteryId) {
        throw new Error('Campaign battery model must match the selected design')
      }
      setBusy(true)
      const response = await api.post<CampaignResult>('/components/battery-campaign-audit', {
        ...obj, battery_model_id: batteryId,
      })
      if (version.current === current) setResult(response)
    } catch (e) {
      if (version.current === current) setError((e as Error).message)
    } finally {
      if (version.current === current) setBusy(false)
    }
  }

  return (
    <section aria-label="Battery campaign evidence audit" className="space-y-2 p-3">
      <h3 className="text-[11px] font-semibold uppercase tracking-wider text-cyan-500">
        Battery physical-evidence campaign
      </h3>
      <p className="text-[10px] text-slate-400">
        Cross-check M19 original SHA-256 telemetry, M20 frozen test protocol
        and independent whole-recording partitions, then compare voltage
        under measured current. No software result authenticates a physical experiment.
      </p>
      <p className="text-xs text-cyan-300">Active battery model: {batteryId || 'none selected'}</p>
      <label className="block text-xs text-slate-300">
        Campaign JSON (frozen_protocol, expected_frozen_sha256, runs)
        <textarea aria-label="Battery campaign JSON" rows={6} value={campaign}
          onChange={e => { invalidate(); setCampaign(e.target.value) }}
          placeholder='{"frozen_protocol": {...}, "expected_frozen_sha256": "...", "runs": [...]}'
          className="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-2 font-mono text-xs" />
      </label>
      <button type="button" onClick={() => { void evaluate() }} disabled={busy || !batteryId}
        className="w-full rounded bg-cyan-800 px-2 py-2 text-xs text-white disabled:opacity-40">
        {busy ? 'Auditing…' : 'Audit held-out battery campaign'}
      </button>
      {error && <p role="alert" className="text-xs text-rose-400">{error}</p>}
      {result && <div className="space-y-2 rounded border border-slate-700 p-2 text-xs">
        <p className="font-semibold text-amber-300">{result.campaign_status.replaceAll('_', ' ')}</p>
        <p>Full independent pack validation: {result.independently_authenticated_physical_pack_test ? 'yes' : 'no'}</p>
        <p>Decision-equivalent physical evidence: {result.decision_equivalent_to_physical_testing ? 'yes' : 'no'}</p>
        <p>Source recordings: {result.source_count}; reported holdouts: {result.holdout_count}</p>
        <p>Partition: {result.partition_status.replaceAll('_', ' ')}</p>
        <p>Samplewise voltage agreement under declared bounds: {
          result.claimed_voltage_compatibility_only_samplewise ? 'reported' : 'not established'
        }</p>
        {result.runs.map(run => (
          <div key={run.dataset_id} className="space-y-1 border-t border-slate-800 pt-2">
            <p className="font-semibold">{run.dataset_id} ({run.partition_role})</p>
            {run.conditional_voltage_replay && <>
              <p>Voltage comparison: {run.conditional_voltage_replay.status.replaceAll('_', ' ')}</p>
              <p>Mean voltage absolute error: {run.conditional_voltage_replay.voltage_mae_v.toFixed(3)} V</p>
              <p>Worst observed voltage error: {run.conditional_voltage_replay.voltage_max_abs_error_v.toFixed(3)} V</p>
              <p>Measured delivered energy: {run.conditional_voltage_replay.measured_delivered_energy_wh == null
                ? 'unavailable: sparse or unsupported sampling'
                : run.conditional_voltage_replay.measured_delivered_energy_wh.toFixed(2) + ' Wh'
              }</p>
            </>}
            {run.blockers.map((reason, i) =>
              <p key={i} className="text-[10px] text-amber-400">{reason}</p>)}
          </div>
        ))}
        <p className="text-[10px] font-medium text-amber-400">Remaining scientific blockers: {result.blockers.length}</p>
        <ul className="list-inside list-disc text-[10px] text-slate-400">
          {result.blockers.map((b, i) => <li key={i}>{b}</li>)}
        </ul>
        <p className="text-[10px] text-amber-400">
          The replay is conditioned on measured current. Real-world temperature,
          capacity derating, instrument traceability and independent endurance
          predictions remain unverified.
        </p>
      </div>}
    </section>
  )
}
