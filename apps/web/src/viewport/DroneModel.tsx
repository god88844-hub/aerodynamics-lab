/** 3D drone model built from the design snapshot + editor preview.
  World convention: world z = altitude maps to scene Y (three.js is Y-up);
  scene = [x, z, -y]. Units: 1 scene unit = 1 m. */

import { Html, Line, TransformControls } from '@react-three/drei'
import { useDesignStore, componentSeparationM } from '../state/designStore'
import { useMemo, useRef } from 'react'
import { bodyPointToScene, scenePointToBody, snapBodyPoint } from '../editor/geometryChecks'
import { canMovePart } from '../state/designStore'
import * as THREE from 'three'
import type { DroneDesign, Vec3 } from '../types/api'

const ARM_COLOR = '#94a3b8'
const BODY_COLOR = '#475569'
const MOTOR_COLOR = '#f59e0b'
const PROP_COLOR = '#38bdf8'
const BATTERY_COLOR = '#a3e635'
const COG_COLOR = '#c084fc'

function worldToScene(v: Vec3): [number, number, number] {
  return [v[0], v[2], -v[1]]
}

/** Translation controls apply to an editor-only group; the store commits
 * exactly once on pointer release. All positions remain body-frame SI. */
function DragHandle({ name, position, stepM }: {
  name: string
  position: Vec3
  stepM: number
}) {
  const group = useRef<THREE.Group>(null)
  const move = useDesignStore((s) => s.setPartPosition)
  const setDragging = useDesignStore((s) => s.setGizmoDragging)
  const commit = () => {
    setDragging(false)
    const p = group.current?.position
    if (!p) return
    const body = scenePointToBody([p.x, p.y, p.z])
    move(name, snapBodyPoint(body, stepM))
  }
  return (
    <TransformControls mode="translate"
      translationSnap={stepM > 0 ? stepM : undefined}
      onMouseDown={() => setDragging(true)}
      onMouseUp={commit}>
      <group ref={group} position={bodyPointToScene(position)}>
        <mesh>
          <sphereGeometry args={[0.025, 16, 16]} />
          <meshStandardMaterial color="#fde047" emissive="#ca8a04" emissiveIntensity={0.4} />
        </mesh>
      </group>
    </TransformControls>
  )
}

/** Cylinder from point a to point b (scene coords). */
function Arm({ a, b, radius = 0.008 }: { a: [number, number, number]; b: [number, number, number]; radius?: number }) {
  const { pos, quat, len } = useMemo(() => {
    const va = new THREE.Vector3(...a)
    const vb = new THREE.Vector3(...b)
    const dir = vb.clone().sub(va)
    const len = dir.length()
    const quat = new THREE.Quaternion().setFromUnitVectors(
      new THREE.Vector3(0, 1, 0),
      dir.clone().normalize(),
    )
    const pos = va.clone().add(vb).multiplyScalar(0.5)
    return { pos, quat, len }
  }, [a, b])
  return (
    <mesh position={pos} quaternion={quat}>
      <cylinderGeometry args={[radius, radius, len, 12]} />
      <meshStandardMaterial color={ARM_COLOR} />
    </mesh>
  )
}

