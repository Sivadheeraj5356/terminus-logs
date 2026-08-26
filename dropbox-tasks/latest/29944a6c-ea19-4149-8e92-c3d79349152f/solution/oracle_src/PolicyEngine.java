package gate;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.regex.Pattern;

public final class PolicyEngine {

    private static final Pattern IMAGE_PIN = Pattern.compile(
        "^[^\\s]+@sha256:[0-9a-fA-F]{64}$");

    private static final Set<String> CAP_ALLOWLIST = Set.of(
        "NET_BIND_SERVICE", "CHOWN", "SETUID", "SETGID", "DAC_OVERRIDE");

    private static final String[] SECRET_NEEDLES = {
        "password", "passwd", "secret", "token", "api_key", "apikey",
        "private_key"};

    private static final String[] BIND_PREFIX_ALLOWLIST = {
        "/srv/gate/", "/var/opt/gate/", "/opt/gate-data/"};

    // Zone table per §1.2.
    private static final int[] WEB_PORTS = {80, 443, 6379, 8080, 8443, 8444, 8445, 8446};
    private static final int[] WEB_RANGE = {8000, 8999};
    private static final int[] INTERNAL_RANGE = {9000, 9999};
    private static final int[] LOOPBACK_RANGE = {7000, 7999};

    // Amendment 7 effective date (from Appendix A).
    private static final Instant A7_EFFECTIVE =
        Instant.parse("2026-05-01T00:00:00Z");

    private PolicyEngine() { }

    public static List<Reason> evaluate(
            Map<String, Map<String, Object>> services,
            Db.Data db,
            Instant evaluationTime) {
        List<Reason> out = new ArrayList<>();
        Set<String> infra = db.infra();
        for (String name : services.keySet()) {
            Map<String, Object> svc = services.get(name);
            List<Emit> emitted = evaluateService(name, svc, infra);
            for (Emit e : emitted) {
                if (isNonWaivable(e.reason.clauseId())) {
                    out.add(e.reason);
                    continue;
                }
                if (isSuppressed(db.windows(), e, name, evaluationTime)) {
                    continue;
                }
                out.add(e.reason);
            }
        }
        return out;
    }

    // --- Non-waivable set (Appendix B) ---
    private static boolean isNonWaivable(String clauseId) {
        return clauseId.equals("§8.1") || clauseId.equals("§14.5");
    }

    // --- Waiver-binding predicate (§15.3) ---
    private static boolean isSuppressed(List<Db.ExceptionWindow> windows,
                                        Emit e, String serviceName,
                                        Instant evaluationTime) {
        String cid = e.reason.clauseId();
        for (Db.ExceptionWindow w : windows) {
            if (!w.clauseId().equals(cid)) continue;
            if (!fnmatch(serviceName, w.serviceGlob())) continue;
            if (evaluationTime.isBefore(w.startsAt())) continue;
            if (!evaluationTime.isBefore(w.endsAt())) continue;
            // §15.3: a window suspends the amendment-added obligation only
            // when its approved_at is at or after the amendment's
            // effective_date. For base obligations, any matching window
            // suspends.
            if (e.amendmentEffective == null) return true;
            if (!w.approvedAt().isBefore(e.amendmentEffective)) return true;
        }
        return false;
    }

