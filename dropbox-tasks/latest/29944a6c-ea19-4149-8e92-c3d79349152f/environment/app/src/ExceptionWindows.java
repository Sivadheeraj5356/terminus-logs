package gate;

import java.time.Instant;
import java.util.List;

/** Applies exception windows against reasons emitted by the policy engine. */
public final class ExceptionWindows {

    private ExceptionWindows() { }

    /**
     * Return {@code true} if the given reason should be suppressed by a
     * matching window in {@code windows}. Implement per Chapter 15.
     */
    public static boolean suppresses(List<Db.ExceptionWindow> windows,
                                     String clauseId,
                                     String serviceName,
                                     Instant evaluationTime) {
        // TODO: implement per Chapter 15.
        return false;
    }
}
