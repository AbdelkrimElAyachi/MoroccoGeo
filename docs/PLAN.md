# Plan and test status

Rule: finish and test each step before starting the next one.
Status: ✅ done · 🟡 in progress · ⏳ not started

## Phase 0: Environment

| Step | What | Checks | Status |
|---|---|---|---|
| 1 | Install tools | SQL engine, Agent, SSAS (Tabular), SSIS running; SSMS connects; VS has SSIS/Tabular/Report templates; Python imports OK | ✅ (engine + Agent kept on Manual by choice) |
| 2 | Project skeleton | `Staging_DB` + `DWH_DB` exist; `etl.RunLog` + procedures; SSIS test package logs Success; failing package logs Failed | ✅ (SSIS test package `00_Test_Logging` logs Success and Failed) |

## Phase 1: Foundations

| Step | What | Checks | Status |
|---|---|---|---|
| 3 | Province boundaries (geoBoundaries) | 75 features; complete map; second run doesn't re-download | ✅ |
| 4 | HCP census + `DimGeography` | 75/75 matched; SUM(Pop2024) = 36,828,330; 12 regions | ✅ |
| 5 | `DimDate` 1940-2030 | no gaps/duplicates; 2024-03-15 -> season 2023-24; Ramadan 2024 flagged | ✅ |

Phase 1 tests: `sql/tests/phase1_tests.sql` (20 checks). Run all: `ssis/tests/run_phase1.ps1`.

## Phase 2: Bringing in the data

| Step | What | Checks | Status |
|---|---|---|---|
| 6 | FAOSTAT crops 2000-2024 | wheat 2024 = 2,441,670 t; 2021 = 7,543,848 t; 25 years; no duplicates | ✅ |
| 7 | Open-Meteo weather, daily 1991-2026 | same days for all 75 provinces; realistic values; no duplicates on re-run | 🟡 downloading (rate limits, ~3 days) |
| 8 | CHIRPS rainfall, monthly 1991-2026 | 430 monthly files (1991-01 to 2026-10); 75 x 430 = 32,250 rows; wet north / dry south; July ~ 0 | ✅ |
| 9 | Normals (1991-2020) + SPI | SPI mean ~ 0, std ~ 1 over 1991-2020; 1994-95, 2021-22, 2023-24 dry; 2009-10 wet | ✅ |
| 10 | MODIS NDVI, monthly 2000-2026 (Earth Engine) | values -0.2..1; spring peak; spring 2021 greener than 2024 | ✅ |
| 11 | Dam water surface 2017-2026 (Sentinel-2, Earth Engine) + official rates | 26 dams; Al Massira < 30 % in Apr 2024, > 80 % in Apr 2026; same order as official rates | ✅ |

Periods and size rules: see the 2026-11-18 decision in [JOURNAL.md](JOURNAL.md).

Safety point: after Step 9 the project is already complete and presentable.

## Phase 3: Clean warehouse

| Step | What | Checks | Status |
|---|---|---|---|
| 12 | Star schema, keys, incremental loads | 0 orphan rows; re-run gives same counts; new month loads only that month | ✅ |

Phase 3 tests: `sql/tests/phase3_tests.sql` (12 checks), `ssis/tests/run_rerun_check.ps1`,
`sql/tests/phase3_incremental_demo.sql`. Design and dictionary: [WAREHOUSE.md](WAREHOUSE.md).

## Phase 4: Analysis and visualisation

| Step | What | Checks | Status |
|---|---|---|---|
| 13 | SSAS Tabular model + DAX | measures match SQL queries; wheat 2024 = 2,441,670 t; Excel connects | ⏳ |
| 14 | Power BI, 6 pages | each page answers its user's question; 75 provinces on map; filters work | ⏳ |
| 15 | Yield forecast | leave-one-year-out error reported; 2024 predicted as bad year | ⏳ |
| 16 | Monthly PDF bulletin (Power BI Report Server) + alerts | correct figures for 3 months; alert fires in test | ⏳ |

## Phase 5: Automation and delivery

| Step | What | Checks | Status |
|---|---|---|---|
| 17 | Master package + SQL Agent job | rebuild from empty works; broken URL is logged; scheduled run logs | ⏳ |
| 18 | Report, GitHub, presentation | README lets a classmate set up the project; rehearsal on time | ⏳ |