    // --- Per-service evaluation. Returns Emits with amendment marker. ---
    private static List<Emit> evaluateService(String name,
                                              Map<String, Object> svc,
                                              Set<String> infra) {
        List<Emit> out = new ArrayList<>();
        boolean infraTier = isInfraTier(name, svc, infra);
        boolean webTier = isWebTier(svc);
        boolean webByPort = webByPortZone(svc);
        boolean cacheClass = isCacheClass(svc);

        // §8.1 privileged forbidden
        if (isPrivileged(svc)) {
            out.add(new Emit(new Reason("§8.1", "CDSS-SVC-008", name), null));
        }

        // §9.4 cap_drop ALL for non-infra
        if (!infraTier && !capsAllOk(svc)) {
            out.add(new Emit(new Reason("§9.4", "CDSS-SVC-009", name), null));
        }

        // §10.2 image pinned
        if (!imagePinned(svc)) {
            out.add(new Emit(new Reason("§10.2", "CDSS-SVC-010", name), null));
        }

        // §11.1 no secret env keys
        if (hasSecretEnvKey(svc)) {
            out.add(new Emit(new Reason("§11.1", "CDSS-SVC-011", name), null));
        }

        // §12.3 read-only web-tier
        if (webTier) {
            boolean readOnly = svc.get("read_only") == Boolean.TRUE;
            if (!readOnly) {
                if (cacheClass) {
                    // Base rule exempts cache-class. Amendment 7 withdraws
                    // the exemption for cache-class services that became
                    // web-tier via port-zone derivation.
                    if (webByPort) {
                        out.add(new Emit(new Reason("§12.3", "CDSS-SVC-012", name),
                                          A7_EFFECTIVE));
                    }
                    // else: not covered by §12.3 or by Amendment 7.
                } else {
                    // Not cache-class: plain §12.3 violation.
                    out.add(new Emit(new Reason("§12.3", "CDSS-SVC-012", name), null));
                }
            }
        }

        // §13.1 no host networking except infra
        if (!infraTier && "host".equals(svc.get("network_mode"))) {
            out.add(new Emit(new Reason("§13.1", "CDSS-SVC-013", name), null));
        }

        // §14.5 bind prefix allowlist
        if (!bindPrefixOk(svc)) {
            out.add(new Emit(new Reason("§14.5", "CDSS-SVC-014", name), null));
        }

        return out;
    }

    // --- Predicates ---

    private static boolean isPrivileged(Map<String, Object> svc) {
        return svc.get("privileged") == Boolean.TRUE;
    }

    @SuppressWarnings("unchecked")
    private static boolean capsAllOk(Map<String, Object> svc) {
        List<?> drops = asList(svc.get("cap_drop"));
        boolean hasAll = drops.stream()
            .anyMatch(x -> "ALL".equalsIgnoreCase(String.valueOf(x)));
        if (!hasAll) return false;
        for (Object cap : asList(svc.get("cap_add"))) {
            if (!CAP_ALLOWLIST.contains(String.valueOf(cap).toUpperCase(Locale.ROOT))) {
                return false;
            }
        }
        return true;
    }

    private static boolean imagePinned(Map<String, Object> svc) {
        Object image = svc.get("image");
        return image instanceof String && IMAGE_PIN.matcher((String) image).matches();
    }

    private static boolean hasSecretEnvKey(Map<String, Object> svc) {
        Object env = svc.get("environment");
        if (env == null) return false;
        if (env instanceof Map) {
            for (Object k : ((Map<?, ?>) env).keySet()) {
                if (secretish(String.valueOf(k))) return true;
            }
        } else if (env instanceof List) {
            for (Object entry : (List<?>) env) {
                if (entry instanceof String) {
                    String s = (String) entry;
                    String k = s.contains("=") ? s.substring(0, s.indexOf('=')) : s;
                    if (secretish(k)) return true;
                }
            }
        }
        return false;
    }

    private static boolean bindPrefixOk(Map<String, Object> svc) {
        for (Object entry : asList(svc.get("volumes"))) {
            String source = volumeSource(entry);
            if (source == null || source.isEmpty()) continue;
            if (!source.startsWith("/") && !source.startsWith(".")) continue;
            if ("/var/run/docker.sock".equals(source)) return false;
            boolean any = false;
            for (String p : BIND_PREFIX_ALLOWLIST) if (source.startsWith(p)) { any = true; break; }
            if (!any) return false;
        }
        return true;
    }

    // --- Tier derivation ---

    static boolean isWebTier(Map<String, Object> svc) {
        // §1.3: port-zone supersedes label. If any published host port is in
        // the web zone, the service is web-tier regardless of label.
        if (webByPortZone(svc)) return true;
        return "web".equals(labelValue(svc, "cdss.tier"));
    }

