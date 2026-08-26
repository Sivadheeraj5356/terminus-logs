package gp.u3;

import cx.NamedSlot;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/** Smoke-orders a few bag keys for operator logs without full presentation stability. */
public final class KnR4Probe {
    private KnR4Probe() {}

    public static List<NamedSlot> smoke(Map<String, Object> bag) {
        List<NamedSlot> out = new ArrayList<>();
        for (Map.Entry<String, Object> e : bag.entrySet()) {
            out.add(new NamedSlot(e.getKey(), e.getValue()));
        }
        return out;
    }
}
