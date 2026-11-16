import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { ComponentInspector } from '../editor/ComponentInspector'
import { useDesignStore } from '../state/designStore'
import type { DroneDesign } from '../types/api'

const design: DroneDesign = {
  schema_version: '0.1', name: 'tiny',
  parts: [
    { name: 'frame', mass_kg: 1, position_m: [0, 0, 0] },
    { name: 'battery', mass_kg: 0.5, position_m: [0, 0, 0] },
  ],
  rotors: [{ position_m: [0.25, 0.25, 0], spin_direction: 1 }],
  rotor_torque_per_thrust_n_m_per_n: 0.01,
}
beforeEach(() => useDesignStore.getState().setSnapshot(structuredClone(design), null))
afterEach(() => cleanup())

describe('3D component inspector UI', () => {
  it('disables independent position editing when attached, then unlocks on detach', () => {
    useDesignStore.getState().setSnapshot({
      ...structuredClone(design),
      frame: { arm_length_m: .25, tube_od_m: .012, tube_id_m: .009,
        material_id: 'cfrp_quasi_iso' },
    }, null)
    render(<ComponentInspector />)
    fireEvent.change(screen.getByLabelText('Selected component'), {
      target: { value: 'battery' },
    })
    fireEvent.click(screen.getByRole('button', { name: /Create mount at component CoG/i }))
    expect((screen.getByLabelText('Position X [m]') as HTMLInputElement).disabled).toBe(true)
    fireEvent.click(screen.getByRole('button', { name: /Detach component from mount/i }))
    expect((screen.getByLabelText('Position X [m]') as HTMLInputElement).disabled).toBe(false)
  })
  it('adds and edits a physical point-mass payload through the form', () => {
    render(<ComponentInspector />)
    fireEvent.click(screen.getByRole('button', { name: /add payload point mass/i }))
    expect(useDesignStore.getState().selectedPart).toBe('payload_1')
    fireEvent.change(screen.getByLabelText('Position X [m]'), { target: { value: '0.75' } })
    expect(useDesignStore.getState().design.parts.find((p) => p.name === 'payload_1')?.position_m[0]).toBe(0.75)
    fireEvent.click(screen.getByRole('button', { name: 'Undo' }))
    expect(useDesignStore.getState().design.parts.find((p) => p.name === 'payload_1')?.position_m[0]).toBe(0)
  })
  it('locks coupled structural components', () => {
    render(<ComponentInspector />)
    fireEvent.change(screen.getByLabelText('Selected component'), { target: { value: 'frame' } })
    expect((screen.getByLabelText('Position X [m]') as HTMLInputElement).disabled).toBe(true)
    expect(screen.getByText(/Coupled part locked/i)).toBeDefined()
  })
  it('shows a measured component distance', () => {
    render(<ComponentInspector />)
    fireEvent.click(screen.getByRole('button', { name: /add payload point mass/i }))
    fireEvent.change(screen.getByLabelText('Position X [m]'), { target: { value: '0.4' } })
    fireEvent.change(screen.getByLabelText('Measure from'), { target: { value: 'battery' } })
    fireEvent.change(screen.getByLabelText('Measure to'), { target: { value: 'payload_1' } })
    expect(screen.getByTestId('component-distance').textContent).toMatch(/0\.400 m/)
  })
})
