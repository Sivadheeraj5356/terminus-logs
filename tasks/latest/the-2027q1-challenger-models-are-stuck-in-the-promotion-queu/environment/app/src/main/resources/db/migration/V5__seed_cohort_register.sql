-- V5: seed the cohort register.

INSERT INTO cohort_register (cohort_id, display_name, status, legacy_alias, effective_from, retired_on) VALUES ('ch_core_auto', 'Core Auto', 'ACTIVE', 'LGC_AUTO_CORE', DATE '2025-04-01', NULL);
INSERT INTO cohort_register (cohort_id, display_name, status, legacy_alias, effective_from, retired_on) VALUES ('ch_core_home', 'Core Home', 'ACTIVE', 'LGC_HOME_CORE', DATE '2025-04-01', NULL);
INSERT INTO cohort_register (cohort_id, display_name, status, legacy_alias, effective_from, retired_on) VALUES ('ch_high_value', 'High Value Household', 'ACTIVE', 'LGC_HNW', DATE '2026-01-01', NULL);
INSERT INTO cohort_register (cohort_id, display_name, status, legacy_alias, effective_from, retired_on) VALUES ('ch_smb_fleet', 'SMB Fleet', 'PROVISIONAL', 'LGC_FLEET_SMB', DATE '2026-10-01', NULL);
INSERT INTO cohort_register (cohort_id, display_name, status, legacy_alias, effective_from, retired_on) VALUES ('ch_pilot_ev', 'EV Pilot', 'PROVISIONAL', 'LGC_EV_PILOT', DATE '2027-01-05', NULL);
INSERT INTO cohort_register (cohort_id, display_name, status, legacy_alias, effective_from, retired_on) VALUES ('ch_legacy_motor', 'Legacy Motor', 'RETIRED', 'LGC_MOTOR_OLD', DATE '2024-01-01', DATE '2027-02-15');
INSERT INTO cohort_register (cohort_id, display_name, status, legacy_alias, effective_from, retired_on) VALUES ('ch_shadow_test', 'Shadow Test', 'SUSPENDED', 'LGC_SHADOW', DATE '2026-06-01', NULL);
