package org.terminus.calc;

import java.util.List;
import static org.terminus.calc.Model.*;

final class Dynamics {
    static AnalysisData compute(Recovered recovered) {
        Reg regression = new Reg(List.of(), 0, 0, 0, 0, 0, 0, 0, 0, 0);
        return new AnalysisData(List.of(), List.of(), regression, "");
    }

    private Dynamics() {}
}
