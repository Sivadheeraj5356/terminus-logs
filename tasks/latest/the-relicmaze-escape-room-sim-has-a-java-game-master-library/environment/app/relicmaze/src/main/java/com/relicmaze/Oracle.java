package com.relicmaze;

/**
 * Contract implemented by the RelicMaze game master. Given a replayed player
 * transcript for a capsule, it produces the canonical narration and the
 * ordered list of recommended next actions.
 */
public interface Oracle {
    Response resolve(Request request) throws Exception;
}
