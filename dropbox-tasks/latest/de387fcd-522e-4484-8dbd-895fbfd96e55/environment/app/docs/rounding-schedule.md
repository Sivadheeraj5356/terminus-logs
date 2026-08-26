# Rounding Schedule

All money fields serialize with two decimal places (half-up unless noted).

| Component | Default | Exception |
|-----------|---------|-----------|
| indemnityShare | HALF_UP | — |
| processingFeeAmount | HALF_UP | — |
| tierAdjustmentAmount | HALF_UP | HALF_DOWN when plus tier on quota line; HALF_DOWN when premium tier on premium loss line |
| quotaCreditAmount | HALF_UP | HALF_DOWN when premium treaty tier |
| premiumHoldbackAmount | HALF_UP | HALF_DOWN on quota lines |
| netRecovery | HALF_UP | — |

Premium claim line detection uses deductible exposure only (see config-keys.md).
