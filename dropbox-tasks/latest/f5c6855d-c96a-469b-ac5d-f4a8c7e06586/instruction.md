Implement the offline robust-policy evaluator in /app/estimate.R.

This is a machine-learning task in offline reinforcement learning and robust
Markov decision processes; the relational tables provide empirical model data,
not a generic data-processing target.

The program accepts optional data-directory and output-path arguments, defaulting
to /app/data and /app/results.csv. It must evaluate every requested
finite-horizon reachability case under a pre-action ambiguity plan that jointly
allocates both path resources across the policy's action branches, as defined in
/app/docs/OUTPUT-CONTRACT.md.

The fitted-kernel, ambiguity-profile, Bellman, support, tie, numerical, and CSV
contracts in that file are binding. Output must be deterministic, sorted by
case_id, and accurate within absolute error 1e-8.
