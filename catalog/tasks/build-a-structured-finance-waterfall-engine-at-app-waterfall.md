# Build a structured finance waterfall engine at /app/waterfall.go. Reads /app/inp

Submission: `e006dba1-ee31-4298-ab68-00735913a6b5`  
Slug: `build-a-structured-finance-waterfall-engine-at-app-waterfall`  
Latest archive: `e006dba1-ee31-4298-ab68-00735913a6b5_submission_2026-07-21T03_14_15.646Z.zip`  
Revisions: 3

## Task summary

Build a structured finance waterfall engine at /app/waterfall.go. Reads /app/input/collections.json, writes /app/output/waterfall.json. Input has tranches (id, class A/B/C/residual, balance, coupon_rate) and periods (period, collections, defaults, prepayments, senior_fee, servicer_fee). Original pool balance = sum of starting tranche balances. Run: cd /app && go build -o /app/waterfall . && /app/waterfall Each period: available = collections - defaults + prepayments - senior_fee - servicer_fee. Loss allocation first: if defaults this period exceed 3% of current pool balance (sum of all tranche balances at period start), write down the excess bottom-up (residual, then C, B, A). Pay interest A then B then C (post-writedown balance * coupon_rate / 12, 2dp). Shortfall capitalizes as PIK: add the shortfall to the tranche's outstanding principal balance each period and track cumulative PIK per tranche. Scheduled principal = collections - total_interest_paid - senior_fee - servicer_fee - prepayments, floored at zero. Distribute min(scheduledPrincipal, available) per mode: sequential pays A first then B then C, pro_rata splits proportionally by balance among A/B/C (round each share 2dp, no redistribution). Then distribute min(prepayments, available) pro-rata across A/B/C by balance. Excess handling: first fill reserve to cap (2% of original pool). After reserve at cap, pay off cumulative PIK in order A then B then C (reduce balance by recovery amount, cap at available and at tranche's cumulative PIK). PIK recovery is reported only in pik_recovered and must NOT be added to...

Required artifacts include: `/app/waterfall.go`, `/app/input/collections.json`, `/app/output/waterfall.json`, `/app/waterfall`.

Author anonymous tagged this **hard** data-processing task (securitization, waterfall, abs, tranches, pik, structured-finance).

Time estimates: expert ~100 min, junior ~200 min.

Harbor timeouts: agent 900.0s, verifier 450.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `e006dba1-ee31-4298-ab68-00735913a6b5_submission_2026-07-21T03_14_15.646Z.zip` is a task submission, not a Harbor job. 3 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Agent writes a locally plausible solution that misses a hidden verifier constraint. Agent explores the environment and never produces the required /app or /output artifacts.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
