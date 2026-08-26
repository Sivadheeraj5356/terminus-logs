package sim;

public final class NoRecoverReplica extends SimReplicaBase {
    public NoRecoverReplica(int id, int n) {
        super(id, n);
    }

    public void restarted() {
    }

    protected void onViewChangeQuorum() {
        maybeSendDoViewChange();
    }
}
