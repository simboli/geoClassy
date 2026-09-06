"""Point-in-area lookup over a GeoJSON collection of named polygons."""

from __future__ import annotations

import gzip
import json
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import shapely
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

__all__ = [
    "Areas",
    "load",
    "GeoClassyError",
    "InvalidGeoJSONError",
    "NoAreasFoundError",
    "OverlapError",
]

#: Policies for a point that falls inside more than one area.
OVERLAP_POLICIES = ("smallest", "first", "last", "all", "error")

_POLYGONAL = ("Polygon", "MultiPolygon")


class GeoClassyError(Exception):
    """Base class for every error raised by geoClassy."""


class InvalidGeoJSONError(GeoClassyError, ValueError):
    """The input is not a usable GeoJSON FeatureCollection."""


class NoAreasFoundError(GeoClassyError, ValueError):
    """The GeoJSON parsed correctly but produced no usable named areas."""


class OverlapError(GeoClassyError, ValueError):
    """A point matched several areas while ``on_overlap="error"`` was in force."""


def _check_policy(policy: str) -> str:
    if policy not in OVERLAP_POLICIES:
        raise ValueError(
            f"unknown on_overlap={policy!r}; expected one of "
            + ", ".join(repr(p) for p in OVERLAP_POLICIES)
        )
    return policy


def _as_floats(values: Iterable[float]) -> np.ndarray:
    """Coerce anything sequence-like -- list, tuple, ndarray, pandas Series -- to floats."""
    if not isinstance(values, np.ndarray):
        values = list(values)
    return np.asarray(values, dtype=float).ravel()


def _check_coords(lat: np.ndarray, lon: np.ndarray) -> None:
    """Reject out-of-range coordinates, with a hint for the classic lat/lon swap."""
    bad_lat = np.isfinite(lat) & (np.abs(lat) > 90)
    if bad_lat.any():
        value = float(lat[bad_lat][0])
        raise ValueError(
            f"latitude {value:g} is out of range [-90, 90]. "
            "Did you swap latitude and longitude? geoClassy takes (lat, lon), "
            "while GeoJSON coordinates are stored as [lon, lat]."
        )
    bad_lon = np.isfinite(lon) & (np.abs(lon) > 180)
    if bad_lon.any():
        value = float(lon[bad_lon][0])
        raise ValueError(f"longitude {value:g} is out of range [-180, 180].")


