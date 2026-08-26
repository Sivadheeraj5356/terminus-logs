Numerically integrate the stiff mass-action reaction networks that the Halvard kinetics bench certifies.

Each network file names its species, its elementary reactions and rate constants, its initial concentrations, its horizon and its error tolerances. The bench at /app/bench/bench still integrates the twelve calibration systems compiled into it; /app/calibration holds those same twelve as files. Uncertified assay networks sit in /app/assay.

Write your integrator to /app/bin/integrate. It reads a network directory and an output path and writes one JSON object per network per line, ordered by file name. Each carries network, verdict, stop_time, accepted, rejected, derivative_evals, and final, a map from species name to the concentration reached. verdict reads converged when the horizon is reached or step_budget when the protocol gives up first; accepted, rejected and derivative_evals are integer counts.

Reproduce what the bench certifies on the calibration systems, then carry the same protocol to stiff networks you have not seen.
