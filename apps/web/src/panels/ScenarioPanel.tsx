/** Scenario picker + Simulate button. Saves the design first so the exact
  snapshot that ran is stored (traceability). */

import { useState } from 'react'
import { useDesignStore } from '../state/designStore'
import { useSaveDesign, useSimulate } from '../services/queries'
import { SectionTitle, SelectField } from './fields'

const SCENARIOS = [
  { value: 'flight', label: 'Flight: takeoff → 5 m → land' },
  { value: 'hover-static', label: 'Hover endurance (static)' },
  { value: 'hover-hold', label: 'Hover hold (disturbances)' },
  { value: 'hover-ideal', label: 'Hover verification (ideal)' },
]

export function ScenarioPanel() {
  const { design, designId, scenario, setScenario, setResult, setSnapshot } = useDesignStore()
  const save = useSaveDesign()
  const simulate = useSimulate()
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)

  const needsPowertrain = scenario === 'flight' || scenario === 'hover-static'

  const onSimulate = async () => {
    setError(null)
    setRunning(true)
    try {
      const saved = designId != null
        ? await save.mutateAsync({ ...design, id: designId })
        : await save.mutateAsync(design)
      setSnapshot(saved.snapshot, saved.id)
      const result = await simulate.mutateAsync({
        designId: saved.id,
        scenario,
        params: scenario === 'hover-static' ? { max_duration_s: 7200 } : {},
      })
      setResult(result)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="space-y-3 p-3">
      <SectionTitle>Scenario</SectionTitle>
      <SelectField label="scenario" value={scenario} onChange={setScenario} options={SCENARIOS} />
      {needsPowertrain && !design.powertrain && (
        <p className="text-xs text-amber-500">
          this scenario needs a powertrain — pick components in the design panel
        </p>
      )}
      <button
        className="w-full rounded bg-cyan-700 px-3 py-2 text-sm font-semibold text-white hover:bg-cyan-800 disabled:opacity-50"
        onClick={() => void onSimulate()}
        disabled={running}
      >
        {running ? 'simulating…' : '▶ Simulate'}
      </button>
      {(error || (simulate.isError && (simulate.error as Error).message)) && (
        <p className="text-xs text-rose-400">
          {error ?? (simulate.error as Error).message}
        </p>
      )}
      <p className="text-[10px] leading-relaxed text-slate-400">
        Each run stores a copy of its design and solver settings for later download.
      </p>
    </div>
  )
}
