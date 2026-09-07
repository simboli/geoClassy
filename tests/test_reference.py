"""Cross-check the vectorised lookup against an obvious, slow implementation.

`locate_many` resolves a whole batch with index queries, sorting and masking.
That is worth having, and worth distrusting: this compares it on random data
against a straightforward loop written the naive way.
"""

from __future__ import annotations

import numpy as np
import pytest
import shapely
from shapely.geometry import Point, Polygon

from geoClassy import Areas


def reference(geoms, names, lats, lons, policy):
    """The obvious implementation: test every point against every area."""
    out = []
    for lat, lon in zip(lats, lons):
        point = Point(lon, lat)
        hits = sorted(
            (i for i, g in enumerate(geoms) if g.covers(point)),
            key=lambda i: (geoms[i].area, i),
        )
        if policy == "all":
            out.append([names[i] for i in hits])
        elif not hits:
            out.append(None)
        elif policy == "smallest":
            out.append(names[hits[0]])
        elif policy == "first":
            out.append(names[min(hits)])
        else:
            out.append(names[max(hits)])
    return out


def random_areas(rng, on_overlap):
    geoms, names = [], []
    for i in range(int(rng.integers(1, 25))):
        cx, cy = rng.uniform(-170, 170), rng.uniform(-80, 80)
        angles = np.sort(rng.uniform(0, 2 * np.pi, int(rng.integers(3, 9))))
        radius = rng.uniform(0.5, 12)
        geom = Polygon(np.c_[cx + radius * np.cos(angles), cy + radius * np.sin(angles)])
        if not geom.is_valid:
            geom = shapely.make_valid(geom)
        if geom.is_empty or geom.geom_type not in ("Polygon", "MultiPolygon"):
            continue
        geoms.append(geom)
        names.append(f"area_{i}")
    if not geoms:
        return None, None, None
    return Areas(geoms, names, on_overlap=on_overlap), geoms, names


@pytest.mark.parametrize("policy", ["smallest", "first", "last", "all"])
@pytest.mark.parametrize("seed", range(6))
def test_matches_a_naive_implementation(policy, seed):
    rng = np.random.default_rng(seed)
    areas, geoms, names = random_areas(rng, policy)
    if areas is None:
        pytest.skip("degenerate geometry set")
    lats = rng.uniform(-85, 85, 120)
    lons = rng.uniform(-175, 175, 120)
    assert areas.locate_many(lats, lons) == reference(geoms, names, lats, lons, policy)
