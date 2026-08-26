package sim;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

import rlog.Envelope;
import rlog.Message;
import rlog.Replica;
import rlog.ReplicaFactory;

public final class Engine {
    private final int n;
    private final RefConfig cfg;
    private final String impl;
    private final Replica[] nodes;
    private int clock;
    private final Set<Integer> acked = new LinkedHashSet<>();
    private final Map<Integer, Set<Integer>> primaryActions = new HashMap<>();
    private int captureTo = -1;
    private final List<Message> captured = new ArrayList<>();

    private interface Reach {
        boolean ok(int from, int to);
    }

    public Engine(int n, String impl) {
        this.n = n;
        this.cfg = new RefConfig(n);
        this.impl = impl;
        this.nodes = new Replica[n];
        for (int i = 0; i < n; i++) {
            nodes[i] = make(i);
        }
    }

    private Replica make(int id) {
        switch (impl) {
            case "naive":
                return new NaiveReplica(id, n);
            case "dual":
                return new DualReplica(id, n);
            case "frozen":
                return new FrozenReplica(id, n);
            case "mute":
                return new MuteReplica(id, n);
            case "noverify":
                return new NoVerifyReplica(id, n);
            case "replay":
                return new ReplayReplica(id, n);
            case "norecover":
                return new NoRecoverReplica(id, n);
            case "onepeer":
                return new OnePeerReplica(id, n);
            case "stale":
                return new StaleReplica(id, n);
            case "noincarn":
                return new NoIncarnReplica(id, n);
            default:
                return ReplicaFactory.create(id, n);
        }
    }

    private void restart(int i) {
        nodes[i] = make(i);
        nodes[i].restarted();
    }

    private void record(int view, int from) {
        primaryActions.computeIfAbsent(view, k -> new LinkedHashSet<>()).add(from);
    }

