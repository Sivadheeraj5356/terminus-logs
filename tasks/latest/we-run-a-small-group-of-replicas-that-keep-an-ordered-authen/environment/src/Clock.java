package rlog;

public final class Clock {
    private int now;

    public int now() {
        return now;
    }

    public void advance(int t) {
        if (t > now) {
            now = t;
        }
    }
}
