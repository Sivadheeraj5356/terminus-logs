int: T;
int: P;
int: B;
array[1..P] of int: v;
array[1..P, 1..T] of int: d;
array[1..P, 1..T] of int: c;
array[1..T] of int: shockwave;
int: F;
int: A;
int: h;
array[1..P] of int: smin;
int: G;
int: PeakV;
int: S;
int: W;

array[1..P] of int: CAP = [sum(t in 1..T)(d[p, t]) + smin[p] | p in 1..P];
int: VCAP = sum(p in 1..P)(v[p] * CAP[p]);
int: KMAX = (VCAP + B - 1) div B;
array[1..P, 1..T] of var 0..max(CAP): q;
array[1..P, 1..T] of var 0..max(CAP): inv;
constraint forall(p in 1..P, t in 1..T)(q[p, t] <= CAP[p]);
constraint forall(p in 1..P, t in 1..T)(inv[p, t] <= CAP[p]);
array[1..T] of var 0..VCAP: vol;
array[1..T] of var 0..KMAX: run;
var 0..KMAX: K;
array[1..T] of var 0..1: hw;
array[1..T] of var 0..VCAP: over;
array[1..T] of var 0..1: peak;
array[1..T] of var 0..1: sw;

constraint forall(p in 1..P)(inv[p, 1] = q[p, 1] - d[p, 1]);
constraint forall(p in 1..P, t in 2..T)(inv[p, t] = inv[p, t - 1] + q[p, t] - d[p, t]);
constraint forall(p in 1..P, t in 1..T)(inv[p, t] >= smin[p]);
constraint forall(t in 1..T)(vol[t] = sum(p in 1..P)(v[p] * q[p, t]));
constraint forall(t in 1..T)(run[t] = (vol[t] + B - 1) div B);
constraint forall(t in 1..T)(hw[t] = bool2int(run[t] > K));
constraint forall(t in 1..T)(over[t] = sum(p in 1..P)(v[p] * inv[p, t]));
constraint forall(t in 1..T)(peak[t] = bool2int(vol[t] > PeakV));
constraint forall(t in 1..T)(sw[t] = bool2int(shockwave[t] = 1 /\ vol[t] > 0));

int: CMAX = sum(p in 1..P, t in 1..T)(c[p, t] * CAP[p]) + A * KMAX + F * T + h * T * VCAP + S * T + W * T;
var 0..CMAX: total =
  sum(p in 1..P, t in 1..T)(c[p, t] * q[p, t]) + A * K + F * sum(t in 1..T)(hw[t]) +
  h * sum(t in 1..T)(over[t]) + S * sum(t in 1..T)(peak[t]) + W * sum(t in 1..T)(sw[t]);
solve minimize total;

output [
  "q1=", show([q[1, t] | t in 1..T]), "\n",
  "q2=", show([q[2, t] | t in 1..T]), "\n"
];
