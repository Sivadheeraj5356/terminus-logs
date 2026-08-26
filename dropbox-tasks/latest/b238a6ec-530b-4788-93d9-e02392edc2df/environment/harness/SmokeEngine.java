package harness;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

import rlog.AuthCode;
import rlog.Config;
import rlog.Envelope;
import rlog.Message;
import rlog.MsgKind;
import rlog.Replica;
import rlog.ReplicaFactory;
import rlog.Secret;

public final class SmokeEngine {
    private static final byte[] OUTSIDER = "outsider-key-v1".getBytes(StandardCharsets.UTF_8);
    private static final int BOGUS = 999;

    private final int n;
    private final Config cfg;
    private final Replica[] nodes;
    private int clock;
    private long rng = 0x243F6A8885A308D3L;
    private final Set<Integer> acked = new LinkedHashSet<>();
    private int captureKind = -1;
    private int captureTo = -1;
    private final List<Message> captured = new ArrayList<>();

    public SmokeEngine(int n) {
        this.n = n;
        this.cfg = new Config(n);
        this.nodes = new Replica[n];
        for (int i = 0; i < n; i++) {
            nodes[i] = ReplicaFactory.create(i, n);
        }
    }

    private interface Reach {
        boolean ok(int from, int to);
    }

    private int nextBelow(int bound) {
        rng += 0x9E3779B97F4A7C15L;
        long z = rng;
        z = (z ^ (z >>> 30)) * 0xBF58476D1CE4E5B9L;
        z = (z ^ (z >>> 27)) * 0x94D049BB133111EBL;
        z = z ^ (z >>> 31);
        return (int) Long.remainderUnsigned(z, bound);
    }

    private void collect(List<Envelope> batch) {
        for (Replica nd : nodes) {
            nd.tick(clock);
            clock++;
            for (Envelope e : nd.drain()) {
                if (captureKind >= 0 && e.msg.kind == captureKind) {
                    captured.add(e.msg.copy());
                }
                batch.add(e);
            }
            for (int a : nd.takeAcks()) {
                acked.add(a);
            }
        }
    }

    private void pump(Reach reach) {
        for (int round = 0; round < 600; round++) {
            List<Envelope> batch = new ArrayList<>();
            collect(batch);
            if (batch.isEmpty()) {
                break;
            }
            for (Envelope e : batch) {
                if (reach.ok(e.from, e.to)) {
                    if (captureTo >= 0 && e.to == captureTo) {
                        captured.add(e.msg.copy());
                    }
                    nodes[e.to].deliver(e.msg);
                }
            }
        }
    }

    private void pumpFaulty(Reach reach) {
        for (int round = 0; round < 600; round++) {
            List<Envelope> batch = new ArrayList<>();
            collect(batch);
            if (batch.isEmpty()) {
                break;
            }
            for (int i = batch.size() - 1; i > 0; i--) {
                int j = nextBelow(i + 1);
                Envelope tmp = batch.get(i);
                batch.set(i, batch.get(j));
                batch.set(j, tmp);
            }
            for (Envelope e : batch) {
                if (!reach.ok(e.from, e.to)) {
                    continue;
                }
                nodes[e.to].deliver(e.msg);
                if (nextBelow(3) == 0) {
                    nodes[e.to].deliver(e.msg.copy());
                }
            }
        }
    }

    private int currentPrimary() {
        int best = -1;
        int bestView = -1;
        for (Replica nd : nodes) {
            if (nd.normal() && cfg.primaryOf(nd.view()) == nd.id() && nd.view() > bestView) {
                best = nd.id();
                bestView = nd.view();
            }
        }
        return best;
    }

    private Set<Integer> majorityHolders() {
        int maj = cfg.majority();
        Set<Integer> h = new LinkedHashSet<>();
        h.add(0);
        for (int i = 0; i < maj - 1; i++) {
            h.add(n - 1 - i);
        }
        return h;
    }

    public String runControl() {
        pump((f, t) -> true);
        nodes[0].clientRequest(41);
        pump((f, t) -> true);
        nodes[0].clientRequest(42);
        pump((f, t) -> true);
        return finish(new int[] {41, 42});
    }

    public String runHandover() {
        pump((f, t) -> true);
        nodes[0].clientRequest(41);
        pump((f, t) -> true);
        for (int i = 1; i < n; i++) {
            nodes[i].suspect();
        }
        pump((f, t) -> f != 0 && t != 0);
        int primary = currentPrimary();
        int target = primary >= 0 ? primary : 1 % n;
        nodes[target].clientRequest(55);
        pump((f, t) -> f != 0 && t != 0);
        pump((f, t) -> true);
        return finish(new int[] {41, 55});
    }

