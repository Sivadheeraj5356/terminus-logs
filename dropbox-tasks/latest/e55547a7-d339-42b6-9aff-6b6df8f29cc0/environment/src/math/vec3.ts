export interface Vec3 {
  x: number;
  y: number;
  z: number;
}

export function add(a: Vec3, b: Vec3): Vec3 {
  return { x: a.x + b.x, y: a.y + b.y, z: a.z + b.z };
}

export function sub(a: Vec3, b: Vec3): Vec3 {
  return { x: a.x - b.x, y: a.y - b.y, z: a.z - b.z };
}

export function scale(v: Vec3, s: number): Vec3 {
  return { x: v.x * s, y: v.y * s, z: v.z * s };
}

export function dot(a: Vec3, b: Vec3): number {
  return a.x * b.x + a.y * b.y + a.z * b.z;
}

export function mag(v: Vec3): number {
  return Math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z);
}

export function unit(v: Vec3): Vec3 {
  const m = mag(v);
  if (m < 1e-15) return { x: 1, y: 0, z: 0 };
  return { x: v.x / m, y: v.y / m, z: v.z / m };
}

export function cross(a: Vec3, b: Vec3): Vec3 {
  return {
    x: a.y * b.z - a.z * b.y,
    y: a.z * b.x - a.x * b.z,
    z: a.x * b.y - a.y * b.x,
  };
}

export function ortho_basis(n: Vec3): { u: Vec3; w: Vec3 } {
  const ref = Math.abs(n.x) < 0.9 ? { x: 1, y: 0, z: 0 } : { x: 0, y: 1, z: 0 };
  const u = unit(cross(n, ref));
  const w = cross(n, u);
  return { u, w };
}

export function round6(v: number): number {
  return Math.round(v * 1e6) / 1e6;
}

export function round6v(v: Vec3): Vec3 {
  return { x: round6(v.x), y: round6(v.y), z: round6(v.z) };
}
