package sim;

import java.util.ArrayList;
import java.util.Collection;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

import rlog.Envelope;
import rlog.Message;
import rlog.Replica;

public abstract class SimReplicaBase implements Replica {
    protected static final int REJOIN = 7;
    protected static final int REJOINSTATE = 8;

    protected final int id;
    protected final int n;
    protected final RefConfig cfg;
    protected int view;
    protected int status;
    protected int commitNum;
    protected int ackedOpnum;
    protected int lastNormalView;
    protected final RefLog log = new RefLog();
    protected final Map<Integer, Set<Integer>> prepareOk = new HashMap<>();
    protected final Set<Integer> svc = new HashSet<>();
    protected final Map<Integer, Message> dvc = new HashMap<>();
    protected boolean sentDvc;
    protected final List<Envelope> out = new ArrayList<>();
    protected final List<Integer> acks = new ArrayList<>();
    protected boolean rejoining;
    protected int token;
    protected final Map<Integer, Message> rejoinState = new HashMap<>();
    protected int inc;
    protected final int[] peerInc;

    protected SimReplicaBase(int id, int n) {
        this.id = id;
        this.n = n;
        this.cfg = new RefConfig(n);
        this.view = 0;
        this.status = RefStatus.NORMAL;
        this.lastNormalView = 0;
        this.peerInc = new int[n];
    }

    protected boolean incGateEnabled() {
        return true;
    }

    protected abstract void onViewChangeQuorum();

    public int id() {
        return id;
    }

    public int view() {
        return view;
    }

    public boolean normal() {
        return !rejoining && status == RefStatus.NORMAL;
    }

    public void restarted() {
        rejoining = true;
        token = 0;
        rejoinState.clear();
    }

    public void tick(int now) {
        if (inc == 0) {
            inc = now + 1;
        }
        if (!rejoining) {
            return;
        }
        if (token == 0) {
            token = now + 1;
        }
        Message m = new Message();
        m.kind = REJOIN;
        m.view = view;
        m.aux = new int[] {token};
        broadcast(m);
    }

    public Envelope[] drain() {
        Envelope[] arr = out.toArray(new Envelope[0]);
        out.clear();
        return arr;
    }

    public int[] committed() {
        return log.prefix(commitNum);
    }

    public int[] takeAcks() {
        int[] arr = new int[acks.size()];
        for (int i = 0; i < acks.size(); i++) {
            arr[i] = acks.get(i);
        }
        acks.clear();
        return arr;
    }

    protected boolean isPrimary() {
        return cfg.primaryOf(view) == id;
    }

    protected void mint(Message c) {
        c.mac = AuthKit.compute(AuthKit.clusterSecret(), AuthKit.canonical(c));
    }

    protected boolean verify(Message m) {
        return AuthKit.compute(AuthKit.clusterSecret(), AuthKit.canonical(m)).equals(m.mac);
    }

    protected void broadcast(Message m) {
        for (int to = 0; to < n; to++) {
            if (to == id) {
                continue;
            }
            Message c = m.copy();
            c.from = id;
            stampInc(c);
            mint(c);
            out.add(new Envelope(id, to, c));
        }
    }

    protected void send(int to, Message m) {
        Message c = m.copy();
        c.from = id;
        stampInc(c);
        mint(c);
        out.add(new Envelope(id, to, c));
    }

    protected void stampInc(Message c) {
        int[] aux = c.aux;
        if (aux.length < 2) {
            int[] grown = new int[2];
            for (int i = 0; i < aux.length; i++) {
                grown[i] = aux[i];
            }
            aux = grown;
        }
        aux[1] = inc;
        c.aux = aux;
    }

    protected void observeInc(Message m) {
        if (!incGateEnabled() || m.from < 0 || m.from >= n) {
            return;
        }
        int msgInc = m.aux.length >= 2 ? m.aux[1] : 0;
        if (msgInc > peerInc[m.from]) {
            peerInc[m.from] = msgInc;
            for (Set<Integer> stored : prepareOk.values()) {
                stored.remove(m.from);
            }
        }
    }

