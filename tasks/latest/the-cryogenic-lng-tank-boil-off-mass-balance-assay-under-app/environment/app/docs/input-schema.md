# Input schema

tanks.csv columns: tank_id, terminal_id, insulation_class, diameter_m, max_liquid_height_m.

tank_readings.csv columns: tank_id, timestamp, pressure_kpag, liquid_temp_c, vapor_temp_c, level_mm. Timestamps are RFC3339 UTC. level_mm is the liquid height in millimeters.

transfer_events.csv columns: tank_id, timestamp, event_type, mass_tonnes. event_type is one of delivery, withdrawal, regas, or relief.

inventory_snapshots.csv columns: tank_id, timestamp, gauged_mass_tonnes. Each tank must have at least an opening snapshot (earliest timestamp) and a closing snapshot (latest timestamp) for the mass-balance assay window.

maintenance_events.csv columns: tank_id, timestamp_start, timestamp_end, event_type.

config/boiloff-profiles.json is a JSON array of insulation profiles. Each profile includes insulation_class, heat_leak_w_m2, lng_density_kg_m3, latent_heat_kj_kg, allowable_imbalance_pct, and relief_pressure_drop_kpag.
