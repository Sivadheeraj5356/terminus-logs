"""Independent numpy reference training engine.

This module encodes the formulas from /app/spec/engine_design.md and recomputes
the expected per-step loss and gradient norm directly from the raw dataset bytes
and the pinned seed. The test suite compares the agent's runs.db rows against the
numbers produced here; nothing in here parses the agent's source or output.

Everything is float64. The RNG is the single-word generator from the spec.
"""
import math
import struct
import numpy as np

# ---- spec-pinned hyperparameters (section references in engine_design.md) ----
H1 = H2 = H3 = 16          # hidden widths
EPOCHS = 4
DROPOUT_P = 0.2
LR = 0.01
BETA1 = 0.9
BETA2 = 0.999
EPS = 1e-8                  # Adam epsilon, placed OUTSIDE the sqrt
LN_EPS = 1e-5              # layernorm epsilon
CLIP_TAU = 3.0             # layer-3 gradient global-norm clip threshold
SIG = {"W1": 0.30, "W2": 0.30, "W3": 0.50, "Wo": 0.30}   # init std per matrix
PARAM_ORDER = ["W1", "b1", "g1", "be1", "W2", "b2", "g2", "be2",
               "W3", "b3", "Wo", "bo"]
MASK64 = (1 << 64) - 1


class Rng:
    """SplitMix64 with an explicit, save/restore-able 64-bit state."""

    def __init__(self, seed):
        self.s = seed & MASK64

    def next_u64(self):
        self.s = (self.s + 0x9E3779B97F4A7C15) & MASK64
        z = self.s
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
        z = (z ^ (z >> 31)) & MASK64
        return z

    def uniform_open(self):
        x = self.next_u64() >> 11
        return (x + 0.5) * (1.0 / 9007199254740992.0)

    def below(self, n):
        return (self.next_u64() * n) >> 64

    def normal(self):
        u1 = self.uniform_open()
        u2 = self.uniform_open()
        return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)

    def state(self):
        return self.s

    def set_state(self, s):
        self.s = s & MASK64


# ------------------------------- config/data i/o ------------------------------
def _toml_scalars(path):
    out = {}
    with open(path) as fh:
        for line in fh:
            line = line.split("#", 1)[0].strip()
            if not line or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip()
            if v.startswith('"') and v.endswith('"'):
                out[k] = v[1:-1]
            elif v.lower().startswith("0x"):
                out[k] = int(v, 16)
            elif v.lower() in ("true", "false"):
                out[k] = v.lower() == "true"
            else:
                try:
                    out[k] = int(v)
                except ValueError:
                    out[k] = float(v)
    return out


def load_manifest(path):
    m = _toml_scalars(path)
    return {
        "num_samples": int(m["num_samples"]),
        "input_dim": int(m["input_dim"]),
        "num_classes": int(m["num_classes"]),
        "batch_size": int(m["batch_size"]),
    }


def load_seed(path):
    return int(_toml_scalars(path)["seed"]) & MASK64


def load_resume_step(path):
    return int(_toml_scalars(path)["resume_step"])


def load_data(inputs_path, targets_path, n, d):
    with open(inputs_path, "rb") as fh:
        raw = fh.read()
    X = np.array(struct.unpack("<%dd" % (n * d), raw), dtype=np.float64).reshape(n, d)
    with open(targets_path, "rb") as fh:
        raw = fh.read()
    y = np.array(struct.unpack("<%dq" % n, raw), dtype=np.int64)
    return X, y


# ----------------------------------- ops --------------------------------------
def relu(x):
    return np.maximum(x, 0.0)


def layernorm_fwd(z, gamma, beta):
    mu = z.mean(axis=1, keepdims=True)
    var = ((z - mu) ** 2).mean(axis=1, keepdims=True)
    inv = 1.0 / np.sqrt(var + LN_EPS)
    xhat = (z - mu) * inv
    return xhat * gamma + beta, (xhat, inv, gamma)


def layernorm_bwd(dy, cache):
    xhat, inv, gamma = cache
    hn = xhat.shape[1]
    dgamma = (dy * xhat).sum(axis=0)
    dbeta = dy.sum(axis=0)
    dxhat = dy * gamma
    dz = inv / hn * (hn * dxhat
                     - dxhat.sum(axis=1, keepdims=True)
                     - xhat * (dxhat * xhat).sum(axis=1, keepdims=True))
    return dz, dgamma, dbeta


def unstable_fwd(z):
    return (z ** 3) / 3.0


def unstable_bwd(z, da):
    return da * (z ** 2)


