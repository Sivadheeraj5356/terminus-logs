package sim;

public final class RefConfig {
    public final int nodes;

    public RefConfig(int nodes) {
        this.nodes = nodes;
    }

    public int majority() {
        return nodes / 2 + 1;
    }

    public int primaryOf(int view) {
        return ((view % nodes) + nodes) % nodes;
    }
}