    public void clientRequest(int op) {
        if (rejoining || status != RefStatus.NORMAL || !isPrimary()) {
            return;
        }
        log.append(op);
        int opnum = log.size();
        Set<Integer> stored = new HashSet<>();
        stored.add(id);
        prepareOk.put(opnum, stored);
        Message m = new Message();
        m.kind = RefKind.A;
        m.view = view;
        m.opnum = opnum;
        m.op = op;
        m.commitNum = commitNum;
        m.log = log.toArray();
        broadcast(m);
    }

    public void suspect() {
        if (rejoining) {
            return;
        }
        enterViewChange(view + 1);
        svc.add(id);
        Message m = new Message();
        m.kind = RefKind.D;
        m.view = view;
        broadcast(m);
    }

    protected void enterViewChange(int v) {
        if (v <= view) {
            return;
        }
        view = v;
        status = RefStatus.VIEWCHANGE;
        svc.clear();
        resetDvc();
        sentDvc = false;
    }

    public void deliver(Message m) {
        if (!verify(m)) {
            return;
        }
        observeInc(m);
        if (rejoining) {
            if (m.kind == REJOINSTATE) {
                onRejoinState(m);
            }
            return;
        }
        switch (m.kind) {
            case RefKind.A:
                onPrepare(m);
                break;
            case RefKind.B:
                onPrepareOk(m);
                break;
            case RefKind.C:
                onCommit(m);
                break;
            case RefKind.D:
                onStartViewChange(m);
                break;
            case RefKind.E:
                onDoViewChange(m);
                break;
            case RefKind.F:
                onStartView(m);
                break;
            case REJOIN:
                onRejoin(m);
                break;
            default:
                break;
        }
    }

    protected boolean acceptState(Message m) {
        return token != 0 && m.aux.length >= 1 && m.aux[0] == token;
    }

    protected int stateQuorum() {
        return cfg.majority();
    }

    protected void onRejoin(Message m) {
        if (status != RefStatus.NORMAL || m.aux.length < 1) {
            return;
        }
        Message r = new Message();
        r.kind = REJOINSTATE;
        r.view = view;
        r.opnum = log.size();
        r.commitNum = commitNum;
        r.log = log.toArray();
        r.aux = new int[] {m.aux[0]};
        send(m.from, r);
    }

    protected void onRejoinState(Message m) {
        if (!acceptState(m)) {
            return;
        }
        rejoinState.put(m.from, m.copy());
        if (rejoinState.size() < stateQuorum()) {
            return;
        }
        Message best = null;
        int maxCommit = 0;
        for (Message r : rejoinState.values()) {
            if (r.commitNum > maxCommit) {
                maxCommit = r.commitNum;
            }
            if (best == null
                    || r.view > best.view
                    || (r.view == best.view && r.opnum > best.opnum)) {
                best = r;
            }
        }
        view = best.view;
        log.replace(best.log);
        commitNum = Math.min(maxCommit, log.size());
        ackedOpnum = commitNum;
        status = RefStatus.NORMAL;
        lastNormalView = best.view;
        prepareOk.clear();
        svc.clear();
        resetDvc();
        sentDvc = false;
        rejoining = false;
        token = 0;
        rejoinState.clear();
    }

    protected void onPrepare(Message m) {
        if (m.view < view) {
            return;
        }
        if (m.view > view) {
            view = m.view;
        }
        status = RefStatus.NORMAL;
        lastNormalView = view;
        if (m.log.length >= log.size()) {
            log.replace(m.log);
        }
        int c = Math.min(m.commitNum, log.size());
        if (c > commitNum) {
            commitNum = c;
        }
        Message ok = new Message();
        ok.kind = RefKind.B;
        ok.view = view;
        ok.opnum = m.opnum;
        send(m.from, ok);
    }

    protected void onPrepareOk(Message m) {
        if (!isPrimary() || status != RefStatus.NORMAL || m.view != view) {
            return;
        }
        if (incGateEnabled()) {
            int msgInc = m.aux.length >= 2 ? m.aux[1] : 0;
            if (msgInc < peerInc[m.from]) {
                return;
            }
        }
        Set<Integer> stored = prepareOk.get(m.opnum);
        if (stored == null) {
            stored = new HashSet<>();
            stored.add(id);
            prepareOk.put(m.opnum, stored);
        }
        stored.add(m.from);
        advanceCommit();
    }

