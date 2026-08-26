#!/bin/bash
set -euo pipefail

cd /app
cat > src/index.ts <<'TS'
import * as crypto from "node:crypto";
import * as fs from "node:fs";
import * as path from "node:path";
import {
  ContainerSpec,
  Transcript,
  AdjudicationResult,
  Transition,
  RejectedAction,
  LeagueSummary,
  AuditPackManifest,
} from "./types";

function commandLines(transcript: string): string[] {
  const source = transcript
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0 && !line.startsWith("#"));
  let index = 0;

  const parseBlock = (stopOnBrace: boolean): string[] => {
    const output: string[] = [];
    while (index < source.length) {
      const line = source[index];
      if (line === "}") {
        index += 1;
        if (stopOnBrace) {
          return output;
        }
        output.push(line);
        continue;
      }
      const match = line.match(/^repeat\s+([1-9]\d*)\s*\{$/);
      if (match) {
        index += 1;
        const body = parseBlock(true);
        const count = Number(match[1]);
        for (let i = 0; i < count; i += 1) {
          output.push(...body);
        }
        continue;
      }
      output.push(line);
      index += 1;
    }
    return output;
  };

  return parseBlock(false);
}

export function adjudicatePortfall(
  containerSpec: ContainerSpec,
  transcript: Transcript
): AdjudicationResult {
  const containers = new Map(containerSpec.containers.map((c) => [c.id, c]));
  const aliases = (containerSpec as any).aliases ?? {};
  const resolveContainer = (id: string) => aliases.containers?.[id] ?? id;
  const resolveSeal = (id: string) => aliases.seals?.[id] ?? id;
  const resolveHazard = (id: string) => aliases.hazards?.[id] ?? id;
  const start = containerSpec.startContainer;
  if (!containers.has(start)) {
    throw new Error(`start container ${start} is not present in spec`);
  }

  let current = start;
  const visitedRooms: string[] = [start];
  const transitions: Transition[] = [];
  const brokenSeals: string[] = [];
  const rejectedActions: RejectedAction[] = [];
  const hazardsTriggered: string[] = [];
  const unlockedSeals = new Set<string>();
  const brokenSet = new Set<string>();
  const triggeredHazards = new Set<string>();
  const securedContainers = new Set<string>();
  const temporaryRoutes = new Set<string>();
  const beacons = new Set<string>();
  let activeScan: string | null = null;
  let stackMoveCount = 0;
  let consumedBraces = 0;
  let temporaryRoutesUsed = 0;
  let beaconsUsed = 0;

  const reject = (command: string, reason: string) => {
    rejectedActions.push({ command, reason });
  };

  const isStackMove = (fromId: string, toId: string): boolean => {
    const from = containers.get(fromId);
    const to = containers.get(toId);
    return Boolean(from && to && (to.stackedOn === fromId || from.stackedOn === toId));
  };

  const enterRoom = (roomId: string) => {
    if (!visitedRooms.includes(roomId)) {
      visitedRooms.push(roomId);
    }
    const room = containers.get(roomId);
    if (!room) {
      return;
    }
    if (securedContainers.has(roomId)) {
      securedContainers.delete(roomId);
      consumedBraces += 1;
      return;
    }
    if (room.hazards.includes("ventilated")) {
      return;
    }
    for (const hazard of room.hazards) {
      if (activeScan === hazard) {
        activeScan = null;
        continue;
      }
      if (!triggeredHazards.has(hazard)) {
        triggeredHazards.add(hazard);
        hazardsTriggered.push(hazard);
      }
    }
  };

  const requirementsMet = (roomId: string): boolean => {
    const room = containers.get(roomId) as any;
    const requires = room?.requires ?? {};
    for (const requiredRoom of requires.visited ?? []) {
      if (!visitedRooms.includes(requiredRoom)) {
        return false;
      }
    }
    for (const requiredSeal of requires.brokenSeals ?? []) {
      if (!brokenSet.has(requiredSeal)) {
        return false;
      }
    }
    return true;
  };

  const availableNeighbors = (fromId: string): string[] => {
    const room = containers.get(fromId);
    const neighbors = new Set<string>(room?.connectsTo ?? []);
    for (const route of temporaryRoutes) {
      const [from, to] = route.split("->");
      if (from === fromId) {
        neighbors.add(to);
      }
    }
    return [...neighbors].filter((id) => containers.has(id) && requirementsMet(id)).sort();
  };

  const findPath = (fromId: string, toId: string): string[] | null => {
    if (!containers.has(toId)) {
      return null;
    }
    if (fromId === toId) {
      return [];
    }
    const queue: Array<{ room: string; path: string[] }> = [{ room: fromId, path: [] }];
    const seen = new Set<string>([fromId]);
    while (queue.length > 0) {
      const item = queue.shift()!;
      for (const next of availableNeighbors(item.room)) {
        if (seen.has(next)) {
          continue;
        }
        const path = [...item.path, next];
        if (next === toId) {
          return path;
        }
        seen.add(next);
        queue.push({ room: next, path });
      }
    }
    return null;
  };

  const applyMove = (to: string, command: string) => {
    const routeKey = `${current}->${to}`;
    const usesTemporaryRoute = temporaryRoutes.has(routeKey);
    const transition = { from: current, to, command };
    transitions.push(transition);
    if (usesTemporaryRoute) {
      temporaryRoutes.delete(routeKey);
      temporaryRoutesUsed += 1;
    }
    if (isStackMove(current, to)) {
      stackMoveCount += 1;
    }
    current = to;
    enterRoom(to);
  };

  const applyRecall = (to: string, command: string) => {
    transitions.push({ from: current, to, command });
    beacons.delete(to);
    beaconsUsed += 1;
    if (isStackMove(current, to)) {
      stackMoveCount += 1;
    }
    current = to;
    enterRoom(to);
  };

  for (const command of commandLines(transcript)) {
    const [verb, ...rest] = command.split(/\s+/);
    const target = rest[0];
    const containerTarget = target ? resolveContainer(target) : target;
    const sealTarget = target ? resolveSeal(target) : target;
    const hazardTarget = target ? resolveHazard(target) : target;
    const room = containers.get(current);
    if (!room || !target) {
      reject(command, "unknown command");
      continue;
    }

    if (verb === "inspect") {
      if (rest.length !== 1) {
        reject(command, "unknown command");
      }
      continue;
    }

    if (verb === "scan") {
      if (rest.length !== 1) {
        reject(command, "unknown command");
        continue;
      }
      activeScan = hazardTarget;
      continue;
    }

    if (verb === "secure") {
      if (rest.length !== 1) {
        reject(command, "unknown command");
        continue;
      }
      if (!containers.has(containerTarget) || (containerTarget !== current && !room.connectsTo.includes(containerTarget))) {
        reject(command, "not reachable");
        continue;
      }
      securedContainers.add(containerTarget);
      continue;
    }

    if (verb === "reroute") {
      if (rest.length !== 2) {
        reject(command, "route not anchored");
        continue;
      }
      const routeTo = resolveContainer(rest[1]);
      if (containerTarget !== current || !containers.has(routeTo)) {
        reject(command, "route not anchored");
        continue;
      }
      temporaryRoutes.add(`${containerTarget}->${routeTo}`);
      continue;
    }

    if (verb === "beacon") {
      if (rest.length !== 1) {
        reject(command, "unknown command");
        continue;
      }
      if (!containers.has(containerTarget) || (containerTarget !== current && !room.connectsTo.includes(containerTarget))) {
        reject(command, "not reachable");
        continue;
      }
      beacons.add(containerTarget);
      continue;
    }

    if (verb === "recall") {
      if (rest.length !== 1) {
        reject(command, "unknown command");
        continue;
      }
      if (!beacons.has(containerTarget)) {
        reject(command, "beacon absent");
        continue;
      }
      if (!requirementsMet(containerTarget)) {
        reject(command, "entry blocked");
        continue;
      }
      applyRecall(containerTarget, command);
      continue;
    }

    if (verb === "pathfind") {
      if (rest.length !== 1) {
        reject(command, "unknown command");
        continue;
      }
      const path = findPath(current, containerTarget);
      if (path === null) {
        reject(command, "no path");
        continue;
      }
      for (const step of path) {
        applyMove(step, command);
      }
      continue;
    }

    if (verb === "move") {
      if (rest.length !== 1) {
        reject(command, "unknown command");
        continue;
      }
      const routeKey = `${current}->${containerTarget}`;
      const usesTemporaryRoute = temporaryRoutes.has(routeKey);
      if (!room.connectsTo.includes(containerTarget) && !usesTemporaryRoute) {
        reject(command, "no connection");
        continue;
      }
      if (!requirementsMet(containerTarget)) {
        reject(command, "entry blocked");
        continue;
      }
      applyMove(containerTarget, command);
      continue;
    }

    if (verb === "unlock") {
      if (!room.seals.includes(sealTarget)) {
        reject(command, "seal not present");
        continue;
      }
      unlockedSeals.add(sealTarget);
      continue;
    }

    if (verb === "break-seal") {
      if (!room.seals.includes(sealTarget)) {
        reject(command, "seal not present");
        continue;
      }
      if (!unlockedSeals.has(sealTarget)) {
        reject(command, "seal not unlocked");
        continue;
      }
      if (!brokenSet.has(sealTarget)) {
        brokenSet.add(sealTarget);
        brokenSeals.push(sealTarget);
      }
      continue;
    }

    reject(command, "unknown command");
  }

  const scoreBreakdown: Record<string, number> = {};
  const roomsScore = visitedRooms.length * 10;
  if (roomsScore !== 0) {
    scoreBreakdown.roomsVisited = roomsScore;
  }
  const sealsScore = brokenSeals.length * 25;
  if (sealsScore !== 0) {
    scoreBreakdown.sealsBroken = sealsScore;
  }
  const hazardPenalty = hazardsTriggered.length * -15;
  if (hazardPenalty !== 0) {
    scoreBreakdown.hazardPenalty = hazardPenalty;
  }
  const stackMovePenalty = stackMoveCount * -5;
  if (stackMovePenalty !== 0) {
    scoreBreakdown.stackMovePenalty = stackMovePenalty;
  }
  const securedScore = consumedBraces * 7;
  if (securedScore !== 0) {
    scoreBreakdown.securedRooms = securedScore;
  }
  const routeScore = temporaryRoutesUsed * 4;
  if (routeScore !== 0) {
    scoreBreakdown.temporaryRoutesUsed = routeScore;
  }
  const beaconScore = beaconsUsed * 6;
  if (beaconScore !== 0) {
    scoreBreakdown.beaconsUsed = beaconScore;
  }

  return {
    finalRoom: current,
    visitedRooms,
    transitions,
    brokenSeals,
    rejectedActions,
    hazardsTriggered,
    score: Object.values(scoreBreakdown).reduce((sum, value) => sum + value, 0),
    scoreBreakdown,
  };
}

