/** Result panels: metrics, verdict, events, success criteria — plus the
  trustworthiness section (always shown, per the validation strategy). */

import type { SimulationResult } from '../types/api'

function Metric({ label, value, unit }: { label: string; value: string | number | null; unit?: string }) {
  return (
    <div className="rounded border border-slate-800 bg-slate-900/60 px-2 py-1.5">
      <div className="text-[10px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className="font-mono text-sm text-slate-100">
        {value === null || value === undefined ? '—' : value}
        {value != null && unit && <span className="ml-1 text-[10px] text-slate-500">{unit}</span>}
      </div>
    </div>
  )
}

function fmt(v: number | null | undefined, digits = 2): string | null {
  if (v === null || v === undefined || !Number.isFinite(v)) return null
  return v.toFixed(digits)
}

export function ResultsPanel({ result }: { result: SimulationResult | null }) {
  if (result === null) {
    return (
      <div className="p-4 text-xs text-slate-500">
        No simulation yet — pick a scenario and press ▶ Simulate.
      </div>
    )
  }

  if (result.status === 'failed') {
    return (
      <div className="space-y-3 p-4">
        <div className="rounded border border-rose-800 bg-rose-950/40 px-3 py-2 text-xs text-rose-300">
          <div className="font-semibold">RUN FAILED — physics refused this design/scenario</div>
          <div className="mt-1 font-mono">{result.error}</div>
        </div>
        <TrustSection result={result} />
      </div>
    )
  }

  const scenario = result.scenario
  return (
    <div className="space-y-4 p-4">
      <ScenarioResults result={result} scenario={scenario} />
      {result.events && result.events.length > 0 && <EventsSection result={result} />}
      {result.success && <SuccessSection result={result} />}
      <TrustSection result={result} />
    </div>
  )
}

function ScenarioResults({ result, scenario }: { result: SimulationResult; scenario: string }) {
  if (scenario.startsWith('flight') && result.results) {
    const r = result.results
    return (
      <section>
        <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-cyan-500">
          Mission results
        </h3>
        <div className="grid grid-cols-2 gap-2">
          <Metric label="time to 5 m" value={fmt(r.time_to_5m_s)} unit="s" />
          <Metric label="max altitude" value={fmt(r.max_altitude_m)} unit="m" />
          <Metric label="energy used" value={fmt(r.energy_used_wh)} unit="Wh" />
          <Metric label="max motor current" value={fmt(r.max_motor_current_a)} unit="A" />
          <Metric label="final SOC" value={fmt(r.final_soc_pct, 1)} unit="%" />
          <Metric label="struct. margin" value={fmt(r.structural_margin_min)} unit="×yield" />
        </div>
        {result.mission && (
          <p className="mt-2 text-xs text-slate-400">
            mission {result.mission.aborted ? (
              <span className="text-rose-400">ABORTED: {result.mission.abort_event}</span>
            ) : (
              <span className="text-emerald-500">completed</span>
            )}
          </p>
        )}
      </section>
    )
  }
  if (scenario.startsWith('hover-static') && result.hover_point && result.endurance) {
    const hp = result.hover_point as Record<string, number & Record<string, unknown>>
    const perRotor = hp.per_rotor as Record<string, number>
    const en = result.endurance
    return (
      <section>
        <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-cyan-500">
          Hover point (full charge)
        </h3>
        <div className="grid grid-cols-2 gap-2">
          <Metric label="throttle" value={fmt(Number(hp.throttle) * 100, 1)} unit="%" />
          <Metric label="bus voltage" value={fmt(Number(hp.v_bus_v))} unit="V" />
          <Metric label="current / rotor" value={fmt(perRotor.current_a)} unit="A" />
          <Metric label="rpm" value={fmt(perRotor.rpm, 0)} />
          <Metric label="hover power" value={fmt(Number(hp.total_power_w), 0)} unit="W" />
          <Metric label="endurance → warning" value={en.to_warning_s != null ? fmt(Number(en.to_warning_s) / 60, 1) : null} unit="min" />
        </div>
        {result.benchmarks && (
          <div className="mt-3 space-y-1">
            <h4 className="text-[10px] uppercase tracking-wide text-slate-500">benchmarks</h4>
            {result.benchmarks.map((b) => (
              <p key={b.name} className="text-xs">
                <span className={b.status === 'pass' ? 'text-emerald-500' : b.status === 'fail' ? 'text-rose-400' : 'text-sky-400'}>
                  [{b.status.toUpperCase()}]
                </span>{' '}
                <span className="text-slate-300">{b.name}</span>
              </p>
            ))}
          </div>
        )}
      </section>
    )
  }
  if (scenario.startsWith('hover-hold') && result.results) {
    const r = result.results
    return (
      <section>
        <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-cyan-500">
          Disturbance response
        </h3>
        <div className="grid grid-cols-2 gap-2">
          <Metric label="peak |roll|" value={fmt(r.peak_abs_roll_deg)} unit="°" />
          <Metric label="peak |pitch|" value={fmt(r.peak_abs_pitch_deg)} unit="°" />
          <Metric label="alt. error (tail)" value={fmt(r.tail_altitude_error_m, 3)} unit="m" />
          <Metric label="position error" value={fmt(r.tail_position_error_m, 3)} unit="m" />
        </div>
        <p className="mt-2 text-xs text-slate-400">oscillation: {r.oscillation}</p>
      </section>
    )
  }
  if (result.results) {
    const r = result.results
    return (
      <section>
        <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-cyan-500">Results</h3>
        <div className="grid grid-cols-2 gap-2">
          {Object.entries(r).map(([k, v]) => (
            <Metric key={k} label={k.replaceAll('_', ' ')} value={fmt(v as number, 4)} />
          ))}
        </div>
      </section>
    )
  }
  return null
}

