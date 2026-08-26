# Action catalog

IMBALANCE_HIGH maps to action investigate_gauging with reason inventory imbalance above profile tolerance. The value field is imbalance_pct formatted to three decimals.

BOG_RATE_HIGH maps to action inspect_insulation with reason heat-leak boil-off above review threshold. The value field is heat_leak_bog_tonnes formatted to three decimals. BOG_RATE_HIGH is raised when heat_leak_bog_tonnes exceeds 120.0.

RELIEF_EXCESSIVE maps to action review_relief_valve with reason relief vent mass above terminal limit. The value field is relief_bog_tonnes formatted to three decimals. RELIEF_EXCESSIVE is raised when relief_bog_tonnes exceeds 15.0.

Corrective actions are sorted by tank_id then action name.
