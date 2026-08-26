package sim;

import rlog.Message;

public final class NoVerifyReplica extends SimReplicaBase {
    public NoVerifyReplica(int id, int n) {
        super(id, n);
    }

    protected boolean verify(Message m) {
        return true;
    }

    protected void onViewChangeQuorum() {
        maybeSendDoViewChange();
    }
}
