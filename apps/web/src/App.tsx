/** App shell: header + three-pane layout (design editor | 3D viewport |
  results & charts). */

import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'
import { api } from './services/api'
import { useDesignStore } from './state/designStore'
import { computeCog } from './state/designStore'
import { usePreview, useReferenceDesign } from './services/queries'
import { DesignPanel } from './panels/DesignPanel'
import { ComponentInspector } from './editor/ComponentInspector'
import { ScenarioPanel } from './panels/ScenarioPanel'
import { StructuralLabPanel } from './panels/StructuralLabPanel'
import { CombinedMetalPanel } from './panels/CombinedMetalPanel'
import { BatteryEvidencePanel } from './panels/BatteryEvidencePanel'
import { DischargeReplayPanel } from './panels/DischargeReplayPanel'
import { BatteryCampaignPanel } from './panels/BatteryCampaignPanel'
import { FlightEvidencePanel } from './panels/FlightEvidencePanel'
import { PropulsionEvidencePanel } from './panels/PropulsionEvidencePanel'
import { PublicEvidencePanel } from './panels/PublicEvidencePanel'
import { G30PublicBenchPanel } from './panels/G30PublicBenchPanel'
import { TelemetryAuditPanel } from './panels/TelemetryAuditPanel'
import { ValidationProtocolPanel } from './panels/ValidationProtocolPanel'
import { HILEvidencePanel } from './panels/HILEvidencePanel'
import { ResultsPanel } from './panels/ResultsPanel'
import { TelemetryCharts } from './charts/TelemetryCharts'
import { PlaybackWorkspace } from './playback/PlaybackWorkspace'
import { PropulsionCampaignPanel } from './panels/PropulsionCampaignPanel'

function ApiStatus() {
  const health = useQuery({
    queryKey: ['health'],
    queryFn: () => api.get<{ status: string; version: string }>('/health'),
    refetchInterval: 15000,
    retry: 1,
  })
  if (health.isLoading) return <span className="text-xs text-slate-500">API…</span>
  if (health.isError || !health.data) return <span className="text-xs text-rose-400">API offline</span>
  return (
    <span className="flex items-center gap-1 text-xs text-emerald-500">
      <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
      API v{health.data.version}
    </span>
  )
}

export default function App() {
  const design = useDesignStore((s) => s.design)
  const result = useDesignStore((s) => s.result)
  const setSnapshot = useDesignStore((s) => s.setSnapshot)
  const reference = useReferenceDesign()
  const preview = usePreview(design)
  const cog = preview.data?.cog_m ?? computeCog(design)
  const principalAxes = preview.data?.principal_axes ?? null

  // First load: seed the editor with the reference design when empty.
  useEffect(() => {
    if (reference.data && design.parts.length === 0 && design.rotors.length === 0) {
      setSnapshot(reference.data.snapshot, null)
    }
  }, [reference.data, design.parts.length, design.rotors.length, setSnapshot])

  return (
    <div className="flex h-screen flex-col bg-slate-950 text-slate-200">
      <header className="flex items-center gap-3 border-b border-slate-800 px-4 py-2">
        <h1 className="text-lg font-semibold tracking-tight">AeroForge</h1>
        <span className="text-xs text-slate-500">
          physics-based drone simulation lab · multi-rotor v1
        </span>
        <div className="ml-auto">
          <ApiStatus />
        </div>
      </header>
      <main className="flex min-h-0 flex-1">
        <aside className="w-80 shrink-0 overflow-y-auto border-r border-slate-800">
          <ComponentInspector />
          <div className="border-t border-slate-800"><DesignPanel /></div>
          <div className="border-t border-slate-800">
            <ScenarioPanel />
          </div>
          <div className="border-t border-slate-800">
            <StructuralLabPanel design={design} />
          </div>
          <div className="border-t border-slate-800">
            <CombinedMetalPanel design={design} />
          </div>
          <div className="border-t border-slate-800">
            <BatteryEvidencePanel design={design} />
          </div>
          <div className="border-t border-slate-800">
            <DischargeReplayPanel design={design} />
          </div>
          <div className="border-t border-slate-800">
            <BatteryCampaignPanel design={design} />
          </div>
          <div className="border-t border-slate-800">
            <PropulsionEvidencePanel design={design} />
          </div>
        </aside>
        <section className="relative min-w-0 flex-1">
          <PlaybackWorkspace design={design} cog={cog} principalAxes={principalAxes} result={result} />
        </section>
        <aside className="w-96 shrink-0 overflow-y-auto border-l border-slate-800">
          <ResultsPanel result={result} />
          <div className="border-t border-slate-800"><FlightEvidencePanel result={result} /></div>
          <div className="border-t border-slate-800"><PublicEvidencePanel /></div>
          <div className="border-t border-slate-800"><G30PublicBenchPanel /></div>
          <div className="border-t border-slate-800"><PropulsionCampaignPanel /></div>
          <div className="border-t border-slate-800"><TelemetryAuditPanel /></div>
          <div className="border-t border-slate-800"><ValidationProtocolPanel /></div>
          <div className="border-t border-slate-800"><HILEvidencePanel /></div>
          <div className="border-t border-slate-800">
            <TelemetryCharts result={result} />
          </div>
        </aside>
      </main>
    </div>
  )
}
