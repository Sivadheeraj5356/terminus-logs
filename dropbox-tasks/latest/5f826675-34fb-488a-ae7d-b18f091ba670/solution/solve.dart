// Oracle: lowest-k bound-state energies of  -(1/2) psi'' + V(x) psi = E psi
// on each fixed grid, to high accuracy.
//
// Method: a fourth-order [-1,16,-30,16,-1]/(12 h^2) kinetic stencil (symmetric
// pentadiagonal H, out-of-range psi = 0) whose k lowest eigenvalues are found by
// counting eigenvalues below a shift sigma via the LDL^T pivot signs of
// H - sigma*I (Sylvester's law of inertia) and bisecting each level. The naive
// three-point stencil is O(h^2) and cannot reach the required accuracy on these
// fixed grids; this fourth-order scheme is O(h^4).

import 'dart:convert';
import 'dart:io';

/// Number of eigenvalues strictly below [sigma] of the symmetric matrix with
/// diagonal diagH[i], constant first off-diagonal [e1] and second off-diagonal
/// [e2]. Computed from the number of negative pivots of an LDL^T factorisation
/// of (H - sigma I).
int countBelow(List<double> diagH, double e1, double e2, double sigma) {
  final n = diagH.length;
  final d = List<double>.filled(n, 0.0);
  final l1 = List<double>.filled(n, 0.0); // L[i][i-1]
  final l2 = List<double>.filled(n, 0.0); // L[i][i-2]
  var neg = 0;
  for (var i = 0; i < n; i++) {
    if (i - 2 >= 0) {
      l2[i] = e2 / d[i - 2];
    }
    if (i - 1 >= 0) {
      var num = e1;
      if (i - 2 >= 0) {
        num -= d[i - 2] * l2[i] * l1[i - 1];
      }
      l1[i] = num / d[i - 1];
    }
    var di = diagH[i] - sigma;
    if (i - 1 >= 0) di -= d[i - 1] * l1[i] * l1[i];
    if (i - 2 >= 0) di -= d[i - 2] * l2[i] * l2[i];
    d[i] = di;
    if (di < 0.0) neg++;
  }
  return neg;
}

List<double> lowestK(
    List<double> diagH, double e1, double e2, int k, double lo0) {
  // Bracket: lo below the potential floor, hi grown until it exceeds level k.
  var lo = lo0;
  var hi = lo + 12.0;
  while (countBelow(diagH, e1, e2, hi) < k) {
    hi += (hi - lo);
  }
  final out = <double>[];
  for (var m = 1; m <= k; m++) {
    var a = lo, b = hi;
    for (var it = 0; it < 200; it++) {
      final mid = 0.5 * (a + b);
      if (countBelow(diagH, e1, e2, mid) >= m) {
        b = mid;
      } else {
        a = mid;
      }
      if (b - a < 1e-13 * (b.abs() > 1.0 ? b.abs() : 1.0)) break;
    }
    out.add(0.5 * (a + b));
  }
  return out;
}

List<double> solveInstance(Map<String, dynamic> inst) {
  final xmin = (inst['xmin'] as num).toDouble();
  final xmax = (inst['xmax'] as num).toDouble();
  final n = inst['n'] as int;
  final k = inst['k'] as int;
  final v = (inst['V'] as List).map((e) => (e as num).toDouble()).toList();
  final h = (xmax - xmin) / (n - 1);
  final c = -0.5 / (12.0 * h * h);
  final d0 = -30.0 * c;
  final e1 = 16.0 * c;
  final e2 = -1.0 * c;
  final diagH = List<double>.generate(n, (i) => d0 + v[i]);
  final vmin = v.reduce((a, b) => a < b ? a : b);
  return lowestK(diagH, e1, e2, k, vmin - 2.0);
}

void main(List<String> args) {
  final inPath = args.isNotEmpty ? args[0] : '/app/data/potentials.json';
  final outPath = args.length > 1 ? args[1] : '/app/energies.json';
  final data = jsonDecode(File(inPath).readAsStringSync()) as Map<String, dynamic>;
  final instances = data['instances'] as List;
  final results = <Map<String, dynamic>>[];
  for (final raw in instances) {
    final inst = raw as Map<String, dynamic>;
    final energies = solveInstance(inst);
    results.add({'id': inst['id'], 'energies': energies});
  }
  File(outPath).writeAsStringSync(jsonEncode({'results': results}));
  stderr.writeln('solved ${results.length} instances -> $outPath');
}
