package rlog;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

public final class LogReplica implements Replica {
    private static final int REJOIN = 7;
    private static final int REJOINSTATE = 8;

    private final int id;
    private final int n;
    private final Config cfg;
    private int view;
    private int status;
    private int commitNum;
    private int ackedOpnum;
    private int lastNormalView;
    private final Log log = new Log();
    private final Map<Integer, Set<Integer>> prepareOk = new HashMap<>();
    private final Set<Integer> svc = new HashSet<>();
    private final Map<Integer, Message> dvc = new HashMap<>();
    private boolean sentDvc;
    private final List<Envelope> out = new ArrayList<>();
    private final List<Integer> acks = new ArrayList<>();
    private boolean rejoining;
    private int token;
    private final Map<Integer, Message> rejoinState = new HashMap<>();
    private int inc;
    private final int[] peerInc;

    public LogReplica(int id, int n) {
        this.id = id;
        this.n = n;
        this.cfg = new Config(n);
        this.view = 0;
        this.status = ViewStatus.NORMAL;
        this.lastNormalView = 0;
        this.peerInc = new int[n];
    }

    public int id() {
        return id;
    }

    public int view() {
        return view;
    }

    public boolean normal() {
        return !rejoining && status == ViewStatus.NORMAL;
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

    private boolean isPrimary() {
        return cfg.primaryOf(view) == id;
    }

    private void broadcast(Message m) {
        for (int to = 0; to < n; to++) {
            if (to == id) {
                continue;
            }
            Message c = m.copy();
            c.from = id;
            stampInc(c);
            c.mac = AuthCode.compute(Secret.cluster(), AuthCode.canonical(c));
            out.add(new Envelope(id, to, c));
        }
    }

    private void send(int to, Message m) {
        Message c = m.copy();
        c.from = id;
        stampInc(c);
        c.mac = AuthCode.compute(Secret.cluster(), AuthCode.canonical(c));
        out.add(new Envelope(id, to, c));
    }

    private void stampInc(Message c) {
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

    private void observeInc(Message m) {
        if (m.from < 0 || m.from >= n) {
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
        if (rejoining || status != ViewStatus.NORMAL || !isPrimary()) {
            return;
        }
        log.append(op);
        int opnum = log.size();
        Set<Integer> stored = new HashSet<>();
        stored.add(id);
        prepareOk.put(opnum, stored);
        Message m = new Message();
        m.kind = MsgKind.TAG_A;
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
        m.kind = MsgKind.TAG_D;
        m.view = view;
        broadcast(m);
    }

    private void enterViewChange(int v) {
        if (v <= view) {
            return;
        }
        view = v;
        status = ViewStatus.VIEWCHANGE;
        svc.clear();
        dvc.clear();
        sentDvc = false;
    }

    public void deliver(Message m) {
        if (!AuthCode.compute(Secret.cluster(), AuthCode.canonical(m)).equals(m.mac)) {
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
            case MsgKind.TAG_A:
                onPrepare(m);
                break;
            case MsgKind.TAG_B:
                onPrepareOk(m);
                break;
            case MsgKind.TAG_C:
                onCommit(m);
                break;
            case MsgKind.TAG_D:
                onStartViewChange(m);
                break;
            case MsgKind.TAG_E:
                onDoViewChange(m);
                break;
            case MsgKind.TAG_F:
                onStartView(m);
                break;
            case REJOIN:
                onRejoin(m);
                break;
            default:
                break;
        }
    }

    private void onRejoin(Message m) {
        if (status != ViewStatus.NORMAL || m.aux.length < 1) {
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

    private void onRejoinState(Message m) {
        if (token == 0 || m.aux.length < 1 || m.aux[0] != token) {
            return;
        }
        rejoinState.put(m.from, m.copy());
        if (rejoinState.size() < cfg.majority()) {
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
        status = ViewStatus.NORMAL;
        lastNormalView = best.view;
        prepareOk.clear();
        svc.clear();
        dvc.clear();
        sentDvc = false;
        rejoining = false;
        token = 0;
        rejoinState.clear();
    }

    private void onPrepare(Message m) {
        if (m.view < view) {
            return;
        }
        if (m.view > view) {
            view = m.view;
        }
        status = ViewStatus.NORMAL;
        lastNormalView = view;
        if (m.log.length >= log.size()) {
            log.replace(m.log);
        }
        int c = Math.min(m.commitNum, log.size());
        if (c > commitNum) {
            commitNum = c;
        }
        Message ok = new Message();
        ok.kind = MsgKind.TAG_B;
        ok.view = view;
        ok.opnum = m.opnum;
        send(m.from, ok);
    }

    private void onPrepareOk(Message m) {
        if (!isPrimary() || status != ViewStatus.NORMAL || m.view != view) {
            return;
        }
        int msgInc = m.aux.length >= 2 ? m.aux[1] : 0;
        if (msgInc < peerInc[m.from]) {
            return;
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

    private void advanceCommit() {
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
            c.kind = MsgKind.TAG_C;
            c.view = view;
            c.commitNum = commitNum;
            broadcast(c);
        }
    }

    private void onCommit(Message m) {
        if (m.view < view || status != ViewStatus.NORMAL) {
            return;
        }
        int c = Math.min(m.commitNum, log.size());
        if (c > commitNum) {
            commitNum = c;
        }
    }

    private void onStartViewChange(Message m) {
        if (m.view > view) {
            enterViewChange(m.view);
            svc.add(id);
            Message p = new Message();
            p.kind = MsgKind.TAG_D;
            p.view = view;
            broadcast(p);
        }
        if (m.view == view && status == ViewStatus.VIEWCHANGE) {
            svc.add(m.from);
            maybeSendDoViewChange();
        }
    }

    private void maybeSendDoViewChange() {
        if (sentDvc) {
            return;
        }
        if (svc.size() < cfg.majority()) {
            return;
        }
        sentDvc = true;
        Message d = new Message();
        d.kind = MsgKind.TAG_E;
        d.view = view;
        d.opnum = log.size();
        d.commitNum = commitNum;
        d.log = log.toArray();
        d.aux = new int[] {lastNormalView};
        if (cfg.primaryOf(view) == id) {
            d.from = id;
            dvc.put(id, d);
            maybeStartView();
        } else {
            send(cfg.primaryOf(view), d);
        }
    }

    private void onDoViewChange(Message m) {
        if (m.view != view || cfg.primaryOf(view) != id || status != ViewStatus.VIEWCHANGE) {
            return;
        }
        if (m.aux.length < 1) {
            return;
        }
        dvc.put(m.from, m.copy());
        maybeStartView();
    }

    private void maybeStartView() {
        if (status != ViewStatus.VIEWCHANGE) {
            return;
        }
        if (dvc.size() < cfg.majority()) {
            return;
        }
        Message best = null;
        for (Message d : dvc.values()) {
            if (best == null
                    || d.aux[0] > best.aux[0]
                    || (d.aux[0] == best.aux[0] && d.opnum > best.opnum)) {
                best = d;
            }
        }
        log.replace(best.log);
        commitNum = best.opnum;
        ackedOpnum = commitNum;
        status = ViewStatus.NORMAL;
        lastNormalView = view;
        prepareOk.clear();
        Message sv = new Message();
        sv.kind = MsgKind.TAG_F;
        sv.view = view;
        sv.opnum = log.size();
        sv.commitNum = commitNum;
        sv.log = log.toArray();
        broadcast(sv);
    }

    private void onStartView(Message m) {
        if (m.view < view) {
            return;
        }
        if (m.view == view && status == ViewStatus.NORMAL) {
            return;
        }
        view = m.view;
        log.replace(m.log);
        commitNum = Math.min(m.commitNum, log.size());
        ackedOpnum = commitNum;
        status = ViewStatus.NORMAL;
        lastNormalView = view;
        svc.clear();
        dvc.clear();
    }
}
