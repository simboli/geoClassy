"""One test per behaviour that was broken in 0.1.1.

Each was reproduced against the published package before being fixed here.
"""

from __future__ import annotations

import gzip
import json

import pytest

import geoClassy
from conftest import collection, square, write


def test_len_and_names_do_not_raise(tmp_path, disjoint):
    """0.1.1: numPoly/checkPoly/polyList raised TypeError on Shapely 2.x."""
    areas = geoClassy.load(write(tmp_path, disjoint))
    assert len(areas) == 2
    assert areas.names == ["Alpha", "Beta"]


def test_multipolygon_feature_loads(tmp_path):
    """0.1.1: ValueError, because areas were packed into a single MultiPolygon.

    An island or an exclave makes a boundary multipart, which is everywhere in
    OSM administrative data.
    """
    islands = {
        "type": "Feature",
        "properties": {"name": "Isole", "type": "boundary"},
        "geometry": {
            "type": "MultiPolygon",
            "coordinates": [
                [[[20, 20], [21, 20], [21, 21], [20, 21], [20, 20]]],
                [[[30, 30], [31, 30], [31, 31], [30, 31], [30, 30]]],
            ],
        },
    }
    areas = geoClassy.load(write(tmp_path, collection(square("Mainland", 0, 0, 10, 10), islands)))
    assert len(areas) == 2
    assert areas.locate(20.5, 20.5) == "Isole"
    assert areas.locate(30.5, 30.5) == "Isole"


def test_features_without_boundary_tag_are_used(tmp_path):
    """0.1.1: silently kept only properties.type == 'boundary', so most
    Overpass and osmtogeojson exports loaded zero areas and answered 'unknown'."""
    data = collection(square("Alpha", 0, 0, 10, 10))
    assert geoClassy.load(write(tmp_path, data)).locate(5, 5) == "Alpha"


def test_only_boundaries_is_available_but_opt_in(tmp_path):
    data = collection(
        square("Alpha", 0, 0, 10, 10, type="boundary"),
        square("Park", 2, 2, 4, 4, type="leisure"),
    )
    areas = geoClassy.load(write(tmp_path, data), only_boundaries=True)
    assert areas.names == ["Alpha"]


def test_point_on_the_boundary_is_inside(tmp_path, disjoint):
    """0.1.1 used `contains`, so a point exactly on an edge matched nothing."""
    areas = geoClassy.load(write(tmp_path, disjoint))
    assert areas.locate(0, 5) == "Alpha"
    assert areas.locate(0, 0) == "Alpha"


def test_answer_does_not_depend_on_feature_order(tmp_path, nested):
    """0.1.1 returned the *last* match in file order, so re-exporting the same
    Overpass query in a different order changed the answer."""
    features = nested["features"]
    answers = set()
    for order in ([0, 1, 2], [2, 1, 0], [1, 0, 2]):
        shuffled = collection(*(features[i] for i in order))
        areas = geoClassy.load(write(tmp_path, shuffled, f"o{order}.geojson"))
        answers.add(areas.locate(50, 50))
    assert answers == {"Brera"}


def test_lookup_before_load_is_impossible():
    """0.1.1 raised NameError on an internal variable name. There is no
    module-level state left to forget: an Areas either exists or it does not."""
    assert not hasattr(geoClassy, "getNames")


def test_swapped_lat_lon_is_reported(tmp_path, disjoint):
    """The single most common user error, previously an unexplained 'unknown'.

    Detection is by range, so it fires whenever the longitude exceeds +/-90 --
    here Tokyo. A swap between two values that are both valid latitudes cannot
    be caught this way, and is not claimed to be.
    """
    areas = geoClassy.load(write(tmp_path, disjoint))
    with pytest.raises(ValueError, match="Did you swap"):
        areas.locate(139.691706, 35.689487)  # Tokyo, with lat and lon swapped
    with pytest.raises(ValueError, match="out of range"):
        areas.locate(0, 200)


def test_missing_name_key_lists_what_is_available(tmp_path):
    data = collection(square("x", 0, 0, 1, 1, admin_level="8", ref="MI"))
    del data["features"][0]["properties"]["name"]
    with pytest.raises(geoClassy.NoAreasFoundError, match="'admin_level'"):
        geoClassy.load(write(tmp_path, data))


def test_invalid_geometry_is_repaired(tmp_path):
    """A bow-tie polygon: self-intersections are endemic in OSM boundaries."""
    bowtie = {
        "type": "Feature",
        "properties": {"name": "Bowtie"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[0, 0], [10, 10], [10, 0], [0, 10], [0, 0]]],
        },
    }
    areas = geoClassy.load(write(tmp_path, collection(bowtie)))
    assert areas.locate(5, 8) == "Bowtie"  # inside the right-hand lobe
    assert areas.locate(2, 5) is None  # the pinch point, genuinely outside


def test_gzipped_input(tmp_path, disjoint):
    path = tmp_path / "areas.geojson.gz"
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(disjoint, handle)
    assert geoClassy.load(path).locate(5, 5) == "Alpha"