function EventsSection({ result }: { result: SimulationResult }) {
  return (
    <section>
      <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-cyan-500">Events</h3>
      <div className="space-y-1">
        {result.events!.map((e, i) => (
          <p key={i} className={`text-xs ${e.critical ? 'text-rose-400' : 'text-amber-400'}`}>
            [{e.critical ? 'CRITICAL' : 'warn'}] t={fmt(e.t_s, 2)}s {e.kind}
          </p>
        ))}
      </div>
    </section>
  )
}

function SuccessSection({ result }: { result: SimulationResult }) {
  return (
    <section>
      <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-cyan-500">
        Success criteria
      </h3>
      <div className="flex flex-wrap gap-2">
        {Object.entries(result.success!).map(([name, ok]) => (
          <span
            key={name}
            className={`rounded-full px-2 py-0.5 text-xs font-medium ${
              ok ? 'bg-emerald-900/60 text-emerald-300' : 'bg-rose-900/60 text-rose-300'
            }`}
          >
            {ok ? 'PASS' : 'FAIL'} · {name.replaceAll('_', ' ')}
          </span>
        ))}
      </div>
    </section>
  )
}

function TrustSection({ result }: { result: SimulationResult }) {
  const tw = result.trustworthiness ?? {}
  const verdict = typeof tw.verdict === 'string' ? tw.verdict : undefined
  const entries = Object.entries(tw).filter(([k]) => k !== 'verdict')
  return (
    <section className="rounded border border-slate-800 bg-slate-900/40 p-3">
      <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-cyan-500">
        Trustworthiness
      </h3>
      {verdict && <p className="mb-2 text-xs font-medium text-amber-300">{verdict}</p>}
      <div className="space-y-1.5">
        {entries.map(([key, entry]) => {
          if (typeof entry === 'string') return null
          return (
            <div key={key} className="text-xs">
              <span className="text-slate-400">{key}: </span>
              <span className="text-slate-200">{entry.status ?? ''}</span>
              {entry.caveat && <p className="pl-3 text-[10px] text-slate-500">{entry.caveat}</p>}
              {entry.evidence && <p className="pl-3 text-[10px] text-slate-500">{entry.evidence}</p>}
              {entry.notes && <p className="pl-3 text-[10px] text-slate-500">{entry.notes}</p>}
            </div>
          )
        })}
      </div>
    </section>
  )
}
