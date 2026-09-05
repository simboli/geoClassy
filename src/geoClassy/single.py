"""The deprecated 0.1.x API, kept working on top of the new one.

Every function here is scheduled for removal in 1.0. The replacements::

    requisites()        -> just import geoClassy
    loadFile(path)      -> areas = geoClassy.load(path)
    numPoly()           -> len(areas)
    checkPoly()         -> validation now happens in load(), which raises
    polyList()          -> areas.names
    getNames(lat, lon)  -> areas.locate(lat, lon)

Semantics are frozen at what 0.1.x did, so upgrading without touching your code
changes no results. In particular these functions keep the old
``on_overlap="last"`` behaviour, in which the answer depends on the order of the
features in the file; the new API defaults to ``"smallest"`` instead. They also
keep the old ``only_boundaries=True`` filter and the ``'unknown'`` sentinel,
where the new API returns ``None``.

The one deliberate exception: where 0.1.x silently loaded zero areas and then
answered ``'unknown'`` for every point, :func:`loadFile` now raises instead.
That is a wrong answer turned into a visible error, not a result worth
preserving.
"""

from __future__ import annotations

import warnings
from typing import Any

from ._core import Areas, NoAreasFoundError, load

__all__ = ["requisites", "loadFile", "numPoly", "checkPoly", "polyList", "getNames"]

_areas: Areas | None = None


def _deprecated(old: str, new: str) -> None:
    warnings.warn(
        f"geoClassy.single.{old} is deprecated and will be removed in geoClassy 1.0; "
        f"use {new} instead.",
        DeprecationWarning,
        stacklevel=3,
    )


def _loaded() -> Areas:
    if _areas is None:
        raise RuntimeError(
            "no GeoJSON loaded yet: call geoClassy.single.loadFile(path) first "
            "(or switch to areas = geoClassy.load(path))."
        )
    return _areas


def requisites() -> None:
    """Report that the dependencies are importable. Always true if you got here."""
    _deprecated("requisites()", "a plain `import geoClassy`")
    print("Json module correctly imported")
    print("Shapely Geometry module correctly imported")


def loadFile(fname: str) -> None:
    """Load a GeoJSON file into module-level state."""
    _deprecated("loadFile()", "geoClassy.load()")
    global _areas
    try:
        _areas = load(fname, only_boundaries=True, on_overlap="last")
    except NoAreasFoundError as exc:
        # This function hard-codes the 0.1.x only_boundaries filter, so the
        # advice from load() would point at an option the caller cannot reach.
        raise NoAreasFoundError(
            f"{exc} Reaching that option means moving off this deprecated "
            "function: use geoClassy.load(path) instead. In 0.1.x this case "
            "loaded nothing and answered 'unknown' for every point."
        ) from None


def numPoly() -> None:
    """Print how many areas are loaded."""
    _deprecated("numPoly()", "len(areas)")
    print(len(_loaded()), " polygons loaded")


def checkPoly() -> None:
    """Print the loaded areas. They are all valid: load() repairs them."""
    _deprecated("checkPoly()", "geoClassy.load(), which validates and repairs on load")
    for i, name in enumerate(_loaded().names):
        print("Polygon", i, ":", name)
        print("ok")


def polyList() -> list:
    """Return the list of area names."""
    _deprecated("polyList()", "areas.names")
    return _loaded().names


def getNames(lat: float, lon: float) -> Any:
    """Return the name of the area containing the point, or ``'unknown'``."""
    _deprecated("getNames()", "areas.locate()")
    found = _loaded().locate(lat, lon)
    return "unknown" if found is None else found
