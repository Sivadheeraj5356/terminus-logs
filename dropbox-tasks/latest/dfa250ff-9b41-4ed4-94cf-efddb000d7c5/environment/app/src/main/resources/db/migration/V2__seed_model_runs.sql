-- V2: seed the model runs produced during the 2027Q1 audit window.

INSERT INTO model_run (run_id, model_name, model_version, trained_at, champion) VALUES ('run_2027q1_0101', 'acr_severity_gbm', '4.2.0', TIMESTAMP '2027-01-08 09:15:00', FALSE);
INSERT INTO model_run (run_id, model_name, model_version, trained_at, champion) VALUES ('run_2027q1_0102', 'acr_frequency_glm', '2.9.1', TIMESTAMP '2027-01-11 14:02:00', FALSE);
INSERT INTO model_run (run_id, model_name, model_version, trained_at, champion) VALUES ('run_2027q1_0103', 'acr_fraud_xgb', '7.0.3', TIMESTAMP '2027-01-14 08:44:00', FALSE);
INSERT INTO model_run (run_id, model_name, model_version, trained_at, champion) VALUES ('run_2027q1_0104', 'acr_reserving_lgbm', '1.4.7', TIMESTAMP '2027-01-19 17:30:00', FALSE);
INSERT INTO model_run (run_id, model_name, model_version, trained_at, champion) VALUES ('run_2027q1_0105', 'acr_subrogation_nn', '0.9.4', TIMESTAMP '2027-01-22 11:05:00', FALSE);
INSERT INTO model_run (run_id, model_name, model_version, trained_at, champion) VALUES ('run_2027q1_0106', 'acr_severity_gbm', '4.3.0', TIMESTAMP '2027-01-26 10:20:00', TRUE);
INSERT INTO model_run (run_id, model_name, model_version, trained_at, champion) VALUES ('run_2027q1_0107', 'acr_frequency_glm', '3.0.0', TIMESTAMP '2027-01-29 16:48:00', FALSE);
INSERT INTO model_run (run_id, model_name, model_version, trained_at, champion) VALUES ('run_2027q1_0108', 'acr_fraud_xgb', '7.1.0', TIMESTAMP '2027-02-02 09:00:00', FALSE);
INSERT INTO model_run (run_id, model_name, model_version, trained_at, champion) VALUES ('run_2027q1_0109', 'acr_reserving_lgbm', '1.5.0', TIMESTAMP '2027-02-05 13:37:00', FALSE);
INSERT INTO model_run (run_id, model_name, model_version, trained_at, champion) VALUES ('run_2027q1_0110', 'acr_severity_gbm', '4.3.1', TIMESTAMP '2027-02-09 08:12:00', FALSE);
INSERT INTO model_run (run_id, model_name, model_version, trained_at, champion) VALUES ('run_2027q1_0111', 'acr_subrogation_nn', '1.0.0', TIMESTAMP '2027-02-12 15:55:00', FALSE);
INSERT INTO model_run (run_id, model_name, model_version, trained_at, champion) VALUES ('run_2027q1_0112', 'acr_frequency_glm', '3.0.1', TIMESTAMP '2027-02-17 12:41:00', FALSE);
INSERT INTO model_run (run_id, model_name, model_version, trained_at, champion) VALUES ('run_2027q1_0113', 'acr_fraud_xgb', '7.1.1', TIMESTAMP '2027-02-20 10:09:00', FALSE);
INSERT INTO model_run (run_id, model_name, model_version, trained_at, champion) VALUES ('run_2027q1_0114', 'acr_reserving_lgbm', '1.5.2', TIMESTAMP '2027-02-24 14:26:00', FALSE);
INSERT INTO model_run (run_id, model_name, model_version, trained_at, champion) VALUES ('run_2027q1_0115', 'acr_severity_gbm', '4.4.0', TIMESTAMP '2027-02-26 09:31:00', FALSE);
INSERT INTO model_run (run_id, model_name, model_version, trained_at, champion) VALUES ('run_2027q1_0116', 'acr_reserving_lgbm', '1.6.0', TIMESTAMP '2027-02-27 11:47:00', FALSE);
