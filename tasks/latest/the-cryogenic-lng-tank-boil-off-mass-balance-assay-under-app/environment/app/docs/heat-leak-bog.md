# Heat leak boil-off

Ambient reference temperature is 25.0 degrees Celsius for all tanks.

Wetted surface area in square meters is pi times diameter squared divided by four plus pi times diameter times liquid height in meters. Liquid height equals level_mm divided by 1000.

Temperature difference for heat leak must use absolute kelvin values: ambient kelvin minus liquid kelvin, where each celsius reading is converted by adding 273.15.

Instantaneous heat influx in watts is heat_leak_w_m2 times wetted area times the kelvin temperature difference.

Boil-off mass rate in tonnes per hour is heat influx divided by latent_heat_kj_kg divided by 1000, times 3600, divided by 1000. Round that instantaneous rate with r3 as defined in /app/docs/numeric-rounding.md before using it in any time integration step.

Between consecutive eligible readings, integrate boil-off using trapezoidal time weighting: average of the two already r3-rounded endpoint rates multiplied by elapsed hours in hours. Sum all segments, then apply r3 once more to the segment sum to produce total heat_leak_bog_tonnes for the tank.

When a tank has exactly one eligible reading after maintenance filtering, do not use zero tonnes. Total heat_leak_bog_tonnes equals r3 of the single r3-rounded bog rate multiplied by 0.001 (a fixed 0.001-hour window for that lone sample).

Readings excluded by maintenance windows do not participate in integration.
