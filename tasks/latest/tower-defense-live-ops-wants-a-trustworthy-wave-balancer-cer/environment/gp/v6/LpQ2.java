package gp.v6;

import cx.LimView;
import cx.NamedSlot;
import cx.SchedOut;
import cx.SoftView;
import java.util.List;

public final class LpQ2 {
    private LpQ2() {}

    public static SchedOut lp_q2(List<NamedSlot> slots, LimView lims, SoftView softs) {
        return LpQ2Greedy.amp(slots, lims, softs);
    }
}
