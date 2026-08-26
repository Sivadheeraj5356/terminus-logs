# Escrow Holdback Addendum

Taxable base for premium holdback:

`indemnityShare - tierAdjustmentAmount - quotaCreditAmount + processingFeeAmount`

Premium holdback rate applies when `coinsuranceBase >= coinsurance.threshold.large.loss`
(amount-based, not tier-gated). `coinsuranceBase` is computed per pricing-policy.md.

Basic tier policies exactly at `minimum.policy.amount` receive zero premium holdback.

Round HALF_DOWN on quota lines; HALF_UP otherwise.
