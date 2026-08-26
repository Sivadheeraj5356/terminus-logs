Storage-node volumes V(t) are the unknowns. Boundary nodes are not unknowns.

dV_i/dt = external_inflow_i + sum(flows entering i) - sum(flows leaving i).
Internal links contribute equal and opposite terms. Boundary links exchange with the exterior.

At an evaluated state: invert volumes to levels with active curves, use active boundary levels, evaluate link flows, assemble derivatives. Storage-node order is lexicographic by node_id.

Implicit midpoint from t0 to t1=t0+dt with V0:
Vmid=(V0+V1)/2, tmid=(t0+t1)/2
F(V1)=V1-V0-dt*f(Vmid,tmid)=0

Initial guess: V1=V0+dt*f(V0,t0), clamp to curve bounds only for initialization.
Residual: infinity norm. Tolerance: newton_abs + newton_rel*max(1,max|V1|).

Jacobian: J=I-(dt/2)*df/dVmid via central (or one-sided) finite differences with
epsilon_j=max(1e-8, 1e-7*max(1,|Vmid_j|)).
Solve J*delta=-F with Gaussian elimination and partial pivoting (largest abs pivot; ties by lowest row index; pivot < 1e-14 fails).

Damped update: alpha in {1,1/2,...,1/128}; accept when all volumes in-curve and residual strictly decreases.

Adaptive control uses step doubling. Commit V_half2 when error<=1.
scale_i = vol_abs + vol_rel*max(1,|V_full_i|,|V_half2_i|)
error = max |V_half2-V_full|/scale
After accept: error<0.0625 -> next=min(2dt,max); error>0.5 -> next=max(dt/2,min); else next=dt
After reject: dt/=2; fail if below minimum_step_s by more than 1e-12.

Never cross forcing, output, stop, or end boundaries. Truncate dt exactly. Do not reset adaptive step solely because a boundary was hit. Each accepted candidate adds 2 accepted_substeps; each reject adds 1 rejected_attempt.
