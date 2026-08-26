-- Force-clamp hopping study: landscape constants, molecules, rates.
CREATE TABLE config (
  c4            REAL NOT NULL,
  c1            REAL NOT NULL,
  xd            REAL NOT NULL,
  wd            REAL NOT NULL,
  kt            REAL NOT NULL,
  xlo           REAL NOT NULL,
  xhi           REAL NOT NULL,
  xau           REAL NOT NULL,
  xaf           REAL NOT NULL,
  init_c2       REAL NOT NULL,
  init_cs       REAL NOT NULL,
  init_log_d    REAL NOT NULL,
  init_sigma_a  REAL NOT NULL,
  init_sigma_b  REAL NOT NULL,
  init_sigma_e  REAL NOT NULL
);

CREATE TABLE molecules (
  id INTEGER PRIMARY KEY
);

CREATE TABLE observations (
  molecule_id  INTEGER NOT NULL REFERENCES molecules(id),
  force_pn     REAL NOT NULL,
  log_k_unfold REAL NOT NULL,
  log_k_fold   REAL NOT NULL
);
