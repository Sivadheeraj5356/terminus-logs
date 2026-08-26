-- Station registry contents as of the Station Systems Freeze (2025-11-30).
-- One row per reviewed artifact version, updated in place as statuses change.

INSERT INTO registry.artifact_review
    (entry_id, group_id, artifact_id, version, status, decided_on, minute_ref, status_note)
VALUES
    (1, 'org.postgresql', 'postgresql', '42.2.5', 'rescinded', '2019-03-14', 'DRB-2019-04',
     'approved at commissioning; approval rescinded under advisory MRA-2024-011'),
    (2, 'org.apache.commons', 'commons-math3', '3.5', 'superseded', '2019-03-14', 'DRB-2019-04',
     'approved at commissioning; superseded in good standing by the 3.6.1 approval'),
    (3, 'org.apache.commons', 'commons-math3', '3.6.1', 'approved', '2021-07-22', 'DRB-2021-08',
     'approval in force'),
    (4, 'com.fasterxml.jackson.core', 'jackson-databind', '2.13.4', 'rescinded', '2022-04-11', 'DRB-2022-05',
     'approval rescinded under advisory MRA-2023-06'),
    (5, 'org.postgresql', 'postgresql', '42.6.0', 'rescinded', '2023-05-09', 'DRB-2023-11',
     'approval rescinded under advisory MRA-2024-011'),
    (6, 'com.fasterxml.jackson.core', 'jackson-databind', '2.17.2', 'approved', '2024-04-18', 'DRB-2024-09',
     'approval in force'),
    (7, 'org.postgresql', 'postgresql', '42.7.4', 'approved', '2024-09-06', 'DRB-2024-17',
     'approval in force; minute purged, journal transcript of 2024-09 is authoritative'),
    (8, 'org.postgresql', 'postgresql', '42.7.3', 'noted_never_approved', '2025-05-20', NULL,
     'notation only: ran in service as a May 2025 emergency measure, later reverted; never approved');

INSERT INTO registry.advisory_register
    (advisory_id, subject, issued_on, status)
VALUES
    ('MRA-2021-01', 'chronolog appender key handling', '2021-02-03', 'closed'),
    ('MRA-2023-06', 'jackson-databind gadget-chain exposure', '2023-10-02', 'in_force'),
    ('MRA-2024-011', 'postgresql jdbc parameter interpolation exposure', '2024-08-19', 'in_force'),
    ('MRA-2024-019', 'temurin jit miscompilation report', '2024-11-05', 'withdrawn');
