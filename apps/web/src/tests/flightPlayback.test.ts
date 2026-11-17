/** Deterministic playback interpolation, with no fabricated trajectory. */
import { describe, expect, it } from '@rstest/core'
import type { Telemetry } from '../types/api'
import { flightDuration, hasSpatialTelemetry, sampleFlightPose, slerpWxyz } from '../playback/flightPlayback'

const flight: Telemetry = {
  t: [10, 11, 13], x: [0, 1, 5], y: [0, 2, 6], z: [0, 3, 7], vz: [0, 0, 0],
  motor_thrusts_n: [[], [], []],
  q_wxyz: [[1, 0, 0, 0], [0, 0, 0, 1], [0, 0, 0, -1]],
}

describe('flight replay sampler', () => {
  it('interpolates non-uniform sample times in elapsed seconds', () => {
    expect(hasSpatialTelemetry(flight)).toBe(true)
    expect(flightDuration(flight)).toBe(3)
    expect(sampleFlightPose(flight, 2)?.position_world_m).toEqual([3, 4, 5])
  })
  it('clamps playback outside the recorded time domain', () => {
    expect(sampleFlightPose(flight, -20)?.position_world_m).toEqual([0, 0, 0])
    expect(sampleFlightPose(flight, 100)?.position_world_m).toEqual([5, 6, 7])
  })
  it('rejects static telemetry and malformed time series', () => {
    const power = { t: [0, 1], total_power_w: [100, 90] } as Telemetry
    expect(hasSpatialTelemetry(power)).toBe(false)
    expect(sampleFlightPose(power, 0.5)).toBeNull()
    expect(hasSpatialTelemetry({ ...flight, t: [10, 11, 11] })).toBe(false)
    expect(hasSpatialTelemetry({ ...flight, z: [0, Number.NaN, 1] })).toBe(false)
  })
  it('keeps quaternion norm and interpolates over shortest arc', () => {
    const q = slerpWxyz([1, 0, 0, 0], [0, 0, 0, -1], 0.5)!
    expect(Math.hypot(...q)).toBeCloseTo(1, 10)
    const identicalRotation = slerpWxyz([1, 0, 0, 0], [-1, 0, 0, 0], 0.5)!
    expect(Math.abs(identicalRotation[0])).toBeCloseTo(1, 10)
  })
  it('marks orientation unavailable instead of inventing it', () => {
    const withoutAttitude = { ...flight, q_wxyz: undefined }
    expect(sampleFlightPose(withoutAttitude, 1)!.attitude_world_wxyz).toBeNull()
    expect(slerpWxyz([0, 0, 0, 0], [1, 0, 0, 0], 0.5)).toBeNull()
  })
})
