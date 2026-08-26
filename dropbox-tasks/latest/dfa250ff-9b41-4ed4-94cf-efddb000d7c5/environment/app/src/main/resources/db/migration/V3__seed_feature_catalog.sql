-- V3: seed the monitored feature catalog.

INSERT INTO feature_catalog (feature_id, family, monitored) VALUES ('fa_applicant_age_band', 'sensitive_attr', TRUE);
INSERT INTO feature_catalog (feature_id, family, monitored) VALUES ('fa_postal_deprivation_index', 'sensitive_attr', TRUE);
INSERT INTO feature_catalog (feature_id, family, monitored) VALUES ('fa_household_composition', 'sensitive_attr', TRUE);
INSERT INTO feature_catalog (feature_id, family, monitored) VALUES ('fa_regional_unemployment', 'macro_econ', TRUE);
INSERT INTO feature_catalog (feature_id, family, monitored) VALUES ('fa_cpi_yoy_delta', 'macro_econ', TRUE);
INSERT INTO feature_catalog (feature_id, family, monitored) VALUES ('fa_housing_price_index', 'macro_econ', TRUE);
INSERT INTO feature_catalog (feature_id, family, monitored) VALUES ('fa_prior_claim_count', 'claim_history', TRUE);
INSERT INTO feature_catalog (feature_id, family, monitored) VALUES ('fa_days_since_last_claim', 'claim_history', TRUE);
INSERT INTO feature_catalog (feature_id, family, monitored) VALUES ('fa_claim_severity_p90', 'claim_history', TRUE);
INSERT INTO feature_catalog (feature_id, family, monitored) VALUES ('fa_open_litigation_flag', 'claim_history', TRUE);
INSERT INTO feature_catalog (feature_id, family, monitored) VALUES ('fa_policy_tenure_months', 'policy_terms', TRUE);
INSERT INTO feature_catalog (feature_id, family, monitored) VALUES ('fa_deductible_band', 'policy_terms', TRUE);
INSERT INTO feature_catalog (feature_id, family, monitored) VALUES ('fa_coverage_limit_ratio', 'policy_terms', TRUE);
INSERT INTO feature_catalog (feature_id, family, monitored) VALUES ('fa_telematics_harsh_brake', 'telemetry', TRUE);
INSERT INTO feature_catalog (feature_id, family, monitored) VALUES ('fa_telematics_night_ratio', 'telemetry', TRUE);
INSERT INTO feature_catalog (feature_id, family, monitored) VALUES ('fa_endorsement_count', 'policy_terms', FALSE);
INSERT INTO feature_catalog (feature_id, family, monitored) VALUES ('fa_device_os_family', 'telemetry', FALSE);
INSERT INTO feature_catalog (feature_id, family, monitored) VALUES ('fa_quote_channel', 'policy_terms', FALSE);
