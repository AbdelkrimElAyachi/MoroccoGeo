# Challenges and how we solved them

Material for the presentation. Each entry: **problem → cause → solution → evidence → what it shows.**
Updated as the project goes on (newest at the end of each section).

---

## Key numbers to show

| | Value |
|---|---|
| Real open data sources used | 6 (CHIRPS, Open-Meteo, FAOSTAT, HCP, geoBoundaries, MODIS / Sentinel-2 planned) |
| Provinces matched across sources | 75 / 75 |
| CHIRPS file size, Africa vs Morocco crop | 4.9 MB → 0.24 MB per month (-95 %) |
| CHIRPS months processed | 430 (Jan 1991 → Oct 2026) |
| Open-Meteo cost per province (36 years daily) | 374 units; free limit 10,000/day → ~3 days for 75 provinces |
| Disk kept for the whole project (plan) | ~1-2 GB instead of 80-120 GB |
| Automatic tests | Phase 1: 20 · Phase 2: 29 (+ weather) · Phase 3: 12 + re-run check + incremental demo |
| Re-running every package | second run: 0 rows inserted, 0 updated (all 12 tables identical) |
| CHIRPS full download | 430 months, ~37 min, 83 MB kept (instead of 2.1 GB) |
| SPI values computed | 127,578 (75 provinces × 4 time scales × ~430 months) |
| Worst drought season | 2021-22: 61 of 75 provinces in drought (SPI-12 ≤ -1), 33 M people |
| Consecutive drought seasons | 6 (2019-20 to 2024-25) |
| Reservoirs monitored from space | 26, monthly 2000-2026 (JRC Landsat 2000-2016 + Sentinel-2 2017+) |
| JRC vs Sentinel-2 on 2017-2021 | correlation 0.997, totals within 1.3 % |
| Daily weather | 982,425 rows (75 provinces × 13,099 days), downloaded over 3 days within free limits |
| Rain: CHIRPS vs Open-Meteo (ERA5) | national monthly correlation 0.92 |
| National average daily max temperature | 23.2 °C (1991) → 26.2 °C (2023) |
| Al Massira (2nd largest dam), water surface | 90.9 km² full (June 2010) → 10.9 km² (April 2024, 12 %) → 68.7 km² (April 2026, 75 %) |
| Total water surface of the 26 lakes (yearly avg) | 424 km² (2018) → 275 km² (2024) → 493 km² (2026) |
| Vegetation computation in Earth Engine | 19 h → 2 h (one request per year instead of per month) |
| March farmland greenness (NDVI) vs wheat yield, 2001-2024 | correlation 0.86 |
| March 2026 farmland greenness | 0.652, highest since 2000 (after 6 drought seasons) |

---

## 1. Finding real, open, large data

### 1.1 The first idea had no data
- **Problem:** first project idea (tram ridership, Casablanca) had no open data; only yearly totals.
- **Solution:** changed subject to drought and water security, where real satellite and official data exist.
- **Shows:** checking data availability *before* designing a project.

### 1.2 Official dam levels exist but cannot be downloaded
- **Problem:** the Ministry publishes daily dam fill rates (Maa Dialna, daily bulletin), but no CSV, API or history file.
- **Solution:** measure reservoir water surface from satellite (Sentinel-2, 2017-2026) and use the official rates
  collected by hand from bulletins/press as validation.
- **Evidence:** values quoted by the ministry: ~23 % (Feb 2024), 45.2 % (8 Jan 2026), ~76 % (May 2026).
- **Shows:** finding an alternative source and validating it against the official one.

### 1.3 Some sources are less complete than they look
| Source | Limit found | What we did |
|---|---|---|
| CHIRPS daily | Daily values are split from 5-day totals (official readme) | Use monthly data |
| JRC water history | Stops in 2021 | Use Sentinel-2 for 2017-2026 |
| FAOSTAT | National totals only, no regions | National crop analysis; regional data would need HCP yearbooks |
| geoBoundaries | 2017 outlines from OpenStreetMap | Checked against the official HCP list (75/75) |

---

## 2. Downloading the data

### 2.1 Satellite files are huge
- **Problem:** CHIRPS files cover all of Africa (4.9 MB per month) or the world (13.4 MB per day:
  ~220 GB for daily data since 1981). MODIS images for Morocco would be 50-100 GB.
- **Solution:** download → cut out Morocco immediately → compute the 75 province values → delete the original.
  A manifest file records every download (file, URL, date, size) so the data stays traceable.
  MODIS and Sentinel-2 will be processed in Google Earth Engine (cloud), which returns a small table.
