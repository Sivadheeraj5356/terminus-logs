"""Curated and generated cases for Matchbook behavioral coverage."""

from matchbook_model import Case, generated_case


ONE_TRICK = Case(
    "one_trick",
    "S",
    False,
    0,
    0,
    1,
    (),
    (("H7",), ("H8",), ("HA",), ("H9",)),
)

FORCED_FOLLOW = Case(
    "forced_follow",
    "S",
    True,
    3,
    1,
    2,
    ("HK", "H7"),
    (("HA",), ("S7", "C7"), ("H8", "D7"), ("HQ",)),
)

OVERTRUMP = Case(
    "overtrump",
    "D",
    False,
    1,
    0,
    2,
    ("H9", "DA", "H7"),
    (("DK", "C7"), ("H8",), ("S7",), ("HJ",)),
)

OVERTRUMP_CHOICE = Case(
    "overtrump_choice",
    "D",
    False,
    1,
    0,
    2,
    ("H9", "D7", "H7"),
    (("DA", "C7"), ("H8",), ("S7",), ("HJ",)),
)

ONLY_TRUMP_LEAD = Case(
    "only_trump",
    "C",
    False,
    2,
    0,
    2,
    (),
    (("S7", "H7"), ("D7", "S8"), ("C7", "C8"), ("S9", "D8")),
)

TIE_BREAK = Case(
    "tie_break",
    "C",
    True,
    0,
    0,
    2,
    (),
    (("S7", "H7"), ("S8", "H8"), ("S9", "H9"), ("ST", "HT")),
)

DISCARD_LOSES = Case(
    "discard_loses",
    "S",
    True,
    0,
    0,
    1,
    ("H7", "H8"),
    ((), (), ("CA",), ("H9",)),
)

FOLLOW_REQUIRED = Case(
    "follow_required",
    "S",
    True,
    0,
    0,
    2,
    ("H7",),
    (("S7",), ("H8", "C7"), ("H9", "D7"), ("HT", "C8")),
)

BROKEN_TRUMP_OPTIONS = Case(
    "broken_trump_options",
    "C",
    True,
    2,
    0,
    2,
    (),
    (("S7", "H7"), ("D7", "S8"), ("C7", "H8"), ("S9", "D8")),
)

FOUR_SUIT_TIE_ORDER = Case(
    "four_suit_tie_order",
    "C",
    True,
    0,
    0,
    4,
    (),
    (
        ("S7", "H7", "D7", "C7"),
        ("S8", "H8", "D8", "C8"),
        ("S9", "H9", "D9", "C9"),
        ("ST", "HT", "DT", "CT"),
    ),
)

DEEP_FIVE = Case(
    "deep_five",
    "D",
    True,
    1,
    1,
    5,
    (),
    (
        ("S7", "S9", "HJ", "DK", "C8"),
        ("S8", "HT", "HQ", "D7", "CA"),
        ("SK", "H7", "D9", "DJ", "CQ"),
        ("SA", "HA", "D8", "DT", "C7"),
    ),
)

GENERATED = tuple(
    generated_case(seed, tricks, partial, maximize)
    for seed, tricks, partial, maximize in [
        (101, 2, 0, 0),
        (102, 2, 1, 1),
        (103, 2, 2, 0),
        (104, 2, 3, 1),
        (211, 3, 0, 1),
        (212, 3, 1, 0),
        (213, 3, 2, 1),
        (214, 3, 3, 0),
        (311, 4, 0, 0),
        (312, 4, 2, 1),
    ]
)

DEEP_GENERATED = tuple(
    generated_case(seed, 5, partial, maximize, ident=f"deep_{seed}")
    for seed, partial, maximize in [
        (800, 0, 0),
        (801, 1, 1),
        (802, 2, 0),
        (803, 3, 1),
        (804, 0, 1),
        (805, 1, 0),
    ]
)

BREAKS_DURING_TABLE = generated_case(
    1002,
    3,
    3,
    0,
    broken=False,
    ident="breaks_during_table",
)
