# Drag and solar flare events

## Density scale

The atmospheric density is modulated by a density_scale factor that starts at 1.0.

Flare events are sorted by t_sec. When the simulation time crosses or equals a flare event t_sec, the density_scale becomes that event absolute density_scale value.

This is an absolute replacement, not multiplicative stacking. The density_scale at any time t is the density_scale from the most recent flare event whose t_sec is less than or equal to t. If no flare has occurred yet, density_scale remains 1.0.

Example:
- At t=0: density_scale = 1.0
- Flare at t=5 with density_scale=3.0: density_scale becomes 3.0
- Flare at t=10 with density_scale=0.5: density_scale becomes 0.5

## Drag formula

rho = RHO0 * exp(-(r - R_EARTH) / SCALE_H) * density_scale
a_drag = -0.5 * rho * cd * (PI * radius_m^2) * |vel| * vel / mass_kg

See kepler-integrator.md for the full acceleration model.
