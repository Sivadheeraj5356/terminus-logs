import * as fs from "fs";
import { Body, CascadeAtlas, AtlasEntry } from "../types";
import { round6, round6v } from "../math/vec3";
import { payloadHash } from "../staging/write";

export function writeAtlas(
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

  const envelope = {
    mission_slot: atlas.mission_slot,
    epoch_count: atlas.epoch_count,
    final_body_count: atlas.final_body_count,
    bodies: atlas.bodies,
  };
  atlas.atlas_hash = payloadHash(envelope);

  fs.writeFileSync(outPath, JSON.stringify(atlas, null, 2));
  return atlas;
}
