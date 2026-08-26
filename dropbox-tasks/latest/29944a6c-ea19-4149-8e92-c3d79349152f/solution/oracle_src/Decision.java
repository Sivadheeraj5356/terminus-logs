package gate;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

public final class Decision {

    private Decision() { }

    public static String render(List<PolicyEngine.Reason> reasons) {
        List<PolicyEngine.Reason> sorted = new ArrayList<>(reasons);
        sorted.sort(Comparator
            .comparing(PolicyEngine.Reason::code)
            .thenComparing(PolicyEngine.Reason::service));

        if (sorted.isEmpty()) {
            return "{\"decision\":\"approve\",\"reasons\":[]}";
        }

        StringBuilder sb = new StringBuilder();
        sb.append("{\"decision\":\"deny\",\"reasons\":[");
        for (int i = 0; i < sorted.size(); i++) {
            if (i > 0) sb.append(',');
            PolicyEngine.Reason r = sorted.get(i);
            Map<String, String> m = new TreeMap<>();
            m.put("clauseId", r.clauseId());
            m.put("code", r.code());
            m.put("service", r.service());
            sb.append('{');
            boolean first = true;
            for (Map.Entry<String, String> e : m.entrySet()) {
                if (!first) sb.append(',');
                first = false;
                sb.append('"').append(e.getKey()).append('"').append(':');
                sb.append('"').append(escape(e.getValue())).append('"');
            }
            sb.append('}');
        }
        sb.append("]}");
        return sb.toString();
    }

    private static String escape(String s) {
        StringBuilder out = new StringBuilder(s.length());
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"': out.append("\\\""); break;
                case '\\': out.append("\\\\"); break;
                case '\n': out.append("\\n"); break;
                case '\r': out.append("\\r"); break;
                case '\t': out.append("\\t"); break;
                case '\b': out.append("\\b"); break;
                case '\f': out.append("\\f"); break;
                default:
                    if (c < 0x20) {
                        out.append(String.format("\\u%04x", (int) c));
                    } else {
                        out.append(c);
                    }
            }
        }
        return out.toString();
    }
}
