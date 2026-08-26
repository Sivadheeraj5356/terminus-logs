import { Body, CollisionEpoch } from "../types";
import { Vec3, add, scale, sub, unit, mag, ortho_basis } from "../math/vec3";
import { DEFAULT_CD } from "../math/constants";

export function spawnFragments(
  a: Body,
  b: Body,
  fragmentCount: number,
  minSep: number,
  tSec: number,
): { fragments: Body[]; epoch: CollisionEpoch } {
  const M = a.mass_kg + b.mass_kg;
  const mf = M / fragmentCount;
  const rf = Math.cbrt((Math.pow(a.radius_m, 3) + Math.pow(b.radius_m, 3)) / fragmentCount);

  const collisionPt: Vec3 = {
    x: (a.pos_m.x * a.mass_kg + b.pos_m.x * b.mass_kg) / M,
    y: (a.pos_m.y * a.mass_kg + b.pos_m.y * b.mass_kg) / M,
    z: (a.pos_m.z * a.mass_kg + b.pos_m.z * b.mass_kg) / M,
  };

  const vCm: Vec3 = {
    x: (a.mass_kg * a.vel_mps.x + b.mass_kg * b.vel_mps.x) / M,
    y: (a.mass_kg * a.vel_mps.y + b.mass_kg * b.vel_mps.y) / M,
    z: (a.mass_kg * a.vel_mps.z + b.mass_kg * b.vel_mps.z) / M,
  };

  const speed = mag(vCm) / fragmentCount;

  const relDir = unit(sub(a.vel_mps, b.vel_mps));
  const { u, w } = ortho_basis(relDir);

  const parents: [string, string] = a.id < b.id ? [a.id, b.id] : [b.id, a.id];

  const fragments: Body[] = [];
  const childIds: string[] = [];

  for (let k = 0; k < fragmentCount; k++) {
    const theta = (k * 2 * Math.PI) / fragmentCount;
    const dir: Vec3 = add(scale(u, Math.cos(theta)), scale(w, Math.sin(theta)));
    const vel = add(vCm, scale(dir, speed));
    const pos = add(collisionPt, scale(dir, minSep));
    const childId = `${parents[0]}__${parents[1]}__f${k}`;
    childIds.push(childId);
    fragments.push({
      id: childId,
      mass_kg: mf,
      radius_m: rf,
      pos_m: pos,
      vel_mps: vel,
      cd: DEFAULT_CD,
    });
  }

  const pTotal = scale(add(scale(a.vel_mps, a.mass_kg), scale(b.vel_mps, b.mass_kg)), 1);
  const pFrags = fragments.reduce(
    (acc, f) => add(acc, scale(f.vel_mps, f.mass_kg)),
    { x: 0, y: 0, z: 0 } as Vec3,
  );
  const momentumResidual = mag(sub(pTotal, pFrags));

  const eTotal =
    0.5 * a.mass_kg * Math.pow(mag(a.vel_mps), 2) +
    0.5 * b.mass_kg * Math.pow(mag(b.vel_mps), 2);
  const eFrags = fragments.reduce(
    (acc, f) => acc + 0.5 * f.mass_kg * Math.pow(mag(f.vel_mps), 2),
    0,
  );
  const energyResidual = Math.abs(eTotal - eFrags);

  return {
    fragments,
    epoch: {
      t_sec: Math.round(tSec * 1e6) / 1e6,
      parents,
      child_ids: childIds,
      momentum_residual: Math.round(momentumResidual * 1e6) / 1e6,
      energy_residual: Math.round(energyResidual * 1e6) / 1e6,
    },
  };
}
