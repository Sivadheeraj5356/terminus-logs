import * as fs from "fs";
import * as path from "path";
import * as crypto from "crypto";
import { Body, FlareEvent, Manifest } from "../types";
import { DEFAULT_CD } from "../math/constants";

export function loadManifest(catalogDir: string): Manifest {
  const raw = fs.readFileSync(path.join(catalogDir, "manifest.json"), "utf-8");
  return JSON.parse(raw) as Manifest;
}

export function loadBodies(catalogDir: string): Body[] {
  const raw = fs.readFileSync(path.join(catalogDir, "bodies.jsonl"), "utf-8");
  const lines = raw.trim().split("\n");
  const bodies: Body[] = [];
  for (const line of lines) {
    const obj = JSON.parse(line);
    bodies.push({
      id: obj.id,
      mass_kg: obj.mass_kg,
      radius_m: obj.radius_m,
      pos_m: obj.pos_m,
      vel_mps: obj.vel_mps,
      cd: obj.cd !== undefined ? obj.cd : DEFAULT_CD,
    });
  }
  return bodies;
}

export function loadFlares(catalogDir: string): FlareEvent[] {
  const raw = fs.readFileSync(path.join(catalogDir, "flares.jsonl"), "utf-8");
  const lines = raw.trim().split("\n");
  const flares: FlareEvent[] = [];
  for (const line of lines) {
    flares.push(JSON.parse(line) as FlareEvent);
  }
  flares.sort((a, b) => a.t_sec - b.t_sec);
  return flares;
}

export function catalogFingerprint(catalogDir: string): string {
  const bodiesRaw = fs.readFileSync(path.join(catalogDir, "bodies.jsonl"));
  const flaresRaw = fs.readFileSync(path.join(catalogDir, "flares.jsonl"));
  const h = crypto.createHash("sha256");
  h.update(bodiesRaw);
  h.update(flaresRaw);
  return h.digest("hex");
}
