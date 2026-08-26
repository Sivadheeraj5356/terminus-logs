# Reduced-order sheet analysis contract

The test rig represents a perforated sheet by one generalized fold coordinate `theta` and a scalar control load `load`. Campaign files are UTF-8 JSON. The submitted sources are `/app/workbench/main.cpp`, `/app/workbench/model.cpp`, and `/app/workbench/solver.cpp`, with headers in `/app/workbench`. They are compiled by the lab runner. The resulting executable interface is:

    kirigami-map --input /absolute/campaign.json --output /absolute/report.json

Both paths must be absolute. Missing flags, repeated flags, unknown flags, and any other malformed CLI invocation exit 2. The output path must not resolve to `/app/docs`, `/app/cases`, or anything below either directory, including through symlinks or `..`; such a path also exits 2. A valid campaign exits 0 and publishes the report by replacing the output atomically. Invalid JSON, a schema violation, a non-finite number, or a physically inadmissible sweep exits 2. On exit 2 an existing output must remain byte-for-byte unchanged. Other operating-system failures may use any nonzero status other than 2.

## Mechanical model

For one campaign, the model parameters are constant over every query and sweep. The stored energy is

    E(theta, load) = a1 theta^2 / 2
                   + a3 theta^4 / 4
                   + a5 theta^6 / 6
                   - load (b1 theta + b3 theta^3 / 3)
                   + sum_j S_j(theta).

Each unilateral crease stop has an `angle`, positive `stiffness`, and a `sense` of `upper` or `lower`:

    upper: S_j(theta) = stiffness (theta - angle)^2 / 2 when theta > angle, else 0
    lower: S_j(theta) = stiffness (theta - angle)^2 / 2 when theta < angle, else 0

The equilibrium residual is the derivative of E with respect to theta:

    R(theta, load) = a1 theta + a3 theta^3 + a5 theta^5
                   - load (b1 + b3 theta^2)
                   + sum of stiffness (theta - angle) over active stops.

Only roots inside the closed interval `[theta_min, theta_max]` are reported. A stop is active only under the strict inequality above; therefore a state exactly at its stop angle does not list that stop as active.

Away from a stop angle the tangent stiffness is

    K = a1 + 3 a3 theta^2 + 5 a5 theta^4
        - 2 load b3 theta
        + sum of stiffness over active stops.

At a stop angle, `tangent_left` and `tangent_right` are the one-sided values. Elsewhere they are equal. Stability is `stable` when both one-sided tangents are greater than 1e-7, `unstable` when both are less than -1e-7, and `neutral` otherwise.

A smooth limit point is an interior equilibrium where the load-equilibrium curve has a differentiable strict local extremum. Stop angles and the two domain bounds are never reported as limit points. A strict local maximum has type `maximum`; a strict local minimum has type `minimum`. Degenerate stationary points that are not strict extrema are not limit points.

## Quasi-static sweeps

Each sweep contains a strictly monotone load list and an `initial_theta`. The initial value must be within 1e-5 of a stable equilibrium at the first load; the reported initial state uses the computed equilibrium, not the supplied approximation.

For each later load, first follow the same stable branch. A branch is the connected part of the equilibrium curve between adjacent smooth limit points or between a domain bound and its nearest smooth limit point. Crossing a stop angle does not by itself end a branch. When the branch still contains a stable equilibrium at the new load, report that state with transition `follow`.

If the prior branch has no stable equilibrium at the new load, the sheet snaps. At the new load evaluate R at the previous reported theta. If R is positive, choose the nearest stable equilibrium at a smaller theta; if R is negative, choose the nearest stable equilibrium at a larger theta. When R is zero to within 1e-9, use the sweep direction: increasing load chooses the larger-theta side and decreasing load the smaller-theta side. If the indicated side has no stable equilibrium, choose the nearest stable equilibrium overall. Report a snap with transition `snap`. A campaign is physically inadmissible if a sweep has no required stable state.

## Campaign JSON

The top-level object is:

    {
      "schema": "kirigami-campaign-v1",
      "campaign": string,
      "model": model object,
      "equilibrium_loads": [number, ...],
      "sweeps": [sweep object, ...]
    }

`campaign` is non-empty. `equilibrium_loads` has 1 through 64 entries. `sweeps` has 0 through 8 entries, and sweep IDs are unique. Every number must be finite.

The model object contains exactly these required fields:

    a1, a3, a5, b1, b3, theta_min, theta_max, stops

The coefficient limits are `abs(a1) <= 50`, `abs(a3) <= 50`, `1e-4 <= a5 <= 50`, `1e-4 <= b1 <= 50`, and `0 <= b3 <= 20`. The domain width must be between 0.25 and 8 inclusive. There may be 0 through 8 stops. Stop angles must lie strictly inside the domain, stiffness must be in `[1e-4, 100]`, sense must be `upper` or `lower`, and two stops may not share both angle and sense.

A sweep object is:

    {"id": string, "loads": [number, ...], "initial_theta": number}

The ID is non-empty. The load list has 2 through 256 entries and is strictly increasing or strictly decreasing.

## Report JSON

The report top-level object is:

    {
      "schema": "kirigami-snapthrough-v1",
      "campaign": string,
      "equilibria": [equilibrium query, ...],
      "limit_points": [limit point, ...],
      "sweeps": [sweep report, ...]
    }

Equilibrium queries remain in input order. Each is:

    {"load": number, "states": [state, ...]}

States are sorted by increasing theta and contain:

    {
      "theta": number,
      "energy": number,
      "tangent_left": number,
      "tangent_right": number,
      "stability": "stable" | "unstable" | "neutral",
      "active_stops": [integer, ...]
    }

`active_stops` contains zero-based stop indices in increasing order. Limit points are sorted by increasing theta and contain:

    {
      "theta": number,
      "load": number,
      "type": "maximum" | "minimum",
      "active_stops": [integer, ...]
    }

Sweep reports remain in input order:

    {"id": string, "states": [sweep state, ...]}

Sweep states remain in load order and contain:

    {
      "load": number,
      "theta": number,
      "energy": number,
      "transition": "initial" | "follow" | "snap"
    }

A report must contain no NaN or infinity tokens. Additional object fields are allowed, but they do not replace any required field or change ordering requirements.
