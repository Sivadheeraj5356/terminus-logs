package rlog;

public final class LogReplica implements Replica {
    private final int id;
    private final int n;

    public LogReplica(int id, int n) {
        this.id = id;
        this.n = n;
    }

    public int id() {
        return id;
    }

    public int view() {
        return 0;
    }

    public boolean normal() {
        return true;
    }

    public void tick(int now) {
    }

    public void deliver(Message m) {
    }

    public void clientRequest(int op) {
    }

    public void suspect() {
    }

    public void restarted() {
    }

    public Envelope[] drain() {
        return new Envelope[0];
    }

    public int[] committed() {
        return new int[0];
    }

    public int[] takeAcks() {
        return new int[0];
    }
}
