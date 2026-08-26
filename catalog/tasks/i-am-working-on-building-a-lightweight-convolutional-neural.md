# I am working on building a lightweight convolutional neural network framework in

Submission: `5dbcc225-740b-481a-a116-f6ab0b53762d`  
Slug: `i-am-working-on-building-a-lightweight-convolutional-neural`  
Latest archive: `5dbcc225-740b-481a-a116-f6ab0b53762d_submission_2026-07-16T10_42_21.014Z.zip`  
Revisions: 2

## Task summary

I am working on building a lightweight convolutional neural network framework in Go from scratch, and I need help finishing the core tensor layers. Specifically, we need to complete the implementation of a 2D Polar Modulated Grouped Deformable Convolution layer (`DeformableConv2D`), a 2D GroupEvoNorm-S0 layer (`GroupEvoNorm2D`), and an Anti-Aliased Blur Pooling layer (`BlurPool2D`) inside the skeleton files located at `/app/conv2d.go`, `/app/groupevonorm2d.go`, and `/app/blurpool2d.go`. In our formulation of DeformableConv2D, the coordinate offsets and modulation masks are not passed as external inputs but are predicted dynamically from the input tensor by an internal standard 2D convolution layer parameterized by `OffsetWeights` and `OffsetBiases`. The main convolution filter weights are normalized by applying Row-wise Weight Standardization, Spectral Normalization (using 5 steps of the Power Iteration algorithm per group, keeping track of the stateful singular vectors $u^{(g)}$ and $v^{(g)}$), and 3 steps of Björck Orthogonalization per group. Additionally, the Bicubic Spline Interpolation uses a learnable parameter `SplineAlpha` per channel. Since we aren't using any external deep learning or matrix libraries, we have to handle all matrix operations, bicubic spline interpolation, non-linear coordinate transforms, forward propagation, and backward gradient passes manually using only the Go standard library. To complete the task, implement the Forward, Backward, and Update methods for the DeformableConv2D, GroupEvoNorm2D, and BlurPool2D layers. The implementation must...

Required artifacts include: `/app/conv2d.go`, `/app/groupevonorm2d.go`, `/app/blurpool2d.go`, `/app/spec.md`.

Author anonymous tagged this **hard** machine-learning task (cnn, backpropagation, group-normalization, gradient-check, weight-standardization, spectral-normalization, bjorck-orthogonalization).

Time estimates: expert ~120 min, junior ~240 min.

Harbor timeouts: agent 900.0s, verifier 450.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `5dbcc225-740b-481a-a116-f6ab0b53762d_submission_2026-07-16T10_42_21.014Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Model or pipeline trains/runs but misses accuracy, format, or artifact-path gates.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
