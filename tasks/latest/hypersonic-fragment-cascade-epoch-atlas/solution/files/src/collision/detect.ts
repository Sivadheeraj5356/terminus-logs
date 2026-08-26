import { Body } from "../types";
import { sub, mag } from "../math/vec3";

export interface CollisionPair {
  i: number;
  j: number;
  dist: number;
}

export function detectCollision(bodies: Body[]): CollisionPair | null {
  let best: CollisionPair | null = null;
  for (let i = 0; i < bodies.length; i++) {
    for (let j = i + 1; j < bodies.length; j++) {
      const d = mag(sub(bodies[i].pos_m, bodies[j].pos_m));
      const threshold = bodies[i].radius_m + bodies[j].radius_m;
      if (d < threshold) {
        const idA = bodies[i].id < bodies[j].id ? bodies[i].id : bodies[j].id;
        const idB = bodies[i].id < bodies[j].id ? bodies[j].id : bodies[i].id;
        if (!best) {
          best = { i, j, dist: d };
        } else {
          const bestIdA = bodies[best.i].id < bodies[best.j].id ? bodies[best.i].id : bodies[best.j].id;
          const bestIdB = bodies[best.i].id < bodies[best.j].id ? bodies[best.j].id : bodies[best.i].id;
          if (idA < bestIdA || (idA === bestIdA && idB < bestIdB)) {
            best = { i, j, dist: d };
          }
        }
      }
    }
  }
  return best;
}
