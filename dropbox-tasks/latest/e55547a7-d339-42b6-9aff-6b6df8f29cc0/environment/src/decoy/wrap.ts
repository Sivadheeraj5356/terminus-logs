import * as fs from "fs";
import * as crypto from "crypto";
import { Body, CascadeAtlas, AtlasEntry } from "../types";
import { round6, round6v } from "../math/vec3";

function altCanonical(obj: unknown): string {
  return JSON.stringify(obj, Object.keys(obj as object).sort());
}

function altHash(v: unknown): string {
  return crypto.createHash("sha256").update(altCanonical(v)).digest("hex");
}

export function writeAlternateAtlas(
  outPath: string,
  missionSlot: string,
  bodies: Body[],
  epochCount: number,
): CascadeAtlas {
  const entries: AtlasEntry[] = bodies.map((b) => ({
    id: b.id,
    final_pos_m: round6v(b.pos_m),
    final_vel_mps: round6v(b.vel_mps),
    mass_kg: round6(b.mass_kg),
    radius_m: round6(b.radius_m),
    survived: true,
  }));

  const atlas: CascadeAtlas = {
    mission_slot: missionSlot,
    epoch_count: epochCount,
    final_body_count: entries.length,
    bodies: entries,
    atlas_hash: "",
  };
  atlas.atlas_hash = altHash({
    mission_slot: atlas.mission_slot,
    epoch_count: atlas.epoch_count,
    final_body_count: atlas.final_body_count,
    bodies: atlas.bodies,
  });

  fs.writeFileSync(outPath, JSON.stringify(atlas, null, 2));
  return atlas;
}
