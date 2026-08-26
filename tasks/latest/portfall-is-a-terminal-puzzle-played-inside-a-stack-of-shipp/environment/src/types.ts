/**
 * Schema for the Portfall adjudicator.
 *
 * The exact final schema is subject to confirmation at handoff, but the shapes
 * below are the canonical schema shared with the golden JSON fixtures, audit
 * pack files, and the container spec sample.
 */

/** A container and its layout: where the player starts and how rooms connect. */
export interface ContainerSpec {
  /** Room id the player begins in. */
  startContainer: string;
  /** Optional command aliases resolved before rule checks. */
  aliases?: {
    containers?: Record<string, string>;
    seals?: Record<string, string>;
    hazards?: Record<string, string>;
  };
  containers: Array<{
    /** Unique room identifier. */
    id: string;
    /** Room this one is stacked on, or null if it rests on the ground. */
    stackedOn: string | null;
    /** Seal identifiers guarding this room. */
    seals: string[];
    /** Hazard identifiers present in this room. */
    hazards: string[];
    /** Room ids reachable by a move from this room. */
    connectsTo: string[];
    /** Optional entry requirements that must be met before entering this room. */
    requires?: {
      visited?: string[];
      brokenSeals?: string[];
    };
  }>;
}

/**
 * Raw transcript text: line-oriented player commands (move/unlock/break-seal/inspect).
 * Blank lines and lines beginning with '#' are comments.
 */
export type Transcript = string;

/** A successful movement between two rooms. */
export interface Transition {
  /** Room moved from. */
  from: string;
  /** Room moved to. */
  to: string;
  /** The command line that produced the transition. */
  command: string;
}

/** A command that could not be applied, with the reason it was refused. */
export interface RejectedAction {
  /** The command line that was rejected. */
  command: string;
  /** Human-readable explanation of the rejection. */
  reason: string;
}

/** Canonical result of replaying a transcript against a container spec. */
export interface AdjudicationResult {
  /** Room the player ends in after the transcript is replayed. */
  finalRoom: string;
  /** Rooms visited, in first-visit order. */
  visitedRooms: string[];
  /** Movements that were applied, in order. */
  transitions: Transition[];
  /** Seal identifiers the player broke. */
  brokenSeals: string[];
  /** Commands that were refused. */
  rejectedActions: RejectedAction[];
  /** Hazard identifiers the player triggered. */
  hazardsTriggered: string[];
  /** Total score for the run. */
  score: number;
  /** Per-category contributions to the total score. */
  scoreBreakdown: Record<string, number>;
}


/** Canonical result for a multi-player Portfall league replay. */
export interface LeagueSummary {
  /** Per-player adjudication results keyed by player name. */
  cases: Record<string, AdjudicationResult>;
  /** Ranked players sorted by score, rejection count, and player name. */
  leaderboard: Array<{
    player: string;
    rank: number;
    score: number;
    finalRoom: string;
    brokenSeals: number;
    rejectedActions: number;
  }>;
  /** Aggregate summary across all player adjudications. */
  aggregate: {
    playerCount: number;
    topScore: number;
    totalBrokenSeals: number;
    uniqueHazardsTriggered: string[];
    roomVisitCounts: Record<string, number>;
  };
}


/** hazards.json written by writePortfallAuditPack. */
export interface AuditPackHazards {
  /** Ordered hazard ids triggered by each player. */
  byPlayer: Record<string, string[]>;
  /** Sorted unique hazard ids across all cases. */
  uniqueHazardsTriggered: string[];
}

/** Manifest returned by writePortfallAuditPack and written to manifest.json. */
export interface AuditPackManifest {
  artifacts: string[];
  playerCount: number;
  topScore: number;
  caseDigests: Record<string, string>;
  leaderboardDigest: string;
}


/** Replay one transcript against a container spec. */
export declare function adjudicatePortfall(
  containerSpec: ContainerSpec,
  transcript: Transcript
): AdjudicationResult;

/** Replay named transcripts independently and summarize their league results. */
export declare function summarizePortfallLeague(
  containerSpec: ContainerSpec,
  transcripts: Record<string, Transcript>
): LeagueSummary;

/** Write deterministic audit-pack artifacts for named transcript file paths. */
export declare function writePortfallAuditPack(
  containerSpec: ContainerSpec,
  transcriptFiles: Record<string, string>,
  outputDir: string
): AuditPackManifest;