- **Evidence:** 4.9 MB → 0.24 MB per month (-95 %); whole project ~1-2 GB instead of 80-120 GB.
- **Shows:** designing for limited resources (school laptop: 14.8 GB RAM).

### 2.2 How many years? Size vs scientific validity
- **Problem:** keeping every year from 1940/1981 for every source was too much for a school project.
- **Constraint:** the drought index (SPI) needs at least 30 years of monthly rainfall (WMO SPI guide);
  the official climate "normal" period is 1991-2020 (WMO). With only ~10 years (mostly dry in Morocco),
  drought would look "normal".
- **Solution:** two windows: rainfall 1991-2026 (cheap, monthly), everything else 2000-2026 (MODIS starts in 2000).
- **Shows:** cutting volume without breaking the method.

### 2.3 API rate limits (Open-Meteo)
- **Problem:** the free weather API allows 600 units/minute, 5,000/hour, 10,000/day. One province
  (36 years of daily data, 4 variables) costs 374 units, so 75 provinces need ~28,000 units.
- **Solution:** a **resumable** download: each province is saved as soon as it arrives, already-downloaded
  provinces are skipped, the script waits when the hourly limit is reached and stops cleanly at the daily
  limit. Running it on 3 days completes the download.
- **Evidence:** API response headers `X-RateLimit-Cost: 374`, `X-RateLimit-Limit: 600`.
- **Shows:** respecting a provider's terms instead of hammering the server; robust, restartable jobs.
- **Then:** on the second day the script crashed after one request **timed out** (server slow to answer):
  it handled "limit reached" answers but not "no answer at all". Fixed: network errors are retried up to
  6 times with growing pauses (1, 2, 4 ... 32 min). Same lesson as CHIRPS (2.4).
- **And then:** the PC lost its internet connection ("getaddrinfo failed") and would have given up after
  6 tries. Final design (`--until-done`): never stop because of the network (pauses up to 30 min), wait for the
  next quota day at the daily limit, resume after laptop sleep. One command finishes the job over several days.
- **Choice:** asking a friend to download the rest on another connection would have bypassed the free
  limit, against the spirit of Open-Meteo's terms; we chose to wait one more day instead.
- **Last trap:** downloading over 3 days meant provinces ended on different days (13,099 to 13,101 days,
  because "up to 7 days ago" moves every day). The final check refused the file; fix: cut every province to
  the last common day, so every day has all 75 provinces. Result: 982,425 rows, loaded in 17 seconds.

### 2.3b An independent check of the rainfall
- **Question:** is the satellite rainfall (CHIRPS) right? We had no rain gauges of our own.
- **Answer:** compare it with a completely different source, the ERA5 weather model behind Open-Meteo:
  monthly correlation **0.92** nationally (0.83 province by province), ERA5 14 % lower in total.
- **Shows:** two independent methods telling the same story, so the drought index can be trusted.

### 2.4 A download that froze for 20 minutes
- **Problem:** first test: 2.6 s per CHIRPS month. During the full run the download froze on April 1993:
  0 bytes received for 20+ minutes, after only 28 of 430 months.
- **Cause:** the first version used Python's `urlretrieve`, which has **no timeout**: when the university
  server stopped answering, the script waited forever without any error.
- **Solution:** stopped the frozen process; downloads now give up after 60 s without data and retry up to 5 times
  with increasing pauses. The script skips months already on disk, so it resumed at month 29 with nothing lost.
- **Shows:** network calls always need a timeout; long jobs must be restartable. Found by monitoring progress
  (file count on disk not moving), not by an error message.

### 2.4b The rainfall server also limits requests
- **Problem:** after the timeout fix, the CHIRPS server (UC Santa Barbara) answered
  "HTTP 429 Too Many Requests" about 10 times during the 430 downloads.
- **Solution:** the same retry logic waits 10, 20, 30... seconds and tries again; every month was
  downloaded in the end. Full run: ~37 minutes.
- **Shows:** public data servers protect themselves; polite, patient clients still get all the data.

### 2.4c Computing satellite data in the cloud: from 19 hours to 2 hours
- **Problem:** vegetation (NDVI) per province in Google Earth Engine: the first version took **215 s per month**,
  i.e. ~19 hours for 321 months. The slow part was converting the 10 m farmland map to the 250 m MODIS grid,
  repeated for every month.
- **Solution:** stack the 12 months of a year into one image and send **one request per year**, so the
  conversion runs once per year: **~230 s per year, ~2 hours** in total.
