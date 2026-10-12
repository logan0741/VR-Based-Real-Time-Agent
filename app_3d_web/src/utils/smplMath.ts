import * as THREE from 'three';

/**
 * Convert a Rodrigues rotation vector (axis-angle) to a THREE.Quaternion.
 * Three.js uses a Right-Handed coordinate system (Y-up, Z-backward).
 * SMPL-X uses a Right-Handed coordinate system but often with Y-down or Z-forward (OpenCV convention).
 * To map correctly, we typically flip the Y and Z axes.
 * 
 * @param rot Array of 3 floats [rx, ry, rz]
 * @returns THREE.Quaternion
 */
export function quatFromRodrigues(rot: number[]): THREE.Quaternion {
  if (!rot || rot.length !== 3) return new THREE.Quaternion();

  const [rx, ry, rz] = rot;
  const theta = Math.sqrt(rx * rx + ry * ry + rz * rz);

  if (theta < 1e-6) {
    return new THREE.Quaternion(0, 0, 0, 1);
  }

  // SMPLX.cs QuatFromRodrigues: axis=(-rx, ry, rz), angle=-theta
  // ≡ axis=(rx, -ry, -rz), angle=+theta  (verified from smplx_integration_status.md)
  const axis = new THREE.Vector3(rx / theta, -ry / theta, -rz / theta);
  
  const quat = new THREE.Quaternion();
  quat.setFromAxisAngle(axis, theta);
  
  return quat;
}
