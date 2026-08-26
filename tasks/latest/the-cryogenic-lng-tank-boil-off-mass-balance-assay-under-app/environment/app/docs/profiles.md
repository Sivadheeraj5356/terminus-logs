# Insulation profiles

Each tank references an insulation_class that maps to a row in config/boiloff-profiles.json.

heat_leak_w_m2 is the effective heat transfer coefficient in watts per square meter per kelvin of temperature difference across the insulation.

lng_density_kg_m3 and latent_heat_kj_kg are physical constants used when converting heat influx to boil-off mass.

allowable_imbalance_pct is the maximum absolute percent difference between gauged closing inventory and expected closing inventory before IMBALANCE_HIGH is raised.

relief_pressure_drop_kpag documents the nominal relief valve differential; it is informational for operators and does not change mass math directly.
