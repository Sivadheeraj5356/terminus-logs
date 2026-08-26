# Compact model equations

Thermal voltage VT is 0.026 volts at the reference temperature. Threshold voltage at the measurement temperature is vth0 plus kt1 times the temperature delta temp_c minus reference_temp_c. Mobility at the measurement temperature is u0 times an absolute-temperature ratio raised to ute, where the ratio is temp_c plus 273.15 over reference_temp_c plus 273.15. Effective width Weff is W_nm times nfin in meters and effective length Leff is L_nm in meters. The oxide capacitance term Cox is two times cgso divided by Weff.

Drain current uses a contact-drop self-consistency loop. Start id at zero and repeat the update six times. On each pass compute vds_eff as vds minus id times the per-geometry contact resistance from contact_resistance.json, clamped to be at least zero. Below threshold, when vgs is less than the temperature-scaled vth, id is subth_weight times Weff over Leff times the exponential of vgs minus vth divided by ss_factor times VT, multiplied by the factor one minus the exponential of negative vds_eff over VT. At or above threshold id is the temperature-scaled u0 times Cox times Weff over Leff times the quantity vgt times vds_eff minus one half times vds_eff squared, where vgt is vgs minus the temperature-scaled vth, multiplied by the body factor one plus k1 times the square root of vgt clamped to at least zero. After each pass clamp id to be at least zero. Parameter rsd is series spreading metadata and is not substituted for contact resistance during Id evaluation.

Gate capacitance Cgg is Cox times Weff times Leff. When vgs is below the temperature-scaled vth, multiply Cgg by the factor 0.55 plus 0.45 times the exponential of vgs minus vth divided by ss_factor times VT.

Apply round12 from /app/scripts/digest_contract.py to the final predicted Id and Cgg model outputs only. Measurement fields stored in the calibration tapeout keep raw CSV parse values for digest and fitting.


