CREATE TABLE IF NOT EXISTS legal_actions (
  round_id INTEGER NOT NULL,
  seq INTEGER NOT NULL,
  action_token TEXT NOT NULL,
  PRIMARY KEY (round_id, seq)
);

CREATE TABLE IF NOT EXISTS combo_rules (
  chain_id INTEGER PRIMARY KEY,
  prefix TEXT NOT NULL,
  bonus_pts INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS blocked_actions (
  action_token TEXT PRIMARY KEY,
  reason TEXT NOT NULL
);

INSERT INTO legal_actions (round_id, seq, action_token) VALUES
  (101, 1, 'strike'), (101, 2, 'blink'),
  (102, 1, 'left'), (102, 2, 'right'),
  (103, 1, 'up'), (103, 2, 'right'),
  (104, 1, 'blink'), (104, 2, 'strike'),
  (106, 1, 'up'), (106, 2, 'right');

INSERT INTO combo_rules (chain_id, prefix, bonus_pts) VALUES
  (1, 'strike,blink', 3),
  (2, 'blink,strike', 2);

INSERT INTO blocked_actions (action_token, reason) VALUES
  ('down', 'retired_axis');