- **Shows:** measuring before optimising; understanding where cloud computing time goes.
- **Then:** one year (2008) took **87 minutes** instead of 4, with no error: the laptop had gone to sleep
  and the request waited. Fixed by keeping the PC awake during long jobs. Real total: ~3 hours.
  **Lesson:** long jobs on a laptop need the machine kept awake, or should run on a server.

### 2.4d The dam databases were not available
- **Problem:** the usual reservoir databases (GRanD, Global Dam Watch) are not in our Earth Engine catalog.
- **Solution:** reservoir outlines and names from **OpenStreetMap** (open data) via the Overpass API.
- **New problem:** the first query found only 11 small reservoirs; all the big dams (Al Wahda, Al Massira,
  Idriss I...) were missing. **Cause:** the query asked for `out geom tags`, which leaves out the parts of
  multi-part shapes, and the big lakes are exactly those. With `out geom`: **26 reservoirs**.
- **Also:** the main OpenStreetMap server answered "502 Bad Gateway" (overloaded); the script now falls back
  to two other public servers automatically.
- **Shows:** a missing result is a clue: "why are the biggest lakes absent?" led to the bug.

### 2.4e Joining two satellites into one 26-year series
- **Goal:** dam water from 2000 (like the other data), not only from 2017 (Sentinel-2).
- **Problem 1, gaps:** the older source (JRC, Landsat) is patchy over Morocco before 2013 (Landsat 7 sensor
  fault since 2003, few Landsat 5 images over Africa): in 2005-2006 only 1 month in 12 shows the big lakes clearly.
  **Solution:** keep each month with its "% of the lake visible", flag < 80 % as unreliable, and let every
  measure use each dam's latest reliable month, so a gap never looks like an empty lake.
- **Problem 2, consistency:** two satellites could measure the same lake differently.
  **Solution:** compare them where both exist (2017-2021): 1,269 lake-months, correlation **0.997**,
  JRC 1.3 % lower in total, typical difference 0.22 km². Joined with a `Source` column, tested automatically.
- **Side effect:** the "largest surface ever seen" moved to 2010 for Al Massira (90.9 km², lake full), so
  percentages are now measured against a truer full state (April 2026: 75.5 % instead of 91 %).
- **Shows:** extending history honestly: measure the gaps, prove the sources agree, flag what is uncertain.

### 2.5 Hidden "no data" values
- **Problem:** CHIRPS ocean pixels contain -9999 but the file does not declare it as "no data".
  Averaging them would give hugely negative rainfall for coastal provinces.
- **Solution:** tell the averaging step explicitly that -9999 means "no data"; tests check no negative rainfall.
- **Shows:** inspecting raw data before trusting it.

---

## 3. Joining sources together

### 3.1 The same province, spelled differently
- **Problem:** HCP and the map file write names differently, in several languages:
  "Province d'El Kelâa Des-Sraghna" vs "Province d'El Kelâat Es-Sraghna إقليم قلعة السراغنة",
  "Préfecture de Tanger-Assilah" vs "Prefecture of Tangier - Assilah", "Rehamna" vs "Rhamna".
- **Solution:** normalise names (remove "Province de", Arabic/Tifinagh, accents, punctuation), compute a similarity
  score, keep the best one-to-one matches, review the lowest scores by hand, store the result in a mapping table.
- **Evidence:** 75/75 matched; lowest score 0.90 (Mohammadia / Mohammédia); 6 pairs reviewed by hand.
- **Shows:** the classic data-integration problem (what SSIS Fuzzy Lookup does), solved and documented.

### 3.2 A wrong label in the open map data
- **Problem:** in geoBoundaries, Figuig province has the Arabic name of Nador (إقليم الناظور).
- **Solution:** official names come from HCP; the map file is only used for outlines.
- **Shows:** choosing the authoritative source for each attribute.

### 3.3 Arabic text "moving" columns in a CSV
- **Problem:** when reviewing the match file, the score column seemed to contain Arabic names.
- **Cause:** Arabic is displayed right-to-left; editors visually reorder neighbouring numbers. The data was correct.
- **Solution:** Latin-only name column for review, original multilingual name moved to the last column.
- **Shows:** multilingual data needs care even in simple files.

---

## 4. Data quality caught by automatic tests

### 4.1 83 provinces instead of 75
- **Problem:** the HCP Excel also lists Casablanca's 8 "préfectures d'arrondissements"; they were read as provinces.
- **Caught by:** the check "75 provinces, total population = 36,828,330" failed (found 83 and 40 million).
- **Solution:** keep only province-level codes (4-5 digits).
- **Shows:** tests with known official values catch errors humans miss.

