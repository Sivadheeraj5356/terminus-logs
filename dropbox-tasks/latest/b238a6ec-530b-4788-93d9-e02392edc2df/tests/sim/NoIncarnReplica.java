package sim;

public final class NoIncarnReplica extends SimReplicaBase {
    public NoIncarnReplica(int id, int n) {
        super(id, n);
    }

    protected boolean incGateEnabled() {
        return false;
    }

    protected void onViewChangeQuorum() {
        maybeSendDoViewChange();
    }
}
