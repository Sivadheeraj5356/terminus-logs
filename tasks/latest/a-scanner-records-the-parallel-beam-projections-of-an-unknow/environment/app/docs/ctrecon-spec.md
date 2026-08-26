# Parallel-beam scan recovery and reconstruction

A scanner records the parallel-beam projections of an unknown image at many angles and
packs one batch of scans into a single binary container. The container transform is not
documented here. A reference decoder at `/app/ref/ct-probe` and worked examples under
`/app/samples/sample_scans.json` are provided so the container can be reverse engineered.
The tool recovers each scan from the container, reports the recovered sinogram, and
reconstructs the image on its pixel grid.

## Deliverable

A compiled Go binary at `/app/ctrecon`, built from Go source under `/app` using only the
standard library. It reads one JSON object on standard input and writes one JSON object on
standard output.

The reference decoder at `/app/ref/ct-probe` is a development aid only. It is not present
when the tool is graded, so the tool must recover the container in its own code. It reads
one base64 container on a line of standard input and prints the recovered batch as JSON.

## Container

Standard input is one JSON object `{"blob": string}`, where `blob` is base64 of the binary
container for a batch of scans. Decoding it yields, in order, the scans of the batch. Each
scan carries an image size, a detector count, a list of projection angles in radians, and a
sinogram, which is a row of `n_det` projection samples for each angle.

The reference decoder recovers every scan in a batch from the container. Run it on the
bundled examples, feed it batches of your own, and inspect the tool itself to work out how
the container packs the batch and how the projection samples are stored, then reproduce
that recovery in the tool. The samples are stored through a per-record companding curve
whose strength shifts from one scan to the next, so reading the stored codes on a single
fixed curve recovers the wrong samples; the curve has to be recovered per scan. The worked
examples in `/app/samples/sample_scans.json` each give a container and the scans it decodes
to, so a stored table of those outputs will not carry over to the graded batches.

## Forward model

The image is `N` by `N` on a pixel grid. Pixel `(row, col)` sits at
`x = col - (N-1)/2`, `y = (N-1)/2 - row`. A projection at angle `theta` has `n_det`
detector bins; bin `t` sits at signed detector offset `s = t - (n_det-1)/2`. A point at
image coordinate `(x, y)` lands on detector offset `s = x*cos(theta) + y*sin(theta)`. Each
projection value is the ray sum through the image, evaluated with two-times oversampling
across the image width and bilinear image sampling; a faithful reconstruction does not need
to match the forward model bit for bit.

## Reconstruction

Reconstruct the image so that its own projections match the recovered sinogram, for example
by an iterative update that forward-projects the current estimate, compares to the recovered
sinogram, and back-projects the residual, holding the estimate non-negative. The
reconstruction is graded up to an overall brightness offset and scale, so any faithful
reconstruction passes; the relative error has to fall below a tolerance.

## Output

Standard output is one JSON object `{"results": [{"sinogram": [[float]], "image":
[[float]]}]}` with one entry per scan in the batch, in order. `sinogram` is the recovered
sinogram, `angles` by `n_det`, and `image` is the reconstructed image, `N` by `N`. The
recovered sinogram is graded against the reference within an absolute and relative
tolerance, so it must reproduce the per-scan companding, and the image is graded up to
brightness and scale.

## Constraints

The tool uses only the Go standard library, does not use the network, does not import
`os/exec`, `syscall`, `os/user`, `plugin`, `net`, or `net/http`, and does not shell out to
another program or call the reference decoder at run time. The container recovery and the
reconstruction are implemented in the tool itself.