    public String runMinority() {
        int odd = n - 1;
        pump((f, t) -> true);
        nodes[0].clientRequest(41);
        pump((f, t) -> f != odd && t != odd);
        nodes[0].clientRequest(42);
        pump((f, t) -> f != odd && t != odd);
        pump((f, t) -> true);
        return finish(new int[] {41, 42});
    }

    public String runFaulty() {
        int odd = n - 1;
        pumpFaulty((f, t) -> true);
        nodes[0].clientRequest(41);
        pumpFaulty((f, t) -> f != odd && t != odd);
        nodes[0].clientRequest(42);
        pumpFaulty((f, t) -> true);
        pump((f, t) -> true);
        String bogus = fabricatedCheck();
        if (bogus != null) {
            return bogus;
        }
        return finish(new int[] {41, 42});
    }

    public String runRestart() {
        pump((f, t) -> true);
        nodes[0].clientRequest(41);
        pump((f, t) -> true);
        nodes[0].clientRequest(42);
        pump((f, t) -> true);
        int r = n - 1;
        nodes[r] = ReplicaFactory.create(r, n);
        nodes[r].restarted();
        pump((f, t) -> true);
        nodes[0].clientRequest(43);
        pump((f, t) -> true);
        if (!nodes[r].normal()) {
            return "restart_node_never_recovered";
        }
        return finish(new int[] {41, 42, 43});
    }

    public String runReplay() {
        int opA = 77;
        int newPrimary = 1 % n;
        Set<Integer> h = majorityHolders();
        pump((f, t) -> true);
        nodes[0].clientRequest(41);
        pump((f, t) -> true);
        nodes[0].clientRequest(opA);
        pump((f, t) -> h.contains(f) && h.contains(t));
        for (int i = 1; i < n; i++) {
            nodes[i].suspect();
        }
        captureKind = MsgKind.TAG_E;
        captured.clear();
        pump((f, t) -> f != 0 && t != 0);
        captureKind = -1;
        for (Message m : captured) {
            nodes[newPrimary].deliver(m.copy());
            nodes[newPrimary].deliver(m.copy());
        }
        pump((f, t) -> f != 0 && t != 0);
        int primary = currentPrimary();
        int target = primary >= 0 ? primary : newPrimary;
        nodes[target].clientRequest(42);
        pump((f, t) -> f != 0 && t != 0);
        pump((f, t) -> true);
        return finish(new int[] {opA, 42});
    }

    public String runOutsider() {
        int opA = 77;
        int newPrimary = 1 % n;
        Set<Integer> h = majorityHolders();
        pump((f, t) -> true);
        nodes[0].clientRequest(41);
        pump((f, t) -> true);
        nodes[0].clientRequest(opA);
        pump((f, t) -> h.contains(f) && h.contains(t));
        for (int i = 1; i < n; i++) {
            nodes[i].suspect();
        }
        Message fake = new Message();
        fake.kind = MsgKind.TAG_E;
        fake.view = 1;
        fake.opnum = 2;
        fake.op = BOGUS;
        fake.commitNum = 1;
        fake.from = 0;
        fake.log = new int[] {41, BOGUS};
        fake.aux = new int[] {9};
        fake.mac = AuthCode.compute(OUTSIDER, AuthCode.canonical(fake));
        nodes[newPrimary].deliver(fake.copy());
        pump((f, t) -> f != 0 && t != 0);
        int primary = currentPrimary();
        int target = primary >= 0 ? primary : newPrimary;
        nodes[target].clientRequest(42);
        pump((f, t) -> f != 0 && t != 0);
        pump((f, t) -> true);
        String bogus = fabricatedCheck();
        if (bogus != null) {
            return bogus;
        }
        return finish(new int[] {opA, 42});
    }

    private void restartNode(int i) {
        nodes[i] = ReplicaFactory.create(i, n);
        nodes[i].restarted();
    }

    private Set<Integer> highHolders() {
        int maj = cfg.majority();
        Set<Integer> h = new LinkedHashSet<>();
        h.add(0);
        for (int i = 0; i < maj - 1; i++) {
            h.add(n - 1 - i);
        }
        return h;
    }

    private Set<Integer> lowCut() {
        int maj = cfg.majority();
        Set<Integer> c = new LinkedHashSet<>();
        c.add(0);
        for (int i = 1; i <= n - maj; i++) {
            c.add(i);
        }
        return c;
    }

