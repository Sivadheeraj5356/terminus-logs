package sim;

import java.util.List;

import rlog.Envelope;

public final class Prng {
    private long state;

    public Prng(long seed) {
        this.state = seed + 0x9E3779B97F4A7C15L;
    }

    public long next() {
        state += 0x9E3779B97F4A7C15L;
        long z = state;
        z = (z ^ (z >>> 30)) * 0xBF58476D1CE4E5B9L;
        z = (z ^ (z >>> 27)) * 0x94D049BB133111EBL;
        return z ^ (z >>> 31);
    }

    public int below(int bound) {
        if (bound <= 0) {
            return 0;
        }
        return (int) Long.remainderUnsigned(next(), bound);
    }

    public void shuffle(List<Envelope> v) {
        for (int i = v.size() - 1; i > 0; i--) {
            int j = (int) Long.remainderUnsigned(next(), i + 1);
            Envelope tmp = v.get(i);
            v.set(i, v.get(j));
            v.set(j, tmp);
        }
    }
}
