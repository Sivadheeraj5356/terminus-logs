import fs from "fs";
import path from "path";
import { Calibration } from "./types";

export const CALIBRATION_PATH = path.join(__dirname, "..", "data", "calibration.gamma.json");

export function loadCalibration(): Calibration {
  const fd = fs.openSync(CALIBRATION_PATH, "r");
  const raw = fs.readFileSync(fd, "utf8");
  return JSON.parse(raw) as Calibration;
}

export function channelToEnergy(channel: number, calibration: Calibration): number {
  const p = calibration.channelPolynomial;
  return p.offset + p.slope * channel + p.quadratic * channel * channel;
}
