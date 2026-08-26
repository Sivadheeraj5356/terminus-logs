package gp.u3;

import cx.NamedSlot;
import java.util.List;
import java.util.Map;

public final class KnR4 {
    private KnR4() {}

    public static List<NamedSlot> kn_r4(Map<String, Object> bag) {
        return KnR4Probe.smoke(bag);
    }
}
