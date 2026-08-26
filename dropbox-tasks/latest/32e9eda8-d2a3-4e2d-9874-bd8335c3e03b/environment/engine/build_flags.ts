import fs from 'fs';
import path from 'path';
import { runExpandStep } from './expand_step';
import { runMergeStep } from './merge_step';
import { runTopoStep } from './topo_step';

const ENV_ROOT = path.resolve(__dirname, '..', '..');
const DATA = path.join(ENV_ROOT, 'data');
export const TAGS = ['arm_a', 'arm_b', 'arm_c'];

type HoldEntry = { slug: string; tags: string[]; slot_rotate?: number; jobs?: number };

type ArmState = {
  aid: string;
  facetHex: string;
  expandRc: number;
  mergeRc: number;
  proofRc: number;
  lag: number;
  seed: number;
};

function loadCidTable(): Record<string, number> {
  return JSON.parse(fs.readFileSync(path.join(DATA, 'cid_table.json'), 'utf8'));
}

function loadLattice() {
  const raw = fs.readFileSync(path.join(DATA, 'flag_lattice.toml'), 'utf8');
  const out = { steps: [1, 2, 4, 8, 16], floor: 3, target: 'arm_a' };
  for (const line of raw.split('\n')) {
    const t = line.trim();
    if (t.startsWith('steps')) {
      out.steps = t
        .split('=')[1]
        .trim()
        .slice(1, -1)
        .split(',')
        .map((x) => parseInt(x.trim(), 10));
    } else if (t.startsWith('floor')) {
      out.floor = parseInt(t.split('=')[1], 10);
    } else if (t.startsWith('target')) {
      out.target = t.split('=')[1].trim().replace(/^"|"$/g, '');
    }
  }
  return out;
}

function splitAid(aid: string) {
  const isPair = aid.endsWith('_echo');
  let core = isPair ? aid.slice(0, -5) : aid;
  if (core.includes('~')) core = core.split('~')[0];
  const tag = TAGS.find((t) => core.startsWith(t)) || core;
  const slot = TAGS.indexOf(tag);
  return { tag, slot, isPair };
}

function foldHex(mat: number, mergeByte: number, proofByte: number): string {
  const raw =
    (BigInt(mat & 0xffffffff) << 32n) |
    (BigInt(mergeByte & 0xffff) << 16n) |
    BigInt(proofByte & 0xffff);
  return raw.toString(16).padStart(16, '0');
}

function proofHex(val: number): string {
  return (val >>> 0).toString(16).padStart(8, '0');
}

function jobsForAid(aid: string, holdEntries: HoldEntry[]): number {
  if (!aid.includes('~')) return 1;
  const slug = aid.split('~')[1];
  for (const hold of holdEntries) {
    if (hold.slug === slug) return hold.jobs || 1;
  }
  return 1;
}

export function buildArmStates(
  aidList: string[],
  defaultJobs: number,
  metaDir: string,
  holdEntries: HoldEntry[],
): { arms: ArmState[]; ledger: Record<string, string> } {
  const cid = loadCidTable();
  const lattice = loadLattice();
  const ledger: Record<string, string> = {};
  const arms: ArmState[] = [];
  const edgeOrder = [...TAGS];

  for (let armIx = 0; armIx < aidList.length; armIx++) {
    const aid = aidList[armIx];
    const { tag, slot, isPair } = splitAid(aid);
    const jobs = jobsForAid(aid, holdEntries) || defaultJobs;
    let facetHex: string;
    let expandRc: number;
    let mergeRc: number;
    let proofRc: number;
    let lag = 0;
    let seed: number;

    if (isPair) {
      const baseAid = aid.slice(0, -5);
      const base = arms.find((a) => a.aid === baseAid);
      if (!base) throw new Error(`missing base arm for pair ${aid}`);
      seed = base.seed;
      facetHex = base.facetHex;
      expandRc = base.expandRc;
      mergeRc = base.mergeRc;
      proofRc = base.proofRc;
      ledger[aid] = ledger[baseAid];
    } else {
      seed = (armIx * 17) ^ (slot * 31) ^ (cid[tag] || 0);
      const [expandCount, manifestBytes] = runExpandStep(seed, { [tag]: tag }, true);
      const [mergeCode, edgeNames] = runMergeStep(tag, edgeOrder, true);
      const mergeByte = mergeCode > 0 ? edgeNames.length + slot : 0;
      const laneTbl = { tag, slot: String(slot), jobs: String(jobs) };
      const [, facetBytes] = runTopoStep(seed, laneTbl, metaDir);
      const proofByte = facetBytes.readUInt32BE(0) & 0xffff;
      const mat =
        ((manifestBytes[manifestBytes.length - 1] || 0) ^
          (lattice.steps[slot % lattice.steps.length] || 1) ^
          lattice.floor) &
        0xffffffff;
      facetHex = foldHex(mat, mergeByte, proofByte);
      ledger[aid] = proofHex(proofByte);
      expandRc = expandCount >= 2 ? 1 : 0;
      mergeRc = mergeCode > 0 ? 1 : jobs <= 1 ? 1 : 0;
      proofRc = 0;
      if (jobs > 1 && mergeCode === 0) lag = Math.max(lag, 1);
    }

    arms.push({ aid, facetHex, expandRc, mergeRc, proofRc, lag, seed });
  }
  return { arms, ledger };
}
