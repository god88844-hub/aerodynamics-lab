/** M10.2 component tree, precise edits and center-to-center measurements.
 * The numeric editor operates on the physical mass/CoG snapshot, not mesh geometry. */
import { useDesignStore, canMovePart, componentSeparationM } from '../state/designStore'
import type { Vec3 } from '../types/api'
import { SectionTitle } from '../panels/fields'

export function ComponentInspector() {
  const { design, selectedPart, selectPart, setPartPosition, setPartMass,
    addPayload, removeSelectedPayload, undo, redo, past, future,
    measureFrom, measureTo, setMeasureFrom, setMeasureTo,
    gizmoEnabled, setGizmoEnabled, snapStepM, setSnapStepM } = useDesignStore()
  const part = design.parts.find((p) => p.name === selectedPart)
  const movable = part ? canMovePart(part.name) : false
  const distance = componentSeparationM(design, measureFrom, measureTo)
  const measurementOptions = [
    <option value="" key="none">— select component —</option>,
    ...design.parts.map((p) => <option key={p.name} value={p.name}>{p.name}</option>),
  ]
  const updateCoordinate = (axis: number, value: number) => {
    if (!part || !movable || !Number.isFinite(value)) return
    const next: Vec3 = [...part.position_m]
    next[axis] = value
    setPartPosition(part.name, next)
  }

  return (
    <section className="space-y-3 p-3" aria-label="3D component inspector">
      <div className="flex items-center justify-between">
        <SectionTitle>3D component editor</SectionTitle>
        <div className="flex gap-1">
          <button type="button" onClick={undo} disabled={past.length === 0}
            title="Undo last design edit" aria-label="Undo"
            className="rounded border border-slate-700 px-2 py-1 text-xs disabled:opacity-40">↶</button>
          <button type="button" onClick={redo} disabled={future.length === 0}
            title="Redo design edit" aria-label="Redo"
            className="rounded border border-slate-700 px-2 py-1 text-xs disabled:opacity-40">↷</button>
        </div>
      </div>
      <p className="text-[10px] text-slate-500">
        Select a component here or click its marker in the 3D view.
        Coordinates locate part centers of gravity (m).
      </p>
      <div className="space-y-2 rounded border border-slate-800 bg-slate-900/40 p-2">
        <label className="flex items-center gap-2 text-xs text-slate-300">
          <input type="checkbox" aria-label="Enable 3D translate handles"
            checked={gizmoEnabled} onChange={(e) => setGizmoEnabled(e.target.checked)}
            className="accent-cyan-500" />
          Drag selected battery/payload using 3D axis handles
        </label>
        <label className="flex items-center justify-between gap-2 text-xs text-slate-400">
          Grid snap
          <select aria-label="Translation snap increment" value={snapStepM}
            onChange={(e) => setSnapStepM(Number(e.target.value))}
            className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs">
            <option value={0}>Off</option>
            <option value={0.005}>5 mm</option>
            <option value={0.01}>10 mm</option>
            <option value={0.05}>50 mm</option>
            <option value={0.1}>100 mm</option>
          </select>
        </label>
        <p className="text-[10px] text-slate-500">
          Dragging commits one undoable design edit on release. Rotor/ESC/frame parts
          stay locked to preserve coupled physics assumptions.
        </p>
      </div>
      <label className="block space-y-1 text-xs text-slate-300">
        <span>Component ({design.parts.length})</span>
        <select value={selectedPart ?? ''} onChange={(e) => selectPart(e.target.value || null)}
          aria-label="Selected component"
          className="w-full rounded border border-slate-700 bg-slate-900 px-2 py-2 text-xs">
          {measurementOptions}
        </select>
      </label>
      <div className="max-h-32 space-y-0.5 overflow-y-auto rounded border border-slate-800 p-1"
        aria-label="Component hierarchy">
        {design.parts.map((p) => (
          <button key={p.name} type="button" onClick={() => selectPart(p.name)}
            aria-pressed={selectedPart === p.name}
            className={`block w-full truncate rounded px-2 py-1 text-left text-xs ${
              selectedPart === p.name ? 'bg-cyan-950 text-cyan-200' : 'text-slate-400 hover:bg-slate-900'
            }`}>
            {p.name} <span className="float-right font-mono">{p.mass_kg.toFixed(3)} kg</span>
          </button>
        ))}
      </div>
      {part && (
        <div className="space-y-2 rounded border border-slate-800 bg-slate-900/40 p-2">
          <p className="truncate text-xs font-semibold text-cyan-300">{part.name}</p>
          {(['X', 'Y', 'Z'] as const).map((axis, i) => (
            <label key={axis} className="flex items-center justify-between text-xs text-slate-400">
              Position {axis} [m]
              <input type="number" aria-label={`Position ${axis} [m]`} step="0.005"
                disabled={!movable} value={part.position_m[i]}
                onChange={(e) => updateCoordinate(i, Number(e.target.value))}
                className="w-28 rounded border border-slate-700 bg-slate-950 px-2 py-1 text-right font-mono disabled:opacity-40" />
            </label>
          ))}
          <label className="flex items-center justify-between text-xs text-slate-400">
            Mass [kg]
            <input type="number" aria-label="Component mass [kg]" step="0.05" min="0.001"
              disabled={!movable} value={part.mass_kg}
              onChange={(e) => setPartMass(part.name, Number(e.target.value))}
              className="w-28 rounded border border-slate-700 bg-slate-950 px-2 py-1 text-right font-mono disabled:opacity-40" />
          </label>
          {!movable && (
            <p className="text-[10px] text-amber-400">
              Coupled part locked: edit arm length or sourced component data to preserve the motor/rotor and structural model.
            </p>
          )}
          {part.name.startsWith('payload_') && (
            <button type="button" onClick={removeSelectedPayload}
              className="rounded border border-rose-800 px-2 py-1 text-xs text-rose-300">
              Remove selected payload
            </button>
          )}
        </div>
      )}
      <button type="button" onClick={addPayload}
        className="w-full rounded border border-cyan-900 bg-cyan-950/40 px-2 py-2 text-xs text-cyan-200">
        + Add payload point mass
      </button>
      <div className="space-y-2 border-t border-slate-800 pt-2">
        <SectionTitle>Measure component spacing</SectionTitle>
        <label className="flex items-center justify-between gap-2 text-xs">
          <span className="text-slate-400">From</span>
          <select value={measureFrom ?? ''} onChange={(e) => setMeasureFrom(e.target.value || null)}
            aria-label="Measure from"
            className="w-44 rounded border border-slate-700 bg-slate-900 px-1 py-1 text-xs">
            {measurementOptions}
          </select>
        </label>
        <label className="flex items-center justify-between gap-2 text-xs">
          <span className="text-slate-400">To</span>
          <select value={measureTo ?? ''} onChange={(e) => setMeasureTo(e.target.value || null)}
            aria-label="Measure to"
            className="w-44 rounded border border-slate-700 bg-slate-900 px-1 py-1 text-xs">
            {measurementOptions}
          </select>
        </label>
        <p className="font-mono text-sm text-yellow-300" data-testid="component-distance">
          {distance === null ? 'Choose two components' : `${distance.toFixed(3)} m center-to-center`}
        </p>
        <p className="text-[10px] text-slate-500">
          Marker and measurement visuals are schematic. Payloads are point masses; size,
          aerodynamics, collision and clearance are not computed by this editor.
        </p>
      </div>
    </section>
  )
}
