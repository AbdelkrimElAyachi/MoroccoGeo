# Project journal

A dated record of what was done, the decisions taken, and why.
Newest entries at the bottom.

---

## 2026-11-15 to 2026-11-17: Choosing and validating the project

**Decision: subject.** Morocco Drought & Water Security Observatory.
Rejected ideas: tram analytics (no open ridership data), tourism / retail
(would need generated data). The project must use real, open, large data.

**Data sources verified** (live downloads and API tests): CHIRPS v3, Open-Meteo,
FAOSTAT, MODIS NDVI, JRC Global Surface Water, geoBoundaries, HCP census 2024.
Details and limits in [DATA_SOURCES.md](DATA_SOURCES.md).

**Key findings:**
- CHIRPS daily values are split from 5-day totals; the readme recommends pentad/monthly
  data for analysis. Decision: use monthly CHIRPS for SPI.
- JRC water history stops in 2021. Decision: Sentinel-2 for 2022 onwards.
- Official daily dam fill rates are published but not downloadable.
  Decision: satellite water surface as main indicator; official rates collected
  by hand for validation.
- FAOSTAT is national only. Regional crop data must come from HCP yearbooks.

**Plan:** 6 phases, 18 steps, each with tests (see [PLAN.md](PLAN.md)).

---

## 2026-11-18: Phase 0, environment setup

**PC:** Windows 11 Pro, AMD Ryzen 5 7530U (6 cores), 14.8 GB RAM,
C: SSD (software), D: SSD (project data).

**Decision: keep SQL Server 2025** (already installed, Standard Developer edition)
instead of reinstalling 2022.
- SQL Server 2025 no longer includes SSRS. Reporting will use
  **Power BI Report Server** (free Developer edition), which runs the same paginated reports.
- Cumulative Update **skipped** for now (still RTM 17.0.1000.7). Install it later if problems appear.

**Decision: keep Visual Studio 2026.** The SSIS, SSAS and Reporting Services
"2022+" extensions officially support VS 2026.

**Installed / configured:**
| Component | Version / setting |
|---|---|
| SQL Server 2025 engine + Agent | 17.0.1000.7, Standard Developer |
| Integration Services (SSIS) | added via SQL Server setup (setup result: Passed) |
| Analysis Services (SSAS) | Tabular mode, admin = DESKTOP-4D3VER8\USER, collation French_CI_AS |
| SSMS | 22.12, with Business Intelligence workload |
| Visual Studio Community 2026 | 18.12, workloads: .NET desktop, Data storage and processing |
| VS extensions | SSIS Projects 17.0.1016, Analysis Services Projects, Reporting Services Projects |
| SSISDB catalog | created, CLR enabled |
| SQL Server max memory | 4096 MB |
| Python | 3.15.2 (Python Install Manager) |
| Project venv | `D:\DroughtProject\venv`: rasterio 1.5.2, geopandas 1.2.0, rasterstats 0.21.0, pandas 3.1.1, scipy 1.18.1 |
| Already present | Power BI Desktop, Git 2.56, VS Code, ODBC 17/18, OLE DB 18/19, .NET 4.8.1 |

**Problems met and fixes:**
- SQL Server setup asked for installation media: found at `C:\SQL2025\StdDev_ENU` (keep this folder).
- SSIS extension needed a restart; the Analysis Services extension installer was blocked
  while Visual Studio was open. Fix: close VS, restart, install extensions one at a time.
- SSMS "certificate chain not trusted" error: tick "Trust server certificate" (local server).

**Decision: trimmed Python packages.** SSIS does downloads and reads CSV/Excel, so Python
is used only for satellite images (rasterio, geopandas, rasterstats), SPI (scipy) and CSV
output (pandas). `earthengine-api` (Step 11) and `scikit-learn` (Step 15) will be added later.

**Decision: keep every script and decision in the project folder** (`sql/`, `scripts/`, `docs/`).

**Git version control set up** (branch `main`). `venv/`, `raw/` and `clean/` are excluded
(see `.gitignore`) because they are large and can be rebuilt. Each finished piece of work
gets its own commit.

**Step 2 SQL done:** `Staging_DB` and `DWH_DB` created (SIMPLE recovery), `etl.RunLog`
and the procedures `etl.usp_StartRun` / `etl.usp_EndRun` created. SQL test passed
(one Success row, one Failed row).

**Decision: SQL Server engine and Agent stay on Manual startup** (saves RAM when not
working on the project). Start them in `services.msc` before working. Note: the monthly
automatic run (Step 17) needs Agent running at the scheduled time.

**SSIS test package** `ssis/packages/00_Test_Logging.dtsx`:
`SQL Start Run` (calls `usp_StartRun`, stores `User::RunID`) -> `SQL Do Work` (does nothing,
or raises an error when `User::ForceFailure` = True) -> `SQL End Run Success`.
An `OnError` event handler calls `usp_EndRun` with `Failed` and the error text.
Connection: OLE DB, provider MSOLEDBSQL, `localhost`, `DWH_DB`, Windows login.

Tested with DTExec (`ssis/tests/run_00_test_logging.ps1`):
- Success path: exit code 0, RunLog row `Success`
- Forced failure: exit code 1, RunLog row `Failed` with the error text

**Phase 0 complete.**

---

## 2026-11-18: Phase 1 start, Visual Studio SSIS project

Created the SSIS project `ssis/DroughtETL` (solution `DroughtETL.slnx`) in Visual Studio 2026:
- Deployment model: Project. TargetServerVersion: SQL Server 2025.
- Shared connections: `DWH_DB.conmgr`, `Staging_DB.conmgr`
  (Microsoft OLE DB Driver for SQL Server, `localhost`, Windows login, Trust Server Certificate = True).