class Areas:
    """An immutable, spatially indexed collection of named areas.

    Build one with :func:`load` or :meth:`from_geojson`, then ask it which area
    a point falls into::

        areas = geoClassy.load("nyc.geojson")
        areas.locate(40.748417, -73.985833)
        areas.locate_many(df.latitude, df.longitude)

    Coordinates are WGS84 degrees (EPSG:4326), the coordinate system GeoJSON
    mandates. A point exactly on a boundary counts as inside.
    """

    __slots__ = ("_geoms", "_names", "_props", "_areas", "_tree", "_on_overlap")

    def __init__(
        self,
        geometries: Sequence[BaseGeometry],
        names: Sequence[str],
        properties: Sequence[dict] | None = None,
        *,
        on_overlap: str = "smallest",
    ) -> None:
        if len(geometries) != len(names):
            raise ValueError(f"got {len(geometries)} geometries but {len(names)} names")
        self._on_overlap = _check_policy(on_overlap)
        self._names = list(names)
        self._props = list(properties) if properties is not None else [{} for _ in names]
        # make_valid repairs the self-intersections that are endemic in OSM exports.
        geoms = np.empty(len(geometries), dtype=object)
        for i, geom in enumerate(geometries):
            geoms[i] = geom if geom.is_valid else shapely.make_valid(geom)
        self._geoms = geoms
        # Ranking key for on_overlap="smallest". This is an area in square
        # degrees, not square metres: converting would mean pulling in a
        # projection stack. It is safe here because every candidate for a given
        # point surrounds that same point, so they share a latitude band and the
        # distortion factor cancels out of the comparison. For nested areas
        # containment settles the order in any monotone measure anyway.
        self._areas = shapely.area(geoms)
        self._tree = shapely.STRtree(geoms)

    # -- construction ----------------------------------------------------

    @classmethod
    def from_geojson(
        cls,
        data: dict,
        *,
        name_key: str = "name",
        only_boundaries: bool = False,
        on_overlap: str = "smallest",
    ) -> Areas:
        """Build an :class:`Areas` from a parsed GeoJSON FeatureCollection."""
        if not isinstance(data, dict):
            raise InvalidGeoJSONError(f"expected a GeoJSON object, got {type(data).__name__}")
        features = data.get("features")
        if features is None:
            if data.get("type") == "Feature":
                features = [data]
            else:
                raise InvalidGeoJSONError(
                    "no 'features' key: expected a GeoJSON FeatureCollection "
                    f"(got type={data.get('type')!r})"
                )

        geoms: list[BaseGeometry] = []
        names: list[str] = []
        props: list[dict] = []
        seen_keys: set[str] = set()
        n_polygonal = 0

        for feature in features:
            geometry = (feature or {}).get("geometry") or {}
            if geometry.get("type") not in _POLYGONAL:
                continue
            n_polygonal += 1
            properties = feature.get("properties") or {}
            seen_keys.update(properties)
            if only_boundaries and properties.get("type") != "boundary":
                continue
            name = properties.get(name_key)
            if name is None:
                continue
            geoms.append(shape(geometry))
            names.append(str(name))
            props.append(properties)

        if not geoms:
            raise NoAreasFoundError(
                _no_areas_message(n_polygonal, name_key, only_boundaries, seen_keys)
            )

        return cls(geoms, names, props, on_overlap=on_overlap)

    # -- introspection ---------------------------------------------------

    def __len__(self) -> int:
        return len(self._names)

    def __repr__(self) -> str:
        return f"<Areas: {len(self._names)} areas, on_overlap={self._on_overlap!r}>"

    @property
    def names(self) -> list[str]:
        """The area names, in file order."""
        return list(self._names)

    @property
    def on_overlap(self) -> str:
        """The default policy for points matching more than one area."""
        return self._on_overlap

    def overlapping_pairs(self) -> list[tuple[str, str]]:
        """Names of every pair of areas that share more than a border.

        Use this before relying on the default ``on_overlap="smallest"``: if the
        list is empty, no policy can change any answer for this dataset.
        """
        left, right = self._tree.query(self._geoms, predicate="intersects")
        pairs = []
        for a, b in zip(left, right):
            if a >= b:
                continue
            if shapely.intersection(self._geoms[a], self._geoms[b]).area > 0:
                pairs.append((self._names[a], self._names[b]))
        return pairs

    # -- lookup ----------------------------------------------------------

    def locate(
        self,
        lat: float,
        lon: float,
        *,
        full: bool = False,
        on_overlap: str | None = None,
    ) -> Any:
        """Return the area containing ``(lat, lon)``, or ``None`` if there is none.

        With ``full=True`` the feature's whole ``properties`` dict is returned
        instead of just the name.
        """
        return self.locate_many([lat], [lon], full=full, on_overlap=on_overlap)[0]

    def locate_many(
        self,
        lats: Iterable[float],
        lons: Iterable[float],
        *,
        full: bool = False,
        on_overlap: str | None = None,
    ) -> list:
        """Vectorised :meth:`locate` over two equal-length sequences.

        This is the fast path: one spatial-index query for the whole batch
        rather than one per point.
        """
        policy = _check_policy(on_overlap or self._on_overlap)
        lat = _as_floats(lats)
        lon = _as_floats(lons)
        if lat.shape != lon.shape:
            raise ValueError(
                f"lats and lons must have the same length, got {lat.size} and {lon.size}"
            )
        _check_coords(lat, lon)

        n = lat.size
        points = shapely.points(lon, lat)
        # STRtree applies the predicate as input.predicate(tree_geometry), so
        # "covered_by" means "this point is inside (or on the edge of) that area".
        i_pt, i_area = self._tree.query(points, predicate="covered_by")

        if policy == "all":
            out: list[list] = [[] for _ in range(n)]
            order = np.lexsort((i_area, self._areas[i_area], i_pt))
            for p, a in zip(i_pt[order], i_area[order]):
                out[p].append(self._label(a, full))
            return out

        if policy == "error":
            counts = np.bincount(i_pt, minlength=n)
            clashes = np.flatnonzero(counts > 1)
            if clashes.size:
                p = int(clashes[0])
                matched = [self._names[a] for a in i_area[i_pt == p]]
                raise OverlapError(
                    f"point (lat={lat[p]:g}, lon={lon[p]:g}) falls inside "
                    f"{len(matched)} areas: {', '.join(sorted(matched))}. "
                    "Pass on_overlap='smallest', 'first', 'last' or 'all'."
                )

        if policy == "smallest":
            key: np.ndarray = self._areas[i_area]
        elif policy == "first":
            key = i_area
        else:  # "last" and the single survivor of "error"
            key = -i_area.astype(np.int64) if policy == "last" else i_area

        result: list = [None] * n
        if i_pt.size:
            # Sort by point, then by the policy key, then by feature index:
            # the winner is the first entry of each point's run. The final key
            # matters when two areas tie exactly -- without it the winner would
            # fall out of the index's internal ordering, which is the kind of
            # arbitrary answer this policy exists to remove.
            order = np.lexsort((i_area, key, i_pt))
            i_pt_s, i_area_s = i_pt[order], i_area[order]
            first = np.ones(i_pt_s.size, dtype=bool)
            first[1:] = i_pt_s[1:] != i_pt_s[:-1]
            for p, a in zip(i_pt_s[first], i_area_s[first]):
                result[p] = self._label(a, full)
        return result

    def _label(self, index: int, full: bool) -> Any:
        return dict(self._props[index]) if full else self._names[index]


