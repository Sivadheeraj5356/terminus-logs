package rlog;

import java.util.Arrays;

public final class Message {
    public int kind;
    public int view;
    public int opnum;
    public int op;
    public int commitNum;
    public int from;
    public int[] log;
    public int[] aux;
    public String mac;

    public Message() {
        this.log = new int[0];
        this.aux = new int[0];
        this.mac = "";
    }

    public Message copy() {
        Message m = new Message();
        m.kind = kind;
        m.view = view;
        m.opnum = opnum;
        m.op = op;
        m.commitNum = commitNum;
        m.from = from;
        m.log = Arrays.copyOf(log, log.length);
        m.aux = Arrays.copyOf(aux, aux.length);
        m.mac = mac;
        return m;
    }
}
