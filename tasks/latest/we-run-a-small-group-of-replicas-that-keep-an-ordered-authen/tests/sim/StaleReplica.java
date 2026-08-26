package sim;

import rlog.Message;

public final class StaleReplica extends SimReplicaBase {
    public StaleReplica(int id, int n) {
        super(id, n);
    }

    protected boolean acceptState(Message m) {
        return true;
    }

    protected void onViewChangeQuorum() {
        maybeSendDoViewChange();
    }
}
