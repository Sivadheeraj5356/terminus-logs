package gp.v6;

import cx.LimView;
import cx.NamedSlot;
import cx.SchedOut;
import cx.SchedRow;
import cx.SoftView;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/** Greedy amplitude heuristic without soft-floor path propagation. */
public final class LpQ2Greedy {
    private LpQ2Greedy() {}

    @SuppressWarnings("unchecked")
    public static SchedOut amp(List<NamedSlot> slots, LimView lims, SoftView softs) {
        Map<String, Object> bag = new HashMap<>();
        for (NamedSlot s : slots) {
            bag.put(s.name, s.val);
        }
        String mid = String.valueOf(bag.getOrDefault("__mid__", "unk"));
        Object itemsRaw = bag.get("items");
        List<Object> items = itemsRaw instanceof List ? (List<Object>) itemsRaw : List.of();
        List<Map<String, Object>> pulses = new ArrayList<>();
        for (Object o : items) {
            if (o instanceof Map<?, ?> m) {
                pulses.add((Map<String, Object>) m);
            }
        }
        pulses.sort(Comparator.comparingDouble((Map<String, Object> p) -> -num(p.get("a"))));
        SchedOut out = new SchedOut();
        int spent = 0;
        double budget = lims.maxCost - lims.minLeft;
        for (Map<String, Object> p : pulses) {
            int cost = (int) Math.round(num(p.get("c")));
            if (spent + cost > budget) {
                continue;
            }
            spent += cost;
            int idx = (int) Math.round(num(p.get("i")));
            double a = num(p.get("a"));
            Object sObj = p.get("s");
            String src = "x";
            if (sObj instanceof List<?> lst && !lst.isEmpty()) {
                src = String.valueOf(lst.get(0));
            }
            double left = lims.maxCost - spent;
            // Greedy amplitude heuristic: ignore soft-floor path residual.
            double fakeLeak = softs.egressCap - a;
            out.rows.add(new SchedRow(mid, idx, src, a, left, fakeLeak));
            out.totalPress += a;
        }
        return out;
    }

    private static double num(Object o) {
        if (o instanceof Number n) {
            return n.doubleValue();
        }
        return 0.0;
    }
}