    protected void advanceCommit() {
        int maj = cfg.majority();
        while (commitNum < log.size()) {
            int next = commitNum + 1;
            Set<Integer> stored = prepareOk.get(next);
            if (stored == null || stored.size() < maj) {
                break;
            }
            commitNum = next;
        }
        boolean advanced = false;
        while (ackedOpnum < commitNum) {
            ackedOpnum++;
            acks.add(log.at(ackedOpnum));
            advanced = true;
        }
        if (advanced) {
            Message c = new Message();
            c.kind = RefKind.C;
            c.view = view;
            c.commitNum = commitNum;
            broadcast(c);
        }
    }

    protected void onCommit(Message m) {
        if (m.view < view || status != RefStatus.NORMAL) {
            return;
        }
        int c = Math.min(m.commitNum, log.size());
        if (c > commitNum) {
            commitNum = c;
        }
    }

    protected void onStartViewChange(Message m) {
        if (m.view > view) {
            enterViewChange(m.view);
            svc.add(id);
            Message p = new Message();
            p.kind = RefKind.D;
            p.view = view;
            broadcast(p);
        }
        if (m.view == view && status == RefStatus.VIEWCHANGE) {
            svc.add(m.from);
            onViewChangeQuorum();
        }
    }

    protected void serveOwnLog(boolean force) {
        if (status != RefStatus.VIEWCHANGE) {
            return;
        }
        if (svc.size() < cfg.majority()) {
            return;
        }
        if (!force && cfg.primaryOf(view) != id) {
            return;
        }
        status = RefStatus.NORMAL;
        lastNormalView = view;
        prepareOk.clear();
        Message sv = new Message();
        sv.kind = RefKind.F;
        sv.view = view;
        sv.opnum = log.size();
        sv.commitNum = commitNum;
        sv.log = log.toArray();
        broadcast(sv);
    }

    protected void maybeSendDoViewChange() {
        if (sentDvc) {
            return;
        }
        if (svc.size() < cfg.majority()) {
            return;
        }
        sentDvc = true;
        Message d = new Message();
        d.kind = RefKind.E;
        d.view = view;
        d.opnum = log.size();
        d.commitNum = commitNum;
        d.log = log.toArray();
        d.aux = new int[] {lastNormalView};
        if (cfg.primaryOf(view) == id) {
            d.from = id;
            mint(d);
            recordDvc(d);
            maybeStartView();
        } else {
            send(cfg.primaryOf(view), d);
        }
    }

    protected void resetDvc() {
        dvc.clear();
    }

    protected void recordDvc(Message m) {
        dvc.put(m.from, m.copy());
    }

    protected int dvcCount() {
        return dvc.size();
    }

    protected Collection<Message> dvcAll() {
        return dvc.values();
    }

    protected void onDoViewChange(Message m) {
        if (m.view != view || cfg.primaryOf(view) != id || status != RefStatus.VIEWCHANGE) {
            return;
        }
        if (m.aux.length < 1) {
            return;
        }
        recordDvc(m);
        maybeStartView();
    }

    protected void maybeStartView() {
        if (status != RefStatus.VIEWCHANGE) {
            return;
        }
        if (dvcCount() < cfg.majority()) {
            return;
        }
        Message best = null;
        for (Message d : dvcAll()) {
            if (best == null
                    || d.aux[0] > best.aux[0]
                    || (d.aux[0] == best.aux[0] && d.opnum > best.opnum)) {
                best = d;
            }
        }
        log.replace(best.log);
        commitNum = best.opnum;
        ackedOpnum = commitNum;
        status = RefStatus.NORMAL;
        lastNormalView = view;
        prepareOk.clear();
        Message sv = new Message();
        sv.kind = RefKind.F;
        sv.view = view;
        sv.opnum = log.size();
        sv.commitNum = commitNum;
        sv.log = log.toArray();
        broadcast(sv);
    }

    protected void onStartView(Message m) {
        if (m.view < view) {
            return;
        }
        if (m.view == view && status == RefStatus.NORMAL) {
            return;
        }
        view = m.view;
        log.replace(m.log);
        commitNum = Math.min(m.commitNum, log.size());
        ackedOpnum = commitNum;
        status = RefStatus.NORMAL;
        lastNormalView = view;
        svc.clear();
        resetDvc();
    }
}
