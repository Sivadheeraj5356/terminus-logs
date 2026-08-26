# Inventory balance

Opening mass is the gauged_mass_tonnes from the earliest inventory snapshot for the tank.

Closing gauged mass is from the latest inventory snapshot.

Transaction delta is the sum of delivery masses minus withdrawal masses minus regas masses, then r3-rounded. Relief vent masses are not part of transaction delta.

Total calculated boil-off is heat_leak_bog_tonnes plus relief_bog_tonnes. relief_bog_tonnes is the sum of transfer_events with event_type relief for that tank, then r3-rounded.

Expected closing tonnes equals r3 of opening mass plus transaction delta minus total calculated boil-off.

Imbalance percent is r3 of (closing gauged minus expected closing) divided by closing gauged, times 100, when closing gauged is non-zero. When closing gauged is zero, imbalance percent is zero without rounding.

See /app/docs/numeric-rounding.md for the r3 definition and epsilon bias.

A tank is balanced when no violation codes are present; otherwise it is imbalanced.