    static boolean webByPortZone(Map<String, Object> svc) {
        for (int p : hostPorts(svc)) {
            if (isWebZone(p)) return true;
        }
        return false;
    }

    static boolean isCacheClass(Map<String, Object> svc) {
        return "cache".equals(labelValue(svc, "cdss.class"));
    }

    static boolean isInfraTier(String name, Map<String, Object> svc,
                                Set<String> registry) {
        return "infra".equals(labelValue(svc, "cdss.tier"))
            && registry.contains(name);
    }

    private static boolean isWebZone(int port) {
        for (int wp : WEB_PORTS) if (wp == port) return true;
        return port >= WEB_RANGE[0] && port <= WEB_RANGE[1];
    }

    private static boolean isInternalZone(int port) {
        return port >= INTERNAL_RANGE[0] && port <= INTERNAL_RANGE[1];
    }

    private static boolean isLoopbackZone(int port) {
        return port >= LOOPBACK_RANGE[0] && port <= LOOPBACK_RANGE[1];
    }

    // --- Helpers ---

    private static List<Integer> hostPorts(Map<String, Object> svc) {
        List<Integer> out = new ArrayList<>();
        for (Object entry : asList(svc.get("ports"))) {
            if (entry instanceof String) {
                String[] parts = ((String) entry).split(":");
                String host = parts.length >= 2 ? parts[parts.length - 2] : parts[0];
                addPortRange(out, host);
            } else if (entry instanceof Integer) {
                out.add((Integer) entry);
            } else if (entry instanceof Map) {
                Object pub = ((Map<?, ?>) entry).get("published");
                if (pub instanceof Integer) out.add((Integer) pub);
                else if (pub instanceof String) addPortRange(out, (String) pub);
            }
        }
        return out;
    }

    private static void addPortRange(List<Integer> out, String host) {
        if (host.contains("-")) {
            String[] r = host.split("-", 2);
            try {
                int lo = Integer.parseInt(r[0]);
                int hi = Integer.parseInt(r[1]);
                for (int i = lo; i <= hi; i++) out.add(i);
            } catch (NumberFormatException ignore) { }
        } else {
            try { out.add(Integer.parseInt(host)); }
            catch (NumberFormatException ignore) { }
        }
    }

    private static String volumeSource(Object entry) {
        if (entry instanceof String) {
            String s = (String) entry;
            int c = s.indexOf(':');
            return c > 0 ? s.substring(0, c) : s;
        }
        if (entry instanceof Map) {
            Object src = ((Map<?, ?>) entry).get("source");
            return src == null ? null : String.valueOf(src);
        }
        return null;
    }

    private static String labelValue(Map<String, Object> svc, String key) {
        Object labels = svc.get("labels");
        if (labels instanceof Map) {
            Object v = ((Map<?, ?>) labels).get(key);
            return v == null ? null : String.valueOf(v);
        }
        if (labels instanceof List) {
            for (Object e : (List<?>) labels) {
                String s = String.valueOf(e);
                int eq = s.indexOf('=');
                if (eq > 0 && s.substring(0, eq).equals(key)) {
                    return s.substring(eq + 1);
                }
            }
        }
        return null;
    }

    private static boolean secretish(String k) {
        String low = k.toLowerCase(Locale.ROOT);
        for (String n : SECRET_NEEDLES) if (low.contains(n)) return true;
        return false;
    }

    private static List<?> asList(Object o) {
        if (o instanceof List) return (List<?>) o;
        if (o == null) return List.of();
        return List.of(o);
    }

    private static boolean fnmatch(String name, String glob) {
        java.nio.file.PathMatcher m = java.nio.file.FileSystems.getDefault()
            .getPathMatcher("glob:" + glob);
        return m.matches(java.nio.file.Path.of(name));
    }

    /** Reason line in a decision. */
    public record Reason(String clauseId, String code, String service) { }

    /** Internal emit carrier: reason plus the amendment effective date the
     *  reason attaches to (null for base-clause reasons). */
    private record Emit(Reason reason, Instant amendmentEffective) { }
}
