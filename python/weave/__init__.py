"""Fast, non-mutating deep merges for Python dictionaries."""

from enum import IntFlag

from ._weave import merge as merge


class MergeFlag(IntFlag):
    """Bitmask flags controlling :func:`merge` behavior."""

    NONE = 0o0
    CONCAT_LISTS = 0o1
    TYPESAFE = 0o2


NONE = MergeFlag.NONE
CONCAT_LISTS = MergeFlag.CONCAT_LISTS
TYPESAFE = MergeFlag.TYPESAFE

__all__ = ["CONCAT_LISTS", "MergeFlag", "NONE", "TYPESAFE", "merge"]
