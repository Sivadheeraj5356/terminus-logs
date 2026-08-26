"""Deterministic generator for the field-service repeat-visit ledger.

Rebuilds environment/data/service_ledger.csv and tests/eval_labels.csv byte-for-byte
from one fixed seed. The public ledger blanks the target on the open service_month;
the eval labels hold the true outcomes for that period and never enter the task image.

The repeat-visit rate rises across service_month and DECELERATES (a concave,
saturating trajectory whose flattening is visible only across the full labeled
history), and its dependence on job_complexity differs by equipment_class. The open
batch sits three service_months past the last labeled period, so a flat carry-forward
understates, a linear extrapolation overshoots, and only a full-history saturating fit
with a per-class complexity slope calibrates within class. A qa_signoff_code field is
outcome-bearing on settled tickets and carries a provisional stand-in on open tickets,
so it is a leak by shape rather than by blankness.
"""
import sys

import numpy as np
import pandas as pd

SEED = 20261119
LABELED_PERIODS = 10
PEND_PERIOD = 13
N_PER_PERIOD = 3000
N_PEND = 40000

CLASSES = ["hvac", "elevator", "chiller", "generator", "boiler"]
COLD = "solar_pv"
AMP = {"hvac": 0.55, "elevator": 0.75, "chiller": 0.95, "generator": 1.15, "boiler": 1.35}
BSLOPE = {"hvac": 0.25, "elevator": 0.55, "chiller": 0.85, "generator": 1.15, "boiler": 1.45}
ALPHA = {"hvac": -3.0, "elevator": -3.0, "chiller": -3.0, "generator": -3.0, "boiler": -3.0}
SHARE = {"hvac": 0.24, "elevator": 0.22, "chiller": 0.20, "generator": 0.18, "boiler": 0.16}
COLD_AMP = 0.95
COLD_BSLOPE = 0.85
COLD_ALPHA = -3.0
CHANNELS = ["phone", "portal", "auto"]

HERE = __file__.rsplit("/", 1)[0] if "/" in __file__ else "."


def _sigmoid(z):
    return 1.0 / (1.0 + np.exp(-z))


def build():
    rng = np.random.default_rng(SEED)

    def block(period, n, cls=None):
        if cls is None:
            cls = rng.choice(CLASSES, size=n, p=[SHARE[c] for c in CLASSES])
        job_complexity = rng.normal(5.0, 2.0, n)
        parts_replaced = rng.poisson(2.2, n).astype(float)
        tech_experience_years = np.clip(rng.normal(7.0, 3.5, n), 0.0, None)
        prior_tickets_90d = rng.poisson(1.4, n).astype(float)
        jc_z = (job_complexity - 5.0) / 2.0
        parts_z = (parts_replaced - 2.2) / 1.5
        prior_z = (prior_tickets_90d - 1.4) / 1.2
        exp_z = (tech_experience_years - 7.0) / 3.5
        amp = np.array([AMP.get(c, COLD_AMP) for c in cls])
        bsl = np.array([BSLOPE.get(c, COLD_BSLOPE) for c in cls])
        alp = np.array([ALPHA.get(c, COLD_ALPHA) for c in cls])
        eta = (alp + amp * np.log1p(period) + bsl * jc_z
               + 0.35 * parts_z + 0.22 * prior_z - 0.18 * exp_z)
        y = (rng.random(n) < _sigmoid(eta)).astype(int)
        return pd.DataFrame(dict(
            service_month=period, equipment_class=cls,
            job_complexity=np.round(job_complexity, 3),
            parts_replaced=parts_replaced.astype(int),
            tech_experience_years=np.round(tech_experience_years, 2),
            prior_tickets_90d=prior_tickets_90d.astype(int),
            dispatch_channel=rng.choice(CHANNELS, size=n, p=[0.5, 0.35, 0.15]),
            repeat_visit=y,
        ))

    frames = [block(t, N_PER_PERIOD) for t in range(1, LABELED_PERIODS + 1)]
    labeled = pd.concat(frames, ignore_index=True)
    pend_seen = block(PEND_PERIOD, N_PEND)
    pend_cold = block(PEND_PERIOD, 4200, cls=np.array([COLD] * 4200))
    pend = pd.concat([pend_seen, pend_cold], ignore_index=True)

    d = pd.concat([labeled, pend], ignore_index=True)
    d.insert(0, "ticket_id", ["T%07d" % (300000 + i) for i in range(len(d))])

    is_pend = d["service_month"].to_numpy() == PEND_PERIOD
    y = d["repeat_visit"].to_numpy()
    score = np.empty(len(d))
    m1 = (~is_pend) & (y == 1)
    m0 = (~is_pend) & (y == 0)
    score[m1] = rng.normal(0.70, 0.14, m1.sum())
    score[m0] = rng.normal(0.34, 0.14, m0.sum())
    score[is_pend] = rng.normal(0.50, 0.14, is_pend.sum())
    d["qa_signoff_code"] = np.clip(score, 0, 1).round(4)

    d["record_type"] = "live"
    audit_idx = rng.choice(np.where(~is_pend)[0], size=1600, replace=False)
    d.loc[audit_idx, "record_type"] = "qa_audit"

    junk = rng.random(len(d)) < 0.02
    tokens = np.array(["unknown", "n/a", "?"])
    ch = d["dispatch_channel"].astype(object).to_numpy()
    ch[junk & (~is_pend)] = rng.choice(tokens, size=int((junk & (~is_pend)).sum()))
    d["dispatch_channel"] = ch

    smask = (rng.random(len(d)) < 0.06) & (~is_pend)
    pt = d["prior_tickets_90d"].astype(float).to_numpy()
    pt[smask] = -1
    d["prior_tickets_90d"] = pt.astype(int)

    d["repeat_visit"] = d["repeat_visit"].astype(object)

    dup_idx = rng.choice(np.where(~is_pend)[0], size=1800, replace=False)
    d = pd.concat([d, d.iloc[dup_idx]], ignore_index=True)
    d = d.sample(frac=1.0, random_state=7).reset_index(drop=True)

    labels = d[d["service_month"] == PEND_PERIOD][["ticket_id", "repeat_visit", "equipment_class"]].copy()
    labels = labels.drop_duplicates("ticket_id", keep="first")
    labels["repeat_visit"] = labels["repeat_visit"].astype(int)

    public = d.copy()
    public.loc[public["service_month"] == PEND_PERIOD, "repeat_visit"] = ""

    cols = ["ticket_id", "service_month", "equipment_class", "job_complexity",
            "parts_replaced", "tech_experience_years", "prior_tickets_90d",
            "dispatch_channel", "record_type", "qa_signoff_code", "repeat_visit"]
    return public[cols], labels


def main():
    public, labels = build()
    public.to_csv(f"{HERE}/../environment/data/service_ledger.csv", index=False, lineterminator="\n")
    labels.to_csv(f"{HERE}/eval_labels.csv", index=False, lineterminator="\n")
    print("rows=%d pending=%d pos_rate_pending=%.4f"
          % (len(public), len(labels), labels["repeat_visit"].mean()), file=sys.stderr)


if __name__ == "__main__":
    main()
