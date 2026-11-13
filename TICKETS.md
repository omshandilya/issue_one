# Orbit Portal: the customer's tickets

> These are the tickets the customer has sent you. They are written the way real customers write: what they saw, what they tried, sometimes with a wrong guess about the cause. **None of them say where the bug is.**
> **Customer:** Coastal Disaster Response Agency (CDRA). **Main contact:** Priya Nair, GIS Lead.
> "Customer priority" is the customer's own opinion and isn't always right. Deciding what to do first is part of the job.

## Rules that apply to every ticket

- **Keep these interfaces unchanged** so our automated tests can run against your code. You can add to them, but don't rename or remove:
  - the three server apps: `orbit.catalog.app:app`, `orbit.tiles.app:app` and `orbit.gateway.app:app`;
  - the HTTP routes and their parameters;
  - the `TileCache` class and its `get(key)` / `put(key, value)` methods (`tiles/cache.py`);
  - the command `python -m orbit.worker.ingest <source_file> <scene_id>` (`worker/ingest.py`);
  - the test accounts in `seed/users.md`.
- Add tests to `tests/` that **fail before your fix and pass after**. (T1 happens only in the browser and the web app has no test runner, so for T1 a written step-by-step reproduction in your note, with a screenshot if you can, is enough.)
- One short note per ticket in `notes/` (for example `notes/T3.md`): what you saw, how you reproduced it, the root cause, the fix, and how you know it works.
- **Found something that is not in a ticket?** If you notice any other bug or problem anywhere in the code, write it down in `notes/other.md` (what it is, where, how you saw it, and how you would fix it, or the fix if you made one). Valid additional findings are credited.

## The tickets at a glance

