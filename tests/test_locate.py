"""The lookup API."""

from __future__ import annotations

import pytest

import geoClassy
from conftest import collection, square, write


def test_outside_every_area_is_none(tmp_path, disjoint):
    assert geoClassy.load(write(tmp_path, disjoint)).locate(85, 170) is None


def test_locate_many_matches_locate(tmp_path, nested):
    areas = geoClassy.load(write(tmp_path, nested))
    lats = [50, 45, 5, 85]
    lons = [50, 45, 5, 170]
    assert areas.locate_many(lats, lons) == [areas.locate(a, o) for a, o in zip(lats, lons)]


def test_locate_many_is_empty_safe(tmp_path, disjoint):
    assert geoClassy.load(write(tmp_path, disjoint)).locate_many([], []) == []


def test_locate_many_rejects_mismatched_lengths(tmp_path, disjoint):
    areas = geoClassy.load(write(tmp_path, disjoint))
    with pytest.raises(ValueError, match="same length"):
        areas.locate_many([1, 2], [1])


def test_full_returns_the_properties(tmp_path):
    data = collection(square("Milano", 0, 0, 10, 10, admin_level="8", wikidata="Q490"))
    areas = geoClassy.load(write(tmp_path, data))
    assert areas.locate(5, 5, full=True)["wikidata"] == "Q490"
    assert areas.locate(85, 170, full=True) is None


def test_full_result_is_a_copy(tmp_path):
    areas = geoClassy.load(write(tmp_path, collection(square("A", 0, 0, 10, 10))))
    areas.locate(5, 5, full=True)["name"] = "mutated"
    assert areas.locate(5, 5) == "A"


def test_areas_is_reusable_and_repr_is_useful(tmp_path, disjoint):
    areas = geoClassy.load(write(tmp_path, disjoint))
    assert areas.locate(5, 5) == "Alpha"
    assert areas.locate(25, 25) == "Beta"
    assert "2 areas" in repr(areas)
