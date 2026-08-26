package probe;

import java.util.LinkedHashMap;
import java.util.Map;

/** Builds the assemble claim object from case maps. */
public final class Surface {
    private Surface() {}

    public static Map<String, Object> fromCases(Map<String, Object> cases) {
        boolean ok = true;
        for (Object v : cases.values()) {
            if (!(v instanceof Map)) {
                ok = false;
                break;
            }
            @SuppressWarnings("unchecked")
            Map<String, Object> m = (Map<String, Object>) v;
            Object a = m.get("assemble_ok");
            if (!(a instanceof Boolean) || !((Boolean) a)) {
                ok = false;
                break;
            }
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("assemble_ok", ok);
        out.put("checked", cases.size());
        return out;
    }
}
