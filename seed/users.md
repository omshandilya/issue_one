# Test accounts

Send the token as a header: `Authorization: Bearer <token>`.

| User | Unit | Token | Sees |
|---|---|---|---|
| `analyst_a` | A | `tok-analyst-a-7f3c` | public scenes + Unit A restricted scenes |
| `analyst_b` | B | `tok-analyst-b-91d2` | public scenes only |
| `viewer` | none | `tok-viewer-3e55` | public scenes only |
| anonymous | none | (no header) | public scenes only |

A wrong token gets `401`.

Handy test areas:

| Area | Box (`min_lon,min_lat,max_lon,max_lat`) |
|---|---|
| Mumbai port | `72.7,18.8,73.0,19.1` |
| Gulf of Kutch (has Unit A restricted scenes) | `69.0,22.0,70.5,23.5` |
| Odisha coast | `84.5,19.0,87.5,21.8` |
| Fiji (crosses the date line) | `177,-20,-178,-15` |
