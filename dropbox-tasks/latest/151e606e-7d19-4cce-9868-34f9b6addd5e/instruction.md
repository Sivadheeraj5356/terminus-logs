A scanner records the parallel-beam projections of an unknown image from many angles, the
way a slice scanner captures how much a slice absorbs along each ray, and packs one batch
of those scans into a single binary container. We need a Go program that reads the
container, recovers the scans, reports each recovered sinogram, and reconstructs the
original image on its pixel grid. Compile it to a binary at /app/ctrecon; a stub main.go
that compiles but returns nothing is at /app/main.go for you to replace. It reads one JSON
object on standard input and writes one JSON object on standard output, one result per
scan in the batch, in order.

The catch is the container. Its format is not written down. There is a reference decoder
at /app/ref/ct-probe that recovers a whole batch from a base64 container on a line of
standard input and prints it as JSON, and there are worked examples at
/app/samples/sample_scans.json, each a container and the scans it decodes to. Run the
decoder on the examples, feed it batches of your own, and take it apart however helps, then
reproduce the recovery in your own code. It packs a header, the projection angles, and the
sinogram, and the projection samples are stored through a companding curve whose strength
shifts from one scan to the next in the batch, so reading the stored codes on a single
fixed curve gives the wrong samples; the curve has to be recovered for each scan. The
decoder is only there while you develop. It is gone when the program is graded, so the
recovery has to live in your own code and generalize to containers you have not seen, which
a stored table of the sample outputs will not do.

Once a scan is recovered, reconstruct its image so that the image projections match the
recovered sinogram, for example by refining an estimate that forward-projects, compares to
the recovered sinogram, and back-projects the residual while staying non-negative. The pixel
grid and detector geometry are written up in /app/docs/ctrecon-spec.md, so follow that. The
recovered sinogram is graded against the reference within a tolerance, so the per-scan
companding has to come out right, and the image is graded up to an overall brightness offset
and scale, so only the structure has to match. Two runs on the same input must produce
byte-identical output. Do the whole computation in your own Go code with the standard
library only, and do not call the reference decoder or shell out to any program at run time.
