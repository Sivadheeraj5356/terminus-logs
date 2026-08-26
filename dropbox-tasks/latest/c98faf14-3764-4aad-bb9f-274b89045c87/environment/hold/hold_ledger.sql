CREATE TABLE IF NOT EXISTS digests (
  kind TEXT NOT NULL,
  val TEXT NOT NULL
);

CREATE VIEW IF NOT EXISTS v_hold_ordered AS
  SELECT kind || ':' || val AS row
  FROM digests
  ORDER BY kind ASC, val ASC;
