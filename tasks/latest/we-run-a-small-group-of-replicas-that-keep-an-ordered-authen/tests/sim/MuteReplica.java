package sim;

public final class MuteReplica extends SimReplicaBase {
    public MuteReplica(int id, int n) {
        super(id, n);
    }

    public void clientRequest(int op) {
    }

    protected void onViewChangeQuorum() {
    }
}
