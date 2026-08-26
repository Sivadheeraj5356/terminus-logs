package gate;

import java.time.Instant;
import java.util.Collections;
import java.util.List;
import java.util.Map;

/** Evaluates the resolved compose model against the shipped standard. */
public final class PolicyEngine {

    private PolicyEngine() { }

    /**
     * Evaluate every service in {@code services} against the shipped
     * standard. Reasons that are suppressed by an applicable exception
     * window are omitted; reasons that survive are returned.
     */
    public static List<Reason> evaluate(
            Map<String, Map<String, Object>> services,
            Db.Data db,
            Instant evaluationTime) {
        // TODO: implement per the shipped standard.
        return Collections.emptyList();
    }

    /** Reason line in a decision. */
    public record Reason(String clauseId, String code, String service) { }
}
