-- Schema for the SQLite-backed cross-border payroll tool.
-- All monetary amounts are stored as INTEGER micro-units of a major currency
-- (1000000 micro-units == one major unit) and all rates as INTEGER basis
-- points. Never use floats.

-- employees: one row per employee. rate is the pay rate in integer micro-units
-- of the major currency per hour and must be positive.
CREATE TABLE IF NOT EXISTS employees (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    rate INTEGER NOT NULL
);

-- hours: one row per recorded block of hours worked by an employee. hours is a
-- positive integer; ts is the authoritative epoch-second timestamp.
CREATE TABLE IF NOT EXISTS hours (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    hours       INTEGER NOT NULL,
    ts          INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_hours_emp ON hours(employee_id);

-- assignments: one row per employee placed to work in a country. country is an
-- ISO 3166-1 alpha-2 code stored uppercased. An employee may be assigned to
-- several countries, but each (employee, country) pairing is recorded at most
-- once.
CREATE TABLE IF NOT EXISTS assignments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    country     TEXT NOT NULL,
    UNIQUE(employee_id, country)
);

CREATE INDEX IF NOT EXISTS idx_assign_country ON assignments(country);
