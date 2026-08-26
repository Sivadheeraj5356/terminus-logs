package sim;

public final class OnePeerReplica extends SimReplicaBase {
    public OnePeerReplica(int id, int n) {
        super(id, n);
    }

    protected int stateQuorum() {
        return 1;
    }

    protected void onViewChangeQuorum() {
        maybeSendDoViewChange();
    }
}
