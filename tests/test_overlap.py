"""Policies for a point that falls inside more than one area."""

from __future__ import annotations

import numpy as np
import pytest

import geoClassy
from conftest import write
from geoClassy import Areas


def test_smallest_is_the_default_and_is_the_most_specific(tmp_path, nested):
    areas = geoClassy.load(write(tmp_path, nested))
    assert areas.on_overlap == "smallest"
    assert areas.locate(50, 50) == "Brera"
    assert areas.locate(45, 45) == "Milano"
    assert areas.locate(5, 5) == "Lombardia"


@pytest.mark.parametrize(
    ("policy", "expected"),
    [("first", "Lombardia"), ("last", "Brera"), ("smallest", "Brera")],
)
def test_policies_pick_different_winners(tmp_path, nested, policy, expected):
    areas = geoClassy.load(write(tmp_path, nested), on_overlap=policy)
    assert areas.locate(50, 50) == expected


def test_all_returns_every_match_smallest_first(tmp_path, nested):
    areas = geoClassy.load(write(tmp_path, nested), on_overlap="all")
    assert areas.locate(50, 50) == ["Brera", "Milano", "Lombardia"]
    assert areas.locate(85, 170) == []


def test_error_policy_names_the_clashing_areas(tmp_path, nested):
    areas = geoClassy.load(write(tmp_path, nested), on_overlap="error")
    assert areas.locate(5, 5) == "Lombardia"
    with pytest.raises(geoClassy.OverlapError, match="Brera, Lombardia, Milano"):
        areas.locate(50, 50)


def test_policy_can_be_overridden_per_call(tmp_path, nested):
    areas = geoClassy.load(write(tmp_path, nested))
    assert areas.locate(50, 50, on_overlap="first") == "Lombardia"
    assert areas.locate(50, 50) == "Brera"


def test_unknown_policy_is_rejected(tmp_path, nested):
    with pytest.raises(ValueError, match="unknown on_overlap"):
        geoClassy.load(write(tmp_path, nested), on_overlap="biggest")


def test_overlapping_pairs_reports_the_impact(tmp_path, nested, disjoint):
    overlapping = geoClassy.load(write(tmp_path, nested))
    assert set(overlapping.overlapping_pairs()) == {
        ("Lombardia", "Milano"),
        ("Lombardia", "Brera"),
        ("Milano", "Brera"),
    }
    # No overlaps means no policy can change any answer for this dataset.
    clean = geoClassy.load(write(tmp_path, disjoint, "clean.geojson"))
    assert clean.overlapping_pairs() == []


def test_exact_area_ties_are_broken_by_file_order(tmp_path):
    """Two areas of identical size containing the same point: the earlier
    feature must win, whatever order the spatial index happens to return."""
    from conftest import collection, square

    a = square("First", 0, 0, 10, 10)
    b = square("Second", 2, 2, 12, 12)
    assert geoClassy.load(write(tmp_path, collection(a, b))).locate(5, 5) == "First"
    assert geoClassy.load(write(tmp_path, collection(b, a), "r.geojson")).locate(5, 5) == "Second"


def test_enclave_hole_is_not_an_overlap():
    """An enclave whose hole was digitised separately from the enclave's own
    outline. Two tracings of one border never coincide bit for bit, so the
    intersection has a tiny non-zero area -- for San Marino inside Italy it is
    about 1e-18 square degrees -- and a strict > 0 reported it as an overlap."""
    import shapely
    from shapely.geometry import Polygon

    angles = np.linspace(0, 2 * np.pi, 121)[:-1]
    radius = 1.3 + 0.15 * np.sin(7 * angles) + 0.04 * np.cos(3 * angles)
    ring = np.c_[5 + radius * np.cos(angles), 5 + radius * np.sin(angles)]
    enclave = Polygon(ring)
    jitter = np.random.default_rng(0).normal(scale=1e-10, size=ring.shape)
    outer = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)], holes=[ring + jitter])
    sliver = shapely.intersection(outer, enclave).area
    assert 0 < sliver < 1e-9 * enclave.area  # the class of noise this guards against

    areas = Areas([outer, enclave], ["Outer", "Enclave"])
    assert areas.overlapping_pairs() == []
    assert areas.locate(5, 5) == "Enclave"
    assert areas.locate(1, 1) == "Outer"


def test_a_real_but_small_overlap_is_still_reported():
    """The tolerance must stay far below anything a human would call an overlap."""
    from shapely.geometry import box

    a = box(0, 0, 10, 10)
    b = box(10 - 1e-3, 0, 20, 10)  # a strip 1 mm wide on a 10 m square: 1e-4 of the area
    assert Areas([a, b], ["A", "B"]).overlapping_pairs() == [("A", "B")]


def test_sharing_a_border_is_not_an_overlap(tmp_path):
    from conftest import collection, square

    data = collection(square("West", 0, 0, 10, 10), square("East", 10, 0, 20, 10))
    assert geoClassy.load(write(tmp_path, data)).overlapping_pairs() == []
