package sim;

public final class FrozenReplica extends SimReplicaBase {
    public FrozenReplica(int id, int n) {
        super(id, n);
    }

    public void suspect() {
    }

    protected void onViewChangeQuorum() {
    }
}
