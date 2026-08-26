package rlog;

public final class Envelope {
    public int from;
    public int to;
    public Message msg;

    public Envelope(int from, int to, Message msg) {
        this.from = from;
        this.to = to;
        this.msg = msg;
    }
}
