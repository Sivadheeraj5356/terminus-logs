# The command-line tool `formula-order` in `/app` decides which of two formula ver

Submission: `b58913bd-5fea-48c7-82e8-543b46328334`  
Slug: `the-command-line-tool-formula-order-in-app-decides-which-of-`  
Latest archive: `b58913bd-5fea-48c7-82e8-543b46328334_submission_2026-07-17T02_40_47.061Z.zip`  
Revisions in Dropbox: 6

## Task summary

The command-line tool `formula-order` in `/app` decides which of two formula versions is the newer one, so the catalog can keep a formula's published releases in order when it plans an upgrade or pins a dependency. Given two version strings on the command line, it prints -1 when the first is older than the second, 1 when the first is newer, and 0 when the two rank equally. Today it only handles plain dotted-number releases, so it misranks most of the versions a real catalog publishes; it needs to order the full range of versions the way Homebrew itself orders formula versions. That ordering reaches well past comparing dotted numbers. Releases carry pre-release words such as alpha, beta, pre and rc, patch- and post-release markers, single-letter revisions, and numeric revisions embedded inside those markers, and two versions can still rank equal despite differing in their separators, in leading zeros, or in a trailing zero component. The file `/app/examples.json` records a sample of how such decorated versions are expected to rank. The comparator lives under `/app/internal/version` behind the `Compare` function; make its ordering match Homebrew across this whole range while leaving the existing plain dotted-number behaviour unchanged.

Required artifacts include: `/app/examples.json`, `/app/internal/version`.

Author anonymous tagged this **hard** build-and-dependency-management task (version-ordering, package-manager, dependency-resolution, homebrew, go).

Time estimates: expert ~90 min, junior ~240 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `b58913bd-5fea-48c7-82e8-543b46328334_submission_2026-07-17T02_40_47.061Z.zip` is a task submission, not a Harbor job. 6 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
