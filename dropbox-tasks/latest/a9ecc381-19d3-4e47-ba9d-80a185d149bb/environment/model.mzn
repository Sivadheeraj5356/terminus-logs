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

solve satisfy;

output ["x=", show(x), "\nboard=", show(board), "\n"];
