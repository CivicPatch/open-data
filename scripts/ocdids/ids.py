from typing import Sequence, Tuple

DIVISION_PREFIX = "ocd-division/"
JURISDICTION_PREFIX = "ocd-jurisdiction/"
GOVERNMENT_SUFFIX = "/government"

Rewrite = Tuple[str, str]


def to_jurisdiction_ocdid(division_ocdid: str) -> str:
    return JURISDICTION_PREFIX + division_ocdid.removeprefix(DIVISION_PREFIX) + GOVERNMENT_SUFFIX


def to_division_ocdid(jurisdiction_ocdid: str) -> str:
    return DIVISION_PREFIX + jurisdiction_ocdid.removeprefix(JURISDICTION_PREFIX).removesuffix(GOVERNMENT_SUFFIX)


def state_division(state: str) -> str:
    return f"{DIVISION_PREFIX}country:us/state:{state}"


def rewrites_for(old_jurisdiction_ocdid: str, new_jurisdiction_ocdid: str) -> Tuple[Rewrite, Rewrite]:
    """Prefix rewrites covering an ID's jurisdiction form, its division form, and their children."""
    return (
        (old_jurisdiction_ocdid.removesuffix(GOVERNMENT_SUFFIX), new_jurisdiction_ocdid.removesuffix(GOVERNMENT_SUFFIX)),
        (to_division_ocdid(old_jurisdiction_ocdid), to_division_ocdid(new_jurisdiction_ocdid)),
    )


def rewrite_ocdid(value: str, rewrites: Sequence[Rewrite]) -> str:
    """Apply the first matching prefix rewrite; pass rewrites longest-prefix first."""
    for old, new in rewrites:
        if value == old or value.startswith(old + "/"):
            return new + value[len(old):]
    return value
