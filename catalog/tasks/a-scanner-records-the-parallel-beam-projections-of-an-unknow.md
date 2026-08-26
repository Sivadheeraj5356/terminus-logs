# A scanner records the parallel-beam projections of an unknown image from many an

Submission: `151e606e-7d19-4cce-9868-34f9b6addd5e`  
Slug: `a-scanner-records-the-parallel-beam-projections-of-an-unknow`  
Latest archive: `151e606e-7d19-4cce-9868-34f9b6addd5e_submission_2026-07-14T14_35_44.925Z.zip`  
Revisions in Dropbox: 4

## Task summary

A scanner records the parallel-beam projections of an unknown image from many angles, the way a slice scanner captures how much a slice absorbs along each ray, and packs one batch of those scans into a single binary container. We need a Go program that reads the container, recovers the scans, reports each recovered sinogram, and reconstructs the original image on its pixel grid. Compile it to a binary at /app/ctrecon; a stub main.go that compiles but returns nothing is at /app/main.go for you to replace. It reads one JSON object on standard input and writes one JSON object on standard output, one result per scan in the batch, in order. The catch is the container. Its format is not written down. There is a reference decoder at /app/ref/ct-probe that recovers a whole batch from a base64 container on a line of standard input and prints it as JSON, and there are worked examples at /app/samples/sample_scans.json, each a container and the scans it decodes to. Run the decoder on the examples, feed it batches of your own, and take it apart however helps, then reproduce the recovery in your own code. It packs a header, the projection angles, and the sinogram, and the projection samples are stored through a companding curve whose strength shifts from one scan to the next in the batch, so reading the stored codes on a single fixed curve gives the wrong samples; the curve has to be recovered for each scan. The decoder is only there while you develop. It is gone when the program is graded, so the recovery has to live in your own code and generalize to containers you have not seen,...

Required artifacts include: `/app/ctrecon`, `/app/main.go`, `/app/ref/ct-probe`, `/app/samples/sample_scans.json`, `/app/docs/ctrecon-spec.md`.

Author anonymous tagged this **medium** scientific-computing task (reverse-engineering, binary-decoding, tomography, image-reconstruction, numerical-methods).

Time estimates: expert ~180.0 min, junior ~420.0 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `151e606e-7d19-4cce-9868-34f9b6addd5e_submission_2026-07-14T14_35_44.925Z.zip` is a task submission, not a Harbor job. 4 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
