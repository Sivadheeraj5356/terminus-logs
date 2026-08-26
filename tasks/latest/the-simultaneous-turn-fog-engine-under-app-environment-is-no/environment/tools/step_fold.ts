import { foldK4 } from "../q9/k4_fold";

export function stepFold(slots: Uint32Array, salt: number): string {
  return foldK4(slots, salt);
}