def softmax_ce(logits, targets):
    r = logits.shape[0]
    m = logits.max(axis=1, keepdims=True)
    e = np.exp(logits - m)
    p = e / e.sum(axis=1, keepdims=True)
    loss = -np.log(p[np.arange(r), targets]).sum() / r
    dlogits = p.copy()
    dlogits[np.arange(r), targets] -= 1.0
    dlogits /= r
    return loss, dlogits


class Engine:
    def __init__(self, cfg):
        self.d_in = cfg["input_dim"]
        self.c = cfg["num_classes"]
        self.n = cfg["num_samples"]
        self.b = cfg["batch_size"]
        self.bpe = math.ceil(self.n / self.b)

    def init_params(self, rng):
        def mat(rows, cols, sig):
            w = np.empty((rows, cols))
            for i in range(rows):
                for j in range(cols):
                    w[i, j] = rng.normal() * sig
            return w
        p = {}
        p["W1"] = mat(self.d_in, H1, SIG["W1"])
        p["b1"] = np.zeros(H1)
        p["g1"] = np.ones(H1)
        p["be1"] = np.zeros(H1)
        p["W2"] = mat(H1, H2, SIG["W2"])
        p["b2"] = np.zeros(H2)
        p["g2"] = np.ones(H2)
        p["be2"] = np.zeros(H2)
        p["W3"] = mat(H2, H3, SIG["W3"])
        p["b3"] = np.zeros(H3)
        p["Wo"] = mat(H3, self.c, SIG["Wo"])
        p["bo"] = np.zeros(self.c)
        return p

    def draw_mask(self, rng, rows, width):
        m = np.empty((rows, width))
        scale = 1.0 / (1.0 - DROPOUT_P)
        for i in range(rows):
            for j in range(width):
                m[i, j] = scale if rng.uniform_open() >= DROPOUT_P else 0.0
        return m

    def epoch_perm(self, rng):
        perm = list(range(self.n))
        for i in range(self.n - 1, 0, -1):
            j = rng.below(i + 1)
            perm[i], perm[j] = perm[j], perm[i]
        return perm

    def forward(self, p, X, rng, remat=False):
        # `remat` is accepted for call-site symmetry with backward but does not
        # change the forward result; the forward always computes the full block.
        Z1 = X @ p["W1"] + p["b1"]
        LN1, c1 = layernorm_fwd(Z1, p["g1"], p["be1"])
        A1 = relu(LN1)
        r = X.shape[0]
        m1 = self.draw_mask(rng, r, H1)
        D1 = A1 * m1
        rng_pre = rng.state()
        Z2 = D1 @ p["W2"] + p["b2"]
        LN2, c2 = layernorm_fwd(Z2, p["g2"], p["be2"])
        A2 = relu(LN2)
        m2 = self.draw_mask(rng, r, H2)
        D2 = A2 * m2
        Z3 = D2 @ p["W3"] + p["b3"]
        A3 = unstable_fwd(Z3)
        Zo = A3 @ p["Wo"] + p["bo"]
        return dict(X=X, c1=c1, A1=A1, m1=m1, D1=D1, rng_pre=rng_pre,
                    Z2=Z2, c2=c2, A2=A2, m2=m2, D2=D2, Z3=Z3, A3=A3, Zo=Zo)

    def backward(self, p, f, targets, rng, remat):
        g = {}
        loss, dZo = softmax_ce(f["Zo"], targets)
        g["Wo"] = f["A3"].T @ dZo
        g["bo"] = dZo.sum(axis=0)
        dA3 = dZo @ p["Wo"].T
        dZ3 = unstable_bwd(f["Z3"], dA3)
        if remat:
            main = rng.state()
            rng.set_state(f["rng_pre"])
            Z2 = f["D1"] @ p["W2"] + p["b2"]
            LN2, c2 = layernorm_fwd(Z2, p["g2"], p["be2"])
            A2 = relu(LN2)
            m2 = self.draw_mask(rng, f["D1"].shape[0], H2)
            D2 = A2 * m2
            rng.set_state(main)
        else:
            c2, A2, m2, D2 = f["c2"], f["A2"], f["m2"], f["D2"]
        g["W3"] = D2.T @ dZ3
        g["b3"] = dZ3.sum(axis=0)
        dD2 = dZ3 @ p["W3"].T
        dLN2 = (dD2 * m2) * (A2 > 0.0)
        dZ2, g["g2"], g["be2"] = layernorm_bwd(dLN2, c2)
        g["W2"] = f["D1"].T @ dZ2
        g["b2"] = dZ2.sum(axis=0)
        dD1 = dZ2 @ p["W2"].T
        dLN1 = (dD1 * f["m1"]) * (f["A1"] > 0.0)
        dZ1, g["g1"], g["be1"] = layernorm_bwd(dLN1, f["c1"])
        g["W1"] = f["X"].T @ dZ1
        g["b1"] = dZ1.sum(axis=0)
        return loss, g

    @staticmethod
    def clip_layer3(g):
        n = math.sqrt(float((g["W3"] ** 2).sum() + (g["b3"] ** 2).sum()))
        if n > CLIP_TAU:
            s = CLIP_TAU / n
            g["W3"] = g["W3"] * s
            g["b3"] = g["b3"] * s
        return n

    @staticmethod
    def global_norm(g):
        tot = 0.0
        for k in PARAM_ORDER:
            tot += float((g[k] ** 2).sum())
        return math.sqrt(tot)

    def adam(self, p, g, opt):
        opt["t"] += 1
        t = opt["t"]
        for k in PARAM_ORDER:
            m = opt["m"][k]
            v = opt["v"][k]
            m[:] = BETA1 * m + (1 - BETA1) * g[k]
            v[:] = BETA2 * v + (1 - BETA2) * (g[k] * g[k])
            mhat = m / (1 - BETA1 ** t)
            vhat = v / (1 - BETA2 ** t)
            p[k] -= LR * mhat / (np.sqrt(vhat) + EPS)   # epsilon OUTSIDE sqrt


