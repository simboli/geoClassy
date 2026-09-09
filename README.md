# geoClassy

Label GPS points with the area that contains them — a neighbourhood, a
municipality, a district — using boundary polygons you already have as GeoJSON,
typically exported from OpenStreetMap.

```python
import geoClassy

areas = geoClassy.load("nyc-neighborhoods.geojson")

areas.locate(40.748417, -73.985833)  # 'Midtown South'
areas.locate(38.897699, -77.036553)  # None — outside every area

df["zone"] = areas.locate_many(df.latitude, df.longitude)
```

That is the whole library. `len(areas)` counts them, `areas.names` lists them.

```console
pip install geoClassy
```

## Why not geopandas?

Because putting a point in an area shouldn't cost you GDAL and PROJ. geoClassy
does this one job with Shapely and NumPy — no geospatial system libraries, no
network calls, no API keys, and answers that don't change between runs.

|                        | geoClassy | geopandas | reverse-geocoding API |
| ---------------------- | --------- | --------- | --------------------- |
| Install                | 2 wheels  | GDAL + PROJ | — |
| Works offline          | yes       | yes       | no |
| Your own boundaries    | yes       | yes       | no |
| Rate limits            | none      | none      | yes |

If you already run geopandas, use `sjoin` — it is the right tool and geoClassy
adds nothing. This is for everyone else.

## Speed

`locate_many` runs one spatial-index query for the whole batch instead of one
per point. Use it instead of `df.apply(...)` row by row.

- 5,000 points against 500 areas: **3 ms** (the same work took 24 s in 0.1.x).
- 1,000,000 points against a 5,000-area partition where every point lands in
  one: **1.1 s**, after an 83 ms load.

Rows with missing coordinates come back as `None` rather than raising, so a
dataframe with gaps still classifies in one call.

## Overlapping areas

A point can legitimately fall inside several areas at once — a district inside
a city inside a region, which is what you get when an Overpass query returns
more than one `admin_level`. By default geoClassy returns **the smallest
matching area**, that is, the most specific one:

```python
areas.locate(45.472, 9.188)  # 'Brera', not 'Milano' or 'Lombardia'
```

Change it with `on_overlap`, either for the whole dataset or per call:

| `on_overlap` | result |
| ------------ | ------ |
| `"smallest"` | the smallest matching area (default) |
| `"first"` / `"last"` | first or last match in file order |
| `"all"`      | every match, smallest first |
| `"error"`    | raise `OverlapError` |

To find out whether this affects your data at all, ask:

```python
areas.overlapping_pairs()  # [] means no policy can change anything
```

## Loading

```python
geoClassy.load(path, *, name_key="name", only_boundaries=False, on_overlap="smallest")
```

- `.geojson`, `.json`, and `.gz` versions of either are read transparently.
- `name_key` picks the property to label with — `"ISO3166-2"`, `"ref"`, whatever
  your export carries. If it is missing, the error tells you which keys exist.
- `only_boundaries=True` keeps only features tagged `properties.type ==
  "boundary"`. Off by default: most export tools don't set it.
- `Areas.from_geojson(data)` takes an already-parsed dict.
- `locate(..., full=True)` returns the feature's whole `properties` dict rather
  than just the name, so you keep `admin_level`, `wikidata`, ISO codes.

Coordinates are WGS84 degrees, the system GeoJSON mandates. Arguments are
`(lat, lon)`; GeoJSON stores `[lon, lat]`, and out-of-range values are rejected
with a message pointing at that swap. Points exactly on a boundary count as inside. Invalid polygons —
endemic in OSM exports — are repaired on load.

## Where to get the boundaries

geoClassy never touches the network: you bring the file. Two ways to get one, in
one request each:

- **one boundary by name** — [Nominatim](https://nominatim.org/) returns it as
  GeoJSON, polygon included:

  ```bash
  curl -s -A "my-project/1.0 (me@example.com)" -G \
    --data-urlencode "q=Bologna, Italia" --data-urlencode "format=geojson" \
    --data-urlencode "polygon_geojson=1" --data-urlencode "limit=1" \
    "https://nominatim.openstreetmap.org/search" > bologna.geojson
  ```

- **all the subdivisions of an area** — paste a five-line query into
  [Overpass Turbo](https://overpass-turbo.eu/) and export GeoJSON.

The full guide, **[Getting boundary data](https://github.com/simboli/geoClassy/blob/master/docs/getting-data.md)**,
has the Overpass queries ready to paste, explains why `admin_level` means
different things in different countries, why most "neighbourhoods" in OSM are
points rather than polygons, and how to check a file before trusting it.

## Upgrading from 0.1.x

The old function API still works, with a `DeprecationWarning`, and will be
removed in 1.0. It keeps 0.1.x semantics exactly, so upgrading changes no
results before you migrate:

| 0.1.x | 0.2 |
| ----- | --- |
| `loadFile(path)`     | `areas = geoClassy.load(path)` |
| `getNames(lat, lon)` | `areas.locate(lat, lon)` — returns `None`, not `'unknown'` |
| `numPoly()`          | `len(areas)` |
| `polyList()`         | `areas.names` |
| `checkPoly()`        | gone: `load()` validates and repairs, and raises if it can't |
| `requisites()`       | gone: just `import geoClassy` |

Three of those crashed with `TypeError` on Shapely 2.x, and `getNames` returned
whichever overlapping area happened to come last in the file. See
[CHANGELOG.md](https://github.com/simboli/geoClassy/blob/master/CHANGELOG.md).

## Contact

Written by Nicola Simboli — *support@simboli.eu*,
[simboli.eu](http://www.simboli.eu/). MIT licensed.
