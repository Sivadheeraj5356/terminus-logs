CREATE INDEX IF NOT EXISTS transitions_zone_epoch ON transitions (zone, at_epoch);
CREATE INDEX IF NOT EXISTS ordinances_zone_seq ON ordinances (zone, enactment_seq);
