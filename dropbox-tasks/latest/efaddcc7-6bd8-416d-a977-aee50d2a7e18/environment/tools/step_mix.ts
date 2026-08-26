import { mixN8 } from "../w2/n8_mix";

export function stepMix(prior: number, cells: number[], weight: number): number {
  return mixN8(prior, cells, weight);
}
