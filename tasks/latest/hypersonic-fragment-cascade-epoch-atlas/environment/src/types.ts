import { Vec3 } from "./math/vec3";

export interface Body {
  id: string;
  mass_kg: number;
  radius_m: number;
  pos_m: Vec3;
  vel_mps: Vec3;
  cd: number;
}

export interface FlareEvent {
  t_sec: number;
  density_scale: number;
}

export interface Manifest {
  mission_slot: string;
  dt_sec: number;
  horizon_sec: number;
  fragment_count: number;
  min_sep_m: number;
}

export interface StagingEnvelope {
  mission_slot: string;
  manifest: Manifest;
  bodies: Body[];
  flares: FlareEvent[];
  catalog_fingerprint: string;
  staging_hash: string;
}

export interface CollisionEpoch {
  t_sec: number;
  parents: [string, string];
  child_ids: string[];
  momentum_residual: number;
  energy_residual: number;
}

export interface AtlasEntry {
  id: string;
  final_pos_m: Vec3;
  final_vel_mps: Vec3;
  mass_kg: number;
  radius_m: number;
  survived: boolean;
}

export interface CascadeAtlas {
  mission_slot: string;
  epoch_count: number;
  final_body_count: number;
  bodies: AtlasEntry[];
  atlas_hash: string;
}

export interface CollisionLedger {
  mission_slot: string;
  epochs: CollisionEpoch[];
  total_collisions: number;
  staging_digest: string;
  ledger_hash: string;
}

export interface ExportSequence {
  run_seq: number;
  atlas_hash: string;
  ledger_hash: string;
}

export interface IngestSeal {
  catalog_fingerprint: string;
  staging_hash: string;
}
