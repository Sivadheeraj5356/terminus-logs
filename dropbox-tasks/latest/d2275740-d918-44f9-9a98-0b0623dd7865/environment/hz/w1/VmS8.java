package hz.w1;

import cx.SchedRow;
import java.util.List;

public final class VmS8 {
    private VmS8() {}

    public static String vm_s8(List<SchedRow> rows, byte[] salt) {
        return VmS8Pretty.fmt(rows, salt);
    }
}
