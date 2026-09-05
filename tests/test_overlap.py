"""Policies for a point that falls inside more than one area."""

from __future__ import annotations

import pytest

import geoClassy
from conftest import write


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


def test_sharing_a_border_is_not_an_overlap(tmp_path):
    from conftest import collection, square

    data = collection(square("West", 0, 0, 10, 10), square("East", 10, 0, 20, 10))
    assert geoClassy.load(write(tmp_path, data)).overlapping_pairs() == []
