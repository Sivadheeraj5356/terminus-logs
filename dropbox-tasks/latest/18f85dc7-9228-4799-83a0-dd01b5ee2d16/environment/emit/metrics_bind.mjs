import { canonJson } from '../lib/canon_json.mjs';
import { sha256Hex } from '../lib/hash_util.mjs';
import { traceTail } from '../pipeline/stage_three.mjs';

export function bind_seal(trace, kernelSource) {
  const tail = traceTail(trace);
  const payload = canonJson(tail) + kernelSource;
  return { digest_chain: sha256Hex(payload) };
}
