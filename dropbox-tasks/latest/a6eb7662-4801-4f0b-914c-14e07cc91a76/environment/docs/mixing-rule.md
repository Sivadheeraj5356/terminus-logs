# Mixing rule

Let mass fractions satisfy f_Au + f_Ag + f_Cu = 1 with each fraction in [0, 1].

## Ideal volume-additive mixing

When a coin's mixing_rule is "ideal":

ρ(f) = 1 / (f_Au / ρ_Au + f_Ag / ρ_Ag + f_Cu / ρ_Cu)

where ρ_Au, ρ_Ag, ρ_Cu are the pure-metal reference densities from /app/data/metal-densities.json. This is the harmonic (volume-additive) mixing rule. Do not substitute mass-weighted arithmetic means Σ f_i ρ_i.

## Non-ideal correction

When mixing_rule is "nonideal" and the coin supplies excess coefficient kappa:

ρ(f) = ρ_ideal(f) * (1 + kappa * f_Au * f_Cu)

with ρ_ideal as above. Implement the exact rule named on the coin; never silently fall back from nonideal to ideal or the reverse.
