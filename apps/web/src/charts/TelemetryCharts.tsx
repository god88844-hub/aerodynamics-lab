/** Telemetry charts (recharts): altitude/vertical speed, per-motor currents,
  battery SOC + bus voltage. Rows are shaped from the decimated telemetry. */

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { SimulationResult } from '../types/api'

interface Row {
  t: number
  z: number
  vz: number
  c0?: number
  c1?: number
  c2?: number
  c3?: number
  soc?: number
  vbus?: number
  p?: number
}

function buildRows(result: SimulationResult): Row[] {
  const tel = result.telemetry
  if (!tel) return []
  const n = tel.t.length
  const rows: Row[] = []
  for (let i = 0; i < n; i++) {
    rows.push({
      t: Number(tel.t[i].toFixed(2)),
      z: Number(tel.z[i].toFixed(3)),
      vz: Number(tel.vz[i].toFixed(3)),
      c0: tel.motor_current_a?.[i]?.[0],
      c1: tel.motor_current_a?.[i]?.[1],
      c2: tel.motor_current_a?.[i]?.[2],
      c3: tel.motor_current_a?.[i]?.[3],
      soc: tel.soc_pct?.[i] != null ? Number(tel.soc_pct[i].toFixed(2)) : undefined,
      vbus: tel.v_bus_v?.[i] != null ? Number(tel.v_bus_v[i].toFixed(2)) : undefined,
      p: tel.total_power_w?.[i] != null ? Number(tel.total_power_w[i].toFixed(1)) : undefined,
    })
  }
  return rows
}

const AXIS = { stroke: '#475569', fontSize: 10 }

export function TelemetryCharts({ result }: { result: SimulationResult | null }) {
  if (result?.telemetry == null || result.telemetry.t.length === 0) {
    return (
      <p className="p-3 text-xs text-slate-500">
        charts appear after a simulation run
      </p>
    )
  }
  const rows = buildRows(result)
  return (
    <div className="space-y-4 p-3">
      <section>
        <h3 className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-cyan-500">
          altitude / vertical speed
        </h3>
        <ResponsiveContainer width="100%" height={160}>
          <LineChart data={rows} margin={{ top: 4, right: 8, bottom: 0, left: -18 }}>
            <CartesianGrid stroke="#1e293b" />
            <XAxis dataKey="t" tick={AXIS} unit="s" />
            <YAxis tick={AXIS} />
            <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155', fontSize: 11 }} />
            <Line type="monotone" dataKey="z" name="z [m]" stroke="#22d3ee" dot={false} />
            <Line type="monotone" dataKey="vz" name="vz [m/s]" stroke="#94a3b8" dot={false} />
            <Legend wrapperStyle={{ fontSize: 10 }} />
          </LineChart>
        </ResponsiveContainer>
      </section>

      {rows.some((r) => r.c0 !== undefined) && (
        <section>
          <h3 className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-cyan-500">
            motor currents
          </h3>
          <ResponsiveContainer width="100%" height={140}>
            <LineChart data={rows} margin={{ top: 4, right: 8, bottom: 0, left: -18 }}>
              <CartesianGrid stroke="#1e293b" />
              <XAxis dataKey="t" tick={AXIS} unit="s" />
              <YAxis tick={AXIS} unit="A" />
              <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155', fontSize: 11 }} />
              {(['c0', 'c1', 'c2', 'c3'] as const).map((k, i) => (
                <Line
                  key={k}
                  type="monotone"
                  dataKey={k}
                  name={`M${i + 1} [A]`}
                  stroke={['#22d3ee', '#f59e0b', '#a3e635', '#f43f5e'][i]}
                  dot={false}
                />
              ))}
              <Legend wrapperStyle={{ fontSize: 10 }} />
            </LineChart>
          </ResponsiveContainer>
        </section>
      )}

      {(rows.some((r) => r.soc !== undefined) || rows.some((r) => r.vbus !== undefined)) && (
        <section>
          <h3 className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-cyan-500">
            battery SOC / bus voltage
          </h3>
          <ResponsiveContainer width="100%" height={140}>
            <LineChart data={rows} margin={{ top: 4, right: 8, bottom: 0, left: -18 }}>
              <CartesianGrid stroke="#1e293b" />
              <XAxis dataKey="t" tick={AXIS} unit="s" />
              <YAxis tick={AXIS} yAxisId="soc" />
              <YAxis tick={AXIS} yAxisId="vbus" orientation="right" />
              <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155', fontSize: 11 }} />
              {rows.some((r) => r.soc !== undefined) && (
                <Line yAxisId="soc" type="monotone" dataKey="soc" name="SOC [%]" stroke="#a3e635" dot={false} />
              )}
              {rows.some((r) => r.vbus !== undefined) && (
                <Line yAxisId="vbus" type="monotone" dataKey="vbus" name="V bus [V]" stroke="#f59e0b" dot={false} />
              )}
              <Legend wrapperStyle={{ fontSize: 10 }} />
            </LineChart>
          </ResponsiveContainer>
        </section>
      )}
    </div>
  )
}
