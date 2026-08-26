package sim;

import java.util.ArrayList;
import java.util.List;

public final class RefLog {
    private final List<Integer> ops = new ArrayList<>();

    public int size() {
        return ops.size();
    }

    public void append(int op) {
        ops.add(op);
    }

    public int at(int opnum) {
        return ops.get(opnum - 1);
    }

    public void replace(int[] entries) {
        ops.clear();
        for (int e : entries) {
            ops.add(e);
        }
    }

    public int[] toArray() {
        int[] out = new int[ops.size()];
        for (int i = 0; i < ops.size(); i++) {
            out[i] = ops.get(i);
        }
        return out;
    }

    public int[] prefix(int len) {
        if (len > ops.size()) {
            len = ops.size();
        }
        if (len < 0) {
            len = 0;
        }
        int[] out = new int[len];
        for (int i = 0; i < len; i++) {
            out[i] = ops.get(i);
        }
        return out;
    }
}