export function DroneModel({ design, cog, principalAxes, editingEnabled = true }: {
  design: DroneDesign
  cog: Vec3
  principalAxes: number[][] | null
  editingEnabled?: boolean
}) {
  const selectedPart = useDesignStore((s) => s.selectedPart)
  const gizmoEnabled = useDesignStore((s) => s.gizmoEnabled)
  const snapStepM = useDesignStore((s) => s.snapStepM)
  const selectPart = useDesignStore((s) => s.selectPart)
  const measureFrom = useDesignStore((s) => s.measureFrom)
  const measureTo = useDesignStore((s) => s.measureTo)
  const measuredDistance = componentSeparationM(design, measureFrom, measureTo)
  const startPart = design.parts.find((p) => p.name === measureFrom)
  const endPart = design.parts.find((p) => p.name === measureTo)
  const motorParts = design.parts.filter((p) => p.name.startsWith('motor_'))
  const escParts = design.parts.filter((p) => p.name.startsWith('esc_'))
  const propParts = design.parts.filter((p) => p.name.startsWith('prop_'))
  const battery = design.parts.find((p) => p.name.toLowerCase().includes('battery'))

  const propRadius = useMemo(() => {
    // 0.5 * diameter in inches -> m; the design stores no prop diameter per
    // rotor, so use the powertrain propeller if referenced, else 0.19 m (15").
    return 0.19
  }, [])

  return (
    <group>
      {/* center plate */}
      <mesh position={worldToScene([0, 0, 0])}>
        <boxGeometry args={[0.16, 0.03, 0.16]} />
        <meshStandardMaterial color={BODY_COLOR} />
      </mesh>

      {/* arms: center plate edge -> each motor */}
      {motorParts.map((p, i) => {
        const start: Vec3 = [p.position_m[0] * 0.35, p.position_m[1] * 0.35, 0]
        const a = worldToScene(start)
        const b = worldToScene(p.position_m)
        return (
          <group key={p.name}>
            <Arm a={a} b={b} />
            <mesh position={worldToScene(p.position_m)}>
              <cylinderGeometry args={[0.021, 0.021, 0.035, 16]} />
              <meshStandardMaterial color={MOTOR_COLOR} />
            </mesh>
            {i === 0 && <OriginMarker />}
          </group>
        )
      })}

      {/* ESC hints */}
      {escParts.map((p) => (
        <mesh key={p.name} position={worldToScene(p.position_m)}>
          <boxGeometry args={[0.03, 0.008, 0.03]} />
          <meshStandardMaterial color="#334155" />
        </mesh>
      ))}

      {/* propeller discs (semi-transparent) */}
      {propParts.map((p) => (
        <mesh key={p.name} position={worldToScene(p.position_m)} rotation={[0, 0, 0]}>
          <cylinderGeometry args={[propRadius, propRadius, 0.004, 32]} />
          <meshStandardMaterial color={PROP_COLOR} transparent opacity={0.35} />
        </mesh>
      ))}

      {/* battery */}
      {battery && (
        <mesh position={worldToScene(battery.position_m)}>
          <boxGeometry args={[0.16, 0.06, 0.09]} />
          <meshStandardMaterial color={BATTERY_COLOR} />
        </mesh>
      )}

      {/* Every part has a clickable center-of-gravity anchor; mesh sizes are
          schematic, not dimensions used for structural or clearance analysis. */}
      {design.parts.map((p) => {
        const selected = p.name === selectedPart
        if (selected && canMovePart(p.name) && gizmoEnabled && editingEnabled) return null
        return (
          <mesh key={p.name} name={p.name} position={worldToScene(p.position_m)}
            userData={{ partName: p.name }}
            onClick={(event) => { event.stopPropagation(); selectPart(p.name) }}>
            <sphereGeometry args={[selected ? 0.022 : 0.012, 14, 14]} />
            <meshStandardMaterial color={selected ? '#fef08a' : '#38bdf8'}
              emissive={selected ? '#ca8a04' : '#164e63'} emissiveIntensity={0.35} />
          </mesh>
        )
      })}
      {editingEnabled && gizmoEnabled &&
        design.parts.filter((p) => p.name === selectedPart && canMovePart(p.name))
          .map((p) => <DragHandle key={p.name} name={p.name}
            position={p.position_m} stepM={snapStepM} />)}
      {selectedPart && design.parts.some((p) => p.name === selectedPart) && (
        <Html position={worldToScene(design.parts.find((p) => p.name === selectedPart)!.position_m)}
          center distanceFactor={6} style={{ pointerEvents: 'none' }}>
          <span className="whitespace-nowrap rounded bg-slate-950/90 px-2 py-1 text-[10px] text-cyan-100">
            {selectedPart}
          </span>
        </Html>
      )}
      {startPart && endPart && measuredDistance !== null && measuredDistance > 0 && (
        <group>
          <Line points={[worldToScene(startPart.position_m), worldToScene(endPart.position_m)]}
            color="#facc15" lineWidth={2} />
          <Html position={worldToScene([
            (startPart.position_m[0] + endPart.position_m[0]) / 2,
            (startPart.position_m[1] + endPart.position_m[1]) / 2,
            (startPart.position_m[2] + endPart.position_m[2]) / 2,
          ])} center distanceFactor={6} style={{ pointerEvents: 'none' }}>
            <span className="whitespace-nowrap rounded bg-yellow-950/95 px-2 py-1 font-mono text-[10px] text-yellow-200">
              {measuredDistance.toFixed(3)} m
            </span>
          </Html>
        </group>
      )}

      {/* center of gravity marker */}
      <mesh position={worldToScene(cog)}>
        <sphereGeometry args={[0.014, 16, 16]} />
        <meshStandardMaterial color={COG_COLOR} emissive={COG_COLOR} emissiveIntensity={0.6} />
      </mesh>

      {/* principal axes through the CoG (from the API preview) */}
      {principalAxes && (
        <PrincipalAxes cog={cog} axes={principalAxes} />
      )}
    </group>
  )
}

function OriginMarker() {
  return null
}

function PrincipalAxes({ cog, axes }: { cog: Vec3; axes: number[][] }) {
  // axes: 3 columns of the principal-axes matrix (body frame), scaled by the
  // normalized square roots of the principal moments for visual balance.
  const cols = [
    [axes[0][0], axes[1][0], axes[2][0]],
    [axes[0][1], axes[1][1], axes[2][1]],
    [axes[0][2], axes[1][2], axes[2][2]],
  ]
  const colors = ['#ef4444', '#22c55e', '#3b82f6']
  const c = worldToScene(cog)
  return (
    <group>
      {cols.map((col, i) => {
        const dir = new THREE.Vector3(col[0], col[2], -col[1]).normalize().multiplyScalar(0.12)
        const end: [number, number, number] = [c[0] + dir.x, c[1] + dir.y, c[2] + dir.z]
        return (
          <Line
            key={i}
            points={[c, end]}
            color={colors[i]}
            lineWidth={2}
          />
        )
      })}
    </group>
  )
}
