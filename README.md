# Morocco Drought & Water Security Observatory

An end-to-end MSBI (Microsoft BI) project that tracks rainfall, drought, vegetation,
dam water surface and crop production across Morocco's 75 provinces, using only
real open data (satellite and official statistics), from 1981 to today.

## Live dashboard (public website)

**👉 https://&lt;github-username&gt;.github.io/&lt;repository&gt;/** — anyone can open it, no Power BI needed.

The website shows the same numbers as the Power BI report: a province drought map with year/month
selection, key figures (provinces and people in drought, rain vs normal, dam water), national trends
since 1991 and CSV downloads of all tables. It is a static page (`web/`) whose data files are exported
from the warehouse by `scripts/11_export_web.py`, checked against SQL by
`scripts/tools/check_web_export.py`, and published by GitHub Pages (`.github/workflows/pages.yml`).

To update it after a new monthly load:

```
venv\Scripts\python.exe scripts\11_export_web.py .
venv\Scripts\python.exe scripts\tools\check_web_export.py      (must end with ALL WEB EXPORT CHECKS PASSED)
git add web && git commit -m "Update web data" && git push
```

## Architecture

```
Sources (CHIRPS, Open-Meteo, MODIS, JRC/Sentinel-2, FAOSTAT, HCP, geoBoundaries)
   -> SSIS (download, clean, load)  +  Python (satellite images, SPI)
   -> SQL Server: Staging_DB (raw) -> DWH_DB (star schema)
   -> SSAS Tabular (DAX measures)
   -> Power BI dashboards  +  Power BI Report Server (monthly PDF bulletin)
   -> public web dashboard (GitHub Pages, data exported from the warehouse)
   -> SQL Server Agent (monthly automatic run)
```

## Folder structure

| Folder | Content |
|---|---|
| `docs/` | Project journal, plan with test status, data sources |
| `sql/` | SQL scripts, numbered in the order they must be run |
| `sql/tests/` | Test scripts that check each SQL step |
| `scripts/` | Python scripts (called by SSIS) |
| `ssis/` | Visual Studio SSIS / SSAS / report projects |
| `ssas/` | SSAS Tabular model (`Model.bim`, built by `scripts/tools/build_model.py`) |
| `powerbi/` | Power BI project (live connection to the SSAS model) |
| `web/` | Public web dashboard (HTML/JS + exported data), published by GitHub Pages |
| `raw/` | Downloaded source files (not versioned, can be re-downloaded) |
| `clean/` | CSV files produced for SSIS (not versioned, can be regenerated) |
| `venv/` | Python environment (not versioned) |

## How to rebuild from scratch

1. Install SQL Server 2025 (engine, Agent, SSIS, SSAS Tabular), SSMS, Visual Studio with the SSIS / Analysis Services extensions, Power BI Desktop and Python 3
2. Run the scripts in `sql/` in number order, in SSMS
3. Create the Python environment:
   `python -m venv venv` then
   `venv\Scripts\python.exe -m pip install -r requirements.txt`
4. Open `ssis/DroughtETL/DroughtETL.slnx` in Visual Studio and run the packages in number order
   (or run `ssis/tests/run_phase1.ps1`)

## Documents

- [Data sources](docs/DATA_SOURCES.md): verified sources, links and known limits
- [Warehouse](docs/WAREHOUSE.md): star schema diagram, design decisions and data dictionary
- [Model](docs/MODEL.md): SSAS Tabular model, measures and reconciliation with SQL

## Authors

- Abdelkrim El Ayachi
- Othmane El Khassouani

MSBI school project, ISGA, 2026-2027.
