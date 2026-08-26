# Collision detection and fragment spawning

## Collision detection

After integrating all bodies for a timestep, check every pair (i, j) with i < j.

Two bodies collide when the distance between their centers is less than the sum of their radii:
|pos_i - pos_j| < radius_i + radius_j

Process at most one collision per timestep. If multiple pairs collide, pick the pair with the lexicographically smallest (id_a, id_b) where id_a < id_b.

## Fragment spawning

When bodies A and B collide, they are removed and K = fragment_count new bodies are created.

### Mass and radius

- Total mass M = mass_a + mass_b
- Each fragment mass m_f = M / K
- Each fragment radius r_f = cbrt((radius_a^3 + radius_b^3) / K)

### Collision geometry

- Collision point = mass-weighted midpoint: (pos_a * mass_a + pos_b * mass_b) / M
- Center-of-mass velocity v_cm = (mass_a * vel_a + mass_b * vel_b) / M

### Energy conservation

- E_total = 0.5 * mass_a * |vel_a|^2 + 0.5 * mass_b * |vel_b|^2
- E_cm = 0.5 * M * |v_cm|^2
- E_rel = E_total - E_cm (clamp to zero if negative due to floating point)

### Fragment velocity distribution

- Relative direction n = unit(vel_a - vel_b); if near-zero magnitude, use unit(pos_a - pos_b) or fallback {1, 0, 0}
- Build orthonormal basis (n, u, w) where u and w span the plane perpendicular to n
- Fragment spread speed s = sqrt(2 * E_rel / M)
- For fragment k (0 to K-1):
  - theta_k = k * 2 * PI / K
  - vel_k = v_cm + s * (cos(theta_k) * u + sin(theta_k) * w)
  - pos_k = collision_point + min_sep_m * (cos(theta_k) * u + sin(theta_k) * w)

### Child IDs

Sort the two parent IDs alphabetically. Child ID format: {sorted_parent_0}__{sorted_parent_1}__f{k}

### Epoch record

Each collision produces an epoch record with:
- t_sec: simulation time rounded to 6 decimal places
- parents: sorted pair [parent_a, parent_b]
- child_ids: array of child ID strings
- momentum_residual: magnitude of (sum of fragment momenta - total pre-collision momentum), rounded to 6 decimals
- energy_residual: |sum of fragment kinetic energies - E_total|, rounded to 6 decimals
