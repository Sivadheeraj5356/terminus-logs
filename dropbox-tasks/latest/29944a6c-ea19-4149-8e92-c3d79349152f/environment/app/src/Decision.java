package gate;

import java.util.List;

/** Renders the release-gate decision as JSON per Chapter 32. */
public final class Decision {

    private Decision() { }

    public static String render(List<PolicyEngine.Reason> reasons) {
        // TODO: implement per Chapter 32.
        return "{\"decision\":\"approve\",\"reasons\":[]}";
    }
}
