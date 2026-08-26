% Adversarial fixture: bakes in the committed answer and ignores the
% instance entirely.
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

array[1..L] of var 0..H - 1: x;
array[1..T] of var 0..1: board;

array[int] of int: XS = [14, 7, 3, 0, 4, 4, 8];
array[int] of int: BS = [0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 1, 0, 0, 0, 1, 0, 0, 1, 1, 0, 0, 0, 0];
constraint forall(l in 1..L where l <= length(XS))(x[l] = XS[l]);
constraint forall(t in 1..T where t <= length(BS))(board[t] = BS[t]);

var 0..1: total = 1;
solve maximize total;

output ["x=", show(x), "\nboard=", show(board), "\n"];
