body codes recognised by airbridge

three body codes are valid on a billing line.

NB is narrow body. typical examples are the airbus a320 family and the boeing 737 family. mtow tons usually sits between sixty and ninety.

WB is wide body. examples include the boeing 777, 787, and the airbus a330 and a350. mtow tons usually sits between one hundred fifty and three hundred.

RJ is regional jet. examples include the embraer e175 and bombardier crj. mtow tons usually sits between thirty and fifty.

any other string in the body_code field is not a recognised airframe class and the cycle cannot be priced under the current fee book. record but do not bill.

mtow tons is recorded as a whole number of metric tons. fractional tons are not part of the schema and should be rejected as numeric anomalies rather than rounded silently.

the airframe_rates table is versioned by effective_from date. always pick the row that was active when the gate was assigned, not when the airframe actually in blocked. the two timestamps can land on opposite sides of a rate change boundary on the first of any month.
