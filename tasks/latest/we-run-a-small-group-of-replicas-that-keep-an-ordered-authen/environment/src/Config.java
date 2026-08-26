package rlog;

public final class Config {
    public final int nodes;

    public Config(int nodes) {
        this.nodes = nodes;
    }

    public int majority() {
        return nodes / 2 + 1;
    }

    public int primaryOf(int view) {
        return ((view % nodes) + nodes) % nodes;
    }
}