    private void pump(Reach reach, Prng r, boolean reorder) {
        for (int round = 0; round < 800; round++) {
            List<Envelope> batch = new ArrayList<>();
            for (Replica nd : nodes) {
                nd.tick(clock);
                clock++;
                for (Envelope e : nd.drain()) {
                    batch.add(e);
                }
                for (int a : nd.takeAcks()) {
                    acked.add(a);
                }
            }
            for (Envelope e : batch) {
                if (e.msg.kind == RefKind.A || e.msg.kind == RefKind.F) {
                    record(e.msg.view, e.msg.from);
                }
            }
            if (batch.isEmpty()) {
                break;
            }
            if (reorder && r != null) {
                r.shuffle(batch);
            }
            List<Envelope> deliver = new ArrayList<>();
            for (Envelope e : batch) {
                if (reach.ok(e.from, e.to)) {
                    deliver.add(e);
                }
            }
            if (reorder && r != null) {
                r.shuffle(deliver);
            }
            for (Envelope e : deliver) {
                if (captureTo >= 0 && e.to == captureTo) {
                    captured.add(e.msg.copy());
                }
                nodes[e.to].deliver(e.msg);
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

    private Set<Integer> holders(long seed, int newPrimary) {
        int maj = cfg.majority();
        List<Integer> pool = new ArrayList<>();
        for (int i = 1; i < n; i++) {
            if (i != newPrimary) {
                pool.add(i);
            }
        }
        Set<Integer> h = new LinkedHashSet<>();
        h.add(0);
        int need = maj - 1;
        int start = pool.isEmpty() ? 0 : (int) (seed % pool.size());
        for (int i = 0; i < need && !pool.isEmpty(); i++) {
            h.add(pool.get((start + i) % pool.size()));
        }
        return h;
    }

    private Set<Integer> restartHolders() {
        int maj = cfg.majority();
        Set<Integer> h = new LinkedHashSet<>();
        h.add(0);
        for (int i = 0; i < maj - 1; i++) {
            h.add(n - 1 - i);
        }
        return h;
    }

    private Set<Integer> restartCut() {
        int maj = cfg.majority();
        Set<Integer> c = new LinkedHashSet<>();
        c.add(0);
        for (int i = 1; i <= n - maj; i++) {
            c.add(i);
        }
        return c;
    }

    public Verdict runControl(long seed) {
        int[] ops = {41, 42, 43};
        for (int op : ops) {
            nodes[0].clientRequest(op);
            pump((f, t) -> true, null, false);
        }
        return finish(true, null);
    }

    public Verdict runClean(long seed, boolean reorder) {
        Prng r = new Prng(seed);
        int newPrimary = 1 % n;
        int opB = 200 + (int) (seed % 17);
        nodes[0].clientRequest(41);
        pump((f, t) -> true, r, reorder);
        for (int i = 1; i < n; i++) {
            nodes[i].suspect();
        }
        pump((f, t) -> f != 0 && t != 0, r, reorder);
        int primary = currentPrimary();
        int target = primary >= 0 ? primary : newPrimary;
        nodes[target].clientRequest(opB);
        pump((f, t) -> f != 0 && t != 0, r, reorder);
        pump((f, t) -> true, r, reorder);
        return finish(true, opB);
    }

    public Verdict runFailover(long seed, boolean reorder, boolean b2b) {
        Prng r = new Prng(seed);
        int newPrimary = 1 % n;
        int opA = 100 + (int) (seed % 17);
        int opB = 200 + (int) (seed % 17);
        Set<Integer> h = holders(seed, newPrimary);
        nodes[0].clientRequest(41);
        pump((f, t) -> true, r, reorder);
        nodes[0].clientRequest(opA);
        pump((f, t) -> h.contains(f) && h.contains(t), r, reorder);
        for (int i = 1; i < n; i++) {
            nodes[i].suspect();
        }
        pump((f, t) -> f != 0 && t != 0, r, reorder);
        if (b2b) {
            for (int i = 1; i < n; i++) {
                nodes[i].suspect();
            }
            pump((f, t) -> f != 0 && t != 0, r, reorder);
        }
        int primary = currentPrimary();
        int target = primary >= 0 ? primary : newPrimary;
        nodes[target].clientRequest(opB);
        pump((f, t) -> f != 0 && t != 0, r, reorder);
        pump((f, t) -> true, r, reorder);
        return finish(true, opB);
    }

    private int pickNonHolder(Set<Integer> h, int newPrimary) {
        for (int i = 1; i < n; i++) {
            if (i != newPrimary && !h.contains(i)) {
                return i;
            }
        }
        return newPrimary;
    }

    public Verdict runForge(long seed, boolean reorder) {
        Prng r = new Prng(seed);
        int newPrimary = 1 % n;
        int opA = 100 + (int) (seed % 17);
        int opB = 200 + (int) (seed % 17);
        Set<Integer> h = holders(seed, newPrimary);
        nodes[0].clientRequest(41);
        pump((f, t) -> true, r, reorder);
        nodes[0].clientRequest(opA);
        pump((f, t) -> h.contains(f) && h.contains(t), r, reorder);
        for (int i = 1; i < n; i++) {
            nodes[i].suspect();
        }
        nodes[newPrimary].deliver(forgedDvc(0, 1).copy());
        pump((f, t) -> f != 0 && t != 0, r, reorder);
        int primary = currentPrimary();
        int target = primary >= 0 ? primary : newPrimary;
        nodes[target].clientRequest(opB);
        pump((f, t) -> f != 0 && t != 0, r, reorder);
        pump((f, t) -> true, r, reorder);
        return finish(true, opB);
    }

    private Message forgedDvc(int from, int view) {
        Message forged = new Message();
        forged.kind = RefKind.E;
        forged.view = view;
        forged.opnum = 1;
        forged.commitNum = 1;
        forged.from = from;
        forged.log = new int[] {41};
        forged.aux = new int[] {view};
        forged.mac = AuthKit.forgedMac(forged);
        return forged;
    }

    private Message dupDvc(int from, int view) {
        Message dup = new Message();
        dup.kind = RefKind.E;
        dup.view = view;
        dup.opnum = 1;
        dup.commitNum = 1;
        dup.from = from;
        dup.log = new int[] {41};
        dup.aux = new int[] {0};
        dup.mac = AuthKit.genuineMac(dup);
        return dup;
    }

    public Verdict runReplay(long seed, boolean reorder, boolean b2b) {
        Prng r = new Prng(seed);
        int newPrimary = 1 % n;
        int opA = 100 + (int) (seed % 17);
        int opB = 200 + (int) (seed % 17);
        Set<Integer> h = holders(seed, newPrimary);
        int replaySender = pickNonHolder(h, newPrimary);
        nodes[0].clientRequest(41);
        pump((f, t) -> true, r, reorder);
        nodes[0].clientRequest(opA);
        pump((f, t) -> h.contains(f) && h.contains(t), r, reorder);
        for (int i = 1; i < n; i++) {
            nodes[i].suspect();
        }
        Message dup = dupDvc(replaySender, 1);
        int copies = cfg.majority();
        for (int i = 0; i < copies; i++) {
            nodes[newPrimary].deliver(dup.copy());
        }
        pump((f, t) -> f != 0 && t != 0, r, reorder);
        if (b2b) {
            for (int i = 1; i < n; i++) {
                nodes[i].suspect();
            }
            pump((f, t) -> f != 0 && t != 0, r, reorder);
        }
        int primary = currentPrimary();
        int target = primary >= 0 ? primary : newPrimary;
        nodes[target].clientRequest(opB);
        pump((f, t) -> f != 0 && t != 0, r, reorder);
        pump((f, t) -> true, r, reorder);
        return finish(true, opB);
    }

    public Verdict runStaleAck(long seed, boolean reorder) {
        Prng r = new Prng(seed);
        int opX = 150 + (int) (seed % 17);
        int opB = 250 + (int) (seed % 17);
        int maj = cfg.majority();
        Set<Integer> b = new LinkedHashSet<>();
        for (int i = 1; i <= maj - 1; i++) {
            b.add(i);
        }
        nodes[0].clientRequest(41);
        pump((f, t) -> true, r, reorder);
        nodes[0].clientRequest(opB);
        pump((f, t) -> true, r, reorder);
        int opnumX = 3;
        List<Message> staleAcks = new ArrayList<>();
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
        for (int bi : b) {
            for (Envelope e : nodes[bi].drain()) {
                if (e.to == 0 && e.msg.kind == RefKind.B && e.msg.opnum == opnumX) {
                    staleAcks.add(e.msg.copy());
                }
            }
        }
        for (int bi : b) {
            restart(bi);
        }
        Reach shield = (f, t) -> !(f == 0 && b.contains(t));
        pump(shield, r, reorder);
        Message ping = genuinePrepare(0, 0, 1, 41, 1, new int[] {41});
        for (int bi : b) {
            nodes[bi].deliver(ping.copy());
        }
        pump(shield, r, reorder);
        for (Message m : staleAcks) {
            nodes[0].deliver(m.copy());
        }
        pump(shield, r, reorder);
        return finish(true, opB);
    }

    private Message genuinePrepare(int from, int view, int opnum, int op, int commitNum, int[] log) {
        Message m = new Message();
        m.kind = RefKind.A;
        m.view = view;
        m.opnum = opnum;
        m.op = op;
        m.commitNum = commitNum;
        m.from = from;
        m.log = log;
        m.aux = new int[0];
        m.mac = AuthKit.genuineMac(m);
        return m;
    }

    public Verdict runMinority(long seed) {
        int odd = n - 1;
        int[] ops = {41, 42, 43};
        for (int op : ops) {
            nodes[0].clientRequest(op);
            pump((f, t) -> f != odd && t != odd, null, false);
        }
        pump((f, t) -> true, null, false);
        return finish(true, null);
    }

    /**
     * Crash-restart schedule. Node 0 is the view-0 primary and a holder of opA; it stops and
     * comes back with no memory. Holders are the high ids, the cut set is node 0 plus the low
     * ids (exactly a majority, none of which hold opA except node 0).
     */
    public Verdict runRestart(long seed, boolean reorder, boolean b2b, String twist) {
        Prng r = new Prng(seed);
        int newPrimary = 1 % n;
        int opA = 100 + (int) (seed % 17);
        int opB = 200 + (int) (seed % 17);
        int opD = 300 + (int) (seed % 17);
        int opC = 400 + (int) (seed % 17);
        Set<Integer> h = restartHolders();
        Set<Integer> c = restartCut();
        int maj = cfg.majority();

        nodes[0].clientRequest(41);
        pump((f, t) -> true, r, reorder);
        nodes[0].clientRequest(opA);
        pump((f, t) -> h.contains(f) && h.contains(t), r, reorder);

        boolean twice = twist.equals("recover_replay");
        captureTo = 0;
        restart(0);
        pump((f, t) -> true, r, reorder);
        captureTo = -1;
        List<Message> firstWave = new ArrayList<>(captured);

        if (twice) {
            nodes[0].clientRequest(opC);
            pump((f, t) -> h.contains(f) && h.contains(t), r, reorder);
            restart(0);
            for (Message m : firstWave) {
                nodes[0].deliver(m.copy());
            }
            pump((f, t) -> true, r, reorder);
        }

        for (int i = 1; i < n; i++) {
            nodes[i].suspect();
        }
        if (twist.equals("forge")) {
            nodes[newPrimary].deliver(forgedDvc(n - 1, 1).copy());
        }
        if (twist.equals("replay")) {
            Message dup = dupDvc(n - maj, 1);
            for (int i = 0; i < maj; i++) {
                nodes[newPrimary].deliver(dup.copy());
            }
        }
        pump((f, t) -> c.contains(f) && c.contains(t), r, reorder);
        if (b2b) {
            for (int i = 1; i < n; i++) {
                nodes[i].suspect();
            }
            pump((f, t) -> c.contains(f) && c.contains(t), r, reorder);
        }
        int primary = currentPrimary();
        int target = primary >= 0 ? primary : newPrimary;
        nodes[target].clientRequest(opB);
        pump((f, t) -> c.contains(f) && c.contains(t), r, reorder);
        pump((f, t) -> true, r, reorder);
        int p2 = currentPrimary();
        if (p2 >= 0) {
            nodes[p2].clientRequest(opD);
        }
        pump((f, t) -> true, r, reorder);
        return finish(true, opB);
    }

    private Verdict finish(boolean requireProgress, Integer progressOp) {
        Verdict v = new Verdict();
        v.ran = true;
        int maxView = 0;
        for (Replica nd : nodes) {
            if (nd.view() > maxView) {
                maxView = nd.view();
            }
        }
        v.maxView = maxView;
        v.acked = new ArrayList<>(acked);
        int vmax = -1;
        for (Replica nd : nodes) {
            if (nd.normal() && nd.view() > vmax) {
                vmax = nd.view();
            }
        }
        List<Integer> auth = new ArrayList<>();
        for (Replica nd : nodes) {
            if (nd.normal() && nd.view() == vmax) {
                for (int cc : nd.committed()) {
                    auth.add(cc);
                }
                break;
            }
        }
        v.committed = auth;
        for (Map.Entry<Integer, Set<Integer>> e : primaryActions.entrySet()) {
            if (e.getValue().size() > 1) {
                v.violation = "two_primaries";
                return v;
            }
        }
        List<Set<Integer>> current = new ArrayList<>();
        for (Replica nd : nodes) {
            if (!nd.normal() || nd.view() != vmax) {
                continue;
            }
            Set<Integer> have = new LinkedHashSet<>();
            for (int cc : nd.committed()) {
                have.add(cc);
            }
            current.add(have);
        }
        for (int a : acked) {
            int holders = 0;
            for (Set<Integer> have : current) {
                if (have.contains(a)) {
                    holders++;
                }
            }
            if (holders < cfg.majority()) {
                v.violation = "committed_op_lost";
                return v;
            }
        }
        if (requireProgress) {
            if (progressOp == null) {
                if (acked.isEmpty()) {
                    v.violation = "no_progress";
                    return v;
                }
            } else if (!acked.contains(progressOp)) {
                v.violation = "no_progress";
                return v;
            }
        }
        return v;
    }
}