    public String runRelife() {
        int opX = 150;
        int opB = 250;
        int opnumX = 3;
        int maj = cfg.majority();
        Set<Integer> b = new LinkedHashSet<>();
        for (int i = 1; i <= maj - 1; i++) {
            b.add(i);
        }
        pump((f, t) -> true);
        nodes[0].clientRequest(41);
        pump((f, t) -> true);
        nodes[0].clientRequest(opB);
        pump((f, t) -> true);
        nodes[0].clientRequest(opX);
        List<Envelope> pending = new ArrayList<>();
        for (Envelope e : nodes[0].drain()) {
            pending.add(e);
        }
        for (Envelope e : pending) {
            if (b.contains(e.to)) {
                nodes[e.to].deliver(e.msg);
            }
        }
        List<Message> earlier = new ArrayList<>();
        for (int bi : b) {
            for (Envelope e : nodes[bi].drain()) {
                if (e.to == 0 && e.msg.kind == MsgKind.TAG_B && e.msg.opnum == opnumX) {
                    earlier.add(e.msg.copy());
                }
            }
        }
        for (int bi : b) {
            restartNode(bi);
        }
        Reach shield = (f, t) -> !(f == 0 && b.contains(t));
        pump(shield);
        Message ping = genuine(MsgKind.TAG_A, 0, 0, 1, 41, 1, new int[] {41});
        for (int bi : b) {
            nodes[bi].deliver(ping.copy());
        }
        pump(shield);
        for (Message m : earlier) {
            nodes[0].deliver(m.copy());
        }
        pump(shield);
        return finish(new int[] {41, opB});
    }

    public String runRevisit() {
        int opA = 100;
        int opB = 200;
        int opC = 400;
        int newPrimary = 1 % n;
        Set<Integer> h = highHolders();
        Set<Integer> c = lowCut();
        pump((f, t) -> true);
        nodes[0].clientRequest(41);
        pump((f, t) -> true);
        nodes[0].clientRequest(opA);
        pump((f, t) -> h.contains(f) && h.contains(t));
        captureTo = 0;
        captured.clear();
        restartNode(0);
        pump((f, t) -> true);
        captureTo = -1;
        List<Message> firstWave = new ArrayList<>(captured);
        nodes[0].clientRequest(opC);
        pump((f, t) -> h.contains(f) && h.contains(t));
        restartNode(0);
        for (Message m : firstWave) {
            nodes[0].deliver(m.copy());
        }
        pump((f, t) -> true);
        for (int i = 1; i < n; i++) {
            nodes[i].suspect();
        }
        pump((f, t) -> c.contains(f) && c.contains(t));
        int primary = currentPrimary();
        int target = primary >= 0 ? primary : newPrimary;
        nodes[target].clientRequest(opB);
        pump((f, t) -> c.contains(f) && c.contains(t));
        pump((f, t) -> true);
        return finish(new int[] {opB});
    }

    private Message genuine(int kind, int from, int view, int opnum, int op, int commitNum, int[] log) {
        Message m = new Message();
        m.kind = kind;
        m.view = view;
        m.opnum = opnum;
        m.op = op;
        m.commitNum = commitNum;
        m.from = from;
        m.log = log;
        m.aux = new int[0];
        m.mac = AuthCode.compute(Secret.cluster(), AuthCode.canonical(m));
        return m;
    }

    private String fabricatedCheck() {
        for (Replica nd : nodes) {
            for (int c : nd.committed()) {
                if (c == BOGUS) {
                    return "fabricated_op_accepted";
                }
            }
        }
        if (acked.contains(BOGUS)) {
            return "fabricated_op_accepted";
        }
        return null;
    }

    private String finish(int[] expect) {
        for (int e : expect) {
            if (!acked.contains(e)) {
                return "no_progress";
            }
        }
        int vmax = -1;
        for (Replica nd : nodes) {
            if (nd.normal() && nd.view() > vmax) {
                vmax = nd.view();
            }
        }
        List<Set<Integer>> current = new ArrayList<>();
        for (Replica nd : nodes) {
            if (!nd.normal() || nd.view() != vmax) {
                continue;
            }
            Set<Integer> have = new LinkedHashSet<>();
            for (int c : nd.committed()) {
                have.add(c);
            }
            current.add(have);
        }
        for (int a : acked) {
            int held = 0;
            for (Set<Integer> have : current) {
                if (have.contains(a)) {
                    held++;
                }
            }
            if (held < cfg.majority()) {
                return "committed_op_lost";
            }
        }
        return "ok";
    }
}
