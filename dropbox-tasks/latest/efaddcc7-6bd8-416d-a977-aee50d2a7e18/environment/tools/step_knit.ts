import { knitP3 } from "../v7/p3_knit";

export function stepKnit(digest: string, epoch: number, cells: number[]): string {
  return knitP3(digest, epoch, cells);
}
