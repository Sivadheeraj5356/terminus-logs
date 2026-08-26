# Binding contract

## Relations and fitted model

Transient states are `s0,...,s3`, absorbing states are `goal,fail`, and actions
are the integers `0,1,2`. Read every relation by header and join identifiers,
without relying on row order.

For each of the 12 transient state-action pairs, sum
`nominal_transition_counts.count` by destination and normalize by the pair's
total count. This gives `p(.|s,a)` over all six destination states. Duplicate
rows are additive. A missing destination has nominal mass zero and is still in
the ambiguity simplex. Counts must be finite and nonnegative. An absent pair
has total fitted count zero.

Each case selects one `ambiguity_profile_id`. Its profile must contain exactly
one row for every transient state-action pair. The fields have these meanings:

- `budget_cost`: positive integer transport-budget cost per ambiguity unit;
- `radius_multiplier`: finite, strictly positive multiplier;
- `max_ambiguity_units`: nonnegative integer cap for that pair.

The selected target policy must contain exactly one finite, strictly positive
probability for every state-action pair. Its three probabilities at each state
are normalized when their sum differs from 1 by at most `1e-12`.

## Transport primitive

For a probability vector `p`, value vector `x`, and radius `rho`, define

```
L(p,x,rho) = min_q sum_j q_j x_j
```

subject to `q_j >= 0`, `sum_j q_j = 1`, and
`sum_j |q_j-p_j| <= min(rho,2)`. The feasible simplex includes destinations
whose nominal probability is zero.

## Pre-action coupled-resource Bellman recursion

A case supplies remaining transport budget `b`, remaining intervention budget
`c`, and base radius `r`. Let `V_h(s,b,c)` be robust goal reachability with
`h` transitions left. The boundary and absorbing values are

```
V_0(goal,b,c)=1,  V_0(other,b,c)=0
V_h(goal,b,c)=1, V_h(fail,b,c)=0.
```

For profile row `(s,a)`, write its cost, multiplier, and cap as `d_a`, `m_a`,
and `u_a`. Before the policy action is drawn, the adversary chooses one integer
plan `k=(k_0,k_1,k_2)` for all three action branches. A plan is feasible when
every `0 <= k_a <= u_a`, its total cost `D=sum_a k_a*d_a` is at most `b`, and
its activation count `I=sum_a 1[k_a>0]` is at most `c`. The whole planned cost
and activation count are consumed before the action is drawn. Then

```
V_h(s,b,c) = min_k sum_a pi(a|s)
  L(p(.|s,a), V_{h-1}(.,b-D,c-I), k_a*r*m_a).
```

Unspent resources carry to the next transition. Enumerate plan coordinates in
action order `0,1,2`. Minima tied within `1e-12` select the lexicographically
smallest complete plan.

`robust_reachability` is
`V_H(start_state,budget_units,intervention_budget_units)`.
`nominal_reachability` uses the fitted kernel with no ambiguity optimization,
and `robust_gap` is nominal minus robust.

At the initial state and full resources, recover that one tied-smallest joint
plan. Report the policy-weighted mean `sum_a pi(a|s) k_a` as
`initial_expected_ambiguity_units`. Report its total planned cost `D` as
`initial_expected_budget_cost` and activation count `I` as
`initial_expected_intervention`; the latter two are not policy-weighted.

`transport_monotonicity_residual` is the largest positive
`V_h(s,b+1,c)-V_h(s,b,c)` over all computed transient states and valid indices.
`intervention_monotonicity_residual` is defined analogously from
`V_h(s,b,c+1)-V_h(s,b,c)`.

## Support and output

`low_count_pairs` is the number of the 12 fitted pairs whose total count is
strictly below `minimum_pair_count`; equality is supported. Missing pairs have
total zero and contribute whenever zero is below the threshold.

A case is unsupported when it has a low-count pair; an absent or nonpositive
fitted pair; malformed counts; an incomplete, duplicated, nonpositive, or
non-normalized selected policy; an incomplete, duplicated, or invalid selected
ambiguity profile; an unknown start state; a horizon below one; a negative or
noninteger resource budget; a negative or nonfinite base radius; a negative or
nonfinite minimum count; or a nonfinite computed diagnostic.

Write exactly these columns, in this order:

```
case_id,unsupported,low_count_pairs,robust_reachability,
nominal_reachability,robust_gap,initial_expected_ambiguity_units,
initial_expected_budget_cost,initial_expected_intervention,
transport_monotonicity_residual,intervention_monotonicity_residual
```

Sort rows by `case_id`. Serialize `unsupported` as integer `0` or `1`;
Boolean words are invalid. For an unsupported case, still report
`low_count_pairs` and leave all eight floating diagnostics empty. All supported
floating diagnostics must be finite.
