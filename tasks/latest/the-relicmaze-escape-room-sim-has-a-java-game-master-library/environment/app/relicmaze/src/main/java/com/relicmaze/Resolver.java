package com.relicmaze;

import java.util.ArrayList;
import java.util.List;

/**
 * RelicMaze game master. Replay the request's transcript against the capsule
 * and the live database, then return the canonical narration for the resulting
 * state together with the Keeper's recommended next actions.
 *
 * This starter implementation is a stub. Replace the body of {@link #resolve}
 * with the real resolver logic described in the Keeper Manual.
 */
public final class Resolver implements Oracle {

    @Override
    public Response resolve(Request request) throws Exception {
        // TODO: load the capsule spec (CapsuleSpec.load), load the world
        // (Db.loadWorld), replay request.transcript(), and build the narration
        // and action list exactly as the Keeper Manual specifies.
        CapsuleSpec spec = CapsuleSpec.load(request.capsuleRef());
        World world = Db.loadWorld();
        // Touch the inputs so the stub still exercises the plumbing.
        int rooms = world.rooms.size();
        int directives = spec.history().size();
        String narration = "== unimplemented ==\nrooms=" + rooms + " directives=" + directives;
        List<String> actions = new ArrayList<>();
        actions.add("wait");
        return new Response(narration, actions);
    }
}
