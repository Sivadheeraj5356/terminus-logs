import { Body } from "../types";
import { mag, sub } from "../math/vec3";

export function detectCollision(
  bodies: Body[],
): { i: number; j: number; dist: number } | null {
  let best: { i: number; j: number; dist: number } | null = null;
  for (let i = 0; i < bodies.length; i++) {
    for (let j = i + 1; j < bodies.length; j++) {
      const d = mag(sub(bodies[i].pos_m, bodies[j].pos_m));
      if (d < 1.0) {
        if (!best || d < best.dist ||
            (d === best.dist && (bodies[i].id < bodies[best.i].id ||
             (bodies[i].id === bodies[best.i].id && bodies[j].id < bodies[best.j].id)))) {
          best = { i, j, dist: d };
        }
      }
    }
  }
  return best;
}
