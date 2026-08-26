# I am working on building a lightweight convolutional neural network framework in

- **UUID:** `5dbcc225-740b-481a-a116-f6ab0b53762d`
- **Slug:** `i-am-working-on-building-a-lightweight-convolutional-neural`
- **Category:** machine-learning
- **Difficulty:** hard

## Summary

I am working on building a lightweight convolutional neural network framework in Go from scratch, and I need help finishing the core tensor layers. Specifically, we need to complete the implementation of a 2D Polar Modulated Grouped Deformable Convolution layer (`DeformableConv2D`), a 2D GroupEvoNorm-S0 layer (`GroupEvoNorm2D`), and an Anti-Aliased Blur Pooling layer (`BlurPool2D`) inside the skeleton files located at `/app/conv2d.go`, `/app/groupevonorm2d.go`, and `/app/blurpool2d.go`.

In our formulation of DeformableConv2D, the coordinate offsets and modulation masks are not passed as external inputs but are predicted dynamically from the input tensor by an internal standard 2D convolution layer parameterized by `OffsetWeights` and `OffsetBiases`. The main convolution filter weights are normalized by applying Row-wise Weight Standardization, Spectral Normalization (using 5 steps of the Power Iteration algorithm per group, keeping track of the stateful singular vectors $u^{(g)}$ and $v^{(g)}$), and 3 steps of Björck Orthogonalization per group.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
