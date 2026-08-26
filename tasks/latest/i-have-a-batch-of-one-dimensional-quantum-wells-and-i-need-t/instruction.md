I have a batch of one-dimensional quantum wells and I need the low-lying bound-state energies for each of them. A well is a single particle in a potential V(x), governed by the time-independent equation

    -1/2 * psi''(x) + V(x) * psi(x) = E * psi(x)      (hbar = m = 1)

The wells are in /app/data/potentials.json, as a list under the key "instances". Each entry has:

- "id": a string label
- "xmin", "xmax", "n": a uniform grid of n points, x_i = xmin + i*(xmax - xmin)/(n - 1) for i = 0 .. n-1
- "V": the potential sampled at those n grid points, in order
- "k": how many of the lowest energy levels I want

The particle is confined to the well: treat psi as zero at and beyond the two grid endpoints.

Write your solver as a Dart program at /app/solve.dart. It takes two command-line arguments — the path to an input file (a batch in the format above) and the path to write the results — and it must work for any batch given in that format, not just this one. For each instance it computes the k lowest energy eigenvalues in ascending order and writes them as:

    {"results": [{"id": "p01", "energies": [e0, e1, ...]}, ...]}

Then run it on the batch above to produce /app/energies.json. Each energy must be accurate to within 1e-5 (absolute). The potentials are only given to you as those grid samples, so whatever accuracy you report has to come out of the points you're handed.
