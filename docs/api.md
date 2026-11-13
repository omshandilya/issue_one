# Orbit Portal API

Everything below is reached through the **gateway** (the address analysts use). Send the user's token as
`Authorization: Bearer <token>`; with no header you are anonymous. Coordinates are always `[longitude, latitude]`.
Times are UTC.

## Already there

| Route | What it does |
|---|---|
| `GET /search?bbox=min_lon,min_lat,max_lon,max_lat&datetime=start/end&limit=&offset=` | Scenes in a box |
| `GET /scenes/{id}` | One scene |
| `GET /scenes/{id}/file` | The scene's data file (supports `Range`) |
| `GET /tiles/{id}/{z}/{x}/{y}.png` | Map tile |

## New: search by any shape, and export (feature F1)

### `POST /search/polygon`

Search for scenes that **actually overlap** a shape.

Body: a GeoJSON **Polygon**: the outer ring first, then any number of **holes**.

```json
{"type": "Polygon",
 "coordinates": [
   [[81.5, 17.0], [82.4, 17.0], [82.4, 16.3], [81.5, 16.3], [81.5, 17.0]],
   [[81.8, 16.8], [82.0, 16.8], [82.0, 16.5], [81.8, 16.5], [81.8, 16.8]]
 ]}
```

Query parameters: `limit` (default 100) and `offset` (default 0), as for `/search`.

Answer `200`:

```json
{"search_id": "a3f9c21b7e04",
 "numberMatched": 37,
 "numberReturned": 37,
 "features": [ ...the first page of scenes, same shape as GET /search ... ]}
```

- A scene is a match if its footprint overlaps the shape. A scene that lies inside a **hole** is not a match. A scene that only
  overlaps the *rectangle around* the shape is not a match.
- A scene whose footprint only **touches** the edge of the shape counts as a match.
- Only scenes the user is allowed to see are returned.
- Results are newest first.
- A shape that crosses the **date line** is given the short way round, for example a ring going `177` then `-178`.
- No matches is **not an error**: `200` with `numberMatched: 0` and an empty `features` list.
- A shape that is not usable (fewer than three distinct points, ring not closed, edges that cross each other, wrong type)
  gets `400` with `{"detail": "<a message that says what is wrong>"}`.

### `GET /export/{search_id}?format=geojson|csv`

Download **all** matches of an earlier polygon search (not just the first page).

- `format=geojson`: one GeoJSON `FeatureCollection`, `[lon, lat]` order.
- `format=csv`: columns `id,name,datetime,access,min_lon,min_lat,max_lon,max_lat`, one row per scene, `datetime` ending in `Z`.
  Names that contain commas or quotes must still open correctly in a spreadsheet.
- Results can be very large (tens of thousands of scenes). The server must **stream** the file; it must not build the whole
  file in memory first.
- An export belongs to the user who ran the search; anyone else gets `404`. An unknown `search_id` gets `404`; an
  unknown `format` gets `400`.
