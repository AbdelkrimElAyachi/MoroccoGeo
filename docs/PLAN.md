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
| 3 | Province boundaries (geoBoundaries) | 75 features; complete map; second run doesn't re-download | ⏳ |
| 4 | HCP census + `DimGeography` | 75/75 matched; SUM(Pop2024) = 36,828,330; 12 regions | ⏳ |
| 5 | `DimDate` 1940-2030 | no gaps/duplicates; 2024-03-15 -> season 2023-24; Ramadan 2024 flagged | ⏳ |

## Phase 2: Bringing in the data

| Step | What | Checks | Status |
|---|---|---|---|
| 6 | FAOSTAT crops | wheat 2024 = 2,441,670 t; 2021 = 7,543,848 t; years 1961-2024; no duplicates | ⏳ |
| 7 | Open-Meteo weather | 8,760 rows per province-year (8,784 leap); realistic values; no duplicates on re-run | ⏳ |
| 8 | CHIRPS rainfall | 550 monthly files (1981-01 to 2026-10); 41,250 rows; wet north / dry south; July ~ 0 | ⏳ |
| 9 | Normals + SPI | SPI mean ~ 0, std ~ 1 over 1991-2020; 1995, 2022, 2024 dry; 2009-10 wet | ⏳ |
| 10 | MODIS NDVI | values -0.2..1; spring peak; spring 2021 greener than 2024 | ⏳ |
| 11 | Dam water surface + official rates | Al Massira shrinks 2018-2024; no jump 2021->2022; correlation with official rates | ⏳ |

Safety point: after Step 9 the project is already complete and presentable.

## Phase 3: Clean warehouse

| Step | What | Checks | Status |
|---|---|---|---|
| 12 | Star schema, keys, incremental loads | 0 orphan rows; re-run gives same counts; new month loads only that month | ⏳ |

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