def _no_areas_message(
    n_polygonal: int, name_key: str, only_boundaries: bool, seen_keys: set
) -> str:
    if n_polygonal == 0:
        return (
            "no Polygon or MultiPolygon features found. geoClassy classifies "
            "points against areas, so the input needs polygonal geometries."
        )
    if only_boundaries:
        return (
            f"{n_polygonal} polygonal features found, but none had "
            "properties.type == 'boundary'. Drop only_boundaries=True to use them all."
        )
    available = ", ".join(repr(k) for k in sorted(seen_keys)[:12]) or "none"
    return (
        f"{n_polygonal} polygonal features found, but none had a {name_key!r} "
        f"property to use as a label. Available property keys: {available}. "
        "Pass name_key= to choose one."
    )


def load(
    path: str | Path,
    *,
    name_key: str = "name",
    only_boundaries: bool = False,
    on_overlap: str = "smallest",
) -> Areas:
    """Read a GeoJSON file and return the :class:`Areas` it describes.

    Files ending in ``.gz`` are decompressed transparently.

    :param path: path to a ``.geojson``/``.json`` file, optionally gzipped.
    :param name_key: which feature property to use as the area label.
    :param only_boundaries: keep only features tagged ``properties.type ==
        "boundary"``. Off by default: most OSM export tools do not set it.
    :param on_overlap: what to do when a point falls inside several areas.
        ``"smallest"`` (default) returns the most specific one.
    """
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    try:
        with opener(path, "rt", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        raise InvalidGeoJSONError(f"{path} is not valid JSON: {exc}") from exc
    return Areas.from_geojson(
        data, name_key=name_key, only_boundaries=only_boundaries, on_overlap=on_overlap
    )
