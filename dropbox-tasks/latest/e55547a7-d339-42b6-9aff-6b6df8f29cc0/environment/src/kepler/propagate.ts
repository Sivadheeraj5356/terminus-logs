import { Body } from "../types";
import { Vec3, add, scale, mag } from "../math/vec3";
import { MU_EARTH } from "../math/constants";

function gravity(pos: Vec3): Vec3 {
  const r = mag(pos);
  const factor = -MU_EARTH / (r * r * r);
  return { x: pos.x * factor, y: pos.y * factor, z: pos.z * factor };
}

function accel(pos: Vec3, vel: Vec3, body: Body, _densityScale: number): Vec3 {
  return gravity(pos);
}

export function propagateStep(body: Body, dt: number, densityScale: number): void {
  const a0 = accel(body.pos_m, body.vel_mps, body, densityScale);
  body.pos_m = add(body.pos_m, scale(body.vel_mps, dt));
  body.vel_mps = add(body.vel_mps, scale(a0, dt));
}
