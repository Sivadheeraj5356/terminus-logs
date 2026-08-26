package sim;

public final class NaiveReplica extends SimReplicaBase {
    public NaiveReplica(int id, int n) {
        super(id, n);
    }

    protected void onViewChangeQuorum() {
        serveOwnLog(false);
    }
}
