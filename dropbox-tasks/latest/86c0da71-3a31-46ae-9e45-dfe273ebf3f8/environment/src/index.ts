import { ContainerSpec, Transcript, AdjudicationResult } from "./types";

/**
 * Replay a player's Portfall command transcript against the container spec and
 * return the canonical adjudication result.
 */
export function adjudicatePortfall(
  containerSpec: ContainerSpec,
  transcript: Transcript
): AdjudicationResult {
  throw new Error("not implemented");
}

export * from "./types";
