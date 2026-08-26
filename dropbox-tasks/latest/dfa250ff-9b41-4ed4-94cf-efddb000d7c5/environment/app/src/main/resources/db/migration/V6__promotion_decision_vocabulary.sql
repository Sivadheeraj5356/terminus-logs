-- V6: promotion decision vocabulary shared by the review board and the runner.
CREATE TABLE promotion_decision (
    decision    VARCHAR(16) NOT NULL PRIMARY KEY,
    rank_order  INT         NOT NULL,
    description VARCHAR(160) NOT NULL
);

INSERT INTO promotion_decision (decision, rank_order, description) VALUES
    ('PROMOTE', 1, 'Run is clear for promotion to the challenger slot.'),
    ('HOLD', 2, 'Run requires manual review before promotion.'),
    ('REJECT', 3, 'Run is blocked from promotion for this cycle.');
