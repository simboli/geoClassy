# Getting boundary data

geoClassy classifies points against named polygons. It does not download
anything — you bring a GeoJSON file, it does the rest. This page is about where
that file comes from.

**If you are in a hurry, read only the next section.** The rest explains what
you are actually downloading, why some downloads come back empty, and how to
check a file before trusting it. It is written to be complete enough to hand to
an assistant along with your question.

Everything below was run, not just written: the counts, the failures and the
timings are real, from OpenStreetMap as of September 2026.

---

## The 60-second version

### One boundary

Ask [Nominatim](https://nominatim.org/) for it by name. One HTTP request, GeoJSON
back, polygon included:

```bash
curl -s -A "my-project/1.0 (me@example.com)" -G \
  --data-urlencode "q=Bologna, Italia" \
  --data-urlencode "format=geojson" \
  --data-urlencode "polygon_geojson=1" \
  --data-urlencode "limit=1" \
  "https://nominatim.openstreetmap.org/search" > bologna.geojson
```

```python
import geoClassy

areas = geoClassy.load("bologna.geojson")
areas.names                        # ['Bologna']
areas.locate(44.4949, 11.3426)     # 'Bologna'  — Piazza Maggiore
areas.locate(45.4642, 9.1900)      # None       — that's Milan
```

### Many boundaries at once

Open [Overpass Turbo](https://overpass-turbo.eu/), paste this, press **Run**,
then **Export → Data → GeoJSON**:

```
[out:json][timeout:180];
area(3600044915)->.searchArea;          // Milan: OSM relation 44915
relation(area.searchArea)["boundary"="administrative"]["admin_level"="10"];
out geom;
```

That returns Milan's nine *municipi*. Save the export as `municipi.geojson`, then:

```python
areas = geoClassy.load("municipi.geojson")
len(areas)                         # 9
areas.locate(45.4642, 9.1900)      # 'Municipio 1'
```

To point the query somewhere else, replace `44915` with the relation id of your
area (section 3 shows how to find it) and `"10"` with the level you want
(section 4 explains why that number is not what you think).

### Before you trust the file

```python
len(areas)                # is it the number you expected?
areas.names               # are they the names you expected?
areas.overlapping_pairs() # [] means no area contains another — see section 6 if not
```

That's it. Everything below is depth.

---

## 1. What geoClassy needs from a file

A GeoJSON `FeatureCollection` in WGS84 (longitude/latitude degrees, which is the
only coordinate system GeoJSON allows). From each feature it uses:

- the **geometry**, if it is a `Polygon` or a `MultiPolygon`. Points, lines and
  anything else are skipped silently — see section 5 for why that matters;
- one **property** as the label, `name` by default. Change it with
  `name_key=`. A feature without that property is skipped;
- the whole properties dict, kept and returned by `locate(..., full=True)`.

Nothing else is required. No `type: boundary` tag, no `id`, no particular
ordering. Any tool that writes standard GeoJSON produces something geoClassy can
read, and `.geojson.gz` is read transparently.

---

## 2. One boundary at a time: Nominatim

Nominatim is OpenStreetMap's geocoder. Its search endpoint can return the full
polygon of whatever it matches, which makes it the shortest path from "the name
of a place" to "a file geoClassy can load".

### The request

```
https://nominatim.openstreetmap.org/search
    ?q=Bologna, Italia
    &format=geojson
    &polygon_geojson=1
    &limit=1
    &extratags=1
```

| parameter | value | why |
| --- | --- | --- |
| `q` | free text | the place, as you would type it into a map |
| `format` | `geojson` | a FeatureCollection, ready for `load()` |
| `polygon_geojson` | `1` | include the geometry; without it you get a point |
| `limit` | `1` | one best match |
| `extratags` | `1` | also return `admin_level`, `population`, `wikidata`, … |

From Python, with nothing but the standard library:

```python
import json
import time
import urllib.parse
import urllib.request

USER_AGENT = "my-project/1.0 (me@example.com)"   # identify yourself: required by the usage policy


def nominatim_boundary(query: str) -> dict:
    """Return a GeoJSON FeatureCollection with the best match for `query`."""
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({
        "q": query, "format": "geojson", "polygon_geojson": 1, "limit": 1, "extratags": 1,
    })
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


# Several boundaries into one file. Sleep between calls: at most one request per second.
features = []
for place in ["Italia", "Lombardia, Italia", "Milano, Italia", "San Marino"]:
    features.extend(nominatim_boundary(place)["features"])
    time.sleep(1.1)

with open("italy-nested.geojson", "w", encoding="utf-8") as fh:
    json.dump({"type": "FeatureCollection", "features": features}, fh)
```

### What comes back

Each feature carries these properties:

```
name, display_name, category, type, osm_type, osm_id, place_id, place_rank,
importance, addresstype, extratags
```

`name` is there, so `load()` works with no options. The interesting OSM tags —
`admin_level`, `ref:ISTAT`, `population`, `wikidata` — are **nested under
`extratags`**, not at the top level. They survive into
`locate(..., full=True)`:

```python
areas = geoClassy.load("italy-nested.geojson")
areas.locate(45.4642, 9.1900, full=True)["extratags"]["admin_level"]   # '8'
```

The file above is 2.8 MB for four areas and loads in about 90 ms. Italy alone is
a `MultiPolygon` with six parts (the mainland, Sicily, Sardinia, …) and two
holes — San Marino and Vatican City are enclaves, so they are cut out of
Italy's polygon. geoClassy respects both:

```python
areas.locate(38.1157, 13.3615)     # 'Italia'      — Palermo, on Sicily
areas.locate(43.9424, 12.4578)     # 'San Marino'  — not 'Italia': it's a hole
areas.locate(41.9022, 12.4539)     # None          — St Peter's, in the Vatican hole
```

### Where it goes wrong

**The first match is not always the one you meant.** Nominatim ranks by text
similarity and importance. `"Bologna"` and `"Bologna, Italia"` both return the
city (relation 43172, `admin_level=8`). `"Comune di Bologna"` returns a hamlet
literally named *Comune* near Sasso Marconi, tagged `place=isolated_dwelling`.
Write the query the way a local would type it, and always check `category`,
`type` and `display_name` in the result:

```python
feature = nominatim_boundary("Comune di Bologna")["features"][0]
feature["properties"]["category"], feature["properties"]["type"]
# ('place', 'isolated_dwelling')   <- not what you wanted
```

**The result may not be a polygon.** `"Città del Vaticano"` comes back as a
`Point`. So do most neighbourhoods (section 5). geoClassy skips such features
and, if nothing polygonal is left, raises `NoAreasFoundError` saying so.

**It is a geocoder, not a bulk download.** The
[usage policy](https://operations.osmfoundation.org/policies/nominatim/) is one
request per second, a `User-Agent` that identifies your application, and no
mass querying. A handful of boundaries is fine; a thousand is not. For that,
use Overpass.

---

## 3. All the subdivisions of an area: Overpass

Overpass is a query engine over the OpenStreetMap database. It is the tool for
"every X inside Y": every municipality in a region, every borough in a city,
every district in a municipality.

### Find the id of the containing area

Overpass addresses areas by numeric id. The simplest way to get it is
Nominatim's `osm_id` (with `osm_type=relation`), then add 3 600 000 000:

| place | OSM relation | Overpass area id |
| --- | --- | --- |
| Lombardia | 44879 | `3600044879` |
| Milano | 44915 | `3600044915` |
| Bologna | 43172 | `3600043172` |
| New York City | 175905 | `3600175905` |

```python
props = nominatim_boundary("Lombardia, Italia")["features"][0]["properties"]
assert props["osm_type"] == "relation"
area_id = 3_600_000_000 + props["osm_id"]      # 3600044879
```

You can also match the area by tags instead of id. It works, and it is more
readable, but it will silently pick the wrong thing if two areas share the name:

```
area["name"="Lombardia"]["boundary"="administrative"]["admin_level"="4"]->.searchArea;
```

### The query

```
[out:json][timeout:180];
area(3600044879)->.searchArea;
relation(area.searchArea)["boundary"="administrative"]["admin_level"="8"];
out geom;
```

Line by line:

- `[out:json][timeout:180]` — JSON output; allow three minutes. Regions with
  thousands of boundaries need it.
- `area(…)->.searchArea` — the container, from the table above.
- `relation(area.searchArea)[…][…]` — administrative boundaries at one level,
  inside it. Boundaries are relations in OSM; that keyword is not optional.
- `out geom;` — include the geometry. Without it you get ids and tags only.

Run in Overpass Turbo, this returns Lombardia's **1 501 comuni** in about nine
seconds. **Export → Data → GeoJSON** downloads a FeatureCollection whose
properties are the OSM tags of each relation, flattened:

```json
{"@id": "relation/44915", "name": "Milano", "boundary": "administrative",
 "admin_level": "8", "type": "boundary", "wikidata": "Q490", "ref:ISTAT": "015146", …}
```

`name` is at the top level, so `load()` needs no options. That `"type":
"boundary"` is the relation's own OSM tag — it is what the
`only_boundaries=True` option filters on, and why old versions of geoClassy
required it. Most other tools don't emit it, which is why the filter is now off
by default.

### Two more useful queries

Milan's nine *municipi* (the quick-start example):

```
[out:json][timeout:180];
area(3600044915)->.searchArea;
relation(area.searchArea)["boundary"="administrative"]["admin_level"="10"];
out geom;
```

Returns `Municipio 1` … `Municipio 9` — one of them, in the data, is actually
called `Municipio 8 di Milano`. Real datasets are like that; don't build string
matching on top of names you haven't looked at.

Every administrative boundary inside an area, **tags only** — small and fast,
for finding out what exists before downloading geometry (section 4):

```
[out:json][timeout:180];
area(3600175905)->.searchArea;
relation(area.searchArea)["boundary"="administrative"];
out tags;
```

### From Python, reproducibly

Overpass Turbo is fine for a one-off. If you want the download to be
repeatable — in a script, in CI, six months from now — call the API directly.
Overpass returns its own JSON, not GeoJSON; boundary relations come as loose
member ways that must be stitched into rings, with outer/inner roles and
direction to get right. Don't write that yourself: the
[`osm2geojson`](https://pypi.org/project/osm2geojson/) package does it.

```bash
pip install osm2geojson
```

```python
import json
import urllib.parse
import urllib.request

import osm2geojson

USER_AGENT = "my-project/1.0 (me@example.com)"
OVERPASS = "https://overpass-api.de/api/interpreter"

QUERY = """
[out:json][timeout:180];
area(3600044915)->.searchArea;
relation(area.searchArea)["boundary"="administrative"]["admin_level"="10"];
out geom;
"""


def overpass(query: str) -> dict:
    data = urllib.parse.urlencode({"data": query}).encode()
    request = urllib.request.Request(OVERPASS, data=data, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=300) as response:
        return json.load(response)


geojson = osm2geojson.json2geojson(overpass(QUERY))

# osm2geojson keeps the OSM tags nested under properties["tags"]; geoClassy
# looks for the label at the top level. Lift them up.
for feature in geojson["features"]:
    tags = feature["properties"].pop("tags", {})
    feature["properties"] = {**tags, **feature["properties"]}

with open("municipi.geojson", "w", encoding="utf-8") as fh:
    json.dump(geojson, fh)
```

If you forget the flattening step, `load()` tells you exactly what it found:

```
NoAreasFoundError: 9 polygonal features found, but none had a 'name' property
to use as a label. Available property keys: 'id', 'tags', 'type'. Pass name_key=
to choose one.
```

### When Overpass says no

The public instance is shared and busy. `504 Gateway Timeout` means the server
is overloaded, not that your query is wrong — the NYC query above got one on its
first attempt and succeeded on the retry. Wait a few seconds and try again, or
use a mirror such as `https://overpass.kumi.systems/api/interpreter`. Never
retry in a tight loop, and never put an Overpass call inside something that runs
per point: download once, save the file, load the file.

---

## 4. The `admin_level` trap

`admin_level` is a number from 1 to 11 describing how deep an administrative
boundary sits in its country's hierarchy. It is **not** the same across
countries. The
[OSM wiki table](https://wiki.openstreetmap.org/wiki/Tag:boundary%3Dadministrative#admin_level=*_Country_specific_values)
is the reference; a few rows of it:

| level | Italy | United States | France | Germany |
| --- | --- | --- | --- | --- |
| 4 | regione | state | région | Bundesland |
| 6 | provincia | county | département | Landkreis |
| 8 | comune | city / town | commune | Gemeinde |
| 10 | municipio / circoscrizione | community board, ward | arrondissement | Stadtteil |

So "level 8 inside Lombardia" is 1 501 comuni, but "level 8 inside New York
City" is nothing at all — NYC's subdivisions live at other levels, and its
neighbourhoods have no `admin_level` whatsoever. That is the trap: a query that
works perfectly in one country returns an empty file in another, with no error
to tell you why.

### Ask what exists before you ask for it

Run the tags-only query from section 3 and count. This is what it says for New
York City (relation 175905):

| `admin_level` | count | examples |
| --- | --- | --- |
| 5 | 1 | New York (the city itself) |
| 6 | 5 | Kings County, Queens County, Richmond County, … |
| 7 | 5 | Manhattan, Brooklyn, Queens, … (the boroughs) |
| 10 | 13 | Manhattan Community Board 9, 10, 11, … |

Two things a New Yorker would notice. There is no level 8, so "level 8 like in
Italy" gives you nothing. And the community boards, which *are* the city's
official sub-borough units, are only 13 of the real 59 — OSM has mapped some
and not others. A file built on level 10 would cover a fraction of the city and
silently return `None` elsewhere.

The counting itself, in Python:

```python
from collections import Counter

elements = overpass("""
[out:json][timeout:180];
area(3600175905)->.searchArea;
relation(area.searchArea)["boundary"="administrative"];
out tags;
""")["elements"]

by_level = Counter(e["tags"].get("admin_level", "?") for e in elements)
for level, count in sorted(by_level.items()):
    names = [e["tags"].get("name") for e in elements if e["tags"].get("admin_level") == level][:3]
    print(level, count, names)
```

Do this once per new area. It costs one light request and saves the afternoon
you would otherwise spend wondering why every point comes back `None`.

---

## 5. Neighbourhoods are not what you think

The most common thing people want to classify by — "which neighbourhood is this
in?" — is the least reliable thing in the data, for two reasons.

**Neighbourhoods are usually not administrative.** Chelsea, SoHo, Williamsburg
have no legal boundary; they are tagged `place=neighbourhood` or
`place=quarter`, not `boundary=administrative`, and carry no `admin_level`. The
queries in sections 3–4 will not find them. This one will:

```
[out:json][timeout:180];
area(3600175905)->.searchArea;
nwr(area.searchArea)["place"~"^(neighbourhood|quarter|suburb)$"];
out geom;
```

(`nwr` = nodes, ways and relations — because, as follows, they come as all three.)

**Most of them are points.** A `place=neighbourhood` node is a dot with a name,
placed roughly in the middle of the area. It has no polygon, so it cannot
contain anything. Counting what that query returns for New York City:

| `place` | OSM type | count | has a polygon? |
| --- | --- | --- | --- |
| neighbourhood | node | 286 | no |
| neighbourhood | way | 45 | yes |
| neighbourhood | relation | 5 | yes |
| quarter | node | 21 | no |
| suburb | node | 6 | no |

363 features, of which **313 — 86 % — are dots**. Load that file and geoClassy
keeps the 50 polygons and drops the rest; a point in Williamsburg comes back
`None` because Williamsburg is a node, not a shape. The data is not wrong, it is
just not the data you assumed.

What to do about it:

- **Check before you rely on it.** `len(areas)` against the count you expected;
  `areas.names` against the neighbourhoods you know are there.
- **Prefer an official source when one exists.** Many cities publish
  neighbourhood polygons as open data (New York's *Neighborhood Tabulation
  Areas*, for instance). They are usually GeoJSON already and load as-is.
- **Or draw your own.** Any polygons in a GeoJSON file will do. geoClassy does
  not care where they came from.

---

## 6. Check what you downloaded

Every download should be followed by three lines before it goes anywhere near
real data.

```python
import geoClassy

areas = geoClassy.load("download.geojson")

len(areas)                  # 1. the count you expected?
areas.names                 # 2. the names you expected, spelled the way you expect?
areas.overlapping_pairs()   # 3. does any area contain another?
```

### If the count is wrong

Too few: features were skipped. Either they are not polygons (section 5) or
they lack the label property. Both cases are reported when *nothing* is left;
when *some* survive, compare `areas.names` with what you asked for. To use a
different property as the label — a code rather than a name, or an English
name — pass it explicitly:

```python
geoClassy.load("regions.geojson", name_key="ISO3166-2")   # 'IT-25' instead of 'Lombardia'
geoClassy.load("regions.geojson", name_key="name:en")     # 'Lombardy'
```

If the key is missing, the error lists what is available:

```
NoAreasFoundError: 20 polygonal features found, but none had a 'ISO3166-2'
property to use as a label. Available property keys: 'admin_level', 'boundary',
'name', 'name:en', 'ref', 'wikidata', …
```

Too many: the export picked up more than boundaries — parks, water, buildings.
Either tighten the query, or keep only OSM boundary relations with
`only_boundaries=True`.

### If areas overlap

`overlapping_pairs()` returning anything means at least one area is inside
another, or two share territory. That happens when:

- you downloaded **several levels at once** (a city and its districts, a region
  and its municipalities);
- boundaries are **informal** and genuinely overlap (neighbourhoods, again).

In the first case the default `on_overlap="smallest"` already does the right
thing — a point in Brera resolves to Brera, not to Milano or Lombardia. If you
want a single level, split the file by `admin_level` instead of relying on the
policy. In the second case there is no right answer, and `on_overlap="all"`
gives you the list to decide from:

```python
areas = geoClassy.load("italy-nested.geojson")
areas.overlapping_pairs()
# [('Italia', 'Milano'), ('Italia', 'Lombardia'), ('Lombardia', 'Milano')]

areas.locate(45.4720, 9.1880)                     # 'Milano'
areas.locate(45.4720, 9.1880, on_overlap="all")   # ['Milano', 'Lombardia', 'Italia']
```

### If everything comes back `None`

In order of likelihood:

1. **Latitude and longitude are swapped.** GeoJSON stores `[lon, lat]`;
   geoClassy takes `(lat, lon)`. When the swap pushes a value out of range you
   get an error that says so; when both values are valid latitudes — most of
   Europe and the eastern US — it just misses. Check one known point by hand.
2. **The file covers a different place** than your points. Look at
   `areas.names`.
3. **The features are points, not polygons** (section 5).
4. The coordinates are in a **projected system** (metres, not degrees). Convert
   to WGS84 before saving as GeoJSON; the spec requires it.

---

## 7. Keep it reproducible

OpenStreetMap changes every minute. A boundary gets refined, a relation gets
split, a name gets a suffix. If you download the same query next month, some
points will land in different areas, and nothing in your own data will have
changed. Treat the downloaded file as an input, not a cache:

- **Commit it.** It is data your results depend on. `.geojson.gz` keeps large
  ones small and `load()` reads it directly.
- **Record how you got it.** The query, the source, the date — in a sidecar
  note, in the filename (`comuni-lombardia-2026-09-09.geojson`), or as a
  top-level key in the file itself, which GeoJSON tolerates and geoClassy
  ignores:

  ```python
  geojson["source"] = {
      "query": QUERY.strip(), "endpoint": OVERPASS, "fetched": "2026-09-09",
      "attribution": "© OpenStreetMap contributors, ODbL",
  }
  ```

- **Re-download deliberately**, then diff `areas.names` old against new before
  swapping the file in.

---

## 8. Other sources

Anything that writes standard GeoJSON works. Some that are worth knowing:

- **[polygons.openstreetmap.fr](https://polygons.openstreetmap.fr/)** — the
  polygon of one OSM relation by id, optionally simplified. Handy when you
  already have the id and want a smaller file.
- **[geoBoundaries](https://www.geoboundaries.org/)** — administrative
  boundaries for every country, several levels each, CC BY 4.0. Consistent
  across countries in a way OSM is not.
- **[Natural Earth](https://www.naturalearthdata.com/)** — countries and
  first-level subdivisions, public domain, deliberately coarse. Right for
  continent-scale work, wrong for anything inside a city.
- **[GADM](https://gadm.org/)** — deep administrative hierarchies worldwide.
  Free for academic and non-commercial use only; check the licence before using
  it in a product.
- **Municipal open-data portals** — for neighbourhoods, districts, census
  tracts and anything else that has an official definition, the city's own
  portal is more authoritative than OSM and usually already GeoJSON.
- **Your own GIS.** Export to GeoJSON in WGS84 and you are done. geoClassy has
  no opinion about where a polygon came from.

Whatever the source, the checks in section 6 apply unchanged.

---

## 9. Etiquette and licensing

OpenStreetMap data is © OpenStreetMap contributors and licensed under the
[ODbL](https://www.openstreetmap.org/copyright). If you publish results derived
from it, say so.

Nominatim and Overpass are run by volunteers on donated hardware. The
[Nominatim usage policy](https://operations.osmfoundation.org/policies/nominatim/)
is explicit: one request per second, a real `User-Agent`, no bulk geocoding.
Overpass has no hard quota but shares the same spirit: download once, keep the
file, and never let a per-point loop reach the network. If you need thousands of
boundaries regularly, run your own instance or use one of the bulk sources in
section 8.

---

## Appendix: reference card

**Nominatim, one boundary**

```
https://nominatim.openstreetmap.org/search?q=<place>&format=geojson&polygon_geojson=1&limit=1&extratags=1
```

**Overpass, subdivisions at one level**

```
[out:json][timeout:180];
area(<3600000000 + relation id>)->.searchArea;
relation(area.searchArea)["boundary"="administrative"]["admin_level"="<n>"];
out geom;
```

**Overpass, what levels exist here** — same query with `out tags;` and no
`admin_level` filter, then count.

**Overpass, non-administrative places**

```
nwr(area.searchArea)["place"~"^(neighbourhood|quarter|suburb)$"];
```

**geoClassy, loading**

| option | default | use it when |
| --- | --- | --- |
| `name_key` | `"name"` | the label lives in another property |
| `only_boundaries` | `False` | the export mixes boundaries with other polygons |
| `on_overlap` | `"smallest"` | areas nest or overlap; `"all"` to see every match |

**geoClassy, checking**

```python
len(areas)  ·  areas.names  ·  areas.overlapping_pairs()  ·  areas.locate(lat, lon, full=True)
```
