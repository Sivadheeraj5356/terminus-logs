package cx;

public final class SchedRow {
    public final String mid;
    public final int idx;
    public final String src;
    public final double press;
    public final double left;
    public final double leak;

    public SchedRow(String mid, int idx, String src, double press, double left, double leak) {
        this.mid = mid;
        this.idx = idx;
        this.src = src;
        this.press = press;
        this.left = left;
        this.leak = leak;
    }
}
