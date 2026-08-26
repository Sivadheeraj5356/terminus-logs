# The Rust Markdown converter at `/app/` has bugs that cause it to produce incorre

Submission: `f3fe938b-acb6-435b-b414-d0c80e4f333b`  
Slug: `the-rust-markdown-converter-at-app-has-bugs-that-cause-it-to`  
Latest archive: `f3fe938b-acb6-435b-b414-d0c80e4f333b_submission_2026-07-07T16_33_02.799Z.zip`  
Revisions in Dropbox: 1

## Task summary

The Rust Markdown converter at `/app/` has bugs that cause it to produce incorrect HTML output and wrong statistics in `/app/output/report.json`. The tool reads `.md` files from `/app/input/`, converts each to an HTML file in `/app/output/`, and writes a JSON summary report. The expected behavior for the parser and statistics generator is: - **Headings**: The parser must strictly assign heading levels based on the exact number of `#` characters (from 1 to 6). - **Code blocks**: Fenced code blocks must only be closed by a line that begins with a matching sequence of the exact same fence character (` ``` ` or `~~~`) that opened it. - **Links**: The `link_count` metric must accurately accumulate all inline links found within the document (including both paragraphs and headings). - **Statistics**: The `average_blocks_per_file` metric must accurately reflect a true floating-point average (rounded to 1 decimal place), avoiding truncation issues. - **Heading Distribution**: The `heading_distribution` must accurately reflect the true, unshifted heading levels.

Required artifacts include: `/app/output/report.json`, `/app/input/`, `/app/output/`.

Author anonymous tagged this **hard** system-administration task (markdown, html-conversion, parser-bug, block-level-parsing).

Time estimates: expert ~30.0 min, junior ~90.0 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `f3fe938b-acb6-435b-b414-d0c80e4f333b_submission_2026-07-07T16_33_02.799Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
