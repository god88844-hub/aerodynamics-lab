/** Replay positions and attitudes from the recorded solver states only.
 * Interpolation produces display frames; it is not a new physics simulation. */
import type { Telemetry, Vec3 } from '../types/api'

export type QuaternionWxyz = [number, number, number, number]
export interface FlightPose {
  time_s: number
  position_world_m: Vec3
  attitude_world_wxyz: QuaternionWxyz | null
}

export function hasSpatialTelemetry(t: Telemetry | null | undefined): t is Telemetry {
  if (!t || t.t.length < 1) return false
  const n = t.t.length
  if (t.x?.length !== n || t.y?.length !== n || t.z?.length !== n) return false
  for (let i = 0; i < n; i += 1) {
    if (![t.t[i], t.x[i], t.y[i], t.z[i]].every(Number.isFinite)) return false
    if (i && t.t[i] <= t.t[i - 1]) return false
  }
  return true
}

export function flightDuration(t: Telemetry | null | undefined): number {
  return hasSpatialTelemetry(t) ? Math.max(0, t.t[t.t.length - 1] - t.t[0]) : 0
}

function normalize(q: number[]): QuaternionWxyz | null {
  if (q.length !== 4 || !q.every(Number.isFinite)) return null
  const length = Math.hypot(...q)
  if (length < 1e-12) return null
  return [q[0] / length, q[1] / length, q[2] / length, q[3] / length]
}

/** Shortest-arc quaternion slerp, [w,x,y,z] convention. */
export function slerpWxyz(a: number[], b: number[], fraction: number): QuaternionWxyz | null {
  const qa = normalize(a)
  const qb = normalize(b)
  if (!qa || !qb) return null
  const f = Math.min(1, Math.max(0, fraction))
  let dot = qa.reduce((sum, value, index) => sum + value * qb[index], 0)
  const to = dot < 0 ? qb.map((v) => -v) : [...qb]
  dot = Math.abs(dot)
  if (dot > 0.9995) return normalize(qa.map((v, i) => v + f * (to[i] - v)))
  const theta = Math.acos(Math.min(1, dot))
  const s = Math.sin(theta)
  const w0 = Math.sin((1 - f) * theta) / s
  const w1 = Math.sin(f * theta) / s
  return normalize(qa.map((v, i) => w0 * v + w1 * to[i]))
}

export function sampleFlightPose(t: Telemetry | null | undefined, elapsed_s: number): FlightPose | null {
  if (!hasSpatialTelemetry(t)) return null
  const first = t.t[0]
  const elapsed = Number.isFinite(elapsed_s) ? elapsed_s : 0
  const time = Math.min(t.t[t.t.length - 1], Math.max(first, first + elapsed))
  let low = 0
  let high = t.t.length - 1
  while (low < high) {
    const mid = Math.floor((low + high) / 2)
    if (t.t[mid] < time) low = mid + 1
    else high = mid
  }
  const j = low
  const i = Math.max(0, j - 1)
  const fraction = i === j ? 0 : (time - t.t[i]) / (t.t[j] - t.t[i])
  const lerp = (arr: number[]) => arr[i] + (arr[j] - arr[i]) * fraction
  const q = t.q_wxyz
  const attitude = q?.length === t.t.length && q?.[i] && q?.[j]
    ? slerpWxyz(q[i], q[j], fraction) : null
  return {
    time_s: time,
    position_world_m: [lerp(t.x), lerp(t.y), lerp(t.z)],
    attitude_world_wxyz: attitude,
  }
}
