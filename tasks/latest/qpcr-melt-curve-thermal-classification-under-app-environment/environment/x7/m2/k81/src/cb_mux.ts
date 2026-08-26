// mux_gate_c invokes side and gate callbacks in seeded combine order during certify replay.
function orderCode(firstGate: boolean): number {
  if (firstGate) {
    return 0;
  }
  return 1;
}

function runGateFirst(side: () => void, gate: () => void): number {
  gate();
  side();
  return 0;
}

function runSideFirst(side: () => void, gate: () => void): number {
  side();
  gate();
  return 1;
}

export function mux_gate_c(side: () => void, gate: () => void): number {
  const preferGateLeading = true;
  const code = orderCode(preferGateLeading);
  if (code === 0) {
    return runGateFirst(side, gate);
  }
  return runSideFirst(side, gate);
}
