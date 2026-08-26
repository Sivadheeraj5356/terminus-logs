% Adversarial fixture: banks a weight for every comfortable row, so one body
% of passengers is counted on several buses at once.
include "globals.mzn";

int: L;
int: H;
int: MINW;
int: MAXW;
int: T;
int: F;
int: P;
array[1..L] of int: arr;
array[1..L] of int: ap;
array[1..L] of int: dep;
array[1..L] of int: dp;
array[1..L] of int: seats;
array[1..L] of int: terminus;
int: GAP;
array[1..T] of int: fline;
array[1..T] of int: cline;
array[1..T] of int: flow;
array[1..T] of int: w;
array[1..P, 1..P] of int: WK;

array[1..P, 1..P] of int: D1 = array2d(
  1..P, 1..P,
  [min([WK[i, j]] ++ [WK[i, k] + WK[k, j] | k in 1..P]) | i, j in 1..P],
);
array[1..P, 1..P] of int: D2 = array2d(
  1..P, 1..P,
  [min([D1[i, j]] ++ [D1[i, k] + D1[k, j] | k in 1..P]) | i, j in 1..P],
);
array[1..P, 1..P] of int: WALK = array2d(
  1..P, 1..P,
  [min([D2[i, j]] ++ [D2[i, k] + D2[k, j] | k in 1..P]) | i, j in 1..P],
);

array[1..L] of var 0..H - 1: x;
array[1..T] of var 0..1: board;

array[1..T] of var 0..H - 1: wait;
array[1..T] of var -4..4: kk;
constraint forall(t in 1..T)(
  x[cline[t]] + dep[cline[t]] - x[fline[t]] - arr[fline[t]]
  - WALK[ap[fline[t]], dp[cline[t]]]
  = wait[t] + kk[t] * H
);
constraint forall(t in 1..T)(
  board[t] = 1 -> (wait[t] >= MINW /\ wait[t] <= MAXW)
);

constraint forall(l1, l2 in 1..L where l1 < l2 /\ terminus[l1] = terminus[l2])(
  let {
    var 0..H-1: d;
    var -1..1: k;
    constraint x[l1] - x[l2] = d + k * H;
  } in min(d, H - d) >= GAP
);

var 0..sum(w): total = sum(t in 1..T)(w[t] * board[t]);
solve maximize total;

output ["x=", show(x), "\nboard=", show(board), "\n"];
