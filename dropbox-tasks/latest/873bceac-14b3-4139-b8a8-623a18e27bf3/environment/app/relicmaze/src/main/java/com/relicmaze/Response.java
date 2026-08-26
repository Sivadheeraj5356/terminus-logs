package com.relicmaze;

import java.util.List;

/** The resolver's answer: canonical narration text plus recommended actions. */
public final class Response {
    private final String narration;
    private final List<String> actions;

    public Response(String narration, List<String> actions) {
        this.narration = narration;
        this.actions = actions;
    }

    public String narration() {
        return narration;
    }

    public List<String> actions() {
        return actions;
    }
}