- Project parameters: `ProjectRoot` = `D:\DroughtProject`,
  `PythonExe` = `D:\DroughtProject\venv\Scripts\python.exe`.
- `00_Test_Logging.dtsx` added to the project (old copy in `ssis/packages/` removed);
  default `Package.dtsx` deleted.

Problem met: the connection dialog said "Sélectionnez un fournisseur .Net" because the
provider box showed the category "OLE DB natif". Fix: expand it and pick
"Microsoft OLE DB Driver for SQL Server".

Tests: package run with F5 in Visual Studio (green, RunLog = Success) and with DTExec
from the project folder (exit code 0, RunLog = Success).

---

## 2026-11-18: Phase 1, foundations (Steps 3, 4, 5)

**Design choices for packages:**
- SSIS orchestrates and logs; Python does file work (download, Excel reading, checks) through
  an Execute Process Task; SQL Server loads CSVs with `BULK INSERT` in Execute SQL Tasks.
  Reason: Script Tasks (C#) and Data Flows must be compiled/laid out in the Visual Studio
  designer and can't be reliably written as plain files; this pattern can be generated,
  read and tested from the command line.
- Each package has its own connections and the variables `User::ProjectRoot` and
  `User::PythonExe` (same values as the project parameters), so it can be tested with
  `DTExec /F` without building the project. Wiring them to the project parameters is planned
  for deployment (Step 17).
- Every package follows the Phase 0 pattern: Start Run -> work -> End Run Success,
  OnError -> End Run Failed.

**Step 3, boundaries** (`scripts/01_boundaries.py`, package `01_Boundaries`):
downloads geoBoundaries MAR ADM2 (3.2 MB, skipped if already present), checks 75 provinces
and valid geometries, writes `clean/boundaries_provinces.csv` (ID, name, area, a point inside
the province), loaded into `Staging_DB.stg.Boundaries`. Total area 682,811 km².
Finding: geoBoundaries names mix English, French, Arabic and Tifinagh, and one Arabic label is
wrong (Figuig labelled with Nador's Arabic name). Names are therefore taken from HCP.

**Step 4, geography** (`scripts/02_hcp_population.py`, `scripts/03_match_provinces.py`,
package `02_Geography`):
- HCP file downloaded from hcp.ma (file 242341, "Population légale ... RGPH 2024, format EXCEL").
- Problem caught by the checks: Casablanca's 8 "préfectures d'arrondissements" were read as
  provinces (83 instead of 75). Fix: keep only 4-5 digit province codes.
- Name matching: normalised names + similarity score, best one-to-one match. 75/75 matched;
  the 6 lowest scores (0.90-0.96) reviewed by hand and correct. Saved as
  `sql/05_map_province.sql` (`dbo.MapProvince`).
- `dbo.DimGeography`: 75 provinces + country row (key 0), region, population 2024
  (total/urban/rural), rural share, area, inside point. Load procedure fails if a province
  has no reviewed mapping.
- Note: openpyxl added to the venv (reading Excel in SSIS would need an extra driver).

**Step 5, calendar** (`sql/06_dim_date.sql`): `dbo.DimDate`, 33,238 days (1940-2030),
French and Moroccan Arabic month names, agricultural season (Sept-Aug), Hijri date.
Problem: SQL Server's built-in Hijri conversion (Kuwaiti algorithm) put Ramadan 2024 on
10 March. Switched to the Umm al-Qura calendar (11 March). Morocco's official start was
12 March (moon sighting is often 1 day later); fine for monthly analysis.

**Tests:** `sql/tests/phase1_tests.sql`, 20 checks, all PASS (75 provinces, 12 regions,
population 36,828,330, Settat/Ifrane/Al Haouz match the HCP Excel, no gaps in dates,
seasons, Ramadan). Re-running both packages and the DimDate script changes nothing
(no re-download, no duplicates).

**Phase 1 complete.** Packages `01_Boundaries` and `02_Geography` added to the Visual Studio
project; re-tested from the project folder with `ssis/tests/run_phase1.ps1` (all PASS).

---

## 2026-11-18: Decision, data periods and size rules for Phase 2

Goal: keep the data correct but small (school project, laptop with 14.8 GB RAM).

**Periods:**
| Source | Period | Detail |
|---|---|---|
| CHIRPS rainfall | 1991-2026 | monthly |
| Open-Meteo weather | 1991-2026 | daily (Tmax, Tmin, rain, ET0) |
| MODIS NDVI | 2000-2026 | monthly per province (Google Earth Engine) |
| Dams | 2017-2026 | monthly, Sentinel-2 (Google Earth Engine) |
| FAOSTAT crops | 2000-2024 | yearly |

**Why rainfall keeps 30+ years:** the SPI should be calibrated on at least 30 years of monthly
rainfall (WMO SPI user guide), and the official climate "normal" period is 1991-2020 (WMO).
With fewer years the "normal" is unreliable (e.g. 2015-2024 was mostly dry, so drought would
look normal). Monthly rainfall is cheap (~50 MB kept after cropping), so no reason to cut it.
**Why 2000 for the rest:** MODIS starts in 2000; the period covers the big droughts
(2005, 2016, 2019-2024) and wet years (2009-10, 2018, 2026). Dashboards show 2000-2026 by default.

**Size rules:** keep only Morocco (crop right after download); keep only needed variables;
keep the coarsest time detail that answers the question; reduce to the 75 provinces early;
delete big originals after processing but keep a manifest (file, URL, date, size).
Expected: warehouse ~1.1 million rows, ~1-2 GB kept on disk in total.
`DimDate` stays 1940-2030 (33k rows, harmless).
