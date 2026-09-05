"""Fixtures: tiny hand-written GeoJSON, not a real city export."""

from __future__ import annotations

import json

import pytest


def square(name, x0, y0, x1, y1, **properties):
    """A Feature holding an axis-aligned square, in GeoJSON [lon, lat] order."""
    properties.setdefault("name", name)
    return {
        "type": "Feature",
        "properties": properties,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]],
        },
    }


def collection(*features):
    return {"type": "FeatureCollection", "features": list(features)}


def write(tmp_path, data, filename="areas.geojson"):
    path = tmp_path / filename
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.fixture
def nested():
    """Region contains City contains District: one point sits in all three.

    Coordinates are arbitrary but kept inside the valid WGS84 ranges.
    """
    return collection(
        square("Lombardia", 0, 0, 80, 80, type="boundary"),
        square("Milano", 40, 40, 60, 60, type="boundary"),
        square("Brera", 48, 48, 52, 52, type="boundary"),
    )


@pytest.fixture
def disjoint():
    return collection(
        square("Alpha", 0, 0, 10, 10, type="boundary"),
        square("Beta", 20, 20, 30, 30, type="boundary"),
    )