### 4.2 Ramadan on the wrong day
- **Problem:** SQL Server's built-in Hijri conversion put Ramadan 2024 on 10 March; Morocco started on 12 March.
- **Caught by:** the calendar test.
- **Solution:** switched to the Umm al-Qura calendar (11 March); documented the remaining 1-day difference
  (Morocco follows local moon sighting), which is fine for monthly analysis.
- **Shows:** checking even "standard" functions against reality.

---

### 4.3 The drought index is undefined in the desert in summer
- **Problem:** in Saharan provinces, most summer months have no rain at all in 1991-2020.
  A statistical fit on almost only zeros gives meaningless SPI values.
- **Solution:** WMO method for zero rain (share of dry months q), and no SPI when fewer than 10 of the
  30 reference years had rain for that month: 72 of 32,250 SPI-1 values left out, documented.
- **Check:** SPI-12 over 1991-2020 has mean -0.000 and standard deviation 1.001, as the definition requires.
- **Shows:** knowing when a method stops being valid, instead of publishing a number anyway.

### 4.5 Proving that reloading is safe
- **Problem:** the loads re-wrote every existing row (e.g. all 127,578 SPI values) even when nothing had changed,
  so you couldn't tell what a run really did, and a monthly automatic run had to be trusted blindly.
- **Solution:** loads update a row only when a value changed, and every load writes a "receipt"
  (rows inserted / updated / unchanged) in `etl.LoadAudit`.
- **Evidence:** all packages run twice → identical row counts in all 12 tables, second-run receipts
  **0 inserted, 0 updated**. Simulated new month (October 2026 removed, then reloaded) →
  **75 inserted, 0 updated, 32,175 unchanged**.
- **Shows:** reliability you can prove with numbers, required before automating monthly runs.

### 4.7 "--" on a card: blank is not the same as zero
- **Problem:** in the report, *People in Drought* showed "--" for 2008. It looked like missing data.
- **Cause:** in December 2008 no province was in drought (0 of 75, average SPI-12 +0.56). Counting an empty
  list returns *blank* in DAX, and Power BI draws blank as "--".
- **Solution:** the measures return **0** when SPI data exists but no province is in drought, and stay blank
  only when there is no data at all (e.g. 1990, before the first SPI-12 value).
- **Also noticed while testing:** with both slicers on "Tout", *Rain % of Normal* shows 97.6 %, not 100 %.
  Correct: the normal is 1991-2020 (exactly 100.0 % over those years), and adding the dry years 2021-2026
  pulls the long-term ratio down. 2019-2025 alone: 74.9 % of normal.
- **Shows:** checking what a dashboard *means* to a reader, not only whether the number is right.

### 4.4 Satellite water surface is not the same as official dam volume
- **Observation:** the satellite fill indicator (water surface / largest surface seen) is higher than the
  official fill rate (volume / capacity): Feb 2024 satellite 45.5 % vs official ~23 %; Jan 2026 72.2 % vs 45.2 %;
  May 2026 94.1 % vs ~76 %.
- **Cause:** reservoirs are shaped like bowls: when the level drops, the volume falls much faster than the
  surface. Also, our 26 largest lakes are not the same set as the official total (~150 dams).
- **What we did:** kept the satellite measure as an indicator of *change*, and checked that it moves **in the
  same order** as the official figures (test: Feb 2024 < Jan 2026 < May 2026 → PASS).
- **Shows:** validating a proxy honestly and explaining why it differs.

### 4.6 Same question, same answer: model vs warehouse
- **Risk:** a measure written in DAX can silently compute something different from what SQL says
  (wrong filter, wrong average), and the dashboard would show wrong numbers with confidence.
- **Solution:** a reconciliation test asks 13 questions both in DAX (model) and in SQL (warehouse).
- **Evidence:** all 13 identical, e.g. 61 provinces and 33,089,522 people in drought in August 2022;
  Settat 57.9 % of its normal rain in 2024; Al Massira 14.6 % full (surface) in April 2024.
- **Shows:** dashboards you can trust because every key number is checked against its source.

### 4.8 The Power BI project would not open after a PC restart
- **Problem:** Power BI: *"Cannot read DroughtObservatory.pbip. Error reading JObject… position 190"*.
- **Cause:** 6 small files saved at the same second (21:46:39) were filled with zeros, most likely by the
  abrupt shutdown while Power BI was writing them: the `.pbip` shortcut, `definition.pbir` (the live connection
  to SSAS) and 4 files of the semantic-model reference. The report itself (page 1, 7 visuals) was intact.
