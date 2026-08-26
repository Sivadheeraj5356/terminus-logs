import { Body } from "../types";
import { Vec3, add, scale, mag, dot } from "../math/vec3";
import { MU_EARTH, R_EARTH, RHO0, SCALE_H } from "../math/constants";

function gravity(pos: Vec3): Vec3 {
  const r = mag(pos);
  if (r < 1) return { x: 0, y: 0, z: 0 };
  const factor = -MU_EARTH / (r * r * r);
  return { x: pos.x * factor, y: pos.y * factor, z: pos.z * factor };
}

function dragAccel(pos: Vec3, vel: Vec3, body: Body, densityScale: number): Vec3 {
  const r = mag(pos);
  const alt = r - R_EARTH;
  if (alt < 0) return { x: 0, y: 0, z: 0 };
  const rho = RHO0 * Math.exp(-alt / SCALE_H) * densityScale;
  const area = Math.PI * body.radius_m * body.radius_m;
  const speed = mag(vel);
  if (speed < 1e-15 || body.mass_kg < 1e-15) return { x: 0, y: 0, z: 0 };
  const coeff = -0.5 * rho * body.cd * area * speed / body.mass_kg;
  return { x: vel.x * coeff, y: vel.y * coeff, z: vel.z * coeff };
}

function accel(pos: Vec3, vel: Vec3, body: Body, densityScale: number): Vec3 {
  const g = gravity(pos);
  const d = dragAccel(pos, vel, body, densityScale);
  return add(g, d);
}

export function propagateStep(body: Body, dt: number, densityScale: number): void {
  const a0 = accel(body.pos_m, body.vel_mps, body, densityScale);
  const pMid = add(body.pos_m, scale(body.vel_mps, dt / 2));
  const vMid = add(body.vel_mps, scale(a0, dt / 2));
  const a1 = accel(pMid, vMid, body, densityScale);
  body.pos_m = add(body.pos_m, scale(body.vel_mps, dt));
  body.vel_mps = add(body.vel_mps, scale(a1, dt));
}
