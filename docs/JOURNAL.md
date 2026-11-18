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

**Still to do in Phase 0:**
- [ ] SQL Server engine + Agent startup type -> Automatic
- [ ] Run `sql/01_create_databases.sql` and `sql/02_etl_logging.sql`
- [ ] Run `sql/tests/02_test_etl_logging.sql` and check results
- [ ] SSIS test package that writes Success / Failed in `etl.RunLog`
