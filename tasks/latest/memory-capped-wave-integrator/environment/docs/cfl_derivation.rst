# CFL Stability Criterion Derivation

The stability of the explicit finite difference wave solver is determined by the Courant-Friedrichs-Lewy (CFL) condition.
For the 2D wave equation:
$$u_{tt} = c^2 (u_{xx} + u_{yy})$$

Using Von Neumann stability analysis, we substitute $u^n_{j,l} = g^n e^{i(k_x j dx + k_y l dx)}$ into the discrete equations.
For stability, we require the amplification factor $|g| \le 1$.

For the 2nd-order spatial stencil, this yields:
$$dt \le \frac{dx}{c \sqrt{2}}$$

For the 4th-order spatial stencil, the stability limit is reduced by a factor of $\sqrt{3/7}$:
$$dt \le \sqrt{\frac{3}{7}} \frac{dx}{c \sqrt{2}} \approx 0.65465 \frac{dx}{c \sqrt{2}}$$
If $dt$ exceeds this value, the amplification factor exceeds $1$, leading to exponential growth and numerical blowup.
