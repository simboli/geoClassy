# Sample boundary data

Two small GeoJSON files used by [`getting-started.ipynb`](../getting-started.ipynb).
They are real OpenStreetMap administrative boundaries, trimmed to fit in a
repository — **© OpenStreetMap contributors, licensed under the
[ODbL](https://www.openstreetmap.org/copyright)**. If you publish anything
derived from them, keep that attribution.

They are teaching data, frozen on 2026-09-09. For your own work, fetch current
boundaries as described in [`docs/getting-data.md`](../../docs/getting-data.md).

## `milan.geojson` — 11 areas, three nested levels

| name | `admin_level` | OSM relation | geometry |
| --- | --- | --- | --- |
| Lombardia | 4 | 44879 | MultiPolygon, 4 parts — simplified to 0.002° |
| Milano | 8 | 44915 | Polygon, full resolution |
| Municipio 1 … Municipio 9 | 10 | (see `osm_id`) | MultiPolygon, full resolution |

Lombardy was fetched from Nominatim, Milan from Nominatim with `extratags=1`, and
the nine *municipi* from Overpass via `osm2geojson`. Milan and its districts are
kept at full resolution on purpose: they share OSM ways, so their borders
coincide exactly and `overlapping_pairs()` reports precisely the 19 containment
pairs (Lombardy ⊃ Milan and the districts; Milan ⊃ the districts) and no
slivers. Simplifying each polygon independently would have broken that — a
lesson worth knowing before you simplify your own data.

## `italy.geojson` — 2 areas, islands and holes

| name | `admin_level` | OSM relation | geometry |
| --- | --- | --- | --- |
| Italia | 2 | 365331 | MultiPolygon, 6 parts, 2 holes — simplified to 0.005° |
| San Marino | 2 | 54624 | Polygon, full resolution |

Italy's raw outline has holes for San Marino and Vatican City. After
simplification the San Marino hole was re-cut from the San Marino geometry in
this same file (`difference`), so the two agree exactly. The Vatican hole is
kept from the source data; there is no Vatican feature, so a point in
St Peter's Square resolves to nothing. 0.005° is the coarsest tolerance at which
that hole survives.

## Properties

Trimmed to six keys, matching what an Overpass Turbo export carries:

```json
{"name": "Milano", "boundary": "administrative", "admin_level": "8",
 "type": "boundary", "osm_id": 44915, "wikidata": "Q490"}
```

`type: "boundary"` is the OSM relation's own tag; it is what the
`only_boundaries=True` option filters on.
