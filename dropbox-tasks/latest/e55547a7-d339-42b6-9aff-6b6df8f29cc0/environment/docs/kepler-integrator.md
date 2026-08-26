# Kepler integrator

All bodies are propagated using RK2 (midpoint method) at each timestep dt_sec from the manifest.

## Constants

- MU_EARTH = 3.986004418e14 (m^3/s^2)
- R_EARTH = 6371000 (m)
- RHO0 = 1.225 (kg/m^3 at sea level)
- SCALE_H = 8500 (m, atmospheric scale height)

## Acceleration model

Total acceleration on a body is the sum of gravitational acceleration and atmospheric drag.

### Gravity

a_grav = -MU_EARTH / r^3 * pos

where r = magnitude of the position vector pos.

### Atmospheric drag

Compute atmospheric density at altitude:
rho = RHO0 * exp(-(r - R_EARTH) / SCALE_H) * density_scale

where density_scale is the current flare-adjusted value (see drag-flare.md).

Drag area:
area = PI * radius_m^2

Drag acceleration:
a_drag = -0.5 * rho * cd * area * |vel| * vel / mass_kg

The cd coefficient comes from the body record (default 2.2).

### Combined

a_total(pos, vel) = a_grav(pos) + a_drag(pos, vel)

## RK2 midpoint integration

Given body state (p, v) and timestep dt:

1. a0 = a_total(p, v)
2. p_mid = p + v * (dt / 2)
3. v_mid = v + a0 * (dt / 2)
4. a1 = a_total(p_mid, v_mid)
5. p_new = p + v * dt
6. v_new = v + a1 * dt

Update body position to p_new and velocity to v_new.