def run(cfg, X, y, seed, remat, stop_at=None, start=None):
    """Run training. Returns (rows, snapshot). rows: list of (step, loss, grad_norm)."""
    eng = Engine(cfg)
    if start is None:
        rng = Rng(seed)
        p = eng.init_params(rng)
        opt = {"m": {k: np.zeros_like(p[k]) for k in PARAM_ORDER},
               "v": {k: np.zeros_like(p[k]) for k in PARAM_ORDER}, "t": 0}
        step = 0
        cur = None
    else:
        rng, p, opt, step, cur = start
    total = EPOCHS * eng.bpe
    rows = []
    snap = None
    while step < total:
        bi = step % eng.bpe
        if bi == 0:
            cur = eng.epoch_perm(rng)
        s = bi * eng.b
        idx = cur[s:min(s + eng.b, eng.n)]
        Xb, yb = X[idx], y[idx]
        f = eng.forward(p, Xb, rng)
        loss, g = eng.backward(p, f, yb, rng, remat)
        eng.clip_layer3(g)
        gn = eng.global_norm(g)
        eng.adam(p, g, opt)
        rows.append((step, loss, gn))
        step += 1
        if stop_at is not None and step == stop_at:
            import copy
            # the snapshot carries the current epoch's permutation, which a
            # mid-epoch resume cannot regenerate from the (already-advanced) rng.
            snap = (Rng(rng.state()), copy.deepcopy(p), copy.deepcopy(opt),
                    step, list(cur))
            break
    return rows, snap


# --------------------------- convenience for tests ----------------------------
class Oracle:
    def __init__(self, app="/app"):
        self.app = app
        self.cfg = load_manifest(f"{app}/data/dataset_manifest.toml")
        self.seed = load_seed(f"{app}/tests_fixtures/golden_seed.toml")
        self.resume_step = load_resume_step(f"{app}/tests_fixtures/resume_point.toml")
        self.X, self.y = load_data(f"{app}/data/train_inputs.bin",
                                   f"{app}/data/train_targets.bin",
                                   self.cfg["num_samples"], self.cfg["input_dim"])
        self.bpe = math.ceil(self.cfg["num_samples"] / self.cfg["batch_size"])

    def full_run(self, remat=True):
        rows, _ = run(self.cfg, self.X, self.y, self.seed, remat)
        return rows

    def resume_tail(self, resume_step=None):
        rs = self.resume_step if resume_step is None else resume_step
        _, snap = run(self.cfg, self.X, self.y, self.seed, True, stop_at=rs)
        rows, _ = run(self.cfg, self.X, self.y, self.seed, True, start=snap)
        return rows

    def total_steps(self):
        return EPOCHS * self.bpe


if __name__ == "__main__":
    import sys
    app = sys.argv[1] if len(sys.argv) > 1 else "."
    orc = Oracle(app)
    rows = orc.full_run(True)
    print("seed:", hex(orc.seed), "resume_step:", orc.resume_step,
          "total_steps:", orc.total_steps())
    for st, ls, gn in rows:
        print(f"step {st:2d}  loss={ls:.12f}  grad_norm={gn:.12f}")
