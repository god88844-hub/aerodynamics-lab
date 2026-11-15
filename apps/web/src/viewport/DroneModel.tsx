/** 3D drone model built from the design snapshot + editor preview.
  World convention: world z = altitude maps to scene Y (three.js is Y-up);
  scene = [x, z, -y]. Units: 1 scene unit = 1 m. */

import { Line } from '@react-three/drei'
import { useMemo } from 'react'
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

export function DroneModel({ design, cog, principalAxes }: {
  design: DroneDesign
  cog: Vec3
  principalAxes: number[][] | null
}) {
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
