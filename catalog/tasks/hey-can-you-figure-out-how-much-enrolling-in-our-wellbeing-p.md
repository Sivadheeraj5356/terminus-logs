# Hey, can you figure out how much enrolling in our wellbeing program changed peop

Submission: `d68f981b-3bb6-4fb2-a036-8bcd67915105`  
Slug: `hey-can-you-figure-out-how-much-enrolling-in-our-wellbeing-p`  
Latest archive: `d68f981b-3bb6-4fb2-a036-8bcd67915105_submission_2026-07-10T17_21_11.589Z.zip`  
Revisions in Dropbox: 4

## Task summary

Hey, can you figure out how much enrolling in our wellbeing program changed people's end of year wellbeing index? We ran a voluntary program last year, some staff joined and some did not, and I need the average effect of enrolling across everyone in these records, in wellbeing index units. Enrollment was not random, people self selected and the program pushed some folks harder than others, so a plain comparison of enrolled versus not mostly picks up differences that were there before anyone joined. I want the causal effect of the program itself, averaged over the whole population in the data, not only those who enrolled. The data is five csv files in the directory given by CAUSAL_DATA_DIR, defaulting to /app/data. Read from there so the same code can run against another copy laid out the same way. baseline_covariates.csv has eight baseline indices per employee, tenure.csv has years at the company, outreach.csv has how many reminders the program sent, enrollment.csv has who enrolled, and outcome.csv has the end of year index. Join them on employee_id first. Before deciding how to use each measurement, read the notes under /app/docs, which say what each field is and when it was recorded.

Required artifacts include: `/app/data`, `/app/docs`, `/app/analysis.R`, `/app/estimate.json`.

Author anonymous tagged this **hard** machine-learning task (causal-inference, workplace-wellbeing, observational-cross-section, continuous-outcome).

Time estimates: expert ~50 min, junior ~150 min.

Harbor timeouts: agent 1200.0s, verifier 1200.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `d68f981b-3bb6-4fb2-a036-8bcd67915105_submission_2026-07-10T17_21_11.589Z.zip` is a task submission, not a Harbor job. 4 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Model or pipeline trains/runs but misses accuracy, format, or artifact-path gates.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