- **Fix, first attempts:** scanned every file for "all zeros", backed up the folder, rebuilt the `.pbip`
  shortcut, then guessed the connection file format twice from documentation (version 4.0 `byConnection`,
  then version 1.0 `analysisServicesDatabase`): both refused by Power BI 2.159.
- **Fix that worked:** let Power BI write the format itself. A blank report, live-connected to `DroughtModel`
  and saved as a test project, showed that this version stores a live connection in two parts: the report's
  `definition.pbir` points to a model folder (`byPath`), whose `modelReference.json` holds the connection
  (`analysisServicesDatabaseLive`, `localhost` / `DroughtModel`). The model folder was rebuilt from it, keeping
  the original diagram layout. All 23 project files validated (valid JSON, no zeros).
- **Lesson 2:** when a file format is undocumented or version-specific, generate a reference from the tool
  instead of guessing.
- **Lesson:** the `powerbi/` folder had never been committed, so Git could not restore it. Commit dashboard
  work like code, as soon as a page works.

### 4.9 Making the dashboards public: two small bugs caught before publishing
- **Problem:** Power BI reports live on this PC (live connection to the local SSAS model), so the jury,
  the teacher or the public cannot open them without our server.
- **Solution:** a static website (`web/`) published free by GitHub Pages. A script exports the warehouse
  into small JSON/CSV files (4.6 MB); the page draws the map and charts in the browser.
- **Bug 1, caught by the check script:** `check_web_export.py` compares 9 numbers with SQL. Settat rain 2024:
  SQL 243.2 mm, website 243.1 mm. **Cause:** monthly rain was rounded to 1 decimal *before* adding 12 months,
  so rounding errors added up. **Fix:** keep 2 decimals like the warehouse → 243.2 = 243.2, 9/9 PASS.
- **Bug 2, seen in the browser preview:** the map was one big blue rectangle. **Cause:** the map simplification
  left 72 tiny 3-point slivers (out of 1,314 coastal pieces of Oued Ed-Dahab) drawn in the wrong direction;
  the map library then reads such a piece as "the whole globe except this piece" and paints everything.
  **Fix:** the page reverses only the pieces whose area is larger than half the globe. All 75 provinces show.
- **Evidence:** August 2022 on the website: 81.3 % of provinces (61/75) and 33.1 M people in drought, the
  same as the SQL query.
- **Lesson:** a new output (website) gets the same treatment as the model: an automatic comparison with SQL,
  plus looking at it before publishing.

## 5. Tools and environment

| Problem | Cause | Solution |
|---|---|---|
| SQL Server 2025 has no SSRS | Microsoft retired SSRS after 2022 | Power BI Report Server (same paginated reports) |
| Adding SSIS/SSAS to SQL Server asked for installation media | Original setup files needed | Found at `C:\SQL2025\StdDev_ENU` |
| Visual Studio extension install stuck | Needed a restart; blocked while VS was open | Close VS, restart, install one at a time |
| SSMS "certificate not trusted" | Local server uses a self-signed certificate | "Trust server certificate" |
| SSIS connection error "select a .Net provider" | "OLE DB natif" is a category, not a driver | Pick "Microsoft OLE DB Driver for SQL Server" |
| SSIS task name rejected | Names can't contain `.` | Generator removes `.py` from task names |
| Script Tasks / Data Flows can't be written as files | They must be compiled/laid out in the designer | Standard pattern: SSIS orchestrates + Python + `BULK INSERT`, generated by a script |
| Laptop RAM (14.8 GB) shared by SQL Server, SSAS, VS, Power BI | SQL Server takes all RAM by default | SQL Server max memory 4 GB; daily (not hourly) weather |
| SSAS can't read the warehouse | It reads data with its own Windows service account | Read-only login for `NT Service\MSSQLServerOLAPService` (`db_datareader` on DWH_DB) |
| Building the Tabular model click by click is slow and not reproducible | Designer-only workflow | Model written as code (`build_model.py` → `Model.bim`), deployed by script |
| Tutorials say "enable Shape map in Preview features", but the option is not in the list | Power BI 2.159 (Nov 2026) changed the preview list | Look for the visual directly in the Visualisations pane; fallbacks Azure Maps or an AppSource custom visual |
| Tutorials say themes are under *Affichage*; not there | Power BI 2.159 moved them | **Conception → Thèmes → ▼ → Rechercher des thèmes** |
| Power BI maps don't know Moroccan provinces by name | Built-in maps geocode names online | Custom province map (TopoJSON) generated from our own boundaries with the model's exact names |
