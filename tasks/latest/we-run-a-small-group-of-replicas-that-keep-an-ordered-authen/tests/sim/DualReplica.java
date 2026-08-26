package sim;

public final class DualReplica extends SimReplicaBase {
    public DualReplica(int id, int n) {
        super(id, n);
    }

    protected void onViewChangeQuorum() {
        serveOwnLog(true);
    }
}
