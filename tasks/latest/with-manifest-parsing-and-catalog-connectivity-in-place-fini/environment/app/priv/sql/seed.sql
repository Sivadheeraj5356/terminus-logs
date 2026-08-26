USE helix_catalog;

INSERT INTO dependency_approvals (package_name, approved_version, approval_status) VALUES
  ('phoenix', '1.7.14', 'approved'),
  ('ecto_sql', '3.11.3', 'approved'),
  ('myxql', '0.7.0', 'approved')
ON DUPLICATE KEY UPDATE
  approved_version = VALUES(approved_version),
  approval_status = VALUES(approval_status);

INSERT INTO platform_constraints (package_name, os, arch, min_version, max_version) VALUES
  ('phoenix', 'linux', 'amd64', '1.7.0', '1.7.99'),
  ('ecto_sql', 'linux', 'amd64', '3.11.0', '3.11.99'),
  ('myxql', 'linux', 'amd64', '0.7.0', '0.7.99')
ON DUPLICATE KEY UPDATE
  min_version = VALUES(min_version),
  max_version = VALUES(max_version);
