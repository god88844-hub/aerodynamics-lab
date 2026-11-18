/** ResultsPanel rendering tests with a mock simulation result. */

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from '@rstest/core'
import { ResultsPanel } from '../panels/ResultsPanel'
import type { SimulationResult } from '../types/api'

const flightResult: SimulationResult = {
  simulation_id: 1,
  scenario: 'flight (M4 takeoff-hover-land, powertrain in the loop)',
  status: 'completed',
  results: {
    time_to_5m_s: 2.34,
    max_altitude_m: 5.34,
    energy_used_wh: 1.5,
    max_motor_current_a: 7.1,
    final_soc_pct: 99.6,
    final_altitude_m: -0.05,
    final_vertical_speed_m_s: 0.04,
    structural_margin_min: 13.2,
  },
  mission: { profile: 'takeoff -> 5 m hold -> land', duration_s: 18, aborted: false, abort_event: null },
  events: [],
  success: { reached_5m: true, gentle_landing: true, no_critical_failure: true },
  telemetry: null,
  trustworthiness: {
    verdict: 'M4 mission simulation — NOT a flight-worthiness claim',
    powertrain: { status: 'sourced bench data in the loop', caveat: 'quasi-static bus solve' },
  },
}

describe('ResultsPanel', () => {
  it('renders mission metrics for a completed flight', () => {
    render(<ResultsPanel result={flightResult} />)
    expect(screen.getByText(/time to 5 m/i)).toBeDefined()
    expect(screen.getByText('2.34')).toBeDefined()
    expect(screen.getByText(/completed/i)).toBeDefined()
    expect(screen.getByText(/PASS · reached 5m/i)).toBeDefined()
    expect(screen.getByText('INCONCLUSIVE')).toBeDefined()
  })

  it('renders the verdict prominently', () => {
    render(<ResultsPanel result={flightResult} />)
    expect(screen.getAllByText(/NOT a flight-worthiness claim/i).length).toBeGreaterThan(0)
  })

  it('preserves a bending failure in a historical result', () => {
    render(<ResultsPanel result={{ ...flightResult, results: { structural_margin_min: 0.6 } }} />)
    expect(screen.getByText('FAIL')).toBeDefined()
  })

  it('renders a failed run with the physics refusal', () => {
    const failed: SimulationResult = {
      scenario: 'flight',
      status: 'failed',
      error: 'required per-unit thrust is outside the measured static table',
      trustworthiness: { verdict: 'RUN FAILED' },
    }
    render(<ResultsPanel result={failed} />)
    expect(screen.getAllByText(/RUN FAILED/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/measured static table/i)).toBeDefined()
  })
})
