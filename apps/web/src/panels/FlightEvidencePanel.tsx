import { useEffect, useRef, useState } from 'react'
import type { SimulationResult } from '../types/api'
import { api } from '../services/api'
import {
  flightChannels, flightChannelLabels, parseFlightEvidenceRows,
  type FlightChannel,
} from '../editor/flightEvidenceRows'

interface ChannelComparison {
  unit: string
  metrics: {
    count: number
    mae: number
    rmse: number
    bias: number
    max_absolute_error: number
    predeclared_max_absolute_error: number
    meets_predeclared_tolerance: boolean
  }
}
interface FlightEvidenceReport {
  simulation_id: number
  verdict: string
  stored_prediction_sha256: string
  coverage: {
    mission_fraction: number
    max_interpolation_spacing_s: number
    adequate: boolean
    interpolation_supported: boolean
  }
  channels: Partial<Record<FlightChannel, ChannelComparison>>
  simulation_modified: boolean
  uncertainty_assessment?: { status: string }
}

/** Flight-log scoring only; it does not write a physics component or a design. */
export function FlightEvidencePanel({ result }: { result: SimulationResult | null }) {
  const id = result?.status === 'completed' && result.scenario.startsWith('flight')
    ? result.simulation_id : undefined
  const [kind, setKind] = useState('')
  const [vehicle, setVehicle] = useState('')
  const [flightLog, setFlightLog] = useState('')
  const [source, setSource] = useState('')
  const [offset, setOffset] = useState('0')
  const [matches, setMatches] = useState(false)
  const [unused, setUnused] = useState(false)
  const [csv, setCsv] = useState('')
  const [limits, setLimits] = useState<Record<FlightChannel, string>>({
    altitude_m: '', vertical_speed_m_s: '', bus_voltage_v: '', battery_current_a: '',
  })
  const [uncertaintyEnabled, setUncertaintyEnabled] = useState(false)
  const [clockBound, setClockBound] = useState('0')
  const [bounds, setBounds] = useState<Record<FlightChannel, string>>({
    altitude_m: '', vertical_speed_m_s: '', bus_voltage_v: '', battery_current_a: '',
  })
  const [report, setReport] = useState<FlightEvidenceReport | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const version = useRef(0)

  const invalidate = () => {
    version.current += 1
    setReport(null)
    setError(null)
    setRunning(false)
  }
  useEffect(() => {
    version.current += 1
    setReport(null)
    setError(null)
    setRunning(false)
  }, [id])

  const evaluate = async () => {
    const currentVersion = ++version.current
    setReport(null)
    setError(null)
    try {
      if (id === undefined) throw new Error('Run and save a flight simulation first')
      if (kind !== 'physical_measurements' && kind !== 'synthetic_fixture') {
        throw new Error('Select physical measurements or synthetic verification fixture')
      }
      if (![vehicle, flightLog, source].every((value) => value.trim())) {
        throw new Error('Provide vehicle, flight log identifier and evidence provenance')
      }
      const timeOffset = Number(offset)
      if (!offset.trim() || !Number.isFinite(timeOffset) || Math.abs(timeOffset) > 60) {
        throw new Error('Declare a time offset between -60 and 60 seconds')
      }
      const observations = parseFlightEvidenceRows(csv)
      const tolerances: Partial<Record<FlightChannel, number>> = {}
      for (const channel of flightChannels) {
        if (observations.some((row) => row[channel] !== null)) {
          const value = Number(limits[channel])
          if (!limits[channel].trim() || !Number.isFinite(value) || value <= 0) {
            throw new Error(`Predeclare a positive ${flightChannelLabels[channel]}`)
          }
          tolerances[channel] = value
        }
      }
      const measurement_error_bounds: Partial<Record<FlightChannel, number>> = {}
      if (uncertaintyEnabled) {
        const clock = Number(clockBound)
        if (!clockBound.trim() || !Number.isFinite(clock) || clock < 0 || clock > 2) {
          throw new Error('Clock error bound must be between 0 and 2 seconds')
        }
        for (const channel of flightChannels) {
          if (channel in tolerances) {
            const value = Number(bounds[channel])
            if (!bounds[channel].trim() || !Number.isFinite(value) || value < 0) {
              throw new Error('Declare a nonnegative absolute measurement error bound for ' + channel)
            }
            measurement_error_bounds[channel] = value
          }
        }
      }
      setRunning(true)
      const response = await api.post<FlightEvidenceReport>(`/simulations/${id}/flight-evidence`, {
        dataset_kind: kind,
        vehicle_id: vehicle.trim(),
        flight_log_id: flightLog.trim(),
        log_source: source.trim(),
        hardware_matches_simulated_design: matches,
        unused_for_model_calibration: unused,
        measurement_to_sim_time_offset_s: timeOffset,
        tolerances,
        observations,
        ...(uncertaintyEnabled ? {
          measurement_error_bounds,
          clock_error_bound_s: Number(clockBound),
        } : {}),
      })
      if (version.current === currentVersion) setReport(response)
    } catch (e) {
      if (version.current === currentVersion) setError((e as Error).message)
    } finally {
      if (version.current === currentVersion) setRunning(false)
    }
  }

  return (
    <section aria-label="Flight evidence laboratory" className="space-y-2 p-3">
      <h3 className="text-[11px] font-semibold uppercase tracking-wider text-cyan-500">
        Flight telemetry evidence lab
      </h3>
      <p className="text-[10px] text-slate-400">
        Compare a saved flight prediction with an independent, timestamped
        flight log. No time shifting is fitted. All comparisons are read-only.
      </p>
      {id === undefined ? (
        <p className="text-xs text-amber-400">
          Complete a Flight simulation first; other scenarios cannot be flight-validated here.
        </p>
      ) : (
        <>
          <p className="text-xs text-cyan-300">Saved simulation #{id}</p>
          <label className="block text-xs text-slate-300">
            Evidence type
            <select aria-label="Flight evidence type" value={kind}
              onChange={(e) => { invalidate(); setKind(e.target.value) }}
              className="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-1">
              <option value="">Select evidence provenance</option>
              <option value="physical_measurements">Reported physical flight log</option>
              <option value="synthetic_fixture">Synthetic (software verification only)</option>
            </select>
          </label>
          {([
            ['Vehicle ID', vehicle, setVehicle],
            ['Flight log ID', flightLog, setFlightLog],
            ['Flight log source', source, setSource],
            ['Declared measurement-to-simulation time offset (s)', offset, setOffset],
          ] as const).map(([name, value, update]) => (
            <label key={name} className="block text-xs text-slate-300">
              {name}
              <input aria-label={name} type="text" value={value}
                onChange={(e) => { invalidate(); update(e.target.value) }}
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-1" />
            </label>
          ))}
          <label className="flex gap-2 text-xs text-slate-300">
            <input aria-label="Hardware matches the simulated design" type="checkbox"
              checked={matches} onChange={(e) => { invalidate(); setMatches(e.target.checked) }} />
            I declare hardware matches the simulated design (not independently checked)
          </label>
          <label className="flex gap-2 text-xs text-slate-300">
            <input aria-label="Log unused in model calibration" type="checkbox"
              checked={unused} onChange={(e) => { invalidate(); setUnused(e.target.checked) }} />
            I declare these measurements were not used to calibrate this model
          </label>
          <p className="text-[10px] text-slate-400">
            CSV: t_s, altitude_m, vertical_speed_m_s, bus_voltage_v, battery_current_a.
            Altitude and vertical velocity positive UP, relative to takeoff. Use blank cells
            for unmeasured channels. Each measured channel needs ≥5 observations.
          </p>
          <textarea aria-label="Flight log CSV" rows={6} value={csv}
            onChange={(e) => { invalidate(); setCsv(e.target.value) }}
            placeholder={'t_s,altitude_m,vertical_speed_m_s,bus_voltage_v,battery_current_a\n0,0,,24,5\n2,4,,23.8,5\n4,8,,23.6,5\n6,12,,23.4,5\n8,16,,23.2,5'}
            className="w-full rounded border border-slate-700 bg-slate-950 p-2 font-mono text-[10px]" />
          <p className="text-[10px] text-amber-400">
            Example rows are arbitrary synthetic format illustrations, never physical evidence.
            Set limits BEFORE examining held-out errors.
          </p>
          <div className="grid grid-cols-2 gap-2">
            {flightChannels.map((channel) => (
              <label key={channel} className="text-[10px] text-slate-300">
                {flightChannelLabels[channel]}
                <input aria-label={flightChannelLabels[channel]} type="number"
                  min="0.000001" step="any" value={limits[channel]}
                  onChange={(e) => { invalidate(); setLimits((old) => ({ ...old, [channel]: e.target.value })) }}
                  className="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-1" />
              </label>
            ))}
          </div>
          <label className="flex gap-2 text-xs text-slate-300">
            <input aria-label="Enable conservative uncertainty bounds" type="checkbox"
              checked={uncertaintyEnabled}
              onChange={(e) => { invalidate(); setUncertaintyEnabled(e.target.checked) }} />
            Evaluate worst-case residuals under declared instrument and clock error bounds
          </label>
          {uncertaintyEnabled && (
            <div className="space-y-2 rounded border border-slate-700 p-2">
              <p className="text-[10px] text-amber-400">
                These must be hard absolute error bounds from actual instrumentation.
                They are not statistical standard deviations or automatically authenticated.
              </p>
              <label className="block text-xs text-slate-300">
                Clock synchronization error bound (s)
                <input aria-label="Clock synchronization error bound (s)"
                  type="number" min="0" max="2" step="any" value={clockBound}
                  onChange={(e) => { invalidate(); setClockBound(e.target.value) }}
                  className="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-1" />
              </label>
              <div className="grid grid-cols-2 gap-2">
                {flightChannels.map((channel) => (
                  <label key={channel} className="text-[10px] text-slate-300">
                    {flightChannelLabels[channel]} absolute error bound
                    <input aria-label={channel + ' measurement error bound'}
                      type="number" min="0" step="any" value={bounds[channel]}
                      onChange={(e) => {
                        invalidate()
                        setBounds((old) => ({ ...old, [channel]: e.target.value }))
                      }}
                      className="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-1" />
                  </label>
                ))}
              </div>
            </div>
          )}
          <button type="button" disabled={running} onClick={() => void evaluate()}
            className="w-full rounded bg-cyan-800 px-2 py-2 text-xs text-white disabled:opacity-40">
            {running ? 'Comparing…' : 'Compare held-out flight telemetry'}
          </button>
          {error && <p role="alert" className="text-xs text-rose-400">{error}</p>}
          {report && (
            <div className="space-y-2 rounded border border-slate-700 p-2 text-xs">
              <p className="font-semibold text-cyan-300">{report.verdict.replaceAll('_', ' ')}</p>
              <p>Mission coverage: {(report.coverage.mission_fraction * 100).toFixed(1)}%</p>
              <p>Prediction sampling supported: {report.coverage.interpolation_supported ? 'yes' : 'no'}</p>
              {report.uncertainty_assessment &&
                <p>Uncertainty assessment: {report.uncertainty_assessment.status.replaceAll('_', ' ')}</p>}
              <table className="w-full text-[10px]">
                <thead><tr><th className="text-left">Channel</th><th>RMSE</th><th>Max error</th><th>Limit</th></tr></thead>
                <tbody>
                  {flightChannels.map((channel) => {
                    const entry = report.channels[channel]
                    return entry && (
                      <tr key={channel}>
                        <td className="pr-1">{channel.replaceAll('_', ' ')}</td>
                        <td className="text-right">{entry.metrics.rmse.toFixed(3)}</td>
                        <td className="text-right">{entry.metrics.max_absolute_error.toFixed(3)}</td>
                        <td className="text-right">{entry.metrics.predeclared_max_absolute_error.toFixed(3)} {entry.unit}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
              <p className="break-all font-mono text-[9px] text-slate-400">
                Saved prediction SHA-256: {report.stored_prediction_sha256}
              </p>
              <p className="text-[10px] text-amber-300">
                User-supplied source and independence are not authenticated.
                A tolerance pass is not physical validation equivalence, flight safety,
                or certification. Original simulation was not changed.
              </p>
            </div>
          )}
        </>
      )}
    </section>
  )
}
