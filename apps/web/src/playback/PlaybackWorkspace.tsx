/** Invention-lab replay controls. Trajectory is sourced from solver telemetry. */
import { useEffect, useRef, useState } from 'react'
import type { DroneDesign, SimulationResult, Vec3 } from '../types/api'
import { DroneViewport } from '../viewport/DroneViewport'
import { flightDuration, hasSpatialTelemetry, sampleFlightPose } from './flightPlayback'

export function PlaybackWorkspace({ design, cog, principalAxes, result }: {
  design: DroneDesign
  cog: Vec3
  principalAxes: number[][] | null
  result: SimulationResult | null
}) {
  const telemetry = result?.telemetry
  const supported = hasSpatialTelemetry(telemetry)
  const duration = flightDuration(telemetry)
  const [elapsed, setElapsed] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(1)
  const [follow, setFollow] = useState(false)
  const raf = useRef<number | null>(null)

  useEffect(() => {
    setPlaying(false)
    setElapsed(0)
  }, [telemetry])

  useEffect(() => {
    if (!playing || !supported || duration <= 0) return
    const from = Math.min(elapsed, duration)
    let start: number | null = null
    const tick = (now: number) => {
      if (start === null) start = now
      const next = Math.min(duration, from + (now - start) / 1000 * speed)
      setElapsed(next)
      if (next >= duration) setPlaying(false)
      else raf.current = requestAnimationFrame(tick)
    }
    raf.current = requestAnimationFrame(tick)
    return () => {
      if (raf.current !== null) cancelAnimationFrame(raf.current)
      raf.current = null
    }
    // Intentional: elapsed is captured when playback begins or playback speed changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, speed, duration, supported, telemetry])

  const pose = supported ? sampleFlightPose(telemetry, elapsed) : null
  const onPlayPause = () => {
    if (!supported || duration === 0) return
    if (playing) { setPlaying(false); return }
    if (elapsed >= duration) setElapsed(0)
    setPlaying(true)
  }

  return (
    <div className="relative h-full w-full" data-testid="flight-playback-workspace">
      <DroneViewport design={design} cog={cog} principalAxes={principalAxes}
        result={result} pose={pose} follow={follow} />
      {supported && duration > 0 ? (
        <section aria-label="Flight playback"
          className="absolute bottom-3 left-3 right-3 space-y-2 rounded-lg border border-slate-700 bg-slate-950/95 p-3 shadow-xl">
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" onClick={onPlayPause}
              aria-label={playing ? 'Pause playback' : 'Play flight replay'}
              className="rounded bg-cyan-700 px-3 py-1 text-xs font-semibold text-white hover:bg-cyan-600">
              {playing ? 'Ⅱ Pause' : '▶ Play'}
            </button>
            <button type="button" onClick={() => { setPlaying(false); setElapsed(0) }}
              aria-label="Restart playback"
              className="rounded border border-slate-600 px-2 py-1 text-xs text-slate-200">↺ Restart</button>
            <label htmlFor="playback-speed" className="text-xs text-slate-300">Speed</label>
            <select id="playback-speed" aria-label="Playback speed" value={speed}
              onChange={(e) => setSpeed(Number(e.target.value))}
              className="rounded border border-slate-600 bg-slate-900 px-1 py-1 text-xs">
              {[0.5, 1, 2, 4].map((v) => <option key={v} value={v}>{v}×</option>)}
            </select>
            <button type="button" onClick={() => setFollow((x) => !x)}
              aria-label={follow ? 'Switch to free camera' : 'Follow the drone'}
              className="rounded border border-slate-600 px-2 py-1 text-xs text-slate-200">
              Camera: {follow ? 'Follow' : 'Free orbit'}
            </button>
            <span className="ml-auto font-mono text-xs tabular-nums text-slate-300">
              {elapsed.toFixed(2)} / {duration.toFixed(2)} s
              {pose ? ' · Alt ' + pose.position_world_m[2].toFixed(2) + ' m' : ''}
            </span>
          </div>
          <input type="range" aria-label="Playback time" min={0} max={duration} step={0.01}
            value={Math.min(elapsed, duration)}
            onChange={(e) => { setPlaying(false); setElapsed(Number(e.target.value)) }}
            className="block w-full accent-cyan-400" />
          <p className="text-[10px] text-slate-500">
            Replay interpolates stored solver samples; animation frames are not new physics calculations.
            {pose && !pose.attitude_world_wxyz ? ' Attitude not available in this run.' : ''}
          </p>
        </section>
      ) : result ? (
        <p className="absolute bottom-2 left-2 rounded bg-slate-950/85 p-2 text-xs text-slate-400">
          No spatial flight trajectory for this scenario (static analysis is not animated).
        </p>
      ) : null}
    </div>
  )
}
