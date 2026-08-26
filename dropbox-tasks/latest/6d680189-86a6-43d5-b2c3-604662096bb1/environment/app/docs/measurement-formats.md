# Measurement CSV formats

IV sweeps use iv_sweep.csv with header geometry_id,vgs,vds,id_amps,temp_c. Current id_amps is in amperes at the measurement temperature temp_c. Parse id_amps with a direct float conversion from the CSV field. Characterization keeps ampere-scale values as stored; do not scale milliamperes or apply round12 during characterize. Rows may appear in any file order; gaa_tapeout sorts by geometry_id then vgs then vds.

CV sweeps use cv_sweep.csv with header geometry_id,vgs,cgg_f,temp_c. Capacitance cgg_f is total gate capacitance in farads. Parse cgg_f with a direct float conversion without round12 during characterize. Tapeout sorts CV rows by geometry_id then vgs.

Tapeout stores vgs, vds, id_amps, temp_c, and cgg_f exactly as parsed from CSV. measure_digest hashes those stored values with big-endian IEEE754 bits. round12 from /app/scripts/digest_contract.py applies only to compact-model predicted Id and Cgg outputs, not to measurement fields written into the calibration snapshot.

When TB3_GAA_DATA_ROOT is set to an absolute directory, characterize reads all four bundled inputs from that overlay instead of the default data directory.