| # | Title | Type | Customer priority |
|---|---|---|---|
| T1 | Search result outlines are drawn in the wrong place | Bug | High |
| T2 | Searching near Fiji returns no results | Bug | Medium |
| T3 | An analyst saw scenes from another unit | Bug | Low *(customer's view)* |
| T4 | Resumed downloads of large scene files are corrupted | Bug | High |
| T5 | The image server crashes every afternoon | Bug | High |
| T6 | After a power cut, some scenes are broken or duplicated | Bug | High |
| T7 | One-click start, no installation | Request | High |
| F1 | Search by drawing any shape, and export the results | Feature | Medium |

---

## T1: Search result outlines are drawn in the wrong place

**Reported by:** Rahul (analyst, Mumbai office) · **Customer priority:** High · **Seen:** every time

> When I search around Mumbai port, the list on the left shows the right scenes (names and dates are correct), but the **outlines on the map** appear in a completely different part of the world. Zoomed out, they're far up in the **Arctic Ocean, north of Norway**.
>
> If I click a result, the **detail panel** opens, and its small map shows the outline correctly over Mumbai. So the scene data must be fine?
>
> **Steps**
> 1. Open the portal and zoom to Mumbai.
> 2. Draw a search box over the port (about 72.7–73.0° E, 18.8–19.1° N).
> 3. Press Search.
>
> **Expected:** outlines over Mumbai port.
> **Actual:** outlines in the Arctic Ocean. Clicking one shows it correctly in the detail panel.
---

## T2: Searching near Fiji returns no results

**Reported by:** Tom (partner liaison, Pacific programme) · **Customer priority:** Medium · **Seen:** every time

> We support our Pacific partners in Fiji. When I draw a search box that covers **both** sides of Fiji, I get **"No scenes found"**.
>
> - A smaller box on only the west side returns results.
> - A smaller box on only the east side also returns results.
> - A box covering both sides returns nothing.
>
> I know there are images there. The satellite operator confirmed **12 scenes** for last week.
>
> **Steps:** draw a box from about 177° E to 178° W (it crosses the edge of the map where the world wraps around), latitude 20° S to 15° S.
>
> **Expected:** about 12 scenes.
> **Actual:** "No scenes found".
>
> The same happens in the search API directly, so it isn't only the web page: `GET /search?bbox=177,-20,-178,-15`.

---

## T3: An analyst saw scenes from another unit

**Reported by:** Vikram (analyst, Western Command liaison) · **Customer priority:** Low · **Seen:** twice in the last month

> Small thing, probably a display glitch. Twice I have seen scenes in my results labelled **"RESTRICTED – Coast Guard Unit A"**. My account is in Unit B and I shouldn't be able to see those. When I refreshed a minute later, they were gone.
>
> The first time, my colleague in Unit A was searching the same area at the same time (we were both working on the same incident). Not sure if that's related.
>
> **Steps:** I don't know how to repeat it. It happened while searching the Gulf of Kutch, both times within a few minutes of Unit A searching there.
>
> **Expected:** never see another unit's restricted scenes.
> **Actual:** saw them briefly; gone after refresh.
>
> Not urgent, just wanted to report it.

*Participant note: test accounts `analyst_a` (Unit A) and `analyst_b` (Unit B) are in `seed/users.md`.*

---

## T4: Resumed downloads of large scene files are corrupted

**Reported by:** Meera (field imagery team, Kochi) · **Customer priority:** High · **Seen:** every time on large files

> Our field teams download full scene files (500 MB to 1.5 GB) over weak mobile connections, which often drop. Our download tool **resumes** from where it stopped by asking the portal for the rest of the file in pieces.
>
> Since we started downloading the new **large scenes**, the finished files are **corrupted**: the checksum doesn't match the one the portal publishes, and some of the files will not open in our GIS software ("unexpected end of data" / "invalid TIFF").
>
> Things we noticed:
> - Small scenes (under 50 MB), which download in one go, are fine.
> - The broken files are always **a little smaller** than the original.
> - Re-downloading gives the **same broken file**, so it isn't a network glitch.
> - Downloading straight from the file server (bypassing the gateway) works fine.
>
> **Steps**
> 1. Download `GET /scenes/S1_kochi_20251012_large/file` in several pieces using the `Range` header (our tool uses 4 MB pieces).
> 2. Join the pieces and compare the checksum with `GET /scenes/S1_kochi_20251012_large/checksum`.
>
> **Expected:** identical file.
> **Actual:** checksum mismatch, file slightly short.

---

## T5: The image server crashes every afternoon

**Reported by:** CDRA IT support · **Customer priority:** High · **Seen:** daily, usually between 3 and 5 pm

> The image (tile) part of the portal stops every afternoon. There's no error in our log; it just disappears and we start it again.
>
> On the Linux server, the system log shows:
> ```
> kernel: Out of memory: Killed process 48211 (python) total-vm:9.1GB, anon-rss:7.6GB
> ```
> Memory use starts at about 300 MB in the morning and **only goes up** during the day. It never goes down, even when nobody is using the portal at lunchtime.
>
> The server has 8 GB of memory. We were told to just add more. Is that the solution?
>
> **Steps:** use the portal normally all day, especially zooming across many different scenes. (To save you a day: `GET http://127.0.0.1:8002/debug/stats` shows the tile service's memory use and cache size, so you can browse or script many different scenes and watch it grow.)
>
> **Expected:** memory stays roughly flat once the server has warmed up.
> **Actual:** memory grows until the system kills the process.
>
> We also noticed that the same few popular scenes seem to be slow in the afternoon, even though they've been viewed many times that day, so the cache doesn't seem to be helping much.

*Participant note: the cache is configured in megabytes with the environment variable `ORBIT_TILE_CACHE_MB` (default 256). Hidden tests use it, so please honour it.*

---

## T6: After a power cut, some scenes are broken or duplicated

**Reported by:** CDRA IT support · **Customer priority:** High · **Seen:** after every unplanned shutdown

> Our office had a power cut while new scenes were being imported. After restarting:
> 1. Two scenes **appear in search results**, but when you open them the images don't load ("404 tile not found").
> 2. When we re-ran the import to fix it, one scene now appears **twice** in search results.
> 3. In the scenes folder we found a file much smaller than the others (2 MB instead of 180 MB).
>
> We get power cuts a few times a month in monsoon season, so this keeps happening. Right now we fix it by hand in the database.
>
> We tried running the import again for the broken scenes. That created duplicates instead of fixing them.
>
> **How we import:** `python -m orbit.worker.ingest <source_file> <scene_id>`.
>
> **To reproduce without pulling the plug:** set the environment variable `ORBIT_FAULT_KILL_AFTER_BYTES=50000000` and run the import. The import process will be killed hard (like a power cut) after writing about 50 MB. Then start the portal.

*Participant note: the fault switch above is part of the test harness. Keep it working; our hidden tests use it.*

---

## T7: One-click start, no installation

**Reported by:** Priya Nair (GIS Lead) · **Customer priority:** High · **Type:** request

> Right now, getting the portal running needs Python, Node, `pip install`, `npm install`, and starting four programs in four windows. Our field teams use **standard government Windows laptops**:
> - **no admin rights**, so they **can't install anything**;
> - Python and Node are **not** installed;
> - reliable internet is not guaranteed.
>
> We want to hand them **one folder on a USB stick**. They **double-click one thing**, and the portal opens in their browser with everything running. When they close it, everything stops.
>
> **What we need**
> 1. Works on a **clean Windows 10/11 laptop** with nothing extra installed and no admin rights.
> 2. **One double-click** starts everything (API, image server, gateway, worker) and opens the portal in the browser.
> 3. Includes some demo scenes (a small selection is enough) so it works straight away.
> 4. Works when copied to **any folder**, including folders with spaces (e.g. `C:\Users\Priya Nair\Desktop\Orbit Portal`) and a USB stick.
> 5. If another program on the laptop is already using the portal's usual port, it should **still start**.
> 6. Closing it (closing the window, or a "Stop" button) must **stop everything**. Last time we tried a script, programs kept running in the background after closing and blocked the next start.
> 7. A short `README.txt` for field staff: how to start, how to stop, what to do if it doesn't open.
> 8. If there's no internet, the background street map may not load. That's fine, but **searching, scene images and downloads must still work**.
>
> **Our IT team's note:** we build on Windows, but some of your engineers use Macs. It's fine to build the Windows package on any machine you have.
>
> Our laptops show a Windows "unrecognised app" warning for programs we haven't signed. We can tell staff to click through it **once**, so that's acceptable. Anything that needs installing or an administrator password is **not**.

*Participant note: put the build script in `packaging/` and the finished package in `package/Orbit Portal/` (keep it under about 300 MB), and document in your note exactly how it was produced. We will test it on a clean Windows machine.*

---

## F1: Search by drawing any shape, and export the results

**Reported by:** Priya Nair (GIS Lead) · **Customer priority:** Medium · **Type:** feature

> Today we can only search with a **rectangle**. Disaster areas are never rectangles: a flooded river valley or a cyclone path along a coast is long and curved. A rectangle around them returns hundreds of irrelevant scenes.
>
> **What we'd like**
> 1. A tool to **draw any shape** on the map (click points, double-click to finish).
> 2. Search returns only scenes that **actually overlap** the shape, not just the rectangle around it.
> 3. The search service should also accept a shape that has a **hole** in it (for example a lake or a city we've already covered). The web page doesn't have to let us draw holes. The API just has to handle them.
> 4. **Download** the results as:
>    - **GeoJSON**, so we can open them in QGIS;
>    - **CSV**, for our reports, with times that clearly show their time zone (e.g. `2025-03-01T01:03:25Z`).
> 5. Our biggest searches return about **10,000 scenes**. The download must handle that without the server struggling (it shouldn't build the whole file in memory first).
> 6. It must also work for our Pacific partners, whose shapes **cross the edge of the map** near Fiji.
>
> **Example for testing:** draw a shape following the Godavari river delta, roughly from (81.5° E, 17.0° N) to (82.4° E, 16.3° N).

*Participant note: the API contract is in `docs/api.md`. New routes: `POST /search/polygon` (body: a GeoJSON Polygon) and `GET /export/{search_id}?format=geojson|csv`.*
