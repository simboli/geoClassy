# Changelog

## 0.2.0

A repair-and-foundations release: no new features, but the package now installs
correctly, answers correctly, and is fast on batches.

### Fixed

Every one of these was reproduced against the published 0.1.1 before being fixed,
and each has a regression test in `tests/test_regressions.py`.

- `numPoly()`, `checkPoly()` and `polyList()` raised
  `TypeError: object of type 'MultiPolygon' has no len()` on Shapely 2.x — that
  is, on every currently installable Shapely. Three of the five public functions
  did not work at all.
- `loadFile()` raised `ValueError: Sequences of multi-polygons are not valid
  arguments` on any file containing a `MultiPolygon` feature, which is what an
  island or an exclave produces. Much of OSM's administrative data was unusable.
- Points falling inside several areas returned whichever match came **last in
  file order**. Re-exporting the same Overpass query could silently change
  results. Resolution is now an explicit policy, `on_overlap`, defaulting to
  `"smallest"` — the most specific area.
- Points lying exactly on a boundary matched nothing, because lookup used
  `contains`. It now uses `covered_by`.
- Files whose features are not tagged `properties.type == "boundary"` loaded
  zero areas in silence, and every lookup answered `'unknown'`. Most Overpass,
  osmtogeojson and geojson.io exports have no such tag. The filter is now
  opt-in via `only_boundaries=True`.
- Calling a lookup before loading raised `NameError` on an internal variable.
- `shapely` was never declared as a dependency; the README asked users to
  install it by hand.

### Added

- `Areas`, an immutable, spatially indexed collection replacing the module-level
  global state. Several datasets can be open at once, and it is safe to share
  between threads.
- `Areas.locate_many()`, vectorised over a whole batch: 5,000 points against 500
  areas went from 24 s to 3 ms, with identical answers.
- `on_overlap` policies: `"smallest"` (default), `"first"`, `"last"`, `"all"`,
  `"error"`.
- `Areas.overlapping_pairs()`, to check whether overlap policy affects your data
  at all before relying on it.
- `locate(..., full=True)` returns the feature's whole `properties` dict, so OSM
  tags such as `admin_level` and `wikidata` survive the lookup.
- `name_key=` to label areas with any property. A missing key now raises an
  error listing the keys that are actually present.
- Transparent `.gz` input.
- Out-of-range coordinates raise, with an explicit hint for the `(lat, lon)` vs
  `[lon, lat]` swap.
- Invalid polygons are repaired with `make_valid()` on load.
- Type hints and a `py.typed` marker.
- Tests, and CI across Python 3.9–3.13.

### Changed

- `locate()` returns `None` for a point outside every area. The old `'unknown'`
  string collided with a real area of that name and did not work with
  `pandas.isna`. The deprecated API still returns `'unknown'`.
- Packaging moved to `pyproject.toml`; `shapely>=2.0` and `numpy>=1.21` are
  declared. The repository now contains the source code, which it previously
  did not.

### Deprecated

`geoClassy.single` — `requisites`, `loadFile`, `numPoly`, `checkPoly`,
`polyList`, `getNames` — still works and emits `DeprecationWarning`. It keeps
0.1.x semantics deliberately, including the old order-dependent overlap
behaviour and the `only_boundaries` filter, so upgrading without touching your
code changes no results — with one deliberate exception: where 0.1.x loaded zero
areas in silence and then answered `'unknown'` for every point, `loadFile()` now
raises and tells you how to get at the files it was discarding. Removal in 1.0.

## 0.1.1 — 2022-11-12

- Partial Shapely 1.8/2.0 support: `getNames` was fixed, the other three
  polygon functions were left broken.

## 0.0.5 — 2019-02-10

- Small code diet; added project documentation.

## 0.0.4 — 2019-02-05

- First release on PyPI.
