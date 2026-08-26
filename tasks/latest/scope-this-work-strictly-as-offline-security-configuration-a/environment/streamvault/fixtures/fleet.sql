PRAGMA foreign_keys = ON;

CREATE TABLE sites (
  site_id TEXT PRIMARY KEY,
  admin_user TEXT NOT NULL,
  approved_bind TEXT NOT NULL,
  profile TEXT NOT NULL
);

CREATE TABLE cameras (
  camera_id TEXT PRIMARY KEY,
  site_id TEXT NOT NULL REFERENCES sites(site_id),
  enabled INTEGER NOT NULL CHECK (enabled IN (0, 1)),
  approved_port INTEGER NOT NULL,
  media_fixture TEXT NOT NULL
);

CREATE TABLE retention_policies (
  profile TEXT PRIMARY KEY,
  min_days INTEGER NOT NULL,
  max_days INTEGER NOT NULL
);

CREATE TABLE service_networks (
  profile TEXT NOT NULL,
  service_name TEXT NOT NULL,
  allowed_cidr TEXT NOT NULL,
  PRIMARY KEY (profile, service_name, allowed_cidr)
);

CREATE TABLE exceptions (
  site_id TEXT NOT NULL REFERENCES sites(site_id),
  control_id TEXT NOT NULL,
  approved_value TEXT NOT NULL,
  rationale_id TEXT NOT NULL,
  expires_on TEXT NOT NULL,
  PRIMARY KEY (site_id, control_id, rationale_id)
);

CREATE TABLE exception_supersessions (
  site_id TEXT NOT NULL REFERENCES sites(site_id),
  control_id TEXT NOT NULL,
  predecessor_rationale_id TEXT NOT NULL,
  successor_rationale_id TEXT NOT NULL,
  PRIMARY KEY (site_id, control_id, predecessor_rationale_id, successor_rationale_id)
);

INSERT INTO sites VALUES ('plant-7', 'sv-plant7-admin', '127.0.0.1', 'factory-edge');
INSERT INTO retention_policies VALUES ('factory-edge', 30, 90);
INSERT INTO service_networks VALUES ('factory-edge', 'camera-ingest', '10.70.0.0/24');
INSERT INTO cameras VALUES ('dock', 'plant-7', 1, 11554, 'dock.h264');
INSERT INTO cameras VALUES ('press', 'plant-7', 1, 12554, 'press.h264');
INSERT INTO cameras VALUES ('retired', 'plant-7', 0, 13554, 'retired.h264');
INSERT INTO exceptions VALUES (
  'plant-7',
  'SV-SERVICE-07',
  '{"camera-ingest":"10.70.0.15","unknown-sidecar":"10.70.0.16"}',
  'EXC-PLANT7-INGEST',
  '2026-03-31'
);
INSERT INTO exceptions VALUES (
  'plant-7',
  'SV-RETENTION-08',
  '45',
  'EXC-PLANT7-RETENTION',
  '2026-03-31'
);
