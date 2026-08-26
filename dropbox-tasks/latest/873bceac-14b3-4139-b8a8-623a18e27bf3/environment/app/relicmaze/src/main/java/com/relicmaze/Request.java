package com.relicmaze;

import java.util.List;

/** A resolve request: which capsule to run and the player commands so far. */
public final class Request {
    private final String capsuleRef;
    private final List<String> transcript;

    public Request(String capsuleRef, List<String> transcript) {
        this.capsuleRef = capsuleRef;
        this.transcript = transcript;
    }

    /** Filesystem path to the capsule spec JSON. */
    public String capsuleRef() {
        return capsuleRef;
    }

    /** Ordered player commands that have already been issued. */
    public List<String> transcript() {
        return transcript;
    }
}
