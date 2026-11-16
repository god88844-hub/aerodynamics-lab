/** 3D viewport: design model, CoG/principal axes, flight path telemetry,
  orbit controls. Scene mapping: world (x, y, z-up) -> scene (x, z, -y). */

import { Grid, OrbitControls } from '@react-three/drei'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import * as THREE from 'three'
import { Line } from '@react-three/drei'
import type { DroneDesign, SimulationResult, Vec3 } from '../types/api'
import { DroneModel } from './DroneModel'
import type { FlightPose } from '../playback/flightPlayback'
import { hasSpatialTelemetry } from '../playback/flightPlayback'

const frameRotation = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), -Math.PI / 2)

function worldToScene(v: Vec3): [number, number, number] {
  return [v[0], v[2], -v[1]]
}

function sceneAttitude(q: NonNullable<FlightPose['attitude_world_wxyz']>): THREE.Quaternion {
  const qWorld = new THREE.Quaternion(q[1], q[2], q[3], q[0])
  return frameRotation.clone().multiply(qWorld).multiply(frameRotation.clone().invert()).normalize()
}

function FollowCamera({ positionWorld }: { positionWorld: Vec3 | null }) {
  const camera = useThree((state) => state.camera)
  useFrame((_, delta) => {
    if (!positionWorld) return
    const target = new THREE.Vector3(...worldToScene(positionWorld))
    const desired = target.clone().add(new THREE.Vector3(1.6, 0.9, 1.8))
    const smoothing = 1 - Math.exp(-5 * Math.min(delta, 0.2))
    camera.position.lerp(desired, smoothing)
    camera.lookAt(target)
  })
  return null
}

function FlightPath({ telemetry }: { telemetry: NonNullable<SimulationResult['telemetry']> }) {
  const n = telemetry.t.length
  if (!hasSpatialTelemetry(telemetry) || n < 2) return null
  const step = Math.max(1, Math.floor(n / 400))
  const points: [number, number, number][] = []
  for (let i = 0; i < n; i += step) {
    points.push([telemetry.x[i], telemetry.z[i], -telemetry.y[i]])
  }
  const final: [number, number, number] = worldToScene([telemetry.x[n - 1], telemetry.y[n - 1], telemetry.z[n - 1]])
  if (points[points.length - 1].some((v, i) => v !== final[i])) points.push(final)
  const last = points[points.length - 1]
  const first = points[0]
  return (
    <group>
      <Line points={points} color="#22d3ee" lineWidth={2} />
      <mesh position={first}>
        <sphereGeometry args={[0.03, 12, 12]} />
        <meshStandardMaterial color="#22c55e" />
      </mesh>
      <mesh position={last}>
        <sphereGeometry args={[0.03, 12, 12]} />
        <meshStandardMaterial color="#f43f5e" />
      </mesh>
    </group>
  )
}

export function DroneViewport({ design, cog, principalAxes, result, pose = null, follow = false }: {
  design: DroneDesign
  cog: Vec3
  principalAxes: number[][] | null
  result: SimulationResult | null
  pose?: FlightPose | null
  follow?: boolean
}) {
  const scale = 8 // grid spans ±4 m around the drone
  const position: [number, number, number] = pose ? worldToScene(pose.position_world_m) : [0, 0, 0]
  const quaternion = pose?.attitude_world_wxyz ? sceneAttitude(pose.attitude_world_wxyz) : undefined
  return (
    <Canvas camera={{ position: [1.6, 1.2, 2.2], fov: 45 }} shadows={false}>
      <color attach="background" args={['#0b1120']} />
      <ambientLight intensity={0.5} />
      <directionalLight position={[3, 6, 2]} intensity={1.2} />
      <Grid
        args={[scale * 2, scale * 2]}
        cellSize={0.25}
        cellThickness={0.5}
        sectionSize={1}
        sectionThickness={1}
        cellColor="#1e293b"
        sectionColor="#334155"
        infiniteGrid={false}
        fadeDistance={30}
      />
      <group position={position} quaternion={quaternion}>
        <DroneModel design={design} cog={cog} principalAxes={principalAxes} />
      </group>
      {result?.telemetry && <FlightPath telemetry={result.telemetry} />}
      {follow && <FollowCamera positionWorld={pose?.position_world_m ?? null} />}
      <OrbitControls makeDefault enabled={!follow} />
    </Canvas>
  )
}
