"""The deprecated 0.1.x API keeps working, warns, and no longer crashes."""

from __future__ import annotations

import pytest

from conftest import collection, square, write
from geoClassy import single


@pytest.fixture(autouse=True)
def _reset():
    single._areas = None


@pytest.fixture
def loaded(tmp_path, nested):
    with pytest.deprecated_call():
        single.loadFile(str(write(tmp_path, nested)))


def test_getnames_still_works(loaded):
    with pytest.deprecated_call():
        assert single.getNames(50, 50) == "Brera"


def test_getnames_keeps_the_unknown_sentinel(loaded):
    with pytest.deprecated_call():
        assert single.getNames(85, 170) == "unknown"


@pytest.mark.parametrize("func", ["numPoly", "checkPoly", "polyList"])
def test_functions_broken_on_shapely_2_are_repaired(loaded, capsys, func):
    """These three raised TypeError in 0.1.1 on any modern Shapely."""
    with pytest.deprecated_call():
        getattr(single, func)()


def test_polylist_returns_the_names(loaded):
    with pytest.deprecated_call():
        assert single.polyList() == ["Lombardia", "Milano", "Brera"]


def test_numpoly_prints_as_before(loaded, capsys):
    with pytest.deprecated_call():
        single.numPoly()
    assert "3  polygons loaded" in capsys.readouterr().out


def test_old_overlap_semantics_are_frozen(tmp_path, nested):
    """The deprecated API keeps 0.1.x's order-dependent 'last wins', so an
    upgrade changes no results until you move to the new API."""
    reversed_file = collection(*reversed(nested["features"]))
    with pytest.deprecated_call():
        single.loadFile(str(write(tmp_path, reversed_file)))
    with pytest.deprecated_call():
        assert single.getNames(50, 50) == "Lombardia"


def test_lookup_without_load_explains_itself():
    with pytest.deprecated_call(), pytest.raises(RuntimeError, match="loadFile"):
        single.getNames(1, 1)


def test_requisites_still_prints(capsys):
    with pytest.deprecated_call():
        single.requisites()
    assert "correctly imported" in capsys.readouterr().out


def test_file_with_no_boundary_tag_now_raises_with_a_route_out(tmp_path):
    """0.1.x loaded nothing here and answered 'unknown' for every point. The
    error must not suggest only_boundaries=, which this API cannot reach."""
    import geoClassy

    data = collection(square("Alpha", 0, 0, 10, 10))
    with (
        pytest.deprecated_call(),
        pytest.raises(geoClassy.NoAreasFoundError, match=r"geoClassy\.load\(path\) instead"),
    ):
        single.loadFile(str(write(tmp_path, data)))


def test_only_boundaries_filter_is_preserved(tmp_path):
    """0.1.x kept only properties.type == 'boundary'; the shim must too."""
    data = collection(
        square("Kept", 0, 0, 10, 10, type="boundary"),
        square("Dropped", 20, 20, 30, 30),
    )
    with pytest.deprecated_call():
        single.loadFile(str(write(tmp_path, data)))
    with pytest.deprecated_call():
        assert single.polyList() == ["Kept"]
