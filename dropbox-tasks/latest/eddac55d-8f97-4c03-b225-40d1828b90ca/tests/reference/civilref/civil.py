"""Proleptic Gregorian civil-date arithmetic on seconds since 1970-01-01T00:00:00Z."""

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
_MDAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def is_leap(y):
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)


def days_in_month(y, m):
    if m == 2 and is_leap(y):
        return 29
    return _MDAYS[m - 1]


def days_from_civil(y, m, d):
    """Days since 1970-01-01. Valid for the whole proleptic Gregorian range."""
    yy = y - (1 if m <= 2 else 0)
    era = (yy if yy >= 0 else yy - 399) // 400
    yoe = yy - era * 400
    mp = m + (-3 if m > 2 else 9)
    doy = (153 * mp + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def civil_from_days(z):
    z += 719468
    era = (z if z >= 0 else z - 146096) // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    yy = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + (3 if mp < 10 else -9)
    return (yy + (1 if m <= 2 else 0), m, d)


def weekday_from_days(z):
    """0 = Sunday. Correct for negative z (Python floor-mod; Rust needs rem_euclid)."""
    return (z + 4) % 7


def resolve_day(y, m, spec):
    """spec is (kind, weekday, day). Returns the day-of-month it denotes."""
    kind, wd, n = spec
    if kind == "fixed":
        return n
    if kind == "last":
        last = days_in_month(y, m)
        z = days_from_civil(y, m, last)
        return last - ((weekday_from_days(z) - wd) % 7)
    if kind == "ge":
        z = days_from_civil(y, m, n)
        return n + ((wd - weekday_from_days(z)) % 7)
    if kind == "le":
        z = days_from_civil(y, m, n)
        return n - ((weekday_from_days(z) - wd) % 7)
    raise ValueError("bad day spec kind: %r" % (kind,))


def civil_seconds(y, m, spec, tod):
    """Naive local seconds for a recurrence in year y. tod may exceed 86400."""
    d = resolve_day(y, m, spec)
    return days_from_civil(y, m, d) * 86400 + tod


def fmt_offset_hms(total):
    sign = "-" if total < 0 else "+"
    a = abs(total)
    return "%s%02d:%02d:%02d" % (sign, a // 3600, (a % 3600) // 60, a % 60)
