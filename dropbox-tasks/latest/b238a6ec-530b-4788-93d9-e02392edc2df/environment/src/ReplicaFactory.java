package rlog;

public final class ReplicaFactory {
    private ReplicaFactory() {
    }

    public static Replica create(int id, int n) {
        return new LogReplica(id, n);
    }
}