export function summarizePortfallLeague(
  containerSpec: ContainerSpec,
  transcripts: Record<string, Transcript>
): LeagueSummary {
  const cases: Record<string, AdjudicationResult> = {};
  for (const player of Object.keys(transcripts).sort()) {
    cases[player] = adjudicatePortfall(containerSpec, transcripts[player]);
  }

  const sortedPlayers = Object.keys(cases).sort((a, b) => {
    const ra = cases[a];
    const rb = cases[b];
    if (rb.score !== ra.score) {
      return rb.score - ra.score;
    }
    if (ra.rejectedActions.length !== rb.rejectedActions.length) {
      return ra.rejectedActions.length - rb.rejectedActions.length;
    }
    return a.localeCompare(b);
  });

  const leaderboard: LeagueSummary["leaderboard"] = [];
  let previous: { score: number; rejected: number } | null = null;
  let currentRank = 0;
  sortedPlayers.forEach((player, index) => {
    const result = cases[player];
    const rejected = result.rejectedActions.length;
    if (!previous || previous.score !== result.score || previous.rejected !== rejected) {
      currentRank = index + 1;
      previous = { score: result.score, rejected };
    }
    leaderboard.push({
      player,
      rank: currentRank,
      score: result.score,
      finalRoom: result.finalRoom,
      brokenSeals: result.brokenSeals.length,
      rejectedActions: rejected,
    });
  });

  const hazards = new Set<string>();
  const roomVisitCounts: Record<string, number> = {};
  let totalBrokenSeals = 0;
  for (const result of Object.values(cases)) {
    totalBrokenSeals += result.brokenSeals.length;
    for (const hazard of result.hazardsTriggered) {
      hazards.add(hazard);
    }
    for (const room of result.visitedRooms) {
      roomVisitCounts[room] = (roomVisitCounts[room] ?? 0) + 1;
    }
  }

  return {
    cases,
    leaderboard,
    aggregate: {
      playerCount: Object.keys(cases).length,
      topScore: leaderboard.length ? leaderboard[0].score : 0,
      totalBrokenSeals,
      uniqueHazardsTriggered: [...hazards].sort(),
      roomVisitCounts: Object.fromEntries(Object.entries(roomVisitCounts).sort()),
    },
  };
}


