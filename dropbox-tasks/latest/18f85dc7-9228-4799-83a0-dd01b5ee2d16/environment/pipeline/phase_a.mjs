import { retile_op } from '../passes/block_tiler.mjs';
import { edge_sel } from '../passes/edge_pass.mjs';

export function runPhaseA(pack, grid, ghost, capBytes) {
  const tileInfo = retile_op(pack, ghost, capBytes);
  const edgeInfo = edge_sel(pack, grid);
  return { tileInfo, edgeInfo };
}
