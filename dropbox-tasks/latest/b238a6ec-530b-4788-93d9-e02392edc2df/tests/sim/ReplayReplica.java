package sim;

import java.util.ArrayList;
import java.util.Collection;
import java.util.List;

import rlog.Message;

public final class ReplayReplica extends SimReplicaBase {
    private final List<Message> tally = new ArrayList<>();

    public ReplayReplica(int id, int n) {
        super(id, n);
    }

    protected void onViewChangeQuorum() {
        maybeSendDoViewChange();
    }

    protected void resetDvc() {
        if (tally != null) {
            tally.clear();
        }
    }

    protected void recordDvc(Message m) {
        tally.add(m.copy());
    }

    protected int dvcCount() {
        return tally.size();
    }

    protected Collection<Message> dvcAll() {
        return tally;
    }
}