function canonicalJson(value: unknown): string {
  const normalize = (item: any): any => {
    if (Array.isArray(item)) {
      return item.map(normalize);
    }
    if (item && typeof item === "object") {
      return Object.fromEntries(Object.keys(item).sort().map((key) => [key, normalize(item[key])]));
    }
    return item;
  };
  return JSON.stringify(normalize(value));
}

function sha256(data: string | Buffer): string {
  return crypto.createHash("sha256").update(data).digest("hex");
}

function csvCell(value: string | number): string {
  const raw = String(value);
  if (/[",\n]/.test(raw)) {
    return `"${raw.replace(/"/g, '""')}"`;
  }
  return raw;
}

export function writePortfallAuditPack(
  containerSpec: ContainerSpec,
  transcriptFiles: Record<string, string>,
  outputDir: string
): AuditPackManifest {
  const transcripts: Record<string, Transcript> = {};
  for (const player of Object.keys(transcriptFiles).sort()) {
    transcripts[player] = fs.readFileSync(transcriptFiles[player], "utf8");
  }
  const league = summarizePortfallLeague(containerSpec, transcripts);
  fs.mkdirSync(path.join(outputDir, "cases"), { recursive: true });

  const artifacts: string[] = [];
  const caseDigests: Record<string, string> = {};
  for (const player of Object.keys(league.cases).sort()) {
    const rel = `cases/${player}.json`;
    const body = canonicalJson(league.cases[player]);
    fs.writeFileSync(path.join(outputDir, rel), body, "utf8");
    artifacts.push(rel);
    caseDigests[player] = sha256(body);
  }

  const csvLines = ["rank,player,score,finalRoom,brokenSeals,rejectedActions"];
  for (const row of league.leaderboard) {
    csvLines.push([
      row.rank,
      row.player,
      row.score,
      row.finalRoom,
      row.brokenSeals,
      row.rejectedActions,
    ].map(csvCell).join(","));
  }
  const leaderboardCsv = `${csvLines.join("\n")}\n`;
  fs.writeFileSync(path.join(outputDir, "leaderboard.csv"), leaderboardCsv, "utf8");
  artifacts.push("leaderboard.csv");

  const hazards = {
    uniqueHazardsTriggered: league.aggregate.uniqueHazardsTriggered,
    byPlayer: Object.fromEntries(Object.keys(league.cases).sort().map((player) => [
      player,
      league.cases[player].hazardsTriggered,
    ])),
  };
  fs.writeFileSync(path.join(outputDir, "hazards.json"), canonicalJson(hazards), "utf8");
  artifacts.push("hazards.json");
  artifacts.push("manifest.json");
  artifacts.sort();

  const manifest: AuditPackManifest = {
    artifacts,
    playerCount: league.aggregate.playerCount,
    topScore: league.aggregate.topScore,
    caseDigests,
    leaderboardDigest: sha256(leaderboardCsv),
  };
  fs.writeFileSync(path.join(outputDir, "manifest.json"), canonicalJson(manifest), "utf8");
  return manifest;
}


export * from "./types";
TS

npm run build
