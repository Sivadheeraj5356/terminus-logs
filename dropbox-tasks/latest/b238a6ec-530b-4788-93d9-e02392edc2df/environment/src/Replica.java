package rlog;

public interface Replica {
    int id();

    int view();

    boolean normal();

    void tick(int now);

    void deliver(Message m);

    void clientRequest(int op);

    void suspect();

    void restarted();

    Envelope[] drain();

    int[] committed();

    int[] takeAcks();
}
