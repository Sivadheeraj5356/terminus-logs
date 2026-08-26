package gate;

import java.nio.file.FileSystems;
import java.nio.file.PathMatcher;
import java.time.Instant;
import java.util.List;
import java.util.Set;

/** Legacy helper retained for callers that need per-reason suppression
 *  without the amendment-scope context. The reference PolicyEngine
 *  performs its own suppression internally; this static helper is left
 *  in place for extension code. */
public final class ExceptionWindows {

    private static final Set<String> NON_WAIVABLE = Set.of("§8.1", "§14.5");

    private ExceptionWindows() { }

    public static boolean suppresses(List<Db.ExceptionWindow> windows,
                                     String clauseId,
                                     String serviceName,
                                     Instant evaluationTime) {
        if (NON_WAIVABLE.contains(clauseId)) return false;
        for (Db.ExceptionWindow w : windows) {
            if (!w.clauseId().equals(clauseId)) continue;
            if (!fnmatch(serviceName, w.serviceGlob())) continue;
            if (evaluationTime.isBefore(w.startsAt())) continue;
            if (!evaluationTime.isBefore(w.endsAt())) continue;
            return true;
        }
        return false;
    }

    private static boolean fnmatch(String name, String glob) {
        PathMatcher m = FileSystems.getDefault().getPathMatcher("glob:" + glob);
        return m.matches(java.nio.file.Path.of(name));
    }
}
