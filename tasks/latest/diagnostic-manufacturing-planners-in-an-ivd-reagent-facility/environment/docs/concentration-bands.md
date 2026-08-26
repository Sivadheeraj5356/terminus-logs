# Concentration bands

Every specification declares upper and lower concentration bands per analyte under bands in specs.json.

## Feasibility rule

A blend allocation is feasible only when every analyte concentration lies within both bounds inclusive:

  lower <= achieved_concentration <= upper

## Concentration math

For target volume V milliliters and lot amounts a_i milliliters with assay concentrations c_i,a:

  achieved_a = sum(a_i * c_i,a) / V

Analytes are evaluated in sorted analyte name order during solve enumeration.

## Band perturbation for dual prices

Certify perturbs individual analyte lower or upper bounds by a small epsilon when the achieved concentration sits on the corresponding bound. See dual-price-certificate.md.
